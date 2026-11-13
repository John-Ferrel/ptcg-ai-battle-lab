# Piloting gap — where v3 disagrees with top pilots, and why simple rules fail

Method: feed real 2026-11-12 replay observations to the public v3 agent (same
model, same deck) and compare its **semantic** action with the recorded action.
Only the acting player whose deck we loaded is compared; duplicate copies of the
same card/ability are treated as equal.

## Agreement

| Deck | Episodes | Decisions | Overall | MAIN | EVOLVE/SEARCH | DMG_COUNTER_ANY |
|---|---:|---:|---:|---:|---:|---:|
| v3 + pult8_08 | 18 | 4,000 | **65.2%** | **54.8%** | 77.0% | 70.5% |
| v3 + Lopunny_05 | 11 | 3,000 | **62.3%** | **52.6%** | 82.6% | 75.7% |

So the model is not "wrong" most of the time, but MAIN is close to a coin flip
against top pilots. The gap is real.

## Dominant patterns (pult8)

1. **Ability ordering.** Our model often uses **Blaziken ex's Seething Spirit**
   (attach a Basic Energy from discard) first; top pilots use **Drakloak's Recon
   Directive** (look at top 2, take 1), evolve, play Munkidori/Poké Pad, or
   attach first. All 161 observed Blaziken-vs-other disagreements had energy in
   the discard, so this is **not** a no-op; it is an information-ordering choice.
2. **Damage-counter target.** Top pilots place counters on low-HP engine pieces
   (Metang 100, Dreepy 70, Drakloak 90); our model chips high-HP ex (Genesect
   ex, Fezandipiti ex). This is the classic "deny the engine, don't chip a wall"
   principle.
3. **Attach vs information.** Our model attaches {P}/{M} energy where top pilots
   use Drakloak/Metang abilities first.
4. **Evolve vs ability.** Our model evolves; top pilots use the ability first.
5. **Attack vs ability.** Our model attacks (Phantom Dive) where top pilots use
   Drakloak's ability first.

Lopunny shows the same shape: `ATTACH {M} -> ABILITY Metang`, `ATTACH {W} ->
PLAY Dunsparce`, `ATTACK -> EVOLVE Dudunsparce`, `DMG_COUNTER_ANY Fan Rotom ->
Mega Lopunny ex`, etc.

## The reranker experiment — negative

A conservative post-hoc rule was added to the v3 agent:

- only in `DMG_COUNTER_ANY` / `DMG_COUNTER` / `DAMAGE` single-target selects;
- only when the model's target has >= 180 HP and a <= 130 HP engine target exists;
- score = `-hp + KO bonus + ability/stage bonus - high-HP penalty`;
- override only if the alternative is better by a margin.

Result: **48.0% vs the base over 200 games** (0 illegal / 0 errors). No gain.

Interpretation: the model's target choice is often part of a coherent multi-turn
plan (set up a Phantom Dive KO, prize race), and a local rule cannot see that
plan. This matches the public lesson that hand-written guards on a learned policy
often cost points. **The piloting gap is a capacity/ordering gap, not a missing
hand rule.**

## What this means

- Do not keep adding hand rules to the public model; the cheap local overrides
  do not survive a 200-game A/B.
- The remaining real lever is **fine-tuning** the model on the current meta
  (BC/DAgger on 11-12 top-pilot decisions) or a newer checkpoint — both are
  bigger efforts than a rule patch.
- For the current ladder, keep the active pair (pult8 core + Lopunny hedge) and
  do not burn submissions on rule variants.

Reports: `docs/PILOT_GAP_PULT8.md`, `docs/PILOT_GAP_LOPUNNY.md`.
