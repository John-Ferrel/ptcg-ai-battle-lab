# Piloting gap — /tmp/v3_lop vs top pilots

Episodes: 11; decisions compared: 3000; semantic agreement: **62.3%**.

## By context

| Context | n | Agreement |
|---|---:|---:|
| MAIN | 1955 | 52.6% |
| EVOLVE/SEARCH | 386 | 82.6% |
| SWITCH | 152 | 79.6% |
| DMG_COUNTER_ANY | 144 | 75.7% |
| TO_ACTIVE | 92 | 71.7% |
| ATTACH_FROM | 68 | 54.4% |
| SETUP_ACTIVE | 27 | 85.2% |
| 40 | 27 | 100.0% |
| DMG_COUNTER | 27 | 88.9% |
| ATTACH_TO | 26 | 92.3% |
| IS_FIRST | 22 | 95.5% |
| DISCARD_ENERGY | 16 | 100.0% |

## Top disagreement patterns

| Context | ours | theirs | n |
|---|---|---|---:|
| MAIN | ATTACH Basic {M} Energy | ABILITY Metang | 15 |
| MAIN | ATTACH Basic {W} Energy | PLAY Dunsparce | 11 |
| MAIN | ATTACK Gale Thrust | EVOLVE Dudunsparce | 8 |
| DMG_COUNTER_ANY | Fan Rotom | Mega Lopunny ex | 8 |
| MAIN | ATTACK Maximum Drilling | ABILITY Metang | 7 |
| MAIN | ATTACK Gale Thrust | PLAY Poké Pad | 6 |
| MAIN | EVOLVE Mega Froslass ex | ABILITY Dudunsparce | 6 |
| MAIN | ATTACH Basic {W} Energy | ABILITY Dudunsparce | 6 |
| MAIN | END | PLAY Poké Pad | 6 |
| DMG_COUNTER_ANY | Mega Lopunny ex | Dunsparce | 6 |
| MAIN | type12 | ATTACH Basic {W} Energy | 5 |
| MAIN | ATTACK Resentful Refrain | ABILITY Dudunsparce | 5 |
| ATTACH_FROM | Metang | Mega Excadrill ex | 5 |
| MAIN | ATTACK Maximum Drilling | ATTACK Undermine | 5 |
| MAIN | EVOLVE Mega Froslass ex | PLAY Dunsparce | 5 |
| MAIN | ATTACH Basic {W} Energy | PLAY Ultra Ball | 5 |
| MAIN | EVOLVE Mega Lopunny ex | ABILITY Dudunsparce | 5 |
| MAIN | PLAY Hilda | EVOLVE Dudunsparce | 5 |
| MAIN | PLAY Poké Pad | PLAY Dunsparce | 5 |
| MAIN | ATTACK Resentful Refrain | PLAY Ultra Ball | 5 |
| MAIN | PLAY Dunsparce | PLAY Dunsparce | 5 |
| MAIN | ATTACH Enriching Energy | PLAY Dunsparce | 5 |
| MAIN | ATTACH Mist Energy | ABILITY Dudunsparce | 5 |
| MAIN | EVOLVE Mega Froslass ex | PLAY Ultra Ball | 5 |
| MAIN | ABILITY Fezandipiti ex | ABILITY Teal Mask Ogerpon ex | 5 |

## Examples

- `126559357` step 13 **MAIN** — ours `ATTACH Mist Energy` vs theirs `PLAY Shaymin`  
  turn 2 | my prizes 6 opp 6 | hand 7 deck 45 | active 848:70/70 vs 756:300/300 | bench 0/2
- `126559357` step 14 **MAIN** — ours `ATTACH Mist Energy` vs theirs `PLAY Buddy-Buddy Poffin`  
  turn 2 | my prizes 6 opp 6 | hand 6 deck 45 | active 848:70/70 vs 756:300/300 | bench 1/2
- `126559357` step 17 **MAIN** — ours `PLAY Lillie's Determination` vs theirs `ABILITY ?`  
  turn 2 | my prizes 6 opp 6 | hand 4 deck 43 | active 848:70/70 vs 756:300/300 | bench 3/2
- `126559357` step 20 **MAIN** — ours `ATTACK Run Around` vs theirs `PLAY Ultra Ball`  
  turn 2 | my prizes 6 opp 6 | hand 8 deck 38 | active 848:70/70 vs 756:300/300 | bench 3/2
- `126559357` step 41 **MAIN** — ours `ATTACH Mist Energy` vs theirs `type12`  
  turn 4 | my prizes 6 opp 6 | hand 5 deck 36 | active 65:60/60 vs 162:80/80 | bench 4/4
- `126559357` step 43 **MAIN** — ours `EVOLVE Dudunsparce` vs theirs `ATTACH Mist Energy`  
  turn 4 | my prizes 6 opp 6 | hand 5 deck 36 | active 849:330/330 vs 162:80/80 | bench 4/4
- `126559357` step 45 **MAIN** — ours `PLAY Lillie's Determination` vs theirs `PLAY Chien-Pao`  
  turn 4 | my prizes 6 opp 6 | hand 3 deck 36 | active 849:330/330 vs 162:80/80 | bench 4/4
- `126559357` step 48 **MAIN** — ours `ATTACH Air Balloon` vs theirs `ABILITY Dudunsparce`  
  turn 4 | my prizes 6 opp 6 | hand 8 deck 29 | active 849:330/330 vs 162:80/80 | bench 5/4
- `126559357` step 50 **MAIN** — ours `PLAY Ultra Ball` vs theirs `ATTACK Gale Thrust`  
  turn 4 | my prizes 6 opp 6 | hand 10 deck 28 | active 849:330/330 vs 162:80/80 | bench 4/4
- `126559357` step 79 **MAIN** — ours `EVOLVE Dudunsparce` vs theirs `PLAY Pokégear 3.0`  
  turn 6 | my prizes 5 opp 6 | hand 12 deck 27 | active 849:30/330 vs 163:120/120 | bench 4/4
- `126559357` step 81 **MAIN** — ours `EVOLVE Dudunsparce` vs theirs `PLAY Battle Cage`  
  turn 6 | my prizes 5 opp 6 | hand 12 deck 26 | active 849:30/330 vs 163:120/120 | bench 4/4
- `126559357` step 82 **MAIN** — ours `EVOLVE Dudunsparce` vs theirs `PLAY Poké Pad`  
  turn 6 | my prizes 5 opp 6 | hand 11 deck 26 | active 849:30/330 vs 163:120/120 | bench 4/4
- `126559357` step 85 **MAIN** — ours `ABILITY Dudunsparce` vs theirs `type12`  
  turn 6 | my prizes 5 opp 6 | hand 10 deck 25 | active 849:30/330 vs 163:120/120 | bench 4/4
- `126559357` step 92 **MAIN** — ours `PLAY Buneary` vs theirs `PLAY Buddy-Buddy Poffin`  
  turn 6 | my prizes 5 opp 6 | hand 13 deck 24 | active 849:330/330 vs 163:120/120 | bench 3/4
- `126559357` step 120 **MAIN** — ours `type12` vs theirs `ATTACH Basic {W} Energy`  
  turn 8 | my prizes 4 opp 6 | hand 11 deck 20 | active 849:30/330 vs 163:120/120 | bench 5/3
- `126559357` step 123 **MAIN** — ours `ATTACK Resentful Refrain` vs theirs `PLAY Hilda`  
  turn 8 | my prizes 4 opp 6 | hand 10 deck 20 | active 861:310/310 vs 163:120/120 | bench 5/3
- `126559357` step 127 **MAIN** — ours `ATTACK Resentful Refrain` vs theirs `ABILITY Dudunsparce`  
  turn 8 | my prizes 4 opp 6 | hand 10 deck 18 | active 861:310/310 vs 163:120/120 | bench 5/3
- `126559357` step 128 **MAIN** — ours `PLAY Buneary` vs theirs `PLAY Pokégear 3.0`  
  turn 8 | my prizes 4 opp 6 | hand 13 deck 17 | active 861:310/310 vs 163:120/120 | bench 4/3
- `126559357` step 148 **MAIN** — ours `PLAY Wally's Compassion` vs theirs `PLAY Boss’s Orders`  
  turn 10 | my prizes 3 opp 6 | hand 14 deck 15 | active 861:90/310 vs 272:190/190 | bench 5/5
- `126559357` step 161 **MAIN** — ours `PLAY Pokégear 3.0` vs theirs `PLAY Battle Cage`  
  turn 1 | my prizes 6 opp 6 | hand 8 deck 43 | active 174:70/70 vs 756:300/300 | bench 2/0