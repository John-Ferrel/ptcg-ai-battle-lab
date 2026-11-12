# DEV NOTES — environment quirks (read first)

## Layout

```
ptcg-ai-battle/
├── src/ptcg_ai/          # shared tooling (NOT used by submissions at runtime)
│   ├── cards.py          # AllCard()/AllAttack() ctypes binding + JSON cache
│   ├── deck.py           # load/validate deck files
│   ├── obs.py            # pure helpers over the raw obs dict
│   └── harness.py        # direct ctypes game loop, Kaggle-contract semantics
├── scripts/arena.py      # N games, multiprocess, seat swap, Wilson CI
├── agents/<name>/        # main.py + deck.csv (+ optional card_meta.json)
├── decks/*.csv           # 60 card ids, one per line
├── data/                 # generated card DB (git-ignored, licensed data)
└── results/              # generated (git-ignored)
```

Run everything with the project venv:

```bash
cd ptcg-ai-battle
.venv/bin/python scripts/build_card_db.py          # once
.venv/bin/python scripts/arena.py --agent-a agents/greedy --deck-a decks/default.csv \
    --agent-b agents/random_legal --deck-b decks/default.csv --games 20 --workers 4
```

## Hard rules

1. **Never modify the engine or `src/ptcg_ai/harness.py`** unless the task says so.
2. A submission agent must be **self-contained** (`agents/<name>/main.py` +
   `deck.csv` + optional data file in the same dir), stdlib only. It cannot
   import `ptcg_ai` or `cg`.
3. Every agent must be legal by construction: clamp the returned indices to the
   offered options and to `[minCount, maxCount]`.
4. The engine is a **process-global singleton**. Never run two battles in one
   process. `arena.py` uses one process per game.
5. Engine RNG is **not seedable** (`std::random_device`). Do not claim
   determinism. Use seat-swapped batches and Wilson CIs.
6. `battle_start` order matters for the trace but seat swap is handled by
   `arena.py`.
7. Card ids, names, attacks and scripts are **licensed competition data**. Do not
   paste the card DB into git; `data/` is git-ignored.

## Useful facts (measured)

- ~10 ms per game with the direct ctypes harness, ~150 ms with `make("cabt")`.
- 406 decisions over 6 random games: MAIN 66%, EVOLVE 13%, SWITCH 4%,
  DISCARD_ENERGY 4%, SETUP_ACTIVE 3%.
- `select.maxCount` can be 5 (setup bench) or 1 (most targets); `minCount` is
  often 0 for optional effects.
- On `obs["select"] is None` return the 60 card ids (deck).
- `deck.csv` may contain basic energy more than 4×; all other cards max 4×.
- Playground pool: 1,431 cards, 1,755 attacks. Old competition lists (1,267
  cards) are still legal.
