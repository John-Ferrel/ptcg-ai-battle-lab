# Deck tournament — real-meta pool, greedy pilot fixed

Status: measured locally, single pilot (`agents/greedy`), engine v2 BO1, seat-swapped.
Deck choice and pilot quality are deliberately separated: **only the 60-card list
changes** between games in this report.

> **Pool change (2026-11-12).** The first version of this experiment used old-
> competition lists. Replay analysis of the live playground showed those
> archetypes are extinct, so the primary pool is now the 12 most frequent exact
> lists from 1,694 real episodes (`decks/meta/`), plus 3 old lists as a control.
> The old 16-deck run is kept as a superseded control arm (§ Old-pool control).

## TL;DR

Top 3 (stage-2 round robin among the top 6; 200 games/pair, greedy on both sides):

| Rank | Deck | Stage-2 win rate | 95% Wilson CI | Aborted |
|---|---|---|---|---|
| 1 | `09_excadrill_empoleon` — Mega Excadrill ex + Empoleon ex | **61.1%** (535–341) | 57.8–64.2% | 124/1000 |
| 2 | `12_excadrill_metagross_b` — Mega Excadrill ex + Metagross (B) | **58.5%** (518–368) | 55.2–61.7% | 114/1000 |
| 3 | `11_excadrill_skarmory` — Mega Excadrill ex + Mega Skarmory ex | **57.3%** (504–376) | 54.0–60.5% | 120/1000 |

All three are Mega Excadrill ex variants and are statistically tied (CIs overlap
by ~6 points; direct head-to-heads are 49–52.5%). The #1/#2/#3 ordering is a
point-estimate ordering, not a measured separation. Mega Excadrill ex is also the
most common archetype in the real meta (39.5% of deck slots), so the pool and the
result agree on the archetype even though the exact list choice is uncertain.

Second tier: Kangaskhan (47.9%) and Kangaskhan+Ogerpon (40.2%). The old-competition
Alakazam list, which was 5th after stage 1, finished last in stage 2 (34.5%).

**Important measurement caveat:** `02_kanga_slowking` triggers a decision-cap
stall under greedy in ~50% of its games (Slowking's *Seek Inspiration* is picked
repeatedly). Those games are excluded from win rates as "aborted", not awarded to
either side; see Method. Every other deck aborts 2–4% of games, all of them
against the Kanga-Slowking list.

## Real meta evidence

Source: 1,694 playground episodes from **2026-11-09**, parsed into
`results/meta_1109/summary.json` (0 parse errors, 36 distinct decks). "Share" is
the fraction of deck slots (2 per game); "WR" is the archetype's game win rate in
those episodes, with the original owners piloting.

| Archetype | Share | Win rate |
|---|---|---|
| Mega Excadrill ex | 39.5% | 50.7% |
| Dragapult ex | 30.2% | 50.3% |
| Mega Lopunny ex | 10.5% | 56.0% |
| Mega Kangaskhan ex | 9.0% | 50.7% |
| Bloodmoon Ursaluna ex | 7.8% | 38.4% |
| Fezandipiti ex | 2.7% | 47.8% |
| Seaking / Hydrapple ex | 0.4% | — |

Alakazam, Dipplin, Lucario and Ogerpon **do not appear at all**. That is why the
old pool is no longer the primary candidate set.

The 12 most frequent *exact* decklists (`decks/meta/01..12`) are: 4 Mega Excadrill
ex builds, 5 Dragapult ex builds, 2 Mega Kangaskhan ex builds, 1 Mega Lopunny ex
build. Bloodmoon Ursaluna ex (7.8% share) is spread over lists below the
per-list frequency cutoff and is not in the top 12.

**Pilot confound, stated up front.** These lists were piloted by their owners on
the ladder, not by `greedy`. The share/WR table above therefore cannot be
compared directly with our greedy-piloted numbers. It tells us *which lists exist
and are successful for humans*; it does not tell us how they score under this
pilot. The local tournament measures the latter, and the gap is large (e.g.
Lopunny is 56.0% in the real meta and 40.6% under greedy).

## Method

- **Pilot:** `agents/greedy` on both seats, loaded once per worker. Policy:
  `ATTACK > ABILITY > EVOLVE > ATTACH > PLAY > RETREAT > END` on MAIN, first
  option / fill-max on every other select context. No card database, no search,
  no matchup logic (`agents/greedy/main.py`).
- **Engine:** local `cabt` via `ptcg_ai.harness.play_game`, BO1, one process per
  worker (the engine is a process-global singleton). Deck lists are passed to
  `battle_start` explicitly, so the pilot's own `deck.csv` is irrelevant.
- **Seat swap:** game index even → deck A is player 0, odd → deck B is player 0.
  Stage 1 = 30 games per seat per pair; stage 2 = 100 per seat per pair.
- **Stage 1:** full round robin, 15 decks → 105 pairs × 60 games = **6,300 games**
  (840 per deck). The three control-vs-control pairs (180 games) were reused from
  the earlier old-pool run rather than replayed. `--workers 2`.
- **Stage 2:** top 6 by stage-1 win rate → 15 pairs × 200 games = **3,000 games**
  (1,000 per deck). `--workers 2`.
- **Statistic:** win rate over decisive, terminated games. Wilson 95% CI.
  Overlapping CIs are treated as "no measured difference". No seed control, so
  this is a statistical comparison, not a replayable one.
- **Legality:** every list checked with `ptcg_ai.deck.validate_deck` (exactly 60
  cards, ≤4 copies except basic energy, ≥1 basic Pokémon). **15/15 candidates
  legal, 0 dropped, 0 repaired by hand.** `results/deck_stage1_meta/validation.csv`
  records every check. No illegal actions in 9,300 games.
- **Seat effect:** none measurable. Within-pair, deck A's win rate as player 0 vs
  player 1 was 48.3% vs 47.5% in stage 1 and 57.9% vs 58.7% in stage 2 (the
  stage-2 aggregate is high because A is the higher-ranked deck in each pair).

### Non-terminating games (important)

`ptcg_ai.harness` caps a game at 6,000 decisions (`MAX_DECISIONS`), after which it
records `error="too many decisions"` and assigns the win to the other player. The
Kanga-Slowking list puts greedy into such a stall: Slowking's *Seek Inspiration*
attack is always preferred, and greedy never breaks the loop. 393/840 stage-1
games and 557/1,000 stage-2 games involving `02_kanga_slowking` hit the cap
(turns ~900–2,000). Every other deck aborts only 2–4% of its games, and all of
those are its games against Kanga-Slowking.

Awarding those games to "the other player" would be a coin flip, so the
aggregator now treats them as **aborted**: excluded from wins/losses and from the
CI denominator, reported in an `aborted` column. This does not change the top-6
set or the stage-2 ordering. It does mean Kanga-Slowking's 65.1% stage-1 /
47.9% stage-2 win rate rests on only ~450 decisive games and is the least certain
number in the tables. On the real ladder this list would be a timeout risk
(600 s overage budget) until the pilot is fixed.

## Candidates

Primary pool: 12 exact lists from `decks/meta/` (copied to
`decks/candidates_meta/` with stable names). Controls: 3 old-competition lists
(Dragapult, Alakazam, Dipplin) from `decks/`. P/T/E = Pokémon / trainer / energy.

| # | Archetype | P/T/E | Key Pokémon line | Source |
|---|---|---|---|---|
| `01_excadrill_metagross` | Mega Excadrill ex + Metagross | 18/26/16 | Beldum ×4, Metang ×4, Drilbur ×3, Mega Excadrill ex ×2 | meta `01` |
| `02_kanga_slowking` | Mega Kangaskhan ex + Slowking | 20/30/10 | Slowpoke ×4, Slowking ×3, Mega Kangaskhan ex ×3 | meta `02` |
| `03_dragapult_budew` | Dragapult ex + Budew | 19/32/9 | Dreepy ×4, Drakloak ×4, Dragapult ex ×3 | meta `03` |
| `04_kanga_ogerpon` | Mega Kangaskhan ex + Ogerpon | 17/28/15 | Teal Mask Ogerpon ex ×4, Latias ex ×2, Mega Kangaskhan ex ×2 | meta `04` |
| `05_lopunny_froslass` | Mega Lopunny ex + Mega Froslass ex | 18/34/8 | Dunsparce ×3, Dudunsparce ×3, Buneary ×2, Mega Lopunny ex ×2, Mega Froslass ex ×2 | meta `05` |
| `06_dragapult_chiyu` | Dragapult ex + Chi-Yu | 18/32/10 | Dreepy ×4, Drakloak ×4, Dragapult ex ×3 | meta `06` |
| `07_dragapult_blaziken` | Dragapult ex + Blaziken ex | 21/31/8 | Dreepy ×4, Drakloak ×4, Dragapult ex ×2, Blaziken ex ×2 | meta `07` |
| `08_dragapult_clefairy` | Dragapult ex + Blaziken ex + Lillie's Clefairy ex | 23/29/8 | Dreepy ×4, Drakloak ×4, Dragapult ex ×2, Blaziken ex ×2 | meta `08` |
| `09_excadrill_empoleon` | Mega Excadrill ex + Empoleon ex | 22/22/16 | Beldum ×4, Metang ×4, Drilbur ×3, Mega Excadrill ex ×2, Empoleon ex ×1 | meta `09` |
| `10_dragapult_moltres` | Dragapult ex + Blaziken ex + Moltres | 22/30/8 | Dreepy ×4, Drakloak ×4, Dragapult ex ×2, Blaziken ex ×2 | meta `10` |
| `11_excadrill_skarmory` | Mega Excadrill ex + Mega Skarmory ex | 22/21/17 | Beldum ×4, Metang ×4, Drilbur ×3, Mega Excadrill ex ×2, Mega Skarmory ex ×1 | meta `11` |
| `12_excadrill_metagross_b` | Mega Excadrill ex + Metagross (variant B) | 21/23/16 | Beldum ×4, Metang ×4, Drilbur ×3, Mega Excadrill ex ×2, Metagross ×2 | meta `12` |
| `13_dragapult_old` | Dragapult ex (old-competition list) | 17/33/10 | Dreepy ×4, Drakloak ×4, Dragapult ex ×3 | control |
| `14_alakazam_old` | Alakazam (old-competition list) | 20/33/7 | Abra ×4, Kadabra ×4, Alakazam ×3 | control |
| `15_dipplin_old` | Dipplin / Thwackey (old-competition list) | 17/36/7 | Grookey ×4, Thwackey ×4, Applin ×4, Dipplin ×4 | control |

Full machine-readable composition (all Pokémon lines):
`results/deck_stage1_meta/composition.csv`.

## Stage 1 — full round robin (60 games/pair, 840/deck)

| Deck | Games | W–L | Aborted | Win rate | 95% CI | Avg turns |
|---|---|---|---|---|---|---|
| `12_excadrill_metagross_b` | 840 | 533–272 | 35 | **66.2%** | 62.9–69.4% | 32.7 |
| `09_excadrill_empoleon` | 840 | 529–274 | 37 | **65.9%** | 62.5–69.1% | 33.0 |
| `11_excadrill_skarmory` | 840 | 526–279 | 35 | **65.3%** | 62.0–68.5% | 32.9 |
| `02_kanga_slowking` | 840 | 291–156 | 393 | 65.1% | 60.6–69.4% | 34.9 |
| `14_alakazam_old` | 840 | 420–382 | 38 | 52.4% | 48.9–55.8% | 34.4 |
| `04_kanga_ogerpon` | 840 | 408–412 | 20 | 49.8% | 46.3–53.2% | 27.2 |
| `15_dipplin_old` | 840 | 407–411 | 22 | 49.8% | 46.3–53.2% | 30.6 |
| `01_excadrill_metagross` | 840 | 397–416 | 27 | 48.8% | 45.4–52.3% | 31.5 |
| `10_dragapult_moltres` | 840 | 388–426 | 26 | 47.7% | 44.2–51.1% | 32.9 |
| `03_dragapult_budew` | 840 | 357–462 | 21 | 43.6% | 40.2–47.0% | 33.5 |
| `06_dragapult_chiyu` | 840 | 348–471 | 21 | 42.5% | 39.1–45.9% | 33.5 |
| `07_dragapult_blaziken` | 840 | 342–467 | 31 | 42.3% | 38.9–45.7% | 32.2 |
| `05_lopunny_froslass` | 840 | 329–482 | 29 | 40.6% | 37.2–44.0% | 31.1 |
| `08_dragapult_clefairy` | 840 | 317–494 | 29 | 39.1% | 35.8–42.5% | 32.2 |
| `13_dragapult_old` | 840 | 315–503 | 22 | 38.5% | 35.2–41.9% | 31.7 |

Draws: 0. Aborted: 393 / 6,300 (6.2%), all Kanga-Slowking games.
Top 6 advanced: `12`, `09`, `11`, `02` (Kanga-Slowking), `14` (Alakazam control),
`04` (Kanga+Ogerpon).

## Stage 2 — top-6 round robin (200 games/pair, 1,000/deck)

| Rank | Deck | Games | W–L | Aborted | Win rate | 95% CI | Avg turns |
|---|---|---|---|---|---|---|---|
| 1 | `09_excadrill_empoleon` | 1000 | 535–341 | 124 | **61.1%** | 57.8–64.2% | 33.1 |
| 2 | `12_excadrill_metagross_b` | 1000 | 518–368 | 114 | **58.5%** | 55.2–61.7% | 32.8 |
| 3 | `11_excadrill_skarmory` | 1000 | 504–376 | 120 | **57.3%** | 54.0–60.5% | 33.0 |
| 4 | `02_kanga_slowking` | 1000 | 212–231 | 557 | 47.9% | 43.2–52.5% | 32.0 |
| 5 | `04_kanga_ogerpon` | 1000 | 371–552 | 77 | 40.2% | 37.1–43.4% | 27.8 |
| 6 | `14_alakazam_old` | 1000 | 303–575 | 122 | 34.5% | 31.4–37.7% | 32.8 |

Draws: 0. Aborted: 557 / 3,000 (18.6%), all Kanga-Slowking games.

Stage-2 head-to-head (row = deck A, cell = A's win rate over completed games;
aborted games in parentheses):

| A \ B | Empoleon | Metagross-B | Skarmory | Kanga-Slow | Kanga-Oger | Alakazam-old |
|---|---|---|---|---|---|---|
| Empoleon | — | 52.5% | 52.5% | 64.5% (124) | 64.0% | 76.0% |
| Metagross-B | 49.5% | — | 49.0% | 58.1% (114) | 64.0% | 71.5% |
| Skarmory | 50.0% | 51.0% | — | 56.3% (120) | 60.5% | 70.5% |
| Kanga-Slow | 35.5% (124) | 41.9% (114) | 43.7% (120) | — | 52.0% (77) | 64.1% (122) |
| Kanga-Oger | 36.0% | 36.0% | 39.5% | 48.0% (77) | — | 55.5% |
| Alakazam-old | 24.0% | 28.5% | 29.5% | 35.9% (122) | 44.5% | — |

## Notable results

- **Excadrill variants are a clear tier, but the list matters as much as the
  archetype**: the worst Excadrill build (`01_excadrill_metagross`, 48.8%) is
  17 points behind the best (`12`, 66.2%) despite sharing the same core. All four
  variants run Beldum→Metang→Metagross and 2× Mega Excadrill ex; the difference
  is the secondary attacker and trainer/energy split.
- **Old-competition Alakazam is a field artifact, not a contender.** 5th after
  stage 1 (52.4%) then last in stage 2 (34.5%, losing 76–24 to Excadrill-Empoleon).
  It farms the weaker half of a mixed field but cannot beat the top tier.
- **Dragapult is the big pilot loser.** 30.2% of the real meta and 50.3% there,
  but 38.5–47.7% under greedy. Five different Dragapult builds all cluster below
  50%; none reaches the Excadrill tier.
- **Mega Lopunny ex is the clearest pilot confound**: 56.0% win rate in the real
  meta (best archetype there), 40.6% under greedy. The list needs Mega Froslass /
  spread sequencing that greedy does not perform.
- **Kanga+Ogerpon is worse than either half suggests**: 49.8% stage 1, 40.2%
  stage 2. The 4 Ogerpon / 15-energy engine that dominated the old pool does not
  carry a Kangaskhan shell here.
- **The old Dragapult control is the worst deck in the tournament (38.5%)**, i.e.
  the old lists are not secretly fine — the meta really did move.
- **Old Dipplin is mid (49.8%)**, so the control arm is not uniformly bad; it is
  simply not better than the current meta lists.

## Old-pool control arm (superseded)

Before the replay analysis, the same protocol was run on 16 old-competition
lists (7 from this repo + 9 from public repos). Those results are kept because
they show how strongly deck ranking depends on the field. 10,200 games, greedy
pilot, 0 aborts/illegal actions.

Old-pool stage 1 (900 games/deck) top 6:
Ogerpon **88.6%** [86.4–90.5], Crustle **82.5%** [79.9–84.8], Grimmsnarl 57.7%
[54.4–60.9], Exodee 57.7% [54.4–60.9], Abomasnow 51.8% [48.5–55.0],
Rocket-Kanga 49.4% [46.2–52.7]. Stage 2 (1,000/deck): Ogerpon **83.3%**
[80.9–85.5], Crustle **67.5%** [64.5–70.3], Rocket-Kanga 41.4% [38.4–44.5],
Exodee 37.5%, Grimmsnarl 35.6%, Abomasnow 34.6%.

Why superseded: Ogerpon/Crustle/Alakazam/Dipplin/Lucario are absent from the
current playground meta (0 appearances in 1,694 episodes), and the greedy pilot
flatters the two simple attacker lists. Files: `decks/candidates/` (old pool),
`results/deck_stage1/`, `results/deck_stage2/`,
`results/deck_tournament_stage2_oldpool.csv`.

The same three old lists were the only controls in the new tournament:
`14_alakazam_old` 52.4% stage 1 → 34.5% stage 2, `15_dipplin_old` 49.8%,
`13_dragapult_old` 38.5%. They occupy 5th, 7th and 15th in a 15-deck field —
i.e. mostly mid-to-low, and none is a finalist.

## Caveat: greedy is a weak pilot; do not treat this as a tier list

`agents/greedy` always attacks when it can, attaches/evolves without planning,
and picks option 0 (or fills max count) on every non-MAIN select. It cannot hold
energy for a next-turn attack, sequence searches, choose an evolution line, use
abilities/discards/switch with intent, or play around a matchup. It also cannot
break the Slowking stall.

Consequences:

1. **Self-sufficient attackers are flattered.** Excadrill (Beldum/Metang engine,
   16–17 energy, straightforward attacker) and Kangaskhan are helped; the
   Excadrill tier may be partly "this is what greedy can drive".
2. **Sequencing decks are penalized.** Lopunny (56.0% real WR → 40.6% here) and
   Dragapult (50.3% → 38.5–47.7%) are the clearest examples. Old Alakazam's
   stage-1 52.4% is the opposite trap: a simple-enough list farming weak decks.
3. **Deck × pilot interaction is real** (RESEARCH.md §4.6). The real-meta
   share/WR table was produced by human pilots; these lists were authored for
   those pilots. This tournament measures "how much does this list reward a
   myopic attacker", not intrinsic deck strength.
4. **Stage 2 is the more trustworthy table** (it removes weak-field farming), but
   it is only 6 decks and the top 3 are within noise.
5. **Kanga-Slowking's numbers are the least reliable** because ~50% of its games
   abort at the decision cap. Do not pick it without fixing the pilot loop.

If a stronger policy lands at `agents/<name>`, re-run both stages with the same
lists before choosing a deck for submission:

```bash
cd ptcg-ai-battle
.venv/bin/python scripts/deck_tournament.py stage1 \
    --candidates decks/candidates_meta --agent agents/<name> \
    --games 200 --workers 2 --out-dir results/deck_stage1_<name>
.venv/bin/python scripts/deck_tournament.py stage2 \
    --summary results/deck_stage1_<name>/summary.csv --agent agents/<name> \
    --top 6 --games 200 --workers 2 --out-dir results/deck_stage2_<name> \
    --csv-out results/deck_tournament_stage2_<name>.csv
```

Use ≥200 games/pair for the final table. Compare per-deck rank between this run
and the new-policy run (Spearman rank correlation). If it is low (<0.5), ignore
this document's ordering and use the new run. Keep the pilot fixed within each
run; never compare decks across different pilots.

## Reproduce / artifacts

- Runner: `scripts/deck_tournament.py` — stage1/stage2 subcommands, batched
  process pool, seat swap, Wilson CI, validation/composition/head-to-head CSVs,
  `--resume` to reuse completed per-pair JSONL, aborted-game accounting.
- Primary candidates: `decks/candidates_meta/*.csv` (15 = 12 meta + 3 controls).
- Source lists: `decks/meta/*.csv` (12), `decks/meta` derived from
  `results/meta_1109/top_decks.json`.
- Finalists: `decks/finalists/1_excadrill_empoleon.csv`,
  `2_excadrill_metagross_b.csv`, `3_excadrill_skarmory.csv`.
- Raw new stage 1: `results/deck_stage1_meta/` — 105 JSONL files, `summary.csv`,
  `summary.json`, `composition.csv`, `head_to_head.csv`, `validation.csv`.
- Raw new stage 2: `results/deck_stage2_meta/` — 15 JSONL files, same tables.
- Combined stage-2 table: `results/deck_tournament_stage2.csv`.
- Old pool (control): `decks/candidates/`, `results/deck_stage1/`,
  `results/deck_stage2/`, `results/deck_tournament_stage2_oldpool.csv`.
- `results/` is git-ignored; committed artifacts are the scripts, deck files and
  this note.
- Cost: new pool **9,300 scheduled games** (6,300 + 3,000; 180 stage-1 games
  reused, so 9,120 actually played), ~11.5 min wall with `--workers 2` under CPU
  contention from other agents. Old pool: 10,200 games, ~2.1 min. Total this
  session: 19,320 games played, 0 illegal actions, 0 agent exceptions; 950
  aborted games, all in the Kanga-Slowking matchup.
