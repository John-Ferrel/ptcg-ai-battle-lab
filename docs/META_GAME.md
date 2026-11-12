# Metagame analysis

Source: `results/meta_1109/episodes.jsonl`, min_score >= 1200.0

1085 matches, 2170 deck slots, 8 archetypes with >= 30 seats.

## Shares and field-weighted win rate

| Archetype | Seats | Share | Field-weighted WR |
|---|---:|---:|---:|
| Mega Excadrill ex / Genesect ex | 828 | 38.2% | 0.425 |
| Dragapult ex / Blaziken ex | 465 | 21.4% | 0.519 |
| Dragapult ex / Drakloak | 287 | 13.2% | 0.565 |
| Mega Lopunny ex / Mega Froslass ex | 241 | 11.1% | 0.549 |
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 137 | 6.3% | 0.625 |
| Lillie’s Clefairy ex / Banette | 75 | 3.5% | 0.400 |
| Mega Kangaskhan ex / Latias ex | 66 | 3.0% | 0.591 |
| Blaziken ex / Dragapult ex | 54 | 2.5% | 0.479 |

**Best response to this field: `Mega Kangaskhan ex / Teal Mask Ogerpon ex` (0.625).**

## Matchup matrix (row win rate vs column; cells with <10 games = `-`)

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 1. Mega Excadrill ex / Genesect ex | - | 31% | 38% | 64% | 21% | 60% | 10% | 35% |
| 2. Dragapult ex / Blaziken ex | 69% | - | 41% | 31% | 30% | 45% | 58% | - |
| 3. Dragapult ex / Drakloak | 62% | 59% | - | 50% | 44% | - | - | - |
| 4. Mega Lopunny ex / Mega Froslass ex | 36% | 69% | 50% | - | 85% | - | - | - |
| 5. Mega Kangaskhan ex / Teal Mask Ogerpon ex | 79% | 70% | 56% | 15% | - | - | - | - |
| 6. Lillie’s Clefairy ex / Banette | 40% | 55% | - | - | - | - | - | - |
| 7. Mega Kangaskhan ex / Latias ex | 90% | 42% | - | - | - | - | - | - |
| 8. Blaziken ex / Dragapult ex | 65% | - | - | - | - | - | - | - |

**Best counters to the most common deck (`Mega Excadrill ex / Genesect ex`, 38.2% share):**

- `Mega Kangaskhan ex / Latias ex`: 90.0% over 30 matches
- `Mega Kangaskhan ex / Teal Mask Ogerpon ex`: 78.6% over 14 matches
- `Dragapult ex / Blaziken ex`: 69.2% over 146 matches
- `Blaziken ex / Dragapult ex`: 64.5% over 31 matches
- `Dragapult ex / Drakloak`: 62.1% over 58 matches

## Equilibrium (fictitious play, symmetric zero-sum deck game)

| Archetype | Equilibrium mix |
|---|---:|
| Dragapult ex / Drakloak | 65.9% |
| Mega Lopunny ex / Mega Froslass ex | 33.9% |

Game value: **0.500** (expected win rate of the equilibrium mix vs itself).

Replicator dynamics drift over 50 iterations: 0.082 (still moving / cycling).

## Caveats

- The matrix is **observational**: pilots differ. A deck's win rate mixes deck strength, pilot skill and matchmaking.
- Cells with few games have wide CIs; only >=10-game cells are shown.
- The game is non-transitive. A pure best response can be punished if the field shifts; the equilibrium is a mix, not a deck.
- The ladder rating is noisy; this analysis is a prior for deck choice, not a guarantee.