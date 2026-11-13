# Piloting gap — /tmp/v3_pult8 vs top pilots

Episodes: 18; decisions compared: 4000; semantic agreement: **65.2%**.

## By context

| Context | n | Agreement |
|---|---:|---:|
| MAIN | 2161 | 54.8% |
| EVOLVE/SEARCH | 687 | 77.0% |
| DMG_COUNTER_ANY | 498 | 70.5% |
| ATTACH_FROM | 109 | 85.3% |
| SWITCH | 108 | 75.9% |
| ATTACH_TO | 87 | 81.6% |
| TO_ACTIVE | 87 | 69.0% |
| DMG_COUNTER | 55 | 78.2% |
| 40 | 50 | 100.0% |
| 16 | 32 | 81.2% |
| SETUP_ACTIVE | 29 | 82.8% |
| IS_FIRST | 28 | 100.0% |

## Top disagreement patterns

| Context | ours | theirs | n |
|---|---|---|---:|
| MAIN | ABILITY Blaziken ex | ABILITY Drakloak | 27 |
| DMG_COUNTER_ANY | Genesect ex | Metang | 19 |
| MAIN | ATTACH Basic {P} Energy | ABILITY Drakloak | 15 |
| DMG_COUNTER_ANY | Fezandipiti ex | Metang | 12 |
| MAIN | ABILITY Blaziken ex | EVOLVE Dragapult ex | 11 |
| MAIN | ABILITY Drakloak | EVOLVE Drakloak | 10 |
| MAIN | ABILITY Blaziken ex | PLAY Munkidori | 10 |
| MAIN | ABILITY Blaziken ex | type12 | 10 |
| MAIN | ABILITY Blaziken ex | PLAY Night Stretcher | 9 |
| MAIN | ABILITY Blaziken ex | ATTACH Basic {R} Energy | 9 |
| MAIN | ATTACH Basic {P} Energy | ATTACH Basic {R} Energy | 9 |
| MAIN | ABILITY Blaziken ex | EVOLVE Drakloak | 9 |
| MAIN | ABILITY Blaziken ex | PLAY Poké Pad | 9 |
| MAIN | ATTACH Basic {R} Energy | ABILITY Drakloak | 9 |
| MAIN | ATTACK Phantom Dive | ABILITY Drakloak | 9 |
| DMG_COUNTER_ANY | Dunsparce | Mega Froslass ex | 9 |
| MAIN | ABILITY Drakloak | PLAY Poké Pad | 8 |
| ATTACH_TO | Basic {P} Energy | Basic {R} Energy | 8 |
| MAIN | ABILITY Blaziken ex | PLAY Ultra Ball | 8 |
| MAIN | EVOLVE Dragapult ex | ABILITY Drakloak | 8 |
| MAIN | ABILITY Blaziken ex | PLAY Lillie's Determination | 7 |
| MAIN | ATTACK Phantom Dive | PLAY Ultra Ball | 7 |
| MAIN | ABILITY Blaziken ex | PLAY Buddy-Buddy Poffin | 7 |
| MAIN | ABILITY Fezandipiti ex | ABILITY Drakloak | 7 |
| MAIN | PLAY Lillie's Determination | ABILITY Drakloak | 6 |

## Blaziken ability context (ours=Blaziken, theirs!=Blaziken)

| has energy in discard | Drakloak ability available | n |
|---|---|---:|
| True | False | 87 |
| True | True | 74 |

## Damage-counter target HP (theirs)

- ctx DMG_COUNTER_ANY: target hp 100 (low=True) x34
- ctx DMG_COUNTER_ANY: target hp 70 (low=True) x28
- ctx DMG_COUNTER_ANY: target hp 310 (low=False) x14
- ctx DMG_COUNTER_ANY: target hp 90 (low=True) x12
- ctx DMG_COUNTER_ANY: target hp 330 (low=False) x11
- ctx DMG_COUNTER_ANY: target hp 120 (low=True) x8
- ctx DMG_COUNTER_ANY: target hp 220 (low=False) x7
- ctx DMG_COUNTER_ANY: target hp 110 (low=True) x6
- ctx DMG_COUNTER_ANY: target hp 320 (low=False) x5
- ctx DMG_COUNTER_ANY: target hp 30 (low=True) x5

## Examples

- `126558485` step 27 **EVOLVE/SEARCH** — ours `Basic {P} Energy` vs theirs `Basic {R} Energy`  
  turn 3 | my prizes 6 opp 6 | hand 5 deck 41 | active 31:100/110 vs 235:30/30 | bench 3/4
- `126558485` step 64 **MAIN** — ours `EVOLVE Combusken` vs theirs `PLAY Dawn`  
  turn 5 | my prizes 5 opp 6 | hand 4 deck 40 | active 31:100/110 vs 120:90/90 | bench 3/4
- `126558485` step 65 **EVOLVE/SEARCH** — ours `Fezandipiti ex` vs theirs `Torchic`  
  turn 5 | my prizes 5 opp 6 | hand 3 deck 40 | active 31:100/110 vs 120:90/90 | bench 3/4
- `126558485` step 68 **MAIN** — ours `EVOLVE Combusken` vs theirs `PLAY Torchic`  
  turn 5 | my prizes 5 opp 6 | hand 6 deck 37 | active 31:100/110 vs 120:90/90 | bench 3/4
- `126558485` step 97 **TO_ACTIVE** — ours `Dreepy` vs theirs `Drakloak`  
  turn 6 | my prizes 5 opp 5 | hand 3 deck 35 | active - vs 121:320/320 | bench 5/4
- `126558485` step 100 **MAIN** — ours `ABILITY Drakloak` vs theirs `PLAY Poké Pad`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 33 | active 120:90/90 vs 121:320/320 | bench 4/4
- `126558485` step 102 **MAIN** — ours `ABILITY Drakloak` vs theirs `EVOLVE Drakloak`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 32 | active 120:90/90 vs 121:320/320 | bench 4/4
- `126558485` step 104 **EVOLVE/SEARCH** — ours `Poké Pad` vs theirs `Area Zero Underdepths`  
  turn 7 | my prizes 5 opp 5 | hand 4 deck 30 | active 120:90/90 vs 121:320/320 | bench 4/4
- `126558485` step 105 **MAIN** — ours `ABILITY Drakloak` vs theirs `PLAY Area Zero Underdepths`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 31 | active 120:90/90 vs 121:320/320 | bench 4/4
- `126558485` step 110 **MAIN** — ours `PLAY Rare Candy` vs theirs `EVOLVE Dragapult ex`  
  turn 7 | my prizes 5 opp 5 | hand 7 deck 27 | active 120:90/90 vs 121:320/320 | bench 5/4
- `126558485` step 113 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `PLAY Munkidori`  
  turn 7 | my prizes 5 opp 5 | hand 4 deck 27 | active 121:320/320 vs 121:320/320 | bench 5/4
- `126558485` step 114 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `PLAY Munkidori`  
  turn 7 | my prizes 5 opp 5 | hand 3 deck 27 | active 121:320/320 vs 121:320/320 | bench 6/4
- `126558485` step 115 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `PLAY Lillie's Determination`  
  turn 7 | my prizes 5 opp 5 | hand 2 deck 27 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 116 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `PLAY Night Stretcher`  
  turn 7 | my prizes 5 opp 5 | hand 6 deck 22 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 117 **EVOLVE/SEARCH** — ours `Basic {D} Energy` vs theirs `Basic {R} Energy`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 22 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 118 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `ATTACH Basic {R} Energy`  
  turn 7 | my prizes 5 opp 5 | hand 6 deck 22 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 119 **MAIN** — ours `ABILITY Blaziken ex` vs theirs `PLAY Unfair Stamp`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 22 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 123 **MAIN** — ours `PLAY Ultra Ball` vs theirs `ATTACK Phantom Dive`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 21 | active 121:320/320 vs 121:320/320 | bench 7/4
- `126558485` step 124 **DMG_COUNTER_ANY** — ours `Drakloak` vs theirs `Munkidori`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 21 | active 121:320/320 vs 121:120/320 | bench 7/4
- `126558485` step 125 **DMG_COUNTER_ANY** — ours `Drakloak` vs theirs `Munkidori`  
  turn 7 | my prizes 5 opp 5 | hand 5 deck 21 | active 121:320/320 vs 121:120/320 | bench 7/4