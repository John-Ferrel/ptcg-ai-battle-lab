# Metagame analysis

Source: `results/meta_1109/episodes.jsonl`, min_score >= 1400.0

142 matches, 284 deck slots, 3 archetypes with >= 15 seats.

## Shares and field-weighted win rate

| Archetype | Seats | Share | Field-weighted WR |
|---|---:|---:|---:|
| Dragapult ex / Drakloak | 134 | 47.2% | 0.474 |
| Dragapult ex / Blaziken ex | 69 | 24.3% | 0.399 |
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 67 | 23.6% | 0.556 |

**Best response to this field: `Mega Kangaskhan ex / Teal Mask Ogerpon ex` (0.556).**

## Matchup matrix (row win rate vs column; cells with <10 games = `-`)

| | 1 | 2 | 3 |
|---|---|---|---|
| 1. Dragapult ex / Drakloak | - | 55% | 45% |
| 2. Dragapult ex / Blaziken ex | 45% | - | 27% |
| 3. Mega Kangaskhan ex / Teal Mask Ogerpon ex | 55% | 73% | - |

**Best counters to the most common deck (`Dragapult ex / Drakloak`, 47.2% share):**

- `Mega Kangaskhan ex / Teal Mask Ogerpon ex`: 55.4% over 56 matches
- `Dragapult ex / Blaziken ex`: 45.3% over 53 matches

## Equilibrium (fictitious play, symmetric zero-sum deck game)

| Archetype | Equilibrium mix |
|---|---:|
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 100.0% |

Game value: **0.500** (expected win rate of the equilibrium mix vs itself).

Replicator dynamics drift over 50 iterations: 0.000 (settling).

## Caveats

- The matrix is **observational**: pilots differ. A deck's win rate mixes deck strength, pilot skill and matchmaking.
- Cells with few games have wide CIs; only >=10-game cells are shown.
- The game is non-transitive. A pure best response can be punished if the field shifts; the equilibrium is a mix, not a deck.
- The ladder rating is noisy; this analysis is a prior for deck choice, not a guarantee.