# PTCG AI Battle Lab

An experimental Pokémon TCG battle agent for the Kaggle **PTCG AI Battle
Challenge Playground** (cabt engine v2): a legality-safe rule engine, a
determinized forward-search overlay, a fast ctypes battle harness, a
seat-swapped arena with confidence intervals, replay mining from 1,694 real
ladder games, and a reproducible submission builder.

> **Local numbers only.** No official Kaggle leaderboard score is claimed in
> this repo. The engine is non-deterministic (no seed control), so results are
> win rates with Wilson 95% CIs. There are no Kaggle credentials in this
> environment.

## Agents

### Strongest local agent / submission candidate — public PPO v3 + Lopunny

Community mining found that the public field is dominated by one PPO
token-transformer family (Dipam Chakraborty, MIT; new-card port and BO3 fixes by
public notebooks). Its packaged output scores **1074.1** on the public ladder.
We downloaded it, benchmarked it, and re-decked the same model to the current
best archetype:

| Matchup | Games | Win rate |
|---|---:|---:|
| public v3 (Alakazam) vs our `heuristic_v1` | 40 | **90.0%** |
| public v3 (Alakazam) vs our `search_v1` | 40 | **100%** |
| public v3 + Lopunny vs public v3 + Alakazam | 160 | **81.9%** |
| public v3 + Lopunny vs v3 + Dragapult / Excadrill | 160 each | 48.1% / 49.4% |

2026-11-09 meta: Alakazam is 1.9% of seats (~45% WR), Mega Lopunny is 10.5% at
**56.0%**. Re-decking the public model to Lopunny is the cheapest large gain.
See `docs/PUBLIC_BASELINE.md`. The tarball
`submissions/public_v3_lop.tar.gz` is ready; uploading is blocked until the
competition rules are accepted on the Kaggle website.

### From-scratch agent — `search_v1` + Dragapult

Built entirely in this repo: a card-DB-aware rule engine, then a determinized
forward-search overlay using the engine's native search API.

- Rule engine `heuristic_v1` (legality by construction) as base policy,
  candidate generator and rollout policy.
- 1-ply determinized search on MAIN: top-4 candidates, 2 rollouts × 8 steps,
  confidence gate (override only on a ≥200-point margin).
- 0 illegal actions / 0 exceptions; p95 40 ms per decision; ~16 s per BO3.

| Arm | Result |
|---|---|
| h1 vs random / first / greedy | 95.0% / 99.0% / 96.0% |
| search vs h1 (Lopunny, 600 games) | **61.3%** (57.4–65.2%) |
| search vs h1 (Dragapult, 600 games) | **54.2%** (50.2–58.2%) |
| final vs pre-iteration agent (200 games) | **90.0%** (85.1–93.4%) |
| imitation baseline (BC) vs h1 | 40.0% — negative result |

Details, ablations and caveats: `EXPERIMENTS.md`.

### Real ladder (2026-11-12)

| Ref | Agent | Status | Score observed |
|---:|---|---|---:|
| 58273092 | public v3 + Lopunny | COMPLETE | 687.6 (seeded 600; first public match won) |
| 58273236 | from-scratch `search_v1` + Dragapult | PENDING | — |

Scores are dynamic and not converged; see `docs/LADDER.md`. The first
from-scratch submission (58273114) errored because the Kaggle loader does not
define `__file__`; all agents now guard it.

## What is here

| Path | Purpose |
|---|---|
| `agents/heuristic_v1/` | rule-based policy (base) |
| `agents/search_v1/` | final agent: search overlay + Dragapult deck |
| `agents/bc_linear/` | imitation arm (negative result, kept for the record) |
| `agents/{random,first,greedy}_legal/` | floor baselines |
| `decks/meta/` | top exact lists mined from real replays |
| `src/ptcg_ai/` | card DB, deck validation, obs helpers, harness, replay parser |
| `scripts/` | arena, gauntlet, meta analysis, replay mining, divergence, BC, submission builder |
| `vendor/cg/` | recovered `cg` SDK shim (enums, card data, forward-search bindings) |
| `docs/` | engineering notes, deck tournament, BC report, search API, public baseline |
| `RESEARCH.md` | competition/engine/prior-art research and route decisions |
| `EXPERIMENTS.md` | protocol, all measured results, threats to validity |

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare_agents.py   # card DB + agent card_meta.json (git-ignored)
```

`kaggle-environments==1.33.3` ships the compiled `cabt` engine. The card
database is licensed competition data and is **not** committed (`data/` and
`agents/*/card_meta.json` are git-ignored); `prepare_agents.py` regenerates both
from the installed engine.

## Run a game / a batch

```bash
# 200 games, alternating seats, 3 worker processes
.venv/bin/python scripts/arena.py \
  --agent-a agents/heuristic_v1 --deck-a decks/meta/03_Dragapult_ex.csv \
  --agent-b agents/greedy       --deck-b decks/meta/03_Dragapult_ex.csv \
  --games 200 --workers 3 --name-a heuristic_v1 --name-b greedy \
  --out results/policy_v1_vs_greedy.jsonl
```

The search agent imports the SDK shim locally:

```bash
PYTHONPATH=vendor .venv/bin/python scripts/arena.py \
  --agent-a agents/search_v1 --deck-a decks/meta/03_Dragapult_ex.csv \
  --agent-b agents/heuristic_v1 --deck-b decks/meta/03_Dragapult_ex.csv \
  --games 200 --workers 3
```

Output: a JSON summary with win rate, Wilson CI, illegal/error counts, turns and
decision latency, plus one JSON line per game.

## Validate a deck

```bash
.venv/bin/python scripts/validate_deck.py decks/meta/*.csv
```

## Build and verify a submission

Primary candidate (public PPO v3, MIT, re-decked to Lopunny):

```bash
.venv/bin/python scripts/fetch_public_v3.py \
  --deck decks/meta/05_Mega_Lopunny_ex.csv \
  --out data/public_v3 \
  --pack submissions/public_v3_lop.tar.gz
PYTHONPATH=vendor .venv/bin/python scripts/kaggle_smoke.py \
  submissions/public_v3_lop.tar.gz --games 3 --opponent agents/greedy
```

From-scratch agent:

```bash
.venv/bin/python scripts/build_submission.py --agent agents/search_v1 \
  --out submissions/search_v1_pult.tar.gz --verify 10
```

The primary tarball is ready; uploading requires accepting the competition
rules on the Kaggle website (the API returns `403 ... accept its rules first`).

The tarball has `main.py` at the top level, `deck.csv`, `base_policy.py`,
`card_meta.json` and `meta/*.csv`. `kaggle_smoke.py` runs it in the real
`make("cabt")` environment (BO1). The agent falls back to the heuristic if
`cg.api` is unavailable, so a missing SDK cannot crash the submission.

## Mine real replays

Kaggle publishes daily replay datasets for the playground. Download one with
`kagglehub` (public, no credentials needed) and analyse it:

```bash
.venv/bin/python - <<'PY'
import kagglehub
print(kagglehub.dataset_download("kaggle/the-pokemon-company-ptcg-ai-battle-challenge-playground-episodes-2026-11-09"))
PY

.venv/bin/python scripts/analyze_episodes.py <episodes_dir> --out results/meta_1109
.venv/bin/python scripts/mine_decisions.py  <episodes_dir> --limit 100
.venv/bin/python scripts/divergence.py      <episodes_dir> --agent agents/heuristic_v1
```

## Test

```bash
.venv/bin/pytest -q
```

## Design in one paragraph

The engine is a process-global ctypes singleton. A battle is a loop of
`obs["select"]` prompts; the agent returns indices into the offered options (or
the 60 card ids when `select` is None). An illegal index, an exception or a
timeout loses the game, so every policy is legal by construction. MAIN is a
sequential menu and attacking ends the turn — the single most important
piloting rule, mined from real replays and encoded as "develop first, attack
last, unless lethal". The from-scratch agent adds determinized forward search on
top, with a confidence gate so search only overrides the heuristic when it is
clearly better. After the public-baseline measurement showed a ~90–100% gap, the
project pivoted: the mature public PPO model is the submission base, and our
experiments now target its deck, turn order and search configuration.

## License / data

Code: MIT (see `LICENSE`). Pokémon card data, the engine and the replay datasets
belong to their owners and are used only locally for the competition; they are
not redistributed in this repository.
