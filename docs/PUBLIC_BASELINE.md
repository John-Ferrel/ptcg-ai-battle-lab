# Public PPO baseline (v3) — the strongest agent in this repo

> Status: **local benchmark + submission candidate.** The Kaggle submission API
> returned `403 ... accept its rules first`; the competition rules must be
> accepted on the website before the tarball can be uploaded.

## What it is

Community research changed the plan. The public field is dominated by one
**PPO token-transformer** agent, published by Dipam Chakraborty and packaged with
the Playground port and BO3 fixes by several public notebooks. On the public
Code tab it scored:

| Package | Public score (dated) |
|---|---:|
| v3 + seat fix + new-card rows (this bundle) | **1074.1** (submission 57071006) |
| same family, `main.py` variant | 983.8 |
| same family, output without archive | 966.5 |
| Dipam base, old card rows | 854.2 |

Sources / attribution:

- Policy and weights: **Dipam Chakraborty**, `github.com/dipamc/kaggle-ptcg-ai-battle`,
  commit `a176778d99da74a44b495bf19299b4795faf12f2` (MIT).
- New-card port + seat/BO3/turn-order fixes + packaged notebook output:
  **busyaprime**, `kaggle.com/code/busyaprime/lb-1074-1-same-agent-as-public-1-better-deck`.
- The bundle is a public notebook output; it is downloaded, not redistributed
  in git (`data/public_v3/` is git-ignored).

The bundle contains `main.py`, `model.pt` (19.5 MB, token transformer
d=256/4 layers/8 heads), `deck.csv`, `ptcg/` (encoder, tracker, policy,
search), `cg/` (official SDK) and `data/` (PCA text embeddings, lingering
effects). `main.py` is policy-only (`cfg=None`, temperature 0), with a
rejection guard and a panic valve below 30 s of overage time.

Important implementation details confirmed in the bundle:

- It **forces "go first"** on `SelectContext.IS_FIRST` (context 41, YES option).
- It resets its BO3 tracker at the start of every episode.
- It returns the deck when `select is None`.
- It degrades to a legal random answer on any internal failure.
- It was built on the official `cg/api.py`; that file confirms the search
  bindings we reverse-engineered in `vendor/cg` — the native signature is
  identical (`AgentStart`, `SearchBegin(agent, input, len, ...)`).
- Max decision time is ~105 ms on our CPU; mean ~5–11 ms.

## Local measurements (same cabt engine, seat-swapped)

All runs: 0 illegal actions, 0 exceptions.

| Matchup | Games | Win rate | CI95 |
|---|---:|---:|---|
| v3 (Alakazam) vs `heuristic_v1` (Dragapult) | 40 | **90.0%** | 77.0–96.0% |
| v3 (Alakazam) vs `search_v1` (Dragapult) | 40 | **100%** | 91.2–100% |
| v3 (Lopunny) vs v3 (Alakazam) | 160 | **81.9%** | — |
| v3 (Lopunny) vs v3 (Dragapult) | 160 | 48.1% | — |
| v3 (Lopunny) vs v3 (Excadrill) | 160 | 49.4% | — |

Deck round-robin with the **same v3 model** (80 games/pair, 5 decks):

| Deck | Overall WR | CI95 |
|---|---:|---|
| Mega Lopunny #5 | **63.4%** | 58.2–68.7% |
| Dragapult #3 | 58.4% | 53.0–63.8% |
| Alakazam (bundle list) | 53.4% | 48.0–58.9% |
| Mega Excadrill #1 | 45.6% | 40.2–51.1% |
| Mega Kangaskhan #2 | 29.1% | 24.1–34.0% |

## Why Lopunny

The real 2026-11-09 meta (1,694 replays, proper archetype labels) has:

| Archetype | Share | Win rate |
|---|---:|---:|
| Mega Excadrill / Genesect | 39.5% | 50.7% |
| Dragapult / Blaziken | 16.4% | 50.6% |
| Dragapult / Drakloak | 11.6% | 47.6% |
| **Mega Lopunny / Froslass** | **10.5%** | **56.0%** |
| Lillie's Clefairy / Banette | 7.7% | 38.5% |
| Mega Kangaskhan / Ogerpon | 4.1% | 58.3% |
| Alakazam (all variants) | **1.9%** | ~45% |

Alakazam was the strongest archetype in early October (community daily-meta
report: 65–68%), but by 9 November it is nearly extinct. The public v3 bundle
still ships an Alakazam list. Re-decking the same model to the current best
archetype is therefore a cheap, large improvement candidate: **v3 + Lopunny
beats v3 + Alakazam 81.9%**, and goes roughly even with the other two current
top decks.

Caveats: these are same-model self-play matches, not ladder results. The deck
ranking can shift with the real field; the submission score is the only
authoritative measurement. Also, the model was trained before the R2 card set;
the `ptcg/port33.py` port maps new card IDs to nearest known embeddings, so
Lopunny/Froslass play through approximations.

## Reproduce

```bash
# downloads the public notebook output (Kaggle credentials required),
# re-decks it with the current-meta Lopunny list and packs a submission
.venv/bin/python scripts/fetch_public_v3.py \
  --deck decks/meta/05_Mega_Lopunny_ex.csv \
  --out data/public_v3 \
  --pack submissions/public_v3_lop.tar.gz
```

Local play against our own agents:

```bash
.venv/bin/python scripts/arena.py \
  --agent-a data/public_v3 --deck-a data/public_v3/deck.csv \
  --agent-b agents/heuristic_v1 --deck-b decks/meta/03_Dragapult_ex.csv \
  --games 40 --workers 2
```

Submit (after accepting the competition rules on the website):

```bash
.venv/bin/kaggle competitions submit \
  -c the-pokemon-company-ptcg-ai-battle-challenge-playground \
  -f submissions/public_v3_lop.tar.gz \
  -m "public v3 PPO (Dipam, MIT) + current-meta Lopunny deck"
```

## Submission status

Attempted on 2026-11-12. The API returned:

```
403 Client Error: Forbidden
You don't have access to this resource.
If this is a competition, you may need to accept its rules first at
  https://www.kaggle.com/competitions/<competition>/rules
```

The rules acceptance is a website action; the CLI/API token cannot do it.
Once the rules are accepted, the tarball above is ready to upload. No
leaderboard score is claimed until an actual submission completes.
