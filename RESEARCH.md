# RESEARCH — Pokémon TCG AI Battle Challenge (Playground)

> Status: Phase 1 research note. All claims below are tied to a source or to a
> measurement made in this repo. Anything unverified is marked **Needs confirmation**.

## 1. Competition format (what we actually have to build)

Source: Kaggle overview pages for `pokemon-tcg-ai-battle` and
`the-pokemon-company-ptcg-ai-battle-challenge-playground`, plus the official
engine docs (`matsuoinstitute.github.io/cabt`).

| Item | Finding |
|---|---|
| Interface | `agent(obs: dict) -> list[int]` |
| Deck phase | `obs["select"] is None` → return the 60 card IDs |
| Action phase | return **indices into `obs["select"]["option"]`**, count between `minCount` and `maxCount` |
| Illegal action | instant loss (player marked `INVALID`, opponent wins) |
| Crash / timeout | instant loss |
| Submission | `.tar.gz` with `main.py` at the **top level** (not nested) + `deck.csv`; `tar -czvf submission.tar.gz *` |
| Match format | engine v2 uses **BO3** by default (`bo` config), forest/standard format |
| Time budget | `remainingOverageTime = 600` seconds per player; `actTimeout = 0` (no per-move clock, the overage pool is the budget) |
| Playground ladder | only the most recent **2** submissions are active; playground = no medals, unlimited practice submissions |
| Engine | `cabt` ("Card Battle") v1/v2, a compiled C++ engine exposed through ctypes |

The playground uses the same simulator API as the main competition. The local
pip package `kaggle-environments==1.33.3` ships a working `cabt` environment
(`make("cabt")`), which is what we use for offline evaluation.

## 2. Engine / observation model

Verified locally by running games and dumping observations.

```
Observation
├── select: SelectData | None      # options + minCount/maxCount + context/type
├── current: State | None          # board
├── logs: list[Log]                # events since the last selection
└── search_begin_input: str        # opaque blob required by the search API
```

Key `SelectContext` values observed in real games (6 random games, 406 decisions):

| context | meaning | share |
|---|---|---|
| 0 MAIN | main action menu | 66% |
| 7 EVOLVE | evolution target choice | 13% |
| 3 SWITCH | pick bench Pokémon to switch in | 4% |
| 30 DISCARD_ENERGY | pick attached energy to discard | 4% |
| 1 SETUP_ACTIVE | opening active | 3% |
| 8 DISCARD | discard a card | 2% |
| 22 ATTACH_TO | choose attach target | 2% |
| 4 TO_ACTIVE | promote after KO | 2% |
| 41 IS_FIRST | go first / second | 1.5% |
| 2 SETUP_BENCH | opening bench | 1% |

`MAIN` options use `OptionType`: `PLAY(7)`, `ATTACH(8)`, `EVOLVE(9)`,
`ABILITY(10)`, `DISCARD(11)`, `RETREAT(12)`, `ATTACK(13)`, `END(14)`.
`PLAY`/`ATTACH`/`EVOLVE` carry `index` (hand index) and `inPlayArea/inPlayIndex`
(target). Attack selection is a *separate* select (`SelectType.ATTACK(6)`) whose
options carry `attackId`.

Card metadata (HP, weakness, resistance, retreat cost, attack cost/damage/text,
evolution links, ex/megaEx flags) is available from the engine through
`AllCard()` / `AllAttack()` (1,431 cards / 1,755 attacks in this build). The pip
package does **not** bind these symbols, but they are exported by `libcg.so`;
`src/ptcg_ai/cards.py` binds them with ctypes and caches JSON.

### Determinism

The engine seeds its RNG from `std::random_device`: **no seed control**. Running
the same decks and the same deterministic Python agent twice gives different
games. Consequences:

- "Reproducible" = fixed code + fixed config + fixed game count + reported
  confidence intervals, not identical game replays.
- Comparisons use seat-swapped games (A as player 0 on even indices, player 1 on
  odd) and enough games that the CI is useful. 40 games is noisy (±~10 pts
  reported by a top competitor); we default to >= 200 for A/B decisions.

### Search API

The engine exposes a real forward model:

```
search_begin(agent_observation, your_deck, your_prize,
             opponent_deck, opponent_prize, opponent_hand, opponent_active,
             manual_coin=False) -> SearchState(searchId, observation)
search_step(searchId, pick) -> SearchState
search_end() / search_release(searchId)
```

It determinizes hidden information (our deck/prizes, opponent deck/prizes/hand)
and supports **branching from the same node**, i.e. a genuine search tree, not a
linear replay. The Python wrapper is not shipped in the pip package, but the
symbols (`SearchBegin`, `SearchStep`, `SearchEnd`, `SearchRelease`) are exported
by `libcg.so`. Binding them is an active work item (see EXPERIMENTS.md).

## 3. Prior art (only sources with code / measured results)

| Source | Track record | What it did | Takeaway for us |
|---|---|---|---|
| `MaliciousMusic/pokemon-tcg-ai-battle` | 160th / 6,807, silver | Small transformer (547k params) trained by imitation on 1.27M decisions from 1100–1270 Elo players; 220 input channels; no search; paired seeded arena | **The leaderboard is not an instrument**: same archive submitted 13× scored 723.8–977.3 (σ 91.3). Hand-written guards on top of the net cost 26.7 pts. Deck scoring had ρ≈0 vs measured win rate. |
| `wmh/ptcg-abc` | top-tier rule-based ladder agents | Shared `BasePolicy` + per-deck policies, divergence-mining vs top human pilots | cabt local A/B is noisy (±10 pts at 40 games, use ≥80). Piloting changes worth 19.5 pts in the matchup matrix. Energy discipline is the #1 recurring bug. |
| `shreyas463/pokemon-tcg-agent` | engineering showcase | Legality-by-construction; heuristic priority; forward-search planner over own turn (~4 ms/decision) | Forward search beat a tuned heuristic in a 500-game sweep. Legality wrapper is cheap insurance. |
| `hotorch/ptcg-ai-battle-strategy` | many search candidates | Determinized search / value tables / opponent reply tables | Search is feasible within the time budget but engineering-heavy. |
| `yijieyuan/kaggle-pokemon-tcg` | 1st place (strategy track) | Write-ups/deck tables only, code withheld | No code to reuse. |
| `SiamRahman29/pokemon-tcg-agent` | large public agent zoo | Deck library + rule-based agents + BC experiments | Useful deck lists and card-data patterns. |

## 4. Technical challenges

1. **Hidden information** — opponent hand/deck/prizes are unknown. Search needs
   a belief over those; the engine's `search_begin` accepts one explicitly.
2. **Stochasticity** — shuffles, coin flips, prize placement; no seed control
   locally. Evaluation must be statistical.
3. **Large, combinatorial action space** — up to 27 legal options in one MAIN
   menu in our sample, plus sub-decisions (targets, counts, ordering).
4. **Hard failure mode** — one illegal index, exception or timeout loses the
   game. Every policy must clamp to the offered options.
5. **Compute budget** — 600 s overage per player per match. A ~1 ms heuristic is
   effectively free; a search must fit in a few ms per decision to be safe.
6. **Deck × policy interaction** — the deck defines the win condition; the same
   policy can be strong with one list and weak with another. Deck and pilot must
   be evaluated separately.
7. **Meta drift** — the playground pool is new (1,431 cards, up from ~1,267 in
   the main competition), so old tier lists are a prior, not ground truth.

## 5. Route comparison

| Route | Feasibility here | Expected strength | Cost | Decision |
|---|---|---|---|---|
| Random / first legal | trivial | floor | ~0 | use as sanity opponents only |
| Rule-based heuristic | high (card DB available, fast) | solid baseline; top rule-based agents reached high ladder in the main competition | low | **v1 baseline** |
| Determinized search (`search_begin`) | medium (bindings must be reverse-engineered) | strongest local lever if it works | medium | **v2 improvement** |
| MCTS | low-medium (needs many rollouts; rollout cost + determinization quality) | unclear vs shallow search | high | only if search throughput is good |
| Self-play RL / BC | low (no replay dataset for the new pool; no GPU budget assumed) | potentially high but data-hungry | very high | out of scope for this iteration |

**Chosen v1 route:** a legality-safe, card-DB-aware rule-based policy, plus a
separate deck tournament to pick the list. Then use the engine's forward search
to upgrade action selection (v2), and measure both against the same opponent
pool with seat-swapped games.

## 6. Evaluation protocol (fixed before experiments)

- Unit: one game (BO1), engine v2. Report **game win rate** and, where relevant,
  match-level BO3 win rate.
- Seats alternate by game index; every matchup runs an even number of games.
- Opponent pool (fixed): `random_legal`, `first_legal`, `greedy`, plus 2–3
  community/stronger reference agents if they run locally.
- Default budget: 200 games per matchup for decisions; 400+ for the final table.
  Report Wilson 95% CI and treat overlapping CIs as "no measured difference".
- Record: win rate, illegal/error rate, avg turns, mean/max decision time,
  wall time, git commit, deck hashes.
- Deck experiments use the *same* pilot; policy experiments use the *same* deck.
  This keeps the two axes separable.

## 7. Open questions / risks

- Search bindings may be impossible to recover safely; fallback = heuristic only.
- The playground's real opponent pool is unknown; local opponents may be weaker
  than the ladder (a known failure mode from the main competition).
- The new card pool may shift the meta; deck choice is validated locally only.
- No Kaggle credentials in this environment → **no official leaderboard score**
  will be claimed. Local numbers only, clearly labelled.
