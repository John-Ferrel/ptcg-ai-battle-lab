# Metagame dynamics — is there an optimal strategy?

Short answer: **no static optimum.** The deck-level game is a non-transitive
zero-sum game (rock–paper–scissors), so a pure "best deck" invites a counter,
the counter invites a counter-counter, and the only stable object is a **mixed
strategy / best response to the current field**. On top of that, the pilot is
part of the strategy: a deck that is the best response under its original pilot
may be unplayable under ours.

This note is the method + the evidence from the 1,694 playground matches of
2026-11-09 (`docs/META_GAME.md`, `docs/META_GAME_ALL.md`).

## 1. Theory in one page

- A match is (approximately) symmetric zero-sum: one win, one loss. The
  deck-choice game is therefore a matrix game. If the matrix is non-transitive,
  it has no pure-strategy saddle point; the value is achieved by a **mixed
  strategy** (Nash equilibrium).
- The ladder is not a single matrix game. It is a **population game** with
  matchmaking by rating, a finite noisy sample, and a meta that moves daily.
  "Optimal" means **maximizing expected rating against the current opponent
  distribution at your rating band**, not winning against a fixed field.
- A counter to the top strategy **can** replace it — that is exactly what
  happens in a non-transitive meta. But then the counter becomes the top
  strategy, and it gets countered. The equilibrium is a cycle/mix, not a
  permanent throne.
- If the top strategy is a **policy advantage** (a much stronger pilot), deck
  counters are weaker: the counter deck may beat the top archetype but lose to
  the rest of the field, and the top pilot may still outplay you in the mirror.
- Ladder noise matters: one public write-up re-submitted the same archive 13
  times and saw 723.8–977.3. A 2-point "counter edge" is below the noise floor
  of a single run.

## 2. Evidence: a real 3-cycle on 2026-11-09

Match-level win rates (BO3 match winner), all ratings, cells with ≥10 matches:

| A vs B | A win rate | Games |
|---|---:|---:|
| Mega Excadrill / Genesect vs **Kangaskhan / Ogerpon** | 21% | 14 |
| **Kangaskhan / Ogerpon** vs Mega Lopunny / Froslass | 15% | 13 |
| **Mega Lopunny / Froslass** vs Mega Excadrill / Genesect | 35% | 132 |

So:

```
Excadrill  --beats 79%-->  Kangaskhan/Ogerpon
Kangaskhan/Ogerpon --loses 85%-->  Lopunny
Lopunny --loses 65%-->  Excadrill
```

This is a genuine cycle. A second cycle involves Dragapult/Blaziken:

```
Dragapult/Blaziken --beats 68%--> Excadrill (189 games)
Lopunny --beats 71%--> Dragapult/Blaziken (85 games)
Excadrill --beats 65%--> Lopunny (132 games)
```

No deck in this graph is unconditionally best.

## 3. Best response depends on the field shares

Field-weighted WR = Σ share(opponent) × WR(deck, opponent). On the
**≥1200 rating band**:

| Deck | Share | Field-weighted WR |
|---|---:|---:|
| Mega Kangaskhan / Ogerpon | 6.3% | **0.625** |
| Mega Kangaskhan / Latias | 3.0% | 0.591 |
| Dragapult / Drakloak | 13.2% | 0.565 |
| Mega Lopunny / Froslass | 11.1% | 0.549 |
| Dragapult / Blaziken | 21.4% | 0.519 |
| Mega Excadrill / Genesect | 38.2% | 0.425 |

The pure best response is **Kangaskhan/Ogerpon** because it beats the 38% 
Excadrill field (79%) and the Dragapult decks (56–70%), and only pays 15% to
Lopunny (11% share). If Lopunny's share doubles, the same deck's weighted WR
falls by roughly 8–10 points. The best response is a function of the shares.

## 4. The pilot is part of the strategy

The table above is **observational**: those win rates were produced by the decks'
original pilots. Our PPO model, re-decked to each list (same model, 80 games per
pair), gives a very different joint ranking:

| Deck under the v3 PPO model | Round-robin WR |
|---|---:|
| Mega Lopunny / Froslass | **63.4%** |
| Dragapult / Drakloak | 58.4% |
| Alakazam (bundle list) | 53.4% |
| Mega Excadrill / Genesect | 45.6% |
| Kangaskhan / Ogerpon | **29.1%** |

So **the deck-level best response (Kangaskhan/Ogerpon, 62.5% field-weighted) is
not executable by our model (29.1% in its own round-robin)**. A counter is only
real if the joint (deck, pilot) can execute it. This is why we submitted
Dragapult/Blaziken and Lopunny, not the theoretical counter.

## 5. How to analyze the mainstream and build a counter

This is a repeatable pipeline; the scripts are in this repo.

1. **Ingest the daily replays** (`scripts/analyze_episodes.py`). One day ≈ 2,000
   BO3 matches. Keep the manifest so you can filter by rating band.
2. **Label archetypes correctly** (`scripts/meta_game.py`): Mega ex first, then
   ex with ≥2 copies, then the highest evolution stage, then copies. A naive
   "highest HP" label misclassifies decks.
3. **Build a match-level matchup matrix**, not game-level, because the ladder is
   BO3. Only trust cells with ≥10 matches; show Wilson intervals for the rest.
4. **Compute shares and field-weighted WR** for each deck. The argmax is the
   pure best response to *this* field.
5. **Check for cycles** (3-cycles are common). If the matrix is non-transitive,
   the equilibrium is a mix. Fictitious play / replicator dynamics tells you
   whether the population is settling or cycling (`scripts/meta_game.py` prints
   both; our 11-09 data is still cycling, drift 0.08).
6. **Control for the pilot**:
   - same-team deck switches (a team that played two decks with ≥15 games each),
   - Bradley–Terry per (team, deck) like the daily-meta notebook,
   - or, best, run the **joint** (deck, pilot) in a field-weighted gauntlet.
7. **Evaluate joint candidates against the field**, not against one opponent:
   `scripts/gauntlet.py` with weights = current shares. This is the practical
   best-response test.
8. **Exploit pilot tendencies** with replay mining: `scripts/divergence.py`
   finds where our policy differs from top pilots on the same states. A counter
   can be deck-level (matchup) or policy-level (punish a predictable pilot).
9. **Use a rolling window and CIs.** The meta moves; an October best response
   can be an November trap (Alakazam was 65–68% in early October, 1.9% of seats
   by 9 November).
10. **Do not overfit to a single ladder run.** The same artifact scored 1102.5
    and 671.0 on two runs; a counter needs a large, repeated edge to be real.

## 6. What would actually counter the current top?

The current top of the public ladder is a strong PPO policy, not a single deck.
A deck-level counter (e.g., Kangaskhan/Ogerpon vs Excadrill) only helps if:

- the target archetype is a large share of your rating band (yes: Excadrill 38%),
- the counter still has decent matchups vs the rest (Kangaskhan/Ogerpon: yes,
  except Lopunny),
- **and** your pilot can execute it (our model: no).

Without a pilot that can play the counter, the practical best response is the
robust deck that the pilot plays best — for our v3 model that is
Lopunny/Dragapult/Blaziken, not the theoretical counter. This is exactly what
the real ladder showed: pult8 stable ~944, Lopunny noisy 671–1102, and the
theoretical counter was not submitted because v3 piloted it at 29%.

## 7. One-sentence answer

There is no permanent optimal deck; the game is a non-transitive population
game, so the best you can do is estimate the current field, compute the best
response, check that your pilot can execute it, and re-estimate as the field
adapts — and because the ladder is noisy, require a large repeated edge before
believing a counter is real.

## 8. Rating-band effect: a local optimum can exist

At **≥1400** (142 matches, only three archetypes with ≥15 seats), the field
narrows:

| Deck | Share | Field-weighted WR |
|---|---:|---:|
| Dragapult / Drakloak | 47.2% | 0.474 |
| Dragapult / Blaziken | 24.3% | 0.399 |
| Kangaskhan / Ogerpon | 23.6% | **0.556** |

Here Kangaskhan/Ogerpon beats both other top decks (55.4% vs Drakloak, 73% vs
Blaziken) and is a **pure local best response**. But Lopunny — the deck that
hard-counters it (85%) — is not in this narrow sample. At the broader ≥1200/all
band, Lopunny is 10–11% of the field and the 3-cycle returns.

So the answer depends on the band:

- **At a narrow top band**, the field can collapse to 2–3 decks and a pure
  counter can be locally optimal for a while.
- **At the broader band**, the field is diverse and non-transitive; only a mix
  is stable.
- The ladder moves agents between bands, so a local optimum at 1400 can be
  invaded by a deck that is common at 1200.

This is also why a **portfolio of two active submissions** (one robust deck +
one counter deck) is a reasonable hedge in a non-transitive meta: you are
playing a mixed strategy with two pure components.

## 9. 2026-11-11 update: climb path and pilot-conditional counter

The parsed ladder dataset (79k matches, CC0) gives a cleaner picture than the
single-day raw replays.

**Latest shares (11-11):** Excadrill 34.0% (WR 45.6%), Dragapult/Blaziken 26.3%
(55.2%), Lopunny 12.8% (53.3%), Dragapult/Drakloak 11.5% (51.5%),
Kangaskhan/Latias 2.8% (**59.1%**), Kangaskhan/Ogerpon 5.3% (56.2%).

**Climb path (the practical answer to "can't submit per band"):**

| Band | Best climber | pult8 WR | Lopunny WR |
|---|---|---:|---:|
| 1000–1200 | **pult8 (71.4%, field-WR 0.704)** | 71.4% | 58.1% |
| 1200–1400 | Kangaskhan/Latias (59.1%, field-WR 0.598) | 52.7% | 54.7% |
| 1400+ | Kangaskhan/Ogerpon (59.8%, field-WR 0.573) | 49.2% | 46.7% |

Dragapult/Blaziken is the best **climber**: it dominates the Excadrill-heavy
1000–1200 band and stays competitive at the top. The theoretical top-band
counters are not executable by our v3 pilot:

- Kangaskhan/Latias vs v3+pult8: **43.8%** (19 stalls, avg 274 turns)
- Kangaskhan/Latias vs v3+Lopunny: **31.7%** (8 stalls)
- pult8_top / pult8_88b26e / Drakloak top vs pult8_08: 48.1% / 48.3% / 48.3%
- Excadrill top vs pult8_08: 30.0%
- go-second vs go-first: 43.8% (go-first is correct)
- temp=1.0 vs temp=0: 48.3% over 420 games (keep argmax)

So the climb path, not the equilibrium, decides the core: pult8 is the deck that
gets you through the bands where Excadrill is 54% of the field, and it is still
~49% at 1400+. The top-band specialist is a paper counter until a pilot can
execute it.

## 10. 2026-11-12 update: the top band narrows

11-12 raw replays (1,625 matches):

| Band | Top decks | Best response |
|---|---|---|
| 1000–1200 | Excadrill 36.0% (0.413), pult8 25.8% (0.571), Drakloak 12.4% (0.548) | Kangaskhan/Ogerpon 0.632 |
| 1200–1400 | Excadrill 29.6% (0.418), pult8 29.0% (0.540), Drakloak 14.9% (0.515) | Kangaskhan/Ogerpon 0.606 |
| 1400+ | **Drakloak 45.2% (0.542)**, pult8 25.9% (0.382), Kangaskhan/Ogerpon 17.2% (0.629), Lopunny 11.7% (0.412) | Kangaskhan/Ogerpon 0.629 |

The top band has narrowed to the Dragapult mirror + Kangaskhan. pult8 is the
best climber through 1000–1400; at 1400+ the Drakloak variant is better in the
real field (0.542 vs 0.382), but under our v3 pilot they are even (48.3% in 120
games), and Drakloak is weak at 1000–1200 (33% on 11-11). That is the classic
"climb vs top-band" tradeoff: a top-band specialist must still survive the lower
bands.

The theoretical top-band best response (Kangaskhan/Ogerpon 0.629) remains
unplayable by v3. The practical portfolio is unchanged: pult8 core + Lopunny
hedge.
