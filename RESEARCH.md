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

Key `SelectContext` values in real games (clean pairing, 40 replays, 16,949
decisions — only the ACTIVE player's fresh observation is paired; the inactive
player keeps a stale select that must be skipped):

| context | meaning | share |
|---|---|---|
| 0 MAIN | main action menu | 51.3% |
| 7 EVOLVE / deck search | evolution prompt or pick from a revealed deck | 16.1% |
| 14 DAMAGE_COUNTER_ANY | free damage-counter placement | 6.7% |
| 21 ATTACH_FROM | choose the energy/card to attach | 4.4% |
| 22 ATTACH_TO | choose the attach target | 3.5% |
| 3 SWITCH | pick a benched Pokémon | 2.9% |
| 8 DISCARD | discard a card | 2.3% |
| 4 TO_ACTIVE | promote after a KO | 2.3% |
| 30 DISCARD_ENERGY | pick attached energy to discard | 2.0% |
| 5 TO_BENCH | put a Pokémon on the bench | 2.0% |
| 1 SETUP_ACTIVE | opening active | 1.1% |

That is ~424 decisions per game. In a random-vs-random sample the mix was more
MAIN-heavy (66%); real pilots reach the evolution/search and damage-placement
sub-games far more often. Context 7 matters: its options can be
`{"area": 1, "index": k}` where `index` addresses `select.deck` (the revealed
remaining deck), i.e. a **search choice**, not a normal evolution.

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
symbols are exported by `libcg.so`; we recovered the native prototypes and bound
them in `vendor/cg` (see `docs/SEARCH_API.md`):

```c
void *AgentStart(void);                       // search-mode engine object
char *SearchBegin(void *agent, const char *input, int input_len,
                  const int *your_deck, const int *your_prize,
                  const int *opponent_deck, const int *opponent_prize,
                  const int *opponent_hand, const int *opponent_active,
                  int manual_coin);
char *SearchStep(void *agent, int search_id, const int *picks, int pick_count);
void  SearchEnd(void *agent);
void  SearchRelease(void *agent, int search_id);
```

**Measured:** a root costs 0.3–0.5 ms; throughput is 3.4k–5.7k search nodes/s
(25–500 full random rollouts/s depending on position length); branching is
verified independent. This is enough for ~50–200 rollouts per decision inside
the 600 s budget. The final agent uses a small search (top-4 candidates,
2 rollouts × 8 steps) with a confidence gate.

## 3. Prior art (only sources with code / measured results)

| Source | Track record | What it did | Takeaway for us |
|---|---|---|---|
| `MaliciousMusic/pokemon-tcg-ai-battle` | 160th / 6,807, silver | Small transformer (547k params) trained by imitation on 1.27M decisions from 1100–1270 Elo players; 220 input channels; no search; paired seeded arena | **The leaderboard is not an instrument**: same archive submitted 13× scored 723.8–977.3 (σ 91.3). Hand-written guards on top of the net cost 26.7 pts. Deck scoring had ρ≈0 vs measured win rate. |
| `wmh/ptcg-abc` | top-tier rule-based ladder agents | Shared `BasePolicy` + per-deck policies, divergence-mining vs top human pilots | cabt local A/B is noisy (±10 pts at 40 games, use ≥80). Piloting changes worth 19.5 pts in the matchup matrix. Energy discipline is the #1 recurring bug. |
| `shreyas463/pokemon-tcg-agent` | engineering showcase | Legality-by-construction; heuristic priority; forward-search planner over own turn (~4 ms/decision) | Forward search beat a tuned heuristic in a 500-game sweep. Legality wrapper is cheap insurance. |
| `hotorch/ptcg-ai-battle-strategy` | many search candidates | Determinized search / value tables / opponent reply tables | Search is feasible within the time budget but engineering-heavy. |
| `yijieyuan/kaggle-pokemon-tcg` | 1st place (strategy track) | Write-ups/deck tables only, code withheld | No code to reuse. |
| `SiamRahman29/pokemon-tcg-agent` | large public agent zoo | Deck library + rule-based agents + BC experiments | Useful deck lists and card-data patterns. |

## 3a. Real playground meta (measured, not guessed)

Kaggle publishes daily replay datasets for the playground. We downloaded
`kaggle/the-pokemon-company-ptcg-ai-battle-challenge-playground-episodes-2026-11-09`
(1,694 games, BO3, engine v2) through `kagglehub` (public, no credentials) and
parsed every game's deck lists and winners (`scripts/analyze_episodes.py`,
results in `results/meta_1109/`).

**Archetype share / win rate over 1,694 games:**

| Archetype | Share | Win rate |
|---|---:|---:|
| Mega Excadrill ex | 39.5% | 50.7% |
| Dragapult ex | 30.2% | 50.3% |
| Mega Lopunny ex | 10.5% | **56.0%** |
| Mega Kangaskhan ex | 9.0% | 50.7% |
| Bloodmoon Ursaluna ex | 7.8% | 38.4% |
| Fezandipiti ex | 2.7% | 47.8% |

Restricted to games where **both** players are rated ≥1200 (`min_score`):

| Archetype | Games | Win rate |
|---|---:|---:|
| Dragapult ex | 806 | 51.7% |
| Mega Excadrill ex | 828 | 45.0% |
| Mega Lopunny ex | 241 | 56.0% |
| Mega Kangaskhan ex | 210 | **59.5%** |
| Bloodmoon Ursaluna ex | 75 | 38.7% |

At ≥1400 only Dragapult (46.3%), Mega Kangaskhan (58.2%) and Mega Lopunny
(64.3%, n=14) survive. The old main-competition archetypes (Alakazam, Dipplin,
Lucario, Ogerpon) are **absent** from the playground pool.

Consequences for the project:

1. Deck choice must move to the new meta. The top 12 exact lists extracted from
   replays are in `decks/meta/`, and the deck tournament uses them as its
   primary pool.
2. These win rates are confounded by pilot skill (the lists were piloted by
   their owners) and by Elo matchmaking, so they are a prior, not a verdict.
3. The replays contain ~433k clean single-pick (state → action) pairs from the
   real field (plus multi-pick decisions), which enables imitation learning and
   policy-divergence mining without any extra simulation.

## 3b. Community reconnaissance (2026-11-12, with Kaggle credentials)

Once the API token was available we read the competition forum, public
notebooks, the public leaderboard and the daily replay exports. This changed the
plan.

| Finding | Evidence | Consequence |
|---|---|---|
| The public field is dominated by one **PPO token-transformer** family | Public Code-tab scores: 1074.1 (busyaprime), 983.8 (Strong Agent Build), 966.5, 952.5, 854.2; top ladder 1596.7 | Reuse the mature public model instead of hand-tuning a heuristic |
| **Turn order matters a lot** | Daily meta report: going first is worth +18–23 points in many matchups; agents choose first ~90% of the time | Force go-first (the public bundle already does) |
| The meta shifted between October and November | Oct 11: Alakazam/Kadabra strongest (65–68%), Hydrapple popular. Nov 9 replays: Alakazam 1.9% of seats (~45% WR), Mega Lopunny 10.5% at 56.0% | Use the current Lopunny list with the public model; re-decking beats the shipped Alakazam list 81.9% |
| The official SDK confirms our reverse-engineered search API | The public bundle ships `cg/api.py` with the same `AgentStart`/`SearchBegin(agent, input, len, ...)` signature | No risk left in the search binding; keep our shim, cite the official one |
| The sample bundle is a `SearchAgent` with `cfg=None` (policy-only), rejection guard and 30 s panic valve | Public notebook output | Use it as the base; search is an optional upgrade, not a requirement |
| BO3 shares one 600 s bank across all three games | Official forum answer | Public model uses ~16 s/BO3; plenty of headroom |

The 2026-11-09 meta with proper archetype labels (the daily-meta notebook's
rule: Mega ex first, then ex with ≥2 copies, then highest stage, then copies):

| Archetype | Seats | Share | WR |
|---|---:|---:|---:|
| Mega Excadrill ex / Genesect ex | 1,337 | 39.5% | 50.7% |
| Dragapult ex / Blaziken ex | 555 | 16.4% | 50.6% |
| Dragapult ex / Drakloak | 393 | 11.6% | 47.6% |
| **Mega Lopunny ex / Mega Froslass ex** | 357 | 10.5% | **56.0%** |
| Lillie's Clefairy ex / Banette | 260 | 7.7% | 38.5% |
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 139 | 4.1% | 58.3% |
| Alakazam / Toucannon | 52 | 1.5% | 50.0% |
| Alakazam / Kadabra | 15 | 0.4% | 26.7% |

**Route decision (updated):** keep the from-scratch heuristic/search work as
the reproducible research arm and documented negative/positive results, but
make the **public PPO v3 + current-meta Lopunny deck** the submission base.
Spend further effort on deck choice, turn order and optional search on top of
the learned policy — not on re-inventing the policy.

## 4. Technical challenges

1. **Hidden information** — opponent hand/deck/prizes are unknown. Search needs
   a belief over those; the engine's `search_begin` accepts one explicitly.
2. **Stochasticity** — shuffles, coin flips, prize placement; no seed control
   locally. Evaluation must be statistical.
3. **Large, combinatorial action space** — up to 39 legal options in one MAIN
   menu in the real replays, plus sub-decisions (targets, counts, ordering).
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
| Determinized search (`search_begin`) | **verified** (native bindings recovered, 3.4k–5.7k nodes/s) | +4 pts on a strong base, +13 pts on a weak base | medium | **v2 improvement (shipped)** |
| MCTS | low-medium (needs many rollouts; rollout cost + determinization quality) | unclear vs shallow search | high | only if search throughput is good |
| Self-play RL / BC | replay dataset exists (1,694 games, 433k single-pick decisions); no GPU assumed | offline agreement 46.4%, but **40% online vs the heuristic** | high | tested as `bc_linear`; negative result |
| **Reuse public PPO checkpoint** | high (public MIT notebook output, 20 MB, CPU inference 5–11 ms) | **90–100% vs all our agents**; public LB 1074.1 | low | **submission base (shipped candidate)** |

**Route (executed):** the first phase built a legality-safe, card-DB-aware rule
policy, a real-meta deck tournament, a determinized search overlay and a linear
imitation arm, all measured against the same opponent pool with seat-swapped
games. Community reconnaissance then showed that the mature public PPO model is
90–100% stronger than every from-scratch arm, so the **submission base is the
public PPO v3 re-decked to the current-meta Lopunny list**; the from-scratch
results remain as the reproducible research arm. Results: `EXPERIMENTS.md`,
`docs/PUBLIC_BASELINE.md`.

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
