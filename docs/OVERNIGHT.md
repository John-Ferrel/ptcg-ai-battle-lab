# Overnight research — 2026-11-12/13

Goal: answer "what should we actually submit, given that we cannot submit per
rating band?" with the latest data and joint (deck, pilot) experiments.

**Bottom line: keep `v3 + Dragapult/Blaziken #08` as the core. No tested deck
beats it under our pilot; the theoretical best responses are not executable by
the public PPO model. The last daily submission is preserved.**

Morning ladder snapshot (16:35 UTC): pult8 **987.5**, Lopunny **823.2**, team
**rank 150/712**. The core climbed while the hedge stayed below it — the
overnight deck analysis and the real ladder agree.

## 1. Latest real meta (2026-11-11, parsed ladder dataset)

Source: `darrensheehan/ptcg-playground-ladder-matches` (79k matches, 192k games,
CC0). 1,630 matches on 11-11.

| Archetype | Share | Match WR | Field-weighted WR |
|---|---:|---:|---:|
| Mega Excadrill / Genesect | 34.0% | 45.6% | 0.442 |
| Dragapult / Blaziken | 26.3% | 55.2% | 0.561 |
| Mega Lopunny / Froslass | 12.8% | 53.3% | 0.532 |
| Dragapult / Drakloak | 11.5% | 51.5% | 0.509 |
| Lillie's Clefairy / Banette | 5.5% | 37.1% | 0.384 |
| Kangaskhan / Ogerpon | 5.3% | 56.2% | 0.530 |
| **Kangaskhan / Latias** | 2.8% | **59.1%** | **0.600** |
| Ethan's Typhlosion / Quilava | 1.9% | 50.0% | 0.536 |

Best response: **Kangaskhan/Latias (0.600)**. But see §4: v3 cannot pilot it.

Compared to 11-09, **Excadrill is falling** (39.5% → 34.0%, WR 50.7% → 45.6%),
**Dragapult/Blaziken is rising** (16.4% → 26.3%, WR 50.6% → 55.2%), Lopunny is
stable (10.5% → 12.8%).

## 2. The climb path (this is the answer to "can't submit per band")

Same day, split by rating band (`rating_low`):

| Band | Top field | Best response | pult8 share / WR / field-WR | Lopunny share / WR / field-WR |
|---|---|---|---:|---:|
| 1000–1200 | Excadrill 54.1%, pult8 16.4% | **pult8 0.704** | 16.4% / **71.4%** / **0.704** | 7.6% / 58.1% / 0.579 |
| 1200–1400 | Excadrill 32.6%, pult8 29.8% | Kangaskhan/Latias 0.598 | 29.8% / 52.7% / 0.532 | 13.2% / 54.7% / 0.531 |
| 1400+ | Drakloak 31.8%, pult8 28.8% | Kangaskhan/Ogerpon 0.573 | 28.8% / 49.2% / 0.465 | 20.6% / 46.7% / 0.489 |

**Dragapult/Blaziken is the best climber**: it is a monster at 1000–1200
(71.4% WR, field-weighted 0.704), still 52.7% at 1200–1400, and 49.2% at 1400+.
That is exactly why it is the stable core: it can carry rating through the lower
bands where Excadrill is 54% of the field.

Lopunny is a high-band/high-variance deck: 58.1% at 1000–1200 but only 7.6% of
that field, 54.7% at 1200–1400, 46.7% at 1400+. Its first run's 1102.5 was a
favorable streak; it is not a reliable climber through Excadrill-heavy bands.

## 3. Turn order

| Window | Going first | Going second |
|---|---:|---:|
| 11-11 all (3,989 games) | 51.4% | 48.6% |
| 11-09..11-11, both ≥1200 (8,377 games) | 51.5% | 48.5% |
| 11-11, both ≥1400 (567 games) | **53.4%** | 46.6% |

The October "+18–23 points" is not the overall average; it is matchup-specific.
For our deck we tested directly: **forcing go-second scores 43.8% vs the
go-first version (160 games)**. Go-first is correct; the public bundle already
forces it.

## 4. Joint (deck, pilot) counter experiments — all under v3

The deck-level best responses are not automatically playable. Same v3 model,
different deck lists, seat-swapped:

| Matchup | Games | Result | Notes |
|---|---:|---:|---|
| pult8_top (924d36) vs pult8_08 | 160 | 48.1% | the 60.9% list is not better under v3 |
| pult8_88b26e vs pult8_08 | 120 | 48.3% | no |
| Drakloak top (ba2c3f) vs pult8_08 | 120 | 48.3% | no |
| Excadrill top (9cab1d) vs pult8_08 | 120 | 30.0% | no |
| **Kangaskhan/Latias** vs pult8_08 | 160 | **43.8%** | **19 stalls/errors, avg 274 turns** |
| **Kangaskhan/Latias** vs Lopunny_05 | 120 | **31.7%** | **8 stalls, avg 171 turns** |
| latest Lopunny vs Lopunny_05 | 120 | 50.0% | same deck family |
| go-second vs go-first (pult8) | 160 | 43.8% | go-first better |

**The theoretical best response (Kangaskhan/Latias, 59.1% under its original
pilot) is not executable by v3**: it loses to pult8, collapses to Lopunny, and
causes long stall games. This is the pilot-conditional constraint in action.

## 5. Public checkpoint search

We checked the newer public bundles:

- `busyaprime/...lb-1132-4`: **same `model.pt`** sha256 `7c88c57d...` as the
  1074.1 bundle; only deck/patch differences.
- `yehhua001/ptcg-w8-model-fine-tune`: output contains the **same** model; its
  log says `Adopt finetuned checkpoint: False` and `rejected_finetuned_model:
  true`.
- No newer public model was found. The public field is saturated on the same
  September checkpoint + R2 port.

## 6. Decision

- **Core slot: pult8_08** (v3 + `decks/latest/pult8_08.csv`, the active 943.7
  run).
- **Second slot: Lopunny_05** (high variance, high-band counter; keep as the
  hedge, not the core).
- **Do not burn the last daily submission** on a deck that is only equal in
  self-play; it risks deactivating the stable core.
- The next real lever is **a better policy** (newer checkpoint or fine-tuning on
  R2 replays), not another deck from the same model.

## 7. Files

- `scripts/meta_report.py` — full meta report from the parsed dataset.
- `docs/META_1111.md`, `META_1111_1000_1200.md`, `META_1111_1200_1400.md`,
  `META_1111_1400.md`, `META_ROLLING_1200.md`.
- `decks/latest/` — exact 11-11 top lists (pult8_top, pult8_08, Lopunny,
  Kangaskhan/Latias, Kangaskhan/Ogerpon, Drakloak, Excadrill).
- Raw joint results in `results/` (git-ignored).

## 8. Temperature ablation

`SearchAgent` supports a real-play temperature; the public bundle uses
`temp=0.0` (argmax). Same pult8 deck:

| Variant | Games | WR vs temp=0 |
|---|---:|---:|
| temp=0.5 | 120 | 41.7% |
| temp=1.0 | 120 | 53.3% |
| temp=1.0 (confirmation) | 300 | 46.3% |
| **temp=1.0 pooled** | **420** | **48.3%** |

No gain; keep `temp=0.0`. The 120-game 53.3% was noise — a good example of why
single 100-game A/Bs are not enough.

## 9. Final recommendation

Keep the active pair as **pult8_08 (core, 987.5)** + **Lopunny_05 (hedge,
823.2)**. Do not spend the last daily submission on a candidate that is only
equal in self-play. The next real lever is a stronger policy (new checkpoint or
fine-tuning), not another deck from the same checkpoint.

## 10. Morning update — 2026-11-12 data

Raw 11-12 replays (1,625 matches) were published at 00:14 UTC. Parsed with the
same pipeline (`results/meta_1112/`, `docs/META_1112*.md`).

| Archetype | Share | Field-WR (all) | Field-WR (≥1200) |
|---|---:|---:|---:|
| Mega Excadrill / Genesect | 35.9% | 0.407 | 0.418 |
| Dragapult / Blaziken | 25.7% | 0.565 | 0.540 |
| Dragapult / Drakloak | 12.4% | 0.543 | 0.515 |
| Mega Lopunny / Froslass | 10.3% | 0.508 | 0.497 |
| **Kangaskhan / Ogerpon** | 6.1% | **0.628** | **0.606** |
| Kangaskhan / Latias | 2.8% | 0.601 | 0.588 |

Best response is still **Kangaskhan/Ogerpon** (0.628) — still not pilot-validated
under v3 (29.1% round-robin; Kang/Latias 43.8% vs pult8 with stalls).

**Top band (≥1400) shifted:**

| Deck | Share | Field-WR |
|---|---:|---:|
| Dragapult / Drakloak | 45.2% | **0.542** |
| Dragapult / Blaziken | 25.9% | 0.382 |
| Kangaskhan / Ogerpon | 17.2% | 0.629 |
| Mega Lopunny | 11.7% | 0.412 |

So pult8 is a **climber** (best at 1000–1400), but at 1400+ the Dragapult mirror
favors the Drakloak variant. Drakloak, however, was only 33% at 1000–1200 on
11-11 — a top-band specialist that may struggle to climb. The practical core is
still pult8; Lopunny remains the hedge; Drakloak is a "top-band specialist"
option only if we accept the climb risk.

**Ladder:** pult8 938.0 (rank 178), Lopunny 827.8, first Lopunny run 1102.5
(inactive), from-scratch 180.3. No new submission; the active pair is preserved.
