# heuristic_v1 — card-data-aware rule policy

Self-contained submission agent (Python stdlib only):

```
agents/heuristic_v1/
├── main.py          # agent(obs) -> list[int]
├── deck.csv         # copy of decks/deck_dipplin.csv (deck not tuned here)
├── card_meta.json   # generated locally; git-ignored (licensed card data)
└── README.md
```

`card_meta.json` is generated from the engine card DB:

```bash
.venv/bin/python scripts/export_agent_card_meta.py --out agents/heuristic_v1/card_meta.json
```

It is optional: if the file is absent, `main.py` still runs with type-agnostic
priors and the same legality guarantees (verified: it still wins games without
the file, just with a weaker card model). The file is **not committed** because
`data/` card dumps are licensed competition data and `.gitignore` intentionally
excludes `agents/*/card_meta.json`; build submissions locally after generating it.

## What the policy does

* **MAIN** scores every offered action with card data:
  * attacks: effective damage (weakness ×2, resistance −30, scaling text such as
    Do the Wave's 20 × benched, tool bonuses such as Brave Bangle), KO bonus
    weighted by prize value / prizes remaining / game win;
  * energy attachment: attaches only up to the chosen attack's cost, prefers the
    active attacker, avoids a doomed active, develops benched attackers;
  * evolution priority (active evolution first, Festival Lead / Stage 2 bonuses);
  * bench development (bench size is the Dipplin damage engine);
  * supporter/item sequencing using card text + `supporterPlayed` /
    `stadiumPlayed` / `energyAttached`, hand size and deck belief;
  * retreat when the active is doomed/status-locked and the bench has a ready
    attacker; `END` is the second-lowest action.
* **Sub-selections** are value-ranked with context-aware direction: search picks
  the best card (using the revealed `select.deck` when the effect exposes it),
  discard picks the cheapest card, damage targets maximize prize/KO value,
  heal/remove-damage picks the most damaged valuable Pokémon, energy discard
  picks the least useful attached energy, etc.
* **All contexts observed in practice are handled**, including `MAIN`,
  `SETUP_ACTIVE`, `SETUP_BENCH`, `SWITCH`, `TO_ACTIVE`, `TO_BENCH`, `DISCARD`,
  `DISCARD_ENERGY`, `ATTACH_TO`, `ATTACH_FROM`, damage/damage-counter targets,
  remove-damage, `SKILL_ORDER`, the SelectType 6 attack select (attackId),
  `IS_FIRST`, `MULLIGAN`, `YES_NO`, `COUNT`, `SPECIAL_CONDITION`, and unknown
  contexts via a legal min/max-clamped fallback.
* **Never throws**: `agent()` catches everything and every return is clamped to
  the offered indices and `[minCount, maxCount]`.

## Validation

Reproduce with:

```bash
.venv/bin/python scripts/policy_selftest.py       # synthetic legality coverage
.venv/bin/python scripts/policy_validate.py       # 200 games per opponent, seat-swapped
```

Final run (200 games each, `--workers 3`, deck `decks/deck_dipplin.csv`,
arena alternates seats; Wilson 95% CI):

| opponent | win rate | 95% CI | illegal | errors | avg decision | max decision |
|---|---:|---|---:|---:|---:|---:|
| random_legal | 91.5% (183/200) | [86.8, 94.6] | 0 | 0 | 0.048 ms | 6.3 ms |
| first_legal | 91.5% (183/200) | [86.8, 94.6] | 0 | 0 | 0.042 ms | 5.0 ms |
| greedy | 84.5% (169/200) | [78.8, 88.9] | 0 | 0 | 0.052 ms | 6.3 ms |
| heuristic_v1 (mirror) | 49.0% (98/200) | [42.2, 55.9] | 0 | 0 | 0.083 ms | 5.7 ms |

Mirror seat split: 69% as player 0, 29% as player 1. The harness gives the
`IS_FIRST` choice to player 0, and player 0 chooses to go first; the residual is
the going-first advantage (seat 0 wins 70% of mirror games), not an asymmetry
between the two seats' code (both seats run the identical agent). Overall
98/200 is within noise of 50%.

Artifacts: `results/policy_v1_vs_{random,first,greedy}.jsonl`,
`results/policy_v1_mirror.jsonl`, summaries and `results/policy_v1_table.json`.

## Known weaknesses (next iteration)

1. **One-ply only** — no opponent-hand/prize belief and no determinized search;
   multi-turn sequencing (when to hold Lillie/Unfair Stamp, when to sacrifice a
   Pokémon) is heuristic.
2. **Attack-text coverage** — scaling/conditional modifiers are only partially
   parsed (bench/energy/hand scalars, Brave Bangle); coin flips, "if you have …"
   bonuses and snipe targeting are approximated. Effect text from other decks is
   scored generically.
3. **Deck-generalisation** — thresholds and card-text weights were validated on
   the Dipplin list; other archetypes (e.g. `deck_ogerpon_field`) are legal and
   functional but not tuned. Search picks from a hidden deck (options with
   `area=1` but no revealed `select.deck`) cannot be distinguished by card id.
