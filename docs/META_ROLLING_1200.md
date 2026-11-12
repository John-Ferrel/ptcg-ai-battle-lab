# Meta report — parsed ladder dataset

Days: 2026-11-09, 2026-11-10, 2026-11-11; rating_low >= 1200.0

**3,429 matches**, **8,377 games**, 9 archetype-seats, 8 archetypes with >= 40 seats.

## Shares / field-weighted win rate

| Archetype | Seats | Share | Match WR | Field-weighted WR |
|---|---:|---:|---:|---:|
| Mega Excadrill ex / Genesect ex | 2,141 | 31.3% | 0.430 (41%-45%) | 0.408 |
| Dragapult ex / Blaziken ex | 1,841 | 26.9% | 0.524 (50%-55%) | 0.541 |
| Dragapult ex / Drakloak | 939 | 13.7% | 0.535 (50%-57%) | 0.553 |
| Mega Lopunny ex / Mega Froslass ex | 881 | 12.9% | 0.541 (51%-57%) | 0.540 |
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 489 | 7.1% | 0.554 (51%-60%) | 0.553 |
| Mega Kangaskhan ex / Latias ex | 229 | 3.3% | 0.594 (53%-66%) | 0.597 |
| Lillie’s Clefairy ex / Banette | 166 | 2.4% | 0.398 (33%-47%) | 0.438 |
| Ethan's Typhlosion / Ethan's Quilava | 156 | 2.3% | 0.545 (47%-62%) | 0.490 |

**Best response to this field: `Mega Kangaskhan ex / Latias ex` (0.597).**

## Matchup matrix (row match win rate vs column; cells with < 20 games = `-`)

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 1. Mega Excadrill ex / Genesect ex | - | 28% (525) | 43% (179) | 63% (278) | 27% (33) | 12% (68) | 57% (95) | 2% (62) |
| 2. Dragapult ex / Blaziken ex | 72% (525) | - | 42% (314) | 37% (326) | 35% (136) | 49% (81) | 64% (36) | 75% (44) |
| 3. Dragapult ex / Drakloak | 57% (179) | 58% (314) | - | 62% (115) | 43% (249) | 38% (29) | - | - |
| 4. Mega Lopunny ex / Mega Froslass ex | 37% (278) | 63% (326) | 38% (115) | - | 95% (42) | 100% (27) | - | 58% (24) |
| 5. Mega Kangaskhan ex / Teal Mask Ogerpon ex | 73% (33) | 65% (136) | 57% (249) | 5% (42) | - | - | - | - |
| 6. Mega Kangaskhan ex / Latias ex | 88% (68) | 51% (81) | 62% (29) | 0% (27) | - | - | - | - |
| 7. Lillie’s Clefairy ex / Banette | 43% (95) | 36% (36) | - | - | - | - | - | - |
| 8. Ethan's Typhlosion / Ethan's Quilava | 98% (62) | 25% (44) | - | 42% (24) | - | - | - | - |

## Turn order (game level)

- going first: **51.5%** (4,312 / 8,377)
- going second: **48.5%** (4,065 / 8,377)

## Same-team multi-deck comparisons (pilot confound)

| Team | Deck A | WR | Deck B | WR |
|---|---|---:|---|---:|
| やる気元気ミワハルキ 2nd ver. | Mega Lopunny ex / Mega Froslass ex | 58.1% (n=265) | Mega Kangaskhan ex / Teal Mask Ogerpon ex | 56.6% (n=244) |
| tyr1218 | Dragapult ex / Blaziken ex | 50.2% (n=249) | Dragapult ex / Blaziken ex | 50.9% (n=228) |
| Ondrej Kubicek | Dragapult ex / Drakloak | 52.1% (n=236) | Mega Excadrill ex / Genesect ex | 47.8% (n=226) |
| fufufukakaka | Mega Excadrill ex / Genesect ex | 53.9% (n=206) | Dragapult ex / Blaziken ex | 51.8% (n=197) |
| アライ塾Kaggle支部 | Mega Lopunny ex / Mega Froslass ex | 53.3% (n=321) | Mega Excadrill ex / Genesect ex | 54.2% (n=72) |
| RtoABC2 | Dragapult ex / Blaziken ex | 51.4% (n=216) | Dragapult ex / Blaziken ex | 60.2% (n=133) |
| バーベナヘレナでコンボ決めたい連合 | Ethan's Typhlosion / Ethan's Quilava | 54.5% (n=156) | Mega Excadrill ex / Genesect ex | 48.4% (n=62) |

## Equilibrium (fictitious play, symmetric zero-sum deck game)

| Archetype | Equilibrium mix |
|---|---:|
| Dragapult ex / Drakloak | 55.9% |
| Mega Lopunny ex / Mega Froslass ex | 28.2% |
| Lillie’s Clefairy ex / Banette | 11.9% |
| Mega Kangaskhan ex / Latias ex | 2.7% |
| Mega Excadrill ex / Genesect ex | 1.3% |

Game value: **0.500**; replicator drift over 50 iterations: 1.377 (still moving / cycling).

## Caveats

- Observational: deck WR mixes deck strength, pilot skill and matchmaking.
- Cells with <20 games are hidden; CIs are wide at this sample size.
- Non-transitive game: the pure best response is a snapshot, not a permanent optimum.
- Ladder ratings are noisy; this is a prior, not a guarantee.