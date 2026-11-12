# search_v1

Submission-ready search overlay on `heuristic_v1`.  See
`docs/SEARCH.md` for the full design, belief model, evaluation protocol and
results.

## Files

| File | Purpose |
|---|---|
| `main.py` | Kaggle entry point (`agent(obs)`); search + fallback |
| `base_policy.py` | verbatim copy of `agents/heuristic_v1/main.py` |
| `card_meta.json` | card metadata used by the base policy |
| `deck.csv` | current deck (`05_Mega_Lopunny_ex.csv`) |
| `meta/*.csv` | opponent-deck priors (Excadrill, Dragapult, Lopunny) |

The agent is self-contained except for the official `cg.api`.  **Do not copy
`vendor/cg` into this directory**; the Kaggle sandbox provides the SDK.  For
local runs put the repo's `vendor/` on `PYTHONPATH`.

## Run locally

```bash
PYTHONPATH=vendor .venv/bin/python scripts/search_eval.py \
    --agent-b agents/search_v1/base_policy.py \
    --name-b heuristic_v1_same_deck \
    --deck agents/search_v1/deck.csv --games 200 --workers 2
```

## Default configuration

`MODE=search`, `BUDGET_S=0.22`, `TOP_K=4`, `ROLLOUTS=2`, `MAX_STEPS=8`,
`BELIEFS=1`, `MARGIN=200`.

Useful environment overrides:

```bash
SEARCH_V1_MODE=one_ply       # cheaper 1-ply variant (see docs/SEARCH.md)
SEARCH_V1_MARGIN=100         # more overrides, more noise
SEARCH_V1_TELEMETRY_DIR=...  # per-worker JSONL telemetry
```

## Packaging

Ship `main.py`, `base_policy.py`, `deck.csv`, `card_meta.json` and `meta/`.
`base_policy.py` is a snapshot of `agents/heuristic_v1/main.py`; re-copy it if
heuristic_v1 changes.
