# Community reconnaissance — 2026-11-12

Read with the Kaggle CLI + the public forum/notebooks. This is the evidence that
made us change the plan from "tune our heuristic" to "reuse the public PPO
baseline, then improve its deck".

## Forum threads

| Topic | What it says |
|---|---|
| #744201 Welcome | Playground = second iteration, updated card set, **BO3**, no medals/prize money |
| #744202 Getting started | Official Discord exists; public sharing must go through forums/notebooks |
| #753145 Private sharing rules | Reusing your own previous-competition code is allowed; private cross-team sharing is not |
| #748298 **Daily meta report** | Going first is worth **+18–23 points** in many matchups; agents choose first ~90%; thinking time does not predict results; early October's strongest agents were **Alakazam/Kadabra (65–68%)**; Hydrapple/Ogerpon was popular but ~50%; links the daily meta notebook |
| #747620 Agent submission | A solo dev's mono-Water Abomasnow pipeline: heuristic → PPO MLP → distilled transformer; v3 ~0.79 vs heuristic, 0.98 vs random; STOP-masking bug; safety validator; no search |
| #750707 Previous source code | Kaggle staff: reusing private code from the previous competition is allowed |

Links:
- https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/discussion/748298
- https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/discussion/747620

## Public notebooks / agents (Code tab)

| Notebook | Public score | What it is |
|---|---:|---|
| `busyaprime/lb-1074-1-same-agent-as-public-1-better-deck` | **1074.1** | v3 PPO + seat fix + new-card rows; outputs `submission.tar.gz` |
| `yinghualengyue/ptcg-strong-agent-build` | 983.8 | same v3 family |
| `matterhorn3838/pokemon-challenge-ultra-900` | 966.5 | same family, packaging/verification |
| `yk120951/notebookee2ab02710` | 952.5 | same family, `main.py` variant |
| `cristobaltudela/ptcg-ai-battle-playground-new-cards-900` | 854.2 | Dipam weights + new cards |
| `jazivxt/rising-tide-fleet-agents` | 687.3 | own code |
| `darrensheehan/ptcg-daily-meta-matchups-turn-order-top-decks` | — | daily meta/BT/turn-order/deck-list analysis (must-read) |
| `dariushafshar/ptcg-bo3-gauntlet-your-agent-vs-6-public-bots` | — | local BO3 gauntlet against public bots |

Top of the public leaderboard is ~**1596.7**; the public PPO family sits around
850–1130. The gap between our from-scratch agents and the public PPO is ~90–100%
win rate locally (see `docs/PUBLIC_BASELINE.md`).

## What the public bundle does

- PPO token-transformer, 19.5 MB, d=256 / 4 layers / 8 heads, CPU inference
  5–11 ms/decision.
- Policy-only by default (`SearchAgent(cfg=None)`), no search.
- **Forces "go first"** on `IS_FIRST` (context 41) — matches the forum
  measurement.
- Resets its BO3 tracker per episode; returns the deck on `select is None`.
- Rejection guard (re-delivered obs) and a panic valve below 30 s of overage.
- New-card port (`ptcg/port33.py`) maps R2 card IDs to nearest trained
  embeddings.
- Ships the official `cg/` SDK; its `cg/api.py` has the same search signature we
  reverse-engineered (`AgentStart`, `SearchBegin(agent, input, len, ...)`).

## Meta timeline

| Date | Strongest / most common | Source |
|---|---|---|
| 2026-10-11 | Alakazam/Kadabra strongest (65–68%); Hydrapple/Ogerpon 33%→66% of top-field seats but ~50% WR | forum #748298 |
| 2026-11-09 | Mega Excadrill 39.5%, Dragapult 27.9%, **Mega Lopunny 10.5% at 56.0%**, Alakazam 1.9% | our parse of 1,694 replays (proper archetype labels) |

Consequence: the public bundle's shipped Alakazam list is stale. Re-decking the
same model to Lopunny is a large, cheap win (81.9% in same-model self-play).

## Sample submission layout (for reference)

Competition Data contains `sample_submission/` with `main.py`, `deck.csv`,
`cg/` (official SDK), and the compiled libs. The platform accepts a `.tar.gz`
with `main.py` at the root; extra files and subdirectories are allowed. The
public v3 bundle uses 27 files, ~21 MB.

## Rules acceptance

Downloading competition data and creating a submission both require accepting
the competition rules on the website. The CLI/API token cannot do it
(`403 ... accept its rules first`). This is the only external blocker to getting
a real leaderboard score.
