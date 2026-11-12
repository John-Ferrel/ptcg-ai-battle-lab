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
  * **turn sequencing / attack gate**: `MAIN` is a sequential menu and `ATTACK`
    ends the turn. Lethal attacks are taken immediately; otherwise any
    non-attack action with positive marginal value (play / ability / evolve /
    attach / useful retreat) is exhausted first, and `END` is the last fallback.
    This mirrors the dominant replay-mined disagreement vs 1400+ pilots
    (`ATTACK` too early instead of developing).
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
    attacker.
* **Deck-search prompts (context 7, ~16% of decisions)** resolve each option
  through `select.deck[k]` (area 1), the discard pile (area 3) or the revealed
  `looking` pile (area 12), then rank targets: missing evolution piece →
  draw/search engine → energy for an unpowered attacker → win condition.
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
| random_legal | 95.0% (190/200) | [91.0, 97.3] | 0 | 0 | 0.060 ms | 3.4 ms |
| first_legal | 99.0% (198/200) | [96.4, 99.7] | 0 | 0 | 0.049 ms | 1.4 ms |
| greedy | 96.0% (192/200) | [92.3, 98.0] | 0 | 0 | 0.057 ms | 1.4 ms |
| heuristic_v1 (mirror) | 46.5% (93/200) | [39.7, 53.4] | 0 | 0 | 0.082 ms | 1.3 ms |

Before/after the replay-mined fixes (same deck, same 200-game protocol):

| opponent | before | after | delta |
|---|---:|---:|---:|
| random_legal | 88.5% | 95.0% | +6.5 pts |
| first_legal | 89.0% | 99.0% | +10.0 pts |
| greedy | 82.5% | 96.0% | +13.5 pts |
| mirror | 47.5% | 46.5% | −1.0 pt (noise) |

Mirror is seat-balanced after the sequencing fix: seat 0 wins 101/200, seat 1
wins 99/200; 93/200 for A is within noise of 50%.

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
