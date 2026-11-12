# Submission artifacts

Tarballs are **not committed** (they contain the licensed engine/lib data and,
for the public baseline, a 20 MB model).

## Primary candidate — public PPO v3 + current-meta Lopunny

`public_v3_lop.tar.gz` (~21 MB)

- Policy/weights: Dipam Chakraborty (MIT), commit `a176778d99da74a44b495bf19299b4795faf12f2`.
- New-card port + BO3/seat/go-first fixes + packaged output: busyaprime's public
  notebook (`LB 1074.1`).
- Deck: `decks/meta/05_Mega_Lopunny_ex.csv` (2026-11-09 meta: 10.5% share,
  56.0% WR; the bundle's original Alakazam list is 1.9% share, ~45% WR).
- Local: beats our `heuristic_v1` 90% and `search_v1` 100% (40 games each);
  beats the same model on Alakazam 81.9% (160 games).
- Verified in the real `make("cabt")` environment (BO1 and BO3, all `DONE`).

Rebuild from the public source:

```bash
.venv/bin/python scripts/fetch_public_v3.py \
  --deck decks/meta/05_Mega_Lopunny_ex.csv \
  --out data/public_v3 \
  --pack submissions/public_v3_lop.tar.gz
```

**Status: submitted.** Ref 58273092 reached **1102.5** (hot streak); a
reactivated run of the same artifact scored 692.5. The stable best is the
Dragapult/Blaziken variant (ref 58273532, **966.5**, team rank 167/712). The
ladder is noisy; see `docs/LADDER.md`.

Original submission command:

```bash
.venv/bin/kaggle competitions submit \
  -c the-pokemon-company-ptcg-ai-battle-challenge-playground \
  -f submissions/public_v3_lop.tar.gz \
  -m "public v3 PPO (Dipam, MIT) + current-meta Lopunny deck"
```

## From-scratch artifact — `search_v1` + Dragapult

`search_v1_pult.tar.gz` (~82 KB)

```
main.py              # search_v1 entry point (falls back to the heuristic if cg.api is absent)
deck.csv             # Dragapult #3 (decks/meta/03_Dragapult_ex.csv)
base_policy.py       # verbatim heuristic_v1
card_meta.json       # derived card facts (git-ignored)
meta/*.csv           # opponent-deck priors for the belief model
```

Rebuild:

```bash
.venv/bin/python scripts/prepare_agents.py
.venv/bin/python scripts/build_submission.py \
  --agent agents/search_v1 --out submissions/search_v1_pult.tar.gz --verify 10
```

Validate in the real Kaggle environment:

```bash
PYTHONPATH=vendor .venv/bin/python scripts/kaggle_smoke.py \
  submissions/search_v1_pult.tar.gz --games 3 --opponent agents/greedy
```

No leaderboard score is claimed for either artifact until an official
submission completes.
