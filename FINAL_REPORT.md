# Final report — PTCG AI Battle Lab

Date: 2026-11-13. Scope: the Kaggle **PTCG AI Battle Challenge Playground**
(cabt engine v2, BO3, deadline 2027-01-08). This is a research/engineering
project, not a claimed leaderboard result.

## 1. What was built

| Layer | Artifact |
|---|---|
| Engine harness | ctypes battle loop, ~10 ms/game; `src/ptcg_ai/harness.py` |
| Evaluation | seat-swapped BO1 arena with Wilson CI, meta-weighted gauntlet, BO3 arena |
| Card data | `AllCard`/`AllAttack` ctypes extraction (1,431 cards / 1,755 attacks) |
| Replay mining | 1,694 real 11-09 games, 1,625 11-12 games; archetypes, matchup matrix, decision pairs |
| Rule policy | `agents/heuristic_v1`: card-DB aware, legal by construction, 0.05 ms/decision |
| Search policy | `agents/search_v1`: recovered native `SearchBegin/Step`, determinized beliefs, confidence gate |
| Imitation arm | `agents/bc_linear`: linear BC on 433k decisions (negative online) |
| Public baseline | public PPO v3 (MIT, Dipam) + deck re-optimization; real ladder submissions |
| Meta tools | `scripts/meta_report.py`, `meta_game.py`, `gauntlet.py`, `divergence.py`, `piloting_gap.py` |
| Fine-tune | `kaggle/finetune/train.py`: BC fine-tune of v3 on 11-12 replays (negative) |
| Submission | `scripts/build_submission.py`, `kaggle_smoke.py`; private Kaggle GPU kernel/dataset |

## 2. Results

### Real ladder (official `publicScore`, dynamic)

| Ref | Agent | Last observed |
|---:|---|---:|
| 58273532 | public v3 + Dragapult/Blaziken #08 | **886.7** |
| 58273729 | public v3 + Lopunny #05 | 843.1 |
| 58273092 | public v3 + Lopunny, first run (inactive) | 1102.5 |
| 58273236 | from-scratch `search_v1` + Dragapult | 180.3 |

Team rank ~237/712 at the last reading. The ladder is noisy: the same Lopunny
artifact produced 1102.5, 749.8, 692.5, 793.9, 671.0, 815.5, 843.1 across runs;
a public write-up reported the same archive scoring 723.8–977.3 over 13
submissions. Single readings are not strength estimates.

### Local, controlled

| Arm | Result |
|---|---|
| `heuristic_v1` vs random / first / greedy | 95.0% / 99.0% / 96.0% |
| `search_v1` vs `heuristic_v1` | 54.2% (Dragapult, 600), 61.3% (Lopunny, 600) |
| `search_v1` vs `heuristic_v1`, BO3 | 63.3% (30 matches) |
| public v3 vs `heuristic_v1` | 90.0% (40) |
| public v3 vs `search_v1` | 100% (40) |
| v3 + Lopunny vs v3 + Alakazam | 81.9% (160) |
| final public v3 vs pre-iteration agent | 90.0% (200) |

### Meta (2026-11-12, 1,623 matches)

| Archetype | Share | Field-WR |
|---|---:|---:|
| Mega Excadrill / Genesect | 35.9% | 0.407 |
| Dragapult / Blaziken | 25.7% | 0.565 |
| Dragapult / Drakloak | 12.4% | 0.543 |
| Mega Lopunny / Froslass | 10.3% | 0.508 |
| Kangaskhan / Ogerpon | 6.1% | **0.628** (paper best response) |
| Kangaskhan / Latias | 2.8% | 0.601 |

Climb path: pult8 is the best climber (0.571 at 1000–1200, 0.540 at 1200–1400,
0.382 at 1400+); Drakloak is a top-band specialist (0.542 at 1400+) but weak at
1000–1200 (33% on 11-11). The theoretical best responses (Kangaskhan decks) are
**not executable by the public v3 pilot** (Kangaskhan/Ogerpon 29.1% in its own
round-robin; Kangaskhan/Latias 43.8% vs pult8 with 19 stalls).

## 3. Negative results (kept honestly)

| Experiment | Result |
|---|---|
| Naive greedy on beginner deck | 30% vs random (n=20) — always-attack/always-fill is bad |
| Linear BC on 433k decisions | Offline top-1 46.4% > heuristic 37.8%, but 40.0% online vs heuristic |
| Search on the learned v3 policy | 40% vs no-search (60 games); default policy-only is better |
| Temperature 1.0 vs 0.0 | 48.3% over 420 games; keep argmax |
| Damage-counter target re-ranker | 48.0% vs base (200 games); local rules lose to the learned plan |
| BC fine-tune of v3 on 11-12 | Offline +11.6 pts, online 51.5% (pult8) / 37.0% (Lopunny); no-go |

## 4. Key lessons

1. **Research the community first.** The public PPO baseline was ~90–100%
   stronger than our from-scratch agents; reusing it was the single biggest
   decision.
2. **The ladder is not an instrument.** Same-artifact variance is ±100+ points;
   use local seat-swapped arenas and replay-derived matchups for decisions, the
   ladder only as a noisy final judge.
3. **Deck and pilot are inseparable.** A deck that is the paper best response
   can be unplayable by your pilot; always evaluate the joint (deck, pilot).
4. **Climb path beats equilibrium.** A top-band specialist that cannot survive
   the lower bands never reaches its band; pult8 is the best climber.
5. **Offline agreement ≠ win rate.** BC top-1 gains did not transfer; hand rules
   on a strong policy lost points.
6. **Legality/loader details matter.** Kaggle's loader `exec()`s `main.py`
   without `__file__`; guard it. Only the latest two submissions are active.
7. **Distribution restrictions are real.** The engine/card data is
   competition-use-only; it is not in this repo.

## 5. Distribution / licensing

- **Not included:** the `ptcgProgram` engine, card database, official `cg` SDK,
  raw Kaggle replays, the public PPO `model.pt`/bundle.
- **Included:** our code (MIT), derived statistics, small deck lists, docs.
- **Replay datasets:** the Kaggle daily episode datasets are CC0; the parsed
  ladder dataset by Darren Sheehan is CC0.
- **Public PPO:** Dipam Chakraborty's repo is MIT; `scripts/fetch_public_v3.py`
  downloads the public notebook output at runtime. Attribution in
  `THIRD_PARTY_NOTICES.md`.
- **Engine terms:** use only for competition entries while the competition runs;
  do not redistribute; delete copies after the competition. See
  `vendor/README.md`.

## 6. Next steps (if continued)

1. **DAgger/self-play with a value head** on the v3 policy; BC alone is
   exhausted (offline +11.6, online +1.5).
2. **Scale-normalized policy loss** for the fine-tune (the current logits are
   ~1e7; CE is unstable).
3. **Newer private/public checkpoint** — the public field is saturated on the
   same September model.
4. **Daily meta monitoring** using `scripts/meta_report.py`; rebalance the
   second slot only when the field shifts materially.
5. **Do not chase ladder noise**; require large repeated edges before
   submitting.

## 7. Reproduce

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare_agents.py
.venv/bin/python -m pytest -q

# local arena
.venv/bin/python scripts/arena.py --agent-a agents/heuristic_v1 \
  --deck-a decks/meta/03_Dragapult_ex.csv --agent-b agents/greedy \
  --deck-b decks/meta/03_Dragapult_ex.csv --games 200 --workers 3

# meta report (Darren dataset, CC0)
.venv/bin/python scripts/meta_report.py --data data/datasets/darren \
  --days 2026-11-12 --out docs/META_1112.md

# public baseline (downloads the public notebook output)
.venv/bin/python scripts/fetch_public_v3.py --deck decks/meta/05_Mega_Lopunny_ex.csv \
  --out data/public_v3 --pack submissions/public_v3_lop.tar.gz

# fine-tune kernel (private Kaggle GPU)
kaggle kernels push -p kaggle/finetune --accelerator NvidiaTeslaT4
```

The search arm requires the official `cg` SDK in `vendor/cg/` (not included; see
`vendor/README.md`).
