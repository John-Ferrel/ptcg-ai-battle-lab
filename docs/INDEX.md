# Documentation index

Start with these three:

| Doc | What it answers |
|---|---|
| `README.md` | what the project is, how to install/run, final status |
| `FINAL_REPORT.md` | what was built, results, negative results, distribution, next steps |
| `EXPERIMENTS.md` | every experiment, protocol, numbers, threats to validity |

## Research / decisions

| Doc | Content |
|---|---|
| `RESEARCH.md` | competition/engine/prior art, meta evidence, route comparison |
| `docs/COMMUNITY.md` | forum threads, public notebooks, scores, what the public field does |
| `docs/PUBLIC_BASELINE.md` | public PPO v3: attribution, local benchmarks, ladder submissions |
| `docs/METAGAME.md` | non-transitive meta, 3-cycles, best response, climb path, counter method |
| `docs/META_1112*.md`, `docs/META_1111*.md`, `docs/META_GAME*.md` | generated meta reports |

## Experiments

| Doc | Content |
|---|---|
| `docs/DECK_TOURNAMENT.md` | deck pool, legality, round-robin, pilot confound |
| `docs/SEARCH.md` | search_v1 design, beliefs, budget, ablations |
| `docs/SEARCH_API.md` | recovered `SearchBegin/Step` ABI (confirmed by the official SDK) |
| `docs/BC.md` | linear behavior cloning (negative online) |
| `docs/PILOT_GAP.md` | v3 vs top pilots: 65.2% agreement, MAIN 54.8%, negative reranker |
| `docs/FINETUNE.md` | v3 BC fine-tune: offline +11.6, online 51.5% / 37.0% — no-go |
| `docs/LADDER.md` | every real submission, observed score, active-submission rules, noise |

## Engineering

| Doc | Content |
|---|---|
| `docs/DEV_NOTES.md` | environment quirks, replay pairing, `__file__` loader pitfall |
| `vendor/README.md` | official SDK is not included (competition-use-only) |
| `THIRD_PARTY_NOTICES.md` | attribution and licenses |

## Code map

- `src/ptcg_ai/` — card DB, deck validation, observation helpers, harness, replay parser.
- `scripts/` — arena/gauntlet/BO3, meta reports, replay mining, divergence, BC, submission builder.
- `agents/` — `heuristic_v1`, `search_v1`, `bc_linear`, floor baselines.
- `decks/` — `meta/` (real-meta lists), `latest/` (11-12 top lists), candidates.
- `kaggle/finetune/` — the private GPU fine-tune kernel (script + metadata).
