# BC — a linear imitation policy trained on playground replays

Status: **experimental arm, negative result online vs `heuristic_v1`**. It beats
`greedy` clearly, it has the highest offline agreement with replay pilots of any
policy we have, but it does **not** beat the card-aware heuristic in games.
Numbers below are local, on our engine, with the fixed deck
`decks/meta/03_Dragapult_ex.csv`; no ladder score is claimed.

## 1. Method

Behavior cloning from the 2026-11-09 Kaggle playground episode dump (1,694 BO3
replays). Replay parsing is `src/ptcg_ai/replay.py`: the action recorded at step
`t+1` for player `p` answers the observation `p` saw at step `t` (off-by-one
pairing, verified by legality). The parser only pairs the **ACTIVE** player: the
inactive slot keeps a stale `select` from an earlier step, so roughly half of the
raw (obs, action) records are stale duplicates and are discarded.

Each kept decision is one small **ranking problem**: one row per offered option,
label 1 on the chosen option, 0 elsewhere. A linear scorer
`score(option | state) = w · φ(option, state)` is trained with binary logistic
loss (`SGDClassifier(loss="log_loss", average=True, alpha=1e-3, 8 epochs,
random_state=0)`). At inference the argmax option wins. This is a pointwise
ranker, not a calibrated policy: per-decision log-loss below is computed by
softmax over the offered option scores.

Decision filter:

| filter | value |
|---|---|
| `select` | not null (deck selection skipped) |
| `maxCount` | == 1 |
| `minCount` | <= 1 |
| option count | 1..40 |
| player status | ACTIVE (fresh observation) |
| action | exactly one in-range index |

Games are filtered by `manifest.csv` `min_score >= 1200` (top 64% by rating).
Rows are weighted by game strength
(`w = clip((min_score - 1100) / 300, 0.5, 2.0)`) so stronger-pilot decisions
contribute more.

Split is **by episode**, not by decision: sorted numeric episode ids, every 5th
(20%) held out. No game contributes decisions to both splits.

### Why deck-search and damage-counter features matter

Two contexts are easy to get wrong and together account for ~20% of decisions:

* **EVOLVE (ctx 7, 13.8% of the kept set)** is a mix of evolution prompts and
  **deck-search prompts** (`option.area == 1`), where `option.index` indexes
  `select["deck"]` (the ordered remaining deck). The extractor resolves the
  actual card id, its HP/type/retreat/evolution flags, and adds an explicit
  `o_deck_search` feature; otherwise the model sees 15-40 anonymous "card"
  options it cannot tell apart.
* **DAMAGE_COUNTER_ANY (ctx 14, 5.9%)** places damage counters on either side's
  bench/active. Options resolve to the target Pokémon, and the feature set adds
  target side (`t_mine`/`t_opp`), HP fraction, prize value, remaining counters,
  post-damage HP and a would-KO flag (`d_ko`, `d_hp_after`, `d_on_opp`,
  `d_on_ex`).

## 2. Features (280 columns, all deterministic and stdlib-computable)

`agents/bc_linear/bc_features.py` is the single source of truth: the extractor
imports it, and the submission agent ships the same file, so training and
inference features are identical by construction.

| group | features |
|---|---|
| select context | one-hot `ctx=<SelectContext>`, one-hot `stype=<SelectType>`, `s_n_options` |
| global state | `s_turn`/20, `s_turn_action`/10, my/opp prizes/6, hand/10, deck/40, bench/5, opp bench/5, my/opp active present, my/opp active HP fraction, my active energy/5, `s_supporter`, `s_energy_attached`, `s_stadium` |
| special conditions | poisoned/burned/asleep/paralyzed/confused for me and opponent (10 flags) |
| option type | one-hot `ot=<OptionType>`, `o_number`/10, `o_deck_search` |
| card identity | `card=<multiplicative-hash(card_id) % 512>` one-hot |
| card properties (data/cards.json) | hp/350, retreat/4, basic/stage1/stage2/ex/megaEx, item/supporter/tool/stadium/energy/pokemon |
| attack identity/props | `atk=<hash(attack_id) % 256>`, energy cost/4, damage/300 |
| target | HP fraction, energy count/5, mine/opp, active, prize value/2, retreat/4 |
| damage counters | `d_dmg`/100, `d_ko`, `d_hp_after`, `d_on_opp`, `d_on_ex` |
| interactions | `x_attack_opphp`, `x_evolve_turn`, `x_play_lowhand`, `x_attach_target_hp` |

Everything is computed from the observation plus the compact
`agents/bc_linear/card_meta.json` (`{card: [hp, cardType, retreat, flags]}`,
`{attack: [cost, damage]}`). Card/attack identity is hashed, not embedded, so the
agent stays small and has no dependency on the licensed card DB at runtime.

## 3. Dataset

| item | value |
|---|---|
| replays available | 1,694 |
| games kept (`min_score >= 1200`) | **1,085** (868 train / 217 valid); scores 1200.1–1555.9, median 1281.7 |
| clean decisions (ACTIVE player, updated parser) | **472,684** (~436/game) |
| decisions used for training/validation | **433,137** (~399/game, 91.6% of clean) |
| option rows (design matrix rows) | **3,425,555** (mean 7.91 options/decision) |
| features | 280 (279 non-zero weights exported) |
| label balance | 12.7% positive option rows |
| train / valid decisions | 346,485 / 86,652 |
| dropped | 36,122 multi-select (`maxCount != 1`), 3,280 non-single action (mostly legal "choose nothing" when `minCount == 0`), 145 >40 options |

Kept context mix (share of 433,137 decisions): **MAIN 55.6%**, **EVOLVE 13.8%**,
ATTACH_FROM 6.1%, DAMAGE_COUNTER_ANY 5.9%, ATTACH_TO 3.3%, SWITCH 3.2%,
DISCARD_ENERGY 2.7%, TO_ACTIVE 2.5%, SETUP_ACTIVE 1.2%, the rest <1%. On the
full clean set (including multi-select) MAIN is 51.3% and EVOLVE 15.7%; EVOLVE
is lower in the training set because many evolution prompts ask for 2
simultaneous picks and are dropped by `maxCount == 1`.

Extraction: 98 s wall, 3 workers; shards (`data/bc/shard_*.npz` +
`*.meta.npz`) and `data/bc/meta.json` are git-ignored.

## 4. Offline metrics (held-out 217 episodes, 86,652 decisions)

Per-decision top-1 and softmax log-loss over the offered options:

| policy | top-1 | log-loss | MAIN top-1 | EVOLVE top-1 | others top-1 |
|---|---|---|---|---|---|
| **bc_linear (valid)** | **0.464** | **1.510** | 0.384 | 0.516 | 0.586 |
| bc_linear (train) | 0.466 | 1.499 | — | — | — |
| random option | 0.246 | 1.766 | — | — | — |
| first option | 0.310 | 1.766 | — | — | — |
| majority option type per context | 0.320 | 1.766 | — | — | — |
| row majority (always "not chosen") | 0.875 (row acc.) | — | — | — | — |

Train/valid gap is ~0, i.e. the model is capacity-limited, not overfit.

**Agreement with the replay pilot on the same 86,652 held-out decisions** (argmax
vs recorded action; latency measured in-process):

| policy | top-1 | MAIN | EVOLVE | others | ms/decision |
|---|---|---|---|---|---|
| bc_linear | **0.478** | 0.392 | 0.516 | 0.616 | 0.11 |
| heuristic_v1 | 0.378 | 0.245 | 0.507 | 0.561 | 0.16 |
| greedy | 0.272 | 0.211 | 0.285 | 0.379 | 0.006 |

Pairwise top-1 agreement: BC↔heuristic_v1 0.411, BC↔greedy 0.243,
greedy↔heuristic_v1 0.292. So BC is the best *imitation* of the replay pilots,
but that is not the same as playing well (see below).

## 5. Online results (seat-swapped, same deck both sides, 3 workers)

`scripts/arena.py`, deck `decks/meta/03_Dragapult_ex.csv` for both players.
Primary run = 200 games; a second independent 200-game batch is shown as a
replication because 200 games only gives a ±7 pt CI.

| opponent | batch | games | wins | win rate | Wilson 95% CI | illegal | errors |
|---|---|---|---|---|---|---|---|
| `greedy` | primary | 200 | 129 | 64.5% | [57.7%, 70.8%] | 0 | 0 |
| `greedy` | replication | 200 | 115 | 57.5% | [50.6%, 64.2%] | 0 | 0 |
| `greedy` | **pooled** | 400 | 244 | **61.0%** | [56.1%, 65.7%] | 0 | 0 |
| `heuristic_v1` | primary | 200 | 85 | 42.5% | [35.9%, 49.4%] | 0 | 0 |
| `heuristic_v1` | replication | 200 | 75 | 37.5% | [31.1%, 44.4%] | 0 | 0 |
| `heuristic_v1` | **pooled** | 400 | 160 | **40.0%** | [35.3%, 44.9%] | 0 | 0 |

Decision latency observed by the harness: 0.061 ms mean / 0.8 ms max vs greedy,
0.093 ms mean / 7.3 ms max vs heuristic_v1 (the max is a warm-up outlier; the
agent is pure Python dict lookups + 280 sparse weights). **No illegal actions and
no exceptions in 800 games.**

Interpretation: **BC beats the engineering baseline (`greedy`) but loses to the
card-aware heuristic** despite having much higher replay agreement. This is the
honest headline: offline agreement is not win rate, and we did not tune on the
validation set to hide it.

## 6. Observed failure modes (held-out decisions)

1. **MAIN sequencing / type confusion (MAIN error 61.6%).** The largest
   confusions are human PLAY → model ABILITY (6,478 errors), PLAY → PLAY wrong
   card (3,926), ABILITY → ABILITY wrong target (2,704), ATTACH → PLAY (1,982),
   EVOLVE → ABILITY (1,777), ATTACK → PLAY (1,485). A pointwise linear scorer
   sees one option at a time and cannot express "develop first, then attack";
   card-identity weights also over-favour abilities.
2. **Which card, not which action, in EVOLVE / deck search (EVOLVE error 48.4%).**
   EVOLVE options are all `CARD` (type 3), so every one of its errors is a
   card-identity error (5,875 wrong-card picks): the model chooses the wrong
   search target (e.g. the wrong evolution piece
   or supporter) from 5–20 named cards. ID hashing + static card properties
   cannot represent synergy with the current hand/board, and hashed buckets
   collide (512 buckets for 1,431 cards).
3. **Large menus and target ambiguity.** Top-1 drops from 0.779 with 2 options
   to 0.502 (3–5), 0.367 (6–10), 0.315 (11–20), 0.325 (21–40). Within
   sub-decisions: ATTACH_FROM energy choice 41.3%, SWITCH target 43.8%,
   DAMAGE_COUNTER target 59.2% (the *side* is correct 100% of the time, the
   specific bench Pokémon is not). Attach menus can be 39 options.

Smaller issues: END is not a major failure (only 102 over-predictions and 243
missed ENDs across 13,049 MAIN decisions with an END option), and humans decline
only 4.9% of `minCount == 0` prompts, so the "always pick something" limitation
is mostly harmless — but it is a systematic bias, not learned behaviour.

## 7. Limitations

* **Offline agreement ≠ win rate.** This arm is the clearest demonstration:
  +10 pts agreement over `heuristic_v1`, −10 pts win rate. Imitating average
  playground pilots teaches plausible actions, not the KO/energy discipline that
  wins games.
* **Distribution shift.** Training games are top-64% BO3 ladder games with many
  unknown decks and pilots; evaluation is one fixed deck against our own agents.
  The model has no opponent-archetype, deck-list, or turn-history features, and
  no notion of the deck it is piloting beyond card ids in hand/board.
* **Linear capacity.** Pointwise logistic ranker; only four hand-written
  interactions. Card identities are hashed into 512 buckets (collisions) and
  attack ids into 256. No option-position, log, or sequence features, so
  multi-step plans (search → evolve → attach → attack) are not represented.
* **Multi-select decisions are untrained.** 7.6% of clean decisions (setup
  bench, two-card evolves, discard N) never appear with a single label; at
  runtime the same scorer ranks them and the agent takes `maxCount` indices.
* **No "decline" action.** When `minCount == 0` the agent always picks an option
  (`maxCount=1`) or `maxCount` options; replays decline only ~5% of the time, so
  the bias is small but real.
* **Noise.** Engine RNG is not seedable; 200-game CIs are ±7 pts, hence the
  replicated batch and pooled estimates. Treat <5 pt differences as unresolved.
* Single fixed deck, single opponent family, no ladder evaluation. The 40-minute
  compute budget also bounds the model to one linear pass over 3.4M option rows.

## 8. Files

| path | role |
|---|---|
| `scripts/bc_extract.py` | replay → sparse shards + `data/bc/meta.json` + `card_meta.json` |
| `scripts/train_bc.py` | trains the SGD logistic ranker, exports `weights.json`, metrics |
| `scripts/bc_offline_compare.py` | offline top-1 vs greedy/heuristic on held-out decisions |
| `agents/bc_linear/main.py` | self-contained submission agent (stdlib only, legal by construction) |
| `agents/bc_linear/bc_features.py` | pure-stdlib feature extractor shared with training |
| `agents/bc_linear/weights.json` | 279 exported `[feature, weight]` pairs (6 KB) |
| `agents/bc_linear/card_meta.json` | compact card/attack metadata (48 KB) |
| `agents/bc_linear/deck.csv` | copy of `decks/meta/03_Dragapult_ex.csv` |
| `data/bc/` | git-ignored shards, meta, metrics |

Reproduce:

```bash
.venv/bin/python scripts/bc_extract.py --episodes <playground>/versions/1 \
    --out data/bc --min-score 1200 --workers 3
.venv/bin/python scripts/train_bc.py --data data/bc --epochs 8 --alpha 1e-3
.venv/bin/python scripts/bc_offline_compare.py --data data/bc \
    --agents agents/greedy agents/heuristic_v1
.venv/bin/python scripts/arena.py --agent-a agents/bc_linear \
    --deck-a decks/meta/03_Dragapult_ex.csv --agent-b agents/heuristic_v1 \
    --deck-b decks/meta/03_Dragapult_ex.csv --games 200 --workers 3
```
