# Submission artifacts

The Kaggle submission is a `.tar.gz` with `main.py` at the top level and a
`deck.csv`. Tarballs are **not committed** (they contain licensed card metadata
generated from the engine). Rebuild with:

```bash
.venv/bin/python scripts/prepare_agents.py
.venv/bin/python scripts/build_submission.py \
  --agent agents/search_v1 --out submissions/search_v1_pult.tar.gz --verify 10
```

Final artifact (local): `search_v1_pult.tar.gz`

```
main.py              # search_v1 entry point (falls back to the heuristic if cg.api is absent)
deck.csv             # Dragapult #3 (decks/meta/03_Dragapult_ex.csv)
base_policy.py       # verbatim heuristic_v1
card_meta.json       # derived card facts (git-ignored)
meta/*.csv           # opponent-deck priors for the belief model
```

Validate it in the real Kaggle environment:

```bash
PYTHONPATH=vendor .venv/bin/python scripts/kaggle_smoke.py \
  submissions/search_v1_pult.tar.gz --games 3 --opponent agents/greedy
```

No Kaggle credentials are available in this environment, so the tarball has
**not** been submitted to the official leaderboard.
