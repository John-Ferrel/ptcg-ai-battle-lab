# EXPERIMENTS

> All numbers are **local** measurements from the pip-installed `cabt` engine
> (v2, `kaggle-environments==1.33.3`). No Kaggle leaderboard score is claimed.
> The engine seeds its RNG from `std::random_device` (no seed control), so every
> comparison is a seat-swapped batch with a Wilson 95% confidence interval.

## Protocol (fixed before the comparisons)

- Unit: one BO1 game. The ladder plays BO3, but BO1 is the cheaper unit and the
  same policies play both seats; BO3 can be derived or smoke-tested separately.
- `scripts/arena.py` alternates seats by game index, reports win rate, Wilson
  95% CI, illegal/error counts, turns and decision latency.
- Budget: 200 games per matchup for decisions, 400–600 for headline claims.
  Overlapping CIs are treated as "no measured difference".
- Deck and pilot are separated: a deck experiment holds the pilot fixed; a
  pilot experiment holds the deck fixed.
- Local opponents are weaker than the real ladder. Self-play (new agent vs the
  previous best, same deck) is therefore the primary improvement signal, with
  the replay-based agreement as a second, independent signal.

## Results at a glance

| Arm | Agent | Deck | Key result |
|---|---|---|---|
| Floor | random / first / greedy | Dipplin | greedy only 30% vs random (n=20, default deck) |
| Baseline | `heuristic_v1` | Dipplin | 95.0% / 99.0% / 96.0% vs random / first / greedy |
| Deck axis | `heuristic_v1` | real meta | Dragapult #3 best mirror deck (63.1% over 1,000 games) |
| Improved | `search_v1` | Lopunny | **61.3%** vs h1 over 600 games (57.4–65.2%) |
| Improved | `search_v1` | Dragapult | **54.2%** vs h1 over 600 games (50.2–58.2%) |
| Alternative | `bc_linear` | Dragapult | 46.4% offline top-1, but only **40.0%** vs h1 online — negative result |
| Final (from scratch) | `search_v1` | Dragapult | **90.0%** vs the pre-iteration agent (200 games) |
| **Public PPO** | **`public_v3`** | **Lopunny #5** | **81.9%** vs the same model on Alakazam; 90–100% vs all our agents |

---

## E0 — Real playground meta (replays, no agent involved)

Source: `kaggle/the-pokemon-company-ptcg-ai-battle-challenge-playground-episodes-2026-11-09`
(1,694 BO3 replays, downloaded with `kagglehub` — public, no credentials), parsed
by `scripts/analyze_episodes.py`. Results in `results/meta_1109/`.

| Archetype | Share | Win rate (all) | Games (both ≥1200) | WR (both ≥1200) |
|---|---:|---:|---:|---:|
| Mega Excadrill ex | 39.5% | 50.7% | 828 | 45.0% |
| Dragapult ex | 30.2% | 50.3% | 806 | 51.7% |
| Mega Lopunny ex | 10.5% | 56.0% | 241 | 56.0% |
| Mega Kangaskhan ex | 9.0% | 50.7% | 210 | **59.5%** |
| Bloodmoon Ursaluna ex | 7.8% | 38.4% | 75 | 38.7% |
| Fezandipiti ex | 2.7% | 47.8% | 10 | 60.0% |

The old main-competition archetypes (Alakazam, Dipplin, Lucario, Ogerpon) are
**absent** from the playground field. Pilot-controlled comparisons (same team
playing two decks, ≥15 games each) show the deck effect is modest (0–6 points)
while the pilot effect is large — e.g. one team: Lopunny 64.9% vs Kangaskhan
59.4%; another: Excadrill 68.1% vs Dragapult 61.8%.

Top-12 exact lists extracted from the replays live in `decks/meta/`.

## E1 — Floors (sanitiy checks)

| Matchup | Games | Win rate (A) | CI95 | Illegal |
|---|---:|---:|---|---:|
| greedy vs random (beginner `default` deck) | 20 | 30.0% | 14.6–51.9% | 0 |
| heuristic_v1 vs random_legal | 200 | **95.0%** | 91.0–97.3% | 0 |
| heuristic_v1 vs first_legal | 200 | **99.0%** | 96.4–99.7% | 0 |
| heuristic_v1 vs greedy | 200 | **96.0%** | 92.3–98.0% | 0 |

The naive greedy baseline losing to random on the beginner deck is a real
negative result: "always attack / always fill" is harmful. It motivated the
card-DB-aware policy.

## E2 — Rule-based policy (`heuristic_v1`)

Deck: Dipplin (the old list used during development), 200 games each,
seat-swapped, 0 illegal / 0 errors, 0.05–0.08 ms per decision (max < 10 ms).

| Opponent | Win rate | CI95 |
|---|---:|---|
| random_legal | 95.0% | 91.0–97.3% |
| first_legal | 99.0% | 96.4–99.7% |
| greedy | 96.0% | 92.3–98.0% |
| mirror | 46.5% | 39.7–53.4% (seat-balanced) |

### E2b — Replay-mined iteration (attack gating)

Divergence mining against top pilots (120 replays with `min_score ≥ 1400`,
55,113 clean decisions) showed **44.1% semantic agreement overall, but only
29.4% on MAIN**. The dominant disagreements were `ATTACK` vs `PLAY/ABILITY`:
top pilots exhaust beneficial non-attack actions before attacking because
**attacking ends the turn**.

Change: MAIN now takes any lethal attack immediately; otherwise takes the best
positive non-attack action; only attacks when no positive development remains;
END is the last fallback. Context 7 was also fixed to resolve deck-search
options through `select.deck` / `discard` / `looking`.

Implementation-reported deltas (200 games each, same protocol):
random 88.5% → 95.0% (+6.5), first 89.0% → 99.0% (+10.0),
greedy 82.5% → 96.0% (+13.5), mirror unchanged within noise.

## E3 — Deck axis (pilot fixed)

### E3a — With the *pre-fix* pilot (for reference)

Round-robin, 200 games/pair, same pilot both sides (`heuristic_v1` pre-fix):

| Deck | Games | WR | CI95 |
|---|---:|---:|---|
| Lopunny #5 | 1,000 | 56.8% | 53.7–59.9% |
| Excadrill #1 | 1,000 | 55.6% | 52.5–58.7% |
| Dragapult #3 | 1,000 | 52.3% | 49.2–55.4% |
| Kangaskhan #2 | 1,000 | 51.0% | 47.9–54.1% |
| Dragapult #8 | 1,000 | 49.3% | 46.2–52.4% |
| Dipplin (old) | 1,000 | 35.0% | 32.0–38.0% |

### E3b — With the *fixed* pilot (the decision run)

Same protocol, 200 games/pair, 3,000 games total:

| Deck | Games | WR | CI95 | Stalls |
|---|---:|---:|---|---:|
| **Dragapult #3** | 1,000 | **63.1%** | 60.1–66.1% | 0.5% |
| Dipplin (old) | 1,000 | 52.8% | 49.7–55.9% | 1.1% |
| Excadrill #1 | 1,000 | 52.5% | 49.4–55.6% | 0.7% |
| Dragapult #8 | 1,000 | 47.9% | 44.8–51.0% | 1.1% |
| Lopunny #5 | 1,000 | 47.4% | 44.3–50.5% | 0.6% |
| Kangaskhan #2 | 1,000 | 36.3% | 33.3–39.3% | 3.3% |

Head-to-head highlights: Dragapult #3 beats Excadrill 64.5%, Lopunny 58.5%,
Dragapult #8 64.0%, Dipplin 68.5%. The attack-gating fix **reordered the deck
ranking**: the tempo deck that rewards "develop, then Phantom Dive" became the
best deck, while the passive Lopunny/Kangaskhan shells fell. This is a direct
pilot × deck interaction and the main reason deck choice was re-run after the
policy change.

### E3c — Greedy-pilot tournament (independent, weaker pilot)

`docs/DECK_TOURNAMENT.md`: 15 legal lists, 9,120 games (60% of the planned
budget used after the meta update), greedy pilot fixed. Top: Excadrill variants
61.1% / 58.5% / 57.3% (statistically tied). `02_kanga_slowking` stalls in ~50%
of its games via Slowking's *Seek Inspiration* and is excluded from win rates.
Conclusion: under a weak pilot the ranking is different and the absolute level
is much lower; the pilot dominates the deck.

## E4 — Forward search (`search_v1`)

The engine's `SearchBegin/SearchStep` were recovered and bound in `vendor/cg`
(see `docs/SEARCH_API.md`). `search_v1` uses the fixed heuristic as candidate
generator, rollout policy and fallback; it builds one determinized belief per
call, searches the top-4 MAIN candidates with 2 rollouts × 8 steps, and only
overrides the heuristic when the search score wins by ≥200 points.

| Matchup (same deck) | Games | Win rate (search) | CI95 | Illegal / errors |
|---|---:|---:|---|---:|
| search vs h1 — Lopunny #5 | 600 | **61.3%** | 57.4–65.2% | 0 / 0 |
| search vs h1 — Dragapult #3 | 600 | **54.2%** | 50.2–58.2% | 0 / 0 |
| search vs greedy — Lopunny | 200 | 89.0% | 83.9–92.6% | 0 / 0 |
| search vs greedy — Dragapult | 200 | 97.0% | 93.6–98.6% | 0 / 0 |
| h1 vs greedy — Dragapult | 200 | 96.5% | 92.9–98.3% | 0 / 0 |
| **search vs h1 — BO3 matches** | **30** | **63.3%** | 45.5–78.1% | 0 bad statuses |

Ablations (from the search report):
- ungated full search: 53.5% (override 43.8%) — no better than h1;
- ungated one-ply: **15.5%** (override 69.7%) — catastrophic;
- margin-200 one-ply: 63.0% on Lopunny at 2.6 ms p50, but **49.3%** on
  Dragapult (400 games) — the cheap variant does not transfer.
- confidence gate is the key ingredient: without it, search overrides too often
  and loses.

Latency (full search, final config): p50 8.9 ms, p95 40.6 ms, p99 50.4 ms,
max 101.4 ms per decision; ~16 s per BO3, far inside the 600 s overage pool.
Search coverage ~65% of decisions (MAIN); override rate 6.3–8.3%.

Interpretation: search is a real, statistically significant improvement on the
weaker base (Lopunny, +11–13 points) and a smaller but positive one on the
stronger base (Dragapult, +4 points, CI barely excludes 50%). The gain shrinks
when the base policy already sequences the deck well — a sensible result.

## E5 — Imitation policy (`bc_linear`) — negative result

Dataset: 1,694 replays → 1,085 games with `min_score ≥ 1200`, split by episode
(868 train / 217 valid), 433,137 single-pick decisions, 3.4 M option rows, 280
sparse features; linear scorer (SGD logistic).

| Policy (hold-out, 86,652 decisions) | Top-1 | Log-loss |
|---|---:|---:|
| **bc_linear** | **46.4%** | 1.510 |
| random option | 24.6% | 1.766 |
| first option | 31.0% | 1.766 |
| majority option type | 32.0% | 1.766 |
| heuristic_v1 (same states) | 37.8% | — |

So BC imitates top pilots better than the rule engine (46.4% vs 37.8%
agreement) — yet it **loses online**:

| Matchup | Games | Win rate (BC) | CI95 |
|---|---:|---:|---|
| bc_linear vs greedy | 400 | 61.0% | 56.1–65.7% |
| bc_linear vs heuristic_v1 | 400 | 40.0% | 35.3–44.9% |

Failure modes: MAIN sequencing/type confusion (PLAY→ABILITY 6,478; PLAY→wrong
card 3,926), deck-search card identity (synergy is not in the static features),
and large menus (top-1 77.9% at 2 options → 31.5% at 11–20). Pointwise linear
scoring cannot express "develop, then attack", which is exactly what the
hand-written gate encodes. This is a clean example of offline agreement not
transferring to win rate.

## E6 — End-to-end iteration

| Agent | Deck | Opponent | Games | Win rate | CI95 |
|---|---|---|---:|---:|---|
| **final `search_v1`** | **Dragapult #3** | pre-iteration h1 + Dipplin | 200 | **90.0%** | 85.1–93.4% |
| **final `search_v1`** | **Dragapult #3** | meta-weighted greedy field | 400 | **91.5%** | 88.4–93.9% |
| **final `search_v1`** | **Dragapult #3** | h1, **BO3 matches** | 30 | **63.3%** | 45.5–78.1% |

The 90% is not "90% on the ladder" — it is the measured improvement over the
first working version of this project under identical local conditions. The
91.5% gauntlet uses the real meta composition (Excadrill 40, Dragapult 30,
Lopunny 11, Kangaskhan 9, Dragapult #8 10) but local greedy pilots, so it is a
sanity/ceiling check, not a ladder estimate.

## E6b — Public PPO baseline (the pivot)

After the first complete iteration we mined the public notebooks and the daily
replay exports. The strongest public agents are all one family: Dipam
Chakraborty's PPO token-transformer, re-packaged with new-card rows and BO3
fixes (public scores 854–1074; top of the leaderboard is ~1596). We downloaded
the notebook output (`busyaprime/lb-1074...`, 20.3 MB) and benchmarked it.

| Matchup | Games | Win rate (public v3) | CI95 |
|---|---:|---:|---|
| v3 (Alakazam) vs `heuristic_v1` (Dragapult) | 40 | **90.0%** | 77.0–96.0% |
| v3 (Alakazam) vs `search_v1` (Dragapult) | 40 | **100%** | 91.2–100% |
| v3+Lopunny vs v3+Alakazam | 160 | **81.9%** | — |
| v3+Lopunny vs v3+Dragapult | 160 | 48.1% | — |
| v3+Lopunny vs v3+Excadrill | 160 | 49.4% | — |

Same-model deck round-robin (80 games/pair):

| Deck | Overall WR | CI95 |
|---|---:|---|
| Mega Lopunny #5 | **63.4%** | 58.2–68.7% |
| Dragapult #3 | 58.4% | 53.0–63.8% |
| Alakazam (bundle list) | 53.4% | 48.0–58.9% |
| Mega Excadrill #1 | 45.6% | 40.2–51.1% |
| Mega Kangaskhan #2 | 29.1% | 24.1–34.0% |

0 illegal actions / 0 exceptions; 5–11 ms mean, ~105 ms max per decision.

Interpretation: the gap between the public PPO and our from-scratch agents is
~90–100% win rate, i.e. far larger than any tuning we had left in the heuristic.
The correct engineering decision is to **use the mature public baseline** (MIT,
credited) and spend our effort on the deck, turn order and search, not on
re-inventing a policy. The public bundle already forces go-first, which matches
the community measurement (+18–23 points in many matchups).

The 2026-11-09 meta also explains the deck result: Alakazam is 1.9% of seats and
~45% WR, while Mega Lopunny is 10.5% of seats at **56.0%** WR. The public bundle
ships an Alakazam list from October; re-decking the same model to Lopunny is the
cheapest large gain (81.9% in same-model self-play).

**Submission status:** the tarball `submissions/public_v3_lop.tar.gz` is ready,
but the Kaggle API returns `403 ... accept its rules first`. Rules acceptance is
a website action; no leaderboard score can be claimed until it is done.

## E8 — Real ladder (in progress, dynamic scores)

| Ref | Agent | Status | Official score (observed) |
|---:|---|---|---:|
| 58273092 | public v3 (Dipam, MIT) + Mega Lopunny #5 | COMPLETE (inactive) | **1102.5** at 13:04 UTC |
| 58273114 | from-scratch `search_v1` + Dragapult | ERROR | — (`__file__` loader bug) |
| 58273236 | same, fixed loader guard | COMPLETE | **491.1** |
| 58273532 | public v3 + Dragapult/Blaziken #8 | COMPLETE | **966.5** |
| 58273092 | v3 + Lopunny (first run, inactive) | COMPLETE | **1102.5** |
| 58273729 | public v3 + Lopunny (reactivated) | COMPLETE | 692.5 |

The scores are **seeded** (600) and still moving: v3+Lopunny 600 → 687.6 → 879.5
over three public episodes; the from-scratch search agent fell to 491.1. The competition's
public score is Elo-like and only the latest two submissions are active. See
`docs/LADDER.md` for the submission log and the loader bug.

Do not compare 687.6 with the public v3's October score of 1074.1: different
meta, different deck, and a single early match. Wait for rated episodes to
accumulate before drawing conclusions.

## Anomalies / legality

- All reported agents: **0 illegal actions, 0 exceptions** in every arena run
  (tens of thousands of games), including the submission tarball in the real
  Kaggle `cabt` environment (BO1 and BO3 smoke tests, all `DONE`).
- "Too many decisions" stalls (>6,000 decisions in one game) occur in mirror
  matches with tank/heal decks: Kangaskhan 3.3%, Dipplin 1.1%, Dragapult #8
  1.1%, Excadrill 0.7%, Lopunny 0.6%, Dragapult #3 0.5%. The final agent had 0
  stalls in 800 self-play games and 2/400 (0.5%) in the gauntlet. The harness
  attributes a stall to the player who exceeded the cap (conservative: counted
  as a loss).

## Threats to validity

1. **No engine seed.** Deltas below ~8 points at n=200 are not treated as
   improvements; headline claims use 400–600 games.
2. **Weak local field.** Baselines are weak; absolute win rates overstate ladder
   performance. Self-play and replay agreement are used as independent signals.
3. **Deck/pilot confounding.** The real-meta win rates come from their original
   pilots; re-piloting changes the ranking (E3a vs E3b). The final deck was
   chosen with the final pilot, not from the replay table alone.
4. **Belief quality in search.** The opponent prior is a 3-archetype mixture;
   mis-identification can flip search decisions. The confidence gate limits the
   damage.
5. **Licensed data.** Card DB and replays are competition data; they are
   git-ignored and not redistributed. Only derived statistics and code are
   committed.
6. **No official submission.** There are no Kaggle credentials in this
   environment, so no leaderboard score exists or is claimed.

## Reproduce

```bash
.venv/bin/python scripts/build_card_db.py

# policy baseline
.venv/bin/python scripts/arena.py --agent-a agents/heuristic_v1 \
  --deck-a decks/meta/03_Dragapult_ex.csv --agent-b agents/greedy \
  --deck-b decks/meta/03_Dragapult_ex.csv --games 200 --workers 3

# search arm (needs the local SDK shim)
PYTHONPATH=vendor .venv/bin/python scripts/arena.py \
  --agent-a agents/search_v1 --deck-a decks/meta/03_Dragapult_ex.csv \
  --agent-b agents/heuristic_v1 --deck-b decks/meta/03_Dragapult_ex.csv \
  --games 600 --workers 3

# BC arm (re-extract first; data/bc is generated)
.venv/bin/python scripts/bc_extract.py --workers 3
.venv/bin/python scripts/train_bc.py
.venv/bin/python scripts/bc_offline_compare.py
```

Exact per-game rows are in `results/` (git-ignored); summary JSONs are the
source of the tables above.

### Ladder noise

The same Lopunny artifact scored **1102.5** on its first run and **692.5** on a
reactivated run; Dragapult/Blaziken held **966.5**. A public write-up reported
the same archive scoring 723.8–977.3 over 13 submissions. The ladder rating is
therefore a noisy instrument; the local self-play and the replay-derived matchup
matrix are the reliable signals. The best stable active submission is
Dragapult/Blaziken at 966.5 (team rank 167/712 at 13:20 UTC).
