# Metagame analysis

Source: `results/meta_1109/episodes.jsonl`

1694 matches, 3388 deck slots, 10 archetypes with >= 30 seats.

## Shares and field-weighted win rate

| Archetype | Seats | Share | Field-weighted WR |
|---|---:|---:|---:|
| Mega Excadrill ex / Genesect ex | 1337 | 39.5% | 0.487 |
| Dragapult ex / Blaziken ex | 555 | 16.4% | 0.514 |
| Dragapult ex / Drakloak | 393 | 11.6% | 0.452 |
| Mega Lopunny ex / Mega Froslass ex | 357 | 10.5% | 0.543 |
| Lillie’s Clefairy ex / Banette | 260 | 7.7% | 0.398 |
| Mega Kangaskhan ex / Teal Mask Ogerpon ex | 139 | 4.1% | 0.616 |
| Mega Kangaskhan ex / Crustle | 98 | 2.9% | 0.374 |
| Blaziken ex / Dragapult ex | 76 | 2.2% | 0.518 |
| Mega Kangaskhan ex / Latias ex | 67 | 2.0% | 0.556 |
| Alakazam / Toucannon | 52 | 1.5% | 0.574 |

**Best response to this field: `Mega Kangaskhan ex / Teal Mask Ogerpon ex` (0.616).**

## Matchup matrix (row win rate vs column; cells with <10 games = `-`)

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1. Mega Excadrill ex / Genesect ex | - | 32% | 63% | 65% | 63% | 21% | 76% | 32% | 10% | 50% |
| 2. Dragapult ex / Blaziken ex | 68% | - | 43% | 29% | 48% | 30% | - | - | 58% | - |
| 3. Dragapult ex / Drakloak | 37% | 57% | - | 48% | 50% | 44% | - | - | - | - |
| 4. Mega Lopunny ex / Mega Froslass ex | 35% | 71% | 52% | - | 92% | 85% | - | - | - | - |
| 5. Lillie’s Clefairy ex / Banette | 37% | 52% | 50% | 8% | - | - | 59% | - | - | - |
| 6. Mega Kangaskhan ex / Teal Mask Ogerpon ex | 79% | 70% | 56% | 15% | - | - | - | - | - | - |
| 7. Mega Kangaskhan ex / Crustle | 24% | - | - | - | 41% | - | - | - | - | - |
| 8. Blaziken ex / Dragapult ex | 68% | - | - | - | - | - | - | - | - | - |
| 9. Mega Kangaskhan ex / Latias ex | 90% | 42% | - | - | - | - | - | - | - | - |
| 10. Alakazam / Toucannon | 50% | - | - | - | - | - | - | - | - | - |

**Best counters to the most common deck (`Mega Excadrill ex / Genesect ex`, 39.5% share):**

- `Mega Kangaskhan ex / Latias ex`: 90.0% over 30 matches
- `Mega Kangaskhan ex / Teal Mask Ogerpon ex`: 78.6% over 14 matches
- `Blaziken ex / Dragapult ex`: 68.3% over 41 matches
- `Dragapult ex / Blaziken ex`: 68.3% over 189 matches
- `Alakazam / Toucannon`: 50.0% over 30 matches

## Equilibrium (fictitious play, symmetric zero-sum deck game)

| Archetype | Equilibrium mix |
|---|---:|
| Mega Excadrill ex / Genesect ex | 28.7% |
| Dragapult ex / Drakloak | 22.7% |
| Mega Lopunny ex / Mega Froslass ex | 22.7% |
| Mega Kangaskhan ex / Latias ex | 16.8% |
| Alakazam / Toucannon | 9.1% |

Game value: **0.500** (expected win rate of the equilibrium mix vs itself).

Replicator dynamics drift over 50 iterations: 1.393 (still moving / cycling).

## Caveats

- The matrix is **observational**: pilots differ. A deck's win rate mixes deck strength, pilot skill and matchmaking.
- Cells with few games have wide CIs; only >=10-game cells are shown.
- The game is non-transitive. A pure best response can be punished if the field shifts; the equilibrium is a mix, not a deck.
- The ladder rating is noisy; this analysis is a prior for deck choice, not a guarantee.