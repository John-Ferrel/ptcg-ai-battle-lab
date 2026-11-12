# search_v1 — determinized forward-search agent

`agents/search_v1` is a submission-ready overlay on `heuristic_v1`.  The base
policy is vendored byte-for-byte as `agents/search_v1/base_policy.py` (copied
from `agents/heuristic_v1/main.py`); it is used as the fallback action, the
candidate generator, and the rollout policy.  The only new dependency is the
official `cg.api` forward-search API (locally restored in `vendor/cg`).

The agent never raises and always returns a legal list.  Search is used only
for MAIN and single-pick ATTACK decisions; every other selection goes straight
to the base policy.

---

## 1. Design

```
agent(obs)
  ├─ deck phase / non-MAIN / non-ATTACK  -> base_policy.agent(obs)
  └─ MAIN or ATTACK
       1. build one belief (hidden zones)
       2. search_begin(observation, belief) -> root
       3. rank options with base_policy
          keep top 4 + END + base action
       4. for each candidate:
            search_step(root, candidate)
            roll out with base_policy (<= 8 nodes / until turn changes)
            score the resulting state
       5. average the rollout scores
       6. override the base action only if the best score beats the base
          action by >= 200 points (confidence gate)
       7. search_end()
```

### Candidate generation

* **MAIN:** `base._score_main` for every option; keep the top 4, END, and the
  base action.  Only single-pick MAIN menus are searched.
* **ATTACK:** `base._score_attack` for each attack option; keep the top 4 and
  the base attack choice.  If the menu allows declining (`minCount == 0`), a
  “skip attack” candidate is included as well.
* Everything else (setup, evolve/deck-search, damage-counter placement,
  discard/attach targets, yes/no, counts, …) is base policy only.

### Rollout

The rollout policy calls `base._choose` on each search observation (converted
to a plain dict).  It stops at:

* a terminal result,
* a selection with no options,
* a turn change (`current.turn != root_turn`), or
* `SEARCH_V1_MAX_STEPS` nodes (default 8).

Each candidate gets `SEARCH_V1_ROLLOUTS` independent samples (default 2)
because the engine is stochastic.

### Leaf score

From the root player's point of view:

```
terminal win/loss                       ±1e7
prize difference (opp - mine) * 500
+ sum(base._battle_value(my Pokemon))
- sum(base._battle_value(opp Pokemon))
+ hand size * 1.5
+ energy attached to my board * 8
```

`base._battle_value` already includes HP, affordable damage, energy, ex prize
value and active-Pokémon weighting.  The leaf score is deliberately cheap;
the base policy supplies the tactical detail.

### Confidence gate

The measured raw search was noisy: it overrode 45% of MAIN decisions and was
statistically neutral against the base policy.  A *margin gate* fixes this:
keep the base action unless the best candidate's average score beats the base
candidate by at least `SEARCH_V1_MARGIN = 200` points.  This reduced the
override rate to ~6–8% and produced the positive results below.  With the gate
disabled (`MARGIN=0`) the agent is neutral; with one-ply scoring and no gate
it is much worse (see §5).

---

## 2. Belief / determinization

One belief per search by default (`SEARCH_V1_BELIEFS=1`).

* **Our deck:** the 60-card `deck.csv` minus visible cards (hand, board,
  discard, attached energy/tools).  If `obs.select.deck` is present (deck-search
  effects), that exact remaining order is used for `your_deck`; otherwise
  `deckCount` cards are sampled from the unseen pool.
* **Our prizes:** sampled from the same unseen pool, exactly `prizeCount`
  cards.  Prize identities are never read.
* **Opponent deck/prizes/hand:** sampled from one of three meta priors shipped
  in `agents/search_v1/meta/`:
  * `01_Mega_Excadrill_ex.csv`
  * `03_Dragapult_ex.csv`
  * `05_Mega_Lopunny_ex.csv` (tuning deck; the shipped deck is
    `03_Dragapult_ex.csv`, see "Deck choice" below)

  The prior is chosen by overlap with **revealed** opponent cards, weighting
  cards that appear in only one prior much more than shared staples.  This
  identifies the archetype from the first exclusive Pokémon/trainer; before
  any signal it samples uniformly.  Revealed opponent cards are removed from
  the prior multiset, then deck/prizes/hand are sampled to the exact counts.
* **Opponent active:** only when the active spot is face-down (`active[0] is
  None`); a Basic Pokémon from the prior is supplied.
* **Basic requirement:** if the sampled opponent deck has no Basic, one
  element is replaced with a Basic from the prior.
* Every array is passed at the exact length the engine expects.  The local
  `vendor/cg` wrapper additionally pads defensively; the official SDK does
  not need padding when the lengths are correct.

The prior is a genuine hidden-information belief, not an oracle.  A diagnostic
run with the opponent prior forced to the eval deck scored 63.5% (200 games),
showing that belief quality is the main sensitivity; the shipped weighted
selector reaches the correct prior from revealed cards, so the default does
not hardcode the eval opponent.

---

## 3. Budget

| Knob | Default |
|---|---|
| per-decision budget | 0.22 s (`SEARCH_V1_BUDGET_S`) |
| top candidates | 4 (`SEARCH_V1_TOP_K`) |
| rollout samples per candidate | 2 (`SEARCH_V1_ROLLOUTS`) |
| rollout horizon | 8 nodes or turn change (`SEARCH_V1_MAX_STEPS`) |
| beliefs | 1 (`SEARCH_V1_BELIEFS`) |
| override margin | 200 (`SEARCH_V1_MARGIN`) |

The first search decision in a process pays a one-time engine/card-metadata
warm-up (~20 ms).  Subsequent `search_begin` calls are ~0.3–0.5 ms.

Measured on the final default configuration (AMD EPYC-Milan shared VM, 6
vCPUs, Python 3.12, 200-game runs, `--workers 2`):

| metric | all decisions | searched decisions |
|---|---:|---:|
| mean | 13.4 ms | 20.5 ms |
| p50 | **8.9 ms** | 18.8 ms |
| p95 | **40.6 ms** | 43.9 ms |
| p99 | 50.4 ms | 52.3 ms |
| max | **101.4 ms** | 101.4 ms |

The max is below the 0.22 s per-decision budget.  At ~13 ms mean and ~1,200
decisions per BO3, the total thinking time is ~16 s, far below the 600 s
overage pool.

---

## 4. Evaluation

Protocol: 200 seat-swapped games, `scripts/arena.py --workers 2`, same deck for
both seats, BO1.  The baseline is `agents/search_v1/base_policy.py` (a
byte-identical copy of `heuristic_v1/main.py`) so its internal `DECK` matches
the harness deck.  The eval wrapper is `scripts/search_eval.py`; it records
per-decision telemetry and aggregates p50/p95/max and override rate.

### Main results

| matchup | games | wins | WR | Wilson 95% CI | illegal | errors |
|---|---:|---:|---:|---|---:|---:|
| search_v1 (A) vs heuristic_v1 | 200 | 118 | 59.0% | 52.1–65.6% | 0 | 0 |
| search_v1 (A) vs heuristic_v1, replication | 200 | 120 | 60.0% | 53.1–66.5% | 0 | 0 |
| **search_v1 (A) vs heuristic_v1, combined** | **400** | **238** | **59.5%** | **54.6–64.2%** | 0 | 0 |
| search_v1 (B) vs heuristic_v1 | 200 | 130 | **65.0%** | 58.2–71.3% | 0 | 0 |
| **search_v1 vs heuristic_v1, all 600 games** | **600** | **368** | **61.3%** | **57.4–65.2%** | 0 | 0 |
| search_v1 (A) vs greedy | 200 | 178 | **89.0%** | 83.9–92.6% | 0 | 0 |
| search_v1 (A) vs heuristic_v1, Excadrill deck | 200 | 109 | 54.5% | 47.6–61.3% | 0 | 0 |

Controls:

| control | games | result |
|---|---:|---|
| heuristic_v1 vs heuristic_v1 (A seat) | 200 | A 52.5% (45.6–59.3%) |
| search_v1 vs search_v1 mirror (A seat) | 100 | A 53.0% (43.3–62.5%) |

The mirror and base controls show a small A-seat/noise advantage (~2.5–3
points).  The search agent still wins 65% from the B seat, so the edge is not
just seat assignment.

### Latency / override rate (default full search)

| run | p50 | p95 | max | override rate (searched) |
|---|---:|---:|---:|---:|
| vs h1, 200 (A) | 8.9 ms | 40.6 ms | 101.4 ms | 6.3% |
| vs h1, 200 (B) | 9.1 ms | 40.9 ms | 95.3 ms | 8.3% |
| vs greedy, 200 (A) | 9.0 ms | 36.7 ms | 72.7 ms | 10.0% |
| Excadrill, 200 (A) | 5.4 ms | 39.2 ms | 80.3 ms | 5.7% |

Search coverage is ~65% of decisions (MAIN); the other ~35% are non-MAIN and
use the base policy directly.

---

## 5. Ablations / negative results

These are honest, same-deck, seat-swapped runs with the same build:

| variant | games | WR vs h1 | p50 | p95 | override |
|---|---:|---:|---:|---:|---:|
| full search, no margin gate | 200 | 53.5% | 11.7 ms | 41.5 ms | 43.8% |
| full search, margin 50 | 200 | 54.0% | 10.2 ms | 43.4 ms | 24.8% |
| full search, margin 100 | 200 | 58.0% | 9.2 ms | 39.6 ms | 12.9% |
| **full search, margin 200 (default)** | **600** | **61.3%** | **8.9 ms** | **40.6 ms** | **6–8%** |
| full search, margin 500 | 200 | 58.0% | 8.8 ms | 39.4 ms | 3.1% |
| full search, 3 rollouts | 200 | 55.5% | 11.9 ms | 58.2 ms | 6.5% |
| full search, 12-step horizon | 200 | 56.0% | 8.9 ms | 51.8 ms | 7.0% |
| full search, 2 beliefs | 200 | 57.5% | 17.5 ms | 78.4 ms | 6.4% |
| **one-ply (no rollout), margin 200** | **400** | **63.0%** | **2.6 ms** | **5.7 ms** | **2.0%** |
| one-ply, margin 200 vs greedy | 200 | 83.5% | 2.2 ms | 5.2 ms | 2.4% |
| one-ply, no margin gate | 200 | **15.5%** | 3.1 ms | 5.5 ms | 69.7% |

Interpretation:

* **The margin gate is essential.**  Ungated search overrides too often and is
  statistically neutral (53.5%, CI 46.6–60.3%); the gate lifts the point
  estimate to ~59–60%.  Ungated one-ply is catastrophically bad (15.5%) because
  a one-step state comparison mismatches mid-turn and post-turn states.
* **Rollouts add less than expected.**  The full 8-node rollout version is
  +11 points over h1, but a cheaper one-ply version with the same gate is
  +13 points and ~5x faster.  The difference (61.3% vs 63.0%) is within noise;
  the rollout version is the shipped default because it follows the intended
  design and is still comfortably inside budget.  Set
  `SEARCH_V1_MODE=one_ply` for the cheaper variant.
* **More rollouts / beliefs / horizon did not help** on this sample; they cost
  2–4x more and scored 55–58%.
* **Belief quality matters.**  Forcing the opponent prior to the eval deck
  scored 63.5% vs 59–60% with the weighted meta mix; the selector recovers the
  correct prior from revealed exclusive cards without hardcoding it.

---

## 6. Failure modes / limits

1. **Belief error.**  Before an archetype-exclusive card is revealed, the
   opponent prior is uncertain.  Multi-belief search (`BELIEFS=2/3`) is
   supported but did not pay for itself in the measured budget.
2. **Stochastic engine.**  `std::random_device` seeds the RNG; there is no
   replay determinism.  Rollout scores are averaged over independent samples.
3. **Rollout horizon.**  Stopping at the turn change can truncate a
   development action before the opponent responds; the leaf score values the
   board at the start of the opponent's turn.  One-ply avoids the compounding
   noise but has its own mid-turn/terminal mismatch.
4. **Margin tuning.**  200 is tuned on the Lopunny/Excadrill samples; a
   different meta or deck may prefer 100–300.  The gate is a variance-control
   device, not a win-probability model.
5. **Search scope.**  Only MAIN and single-pick ATTACK menus.  Multi-pick
   MAIN menus, deck-search (context 7) and every other sub-selection use the
   base policy.  This is deliberate for v1.  With the tested decks the ATTACK
   sub-select almost always offers a single attack, so the ATTACK search branch
   is implemented but was not exercised by the 200-game evaluations; it falls
   back legally if the menu is not single-pick.
6. **Process-global engine.**  One battle and one search object per process;
   `search_end()` is called after every decision.  Do not run battles or
   searches concurrently in one process.
7. **Submission packaging.**  The agent is self-contained except for the
   official `cg.api`: ship `main.py`, `base_policy.py`, `deck.csv`,
   `card_meta.json`, and `meta/*.csv`.  Do **not** copy `vendor/cg` into the
   agent dir; the Kaggle sandbox provides it.
8. **Base policy snapshot.**  `base_policy.py` is a verbatim copy of
   `agents/heuristic_v1/main.py` at implementation time.  If heuristic_v1 is
   changed later, re-copy it to keep the local evaluation and the submission
   in sync.  The copy is intentional: a submission cannot import a sibling
   agent directory.
9. **Latency tail.**  The first search decision pays engine/card-meta warm-up;
   max observed 101 ms, below the 220 ms budget.  A cold process with a much
   larger card DB could approach the budget.
10. **Local vs sandbox SDK.**  Evaluation used `vendor/cg`; the Kaggle sandbox
    provides the official `cg.api`.  The documented public signatures are the
    same, but any sandbox-specific error/return-type differences would be
    handled by the fallback wrapper.

---

## 7. Files

```
agents/search_v1/
├── main.py          # search agent (this document's design)
├── base_policy.py   # verbatim copy of agents/heuristic_v1/main.py
├── card_meta.json   # card metadata for base_policy
├── deck.csv         # 03_Dragapult_ex.csv
└── meta/
    ├── 01_Mega_Excadrill_ex.csv
    ├── 03_Dragapult_ex.csv
    └── 05_Mega_Lopunny_ex.csv

scripts/search_eval.py   # arena + telemetry aggregation
docs/SEARCH.md           # this file
```

Run locally:

```bash
PYTHONPATH=vendor .venv/bin/python scripts/search_eval.py \
    --agent-b agents/search_v1/base_policy.py \
    --name-b heuristic_v1_same_deck \
    --deck agents/search_v1/deck.csv --games 200 --workers 2
```
