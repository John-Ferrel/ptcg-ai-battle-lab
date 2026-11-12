# Search API — recovered binding (`cg.api`)

## Confirmed against the official SDK (2026-11-12)

The public PPO v3 notebook output ships the competition's official `cg/api.py`.
Its `search_begin` uses exactly the prototypes recovered here:

```python
agent_ptr = lib.AgentStart()
lib.SearchBegin(agent_ptr, sbi.encode("ascii"), len(sbi), ...)
lib.SearchStep(agent_ptr, search_id, picks, len(picks))
```

So the binding is no longer a reverse-engineering guess: it matches the official
wrapper. Our `vendor/cg/api.py` is kept because it is our own code and works with
the pip-installed engine; the official file is competition data and is not
committed.

Status: **works**.  The forward-search symbols exported by the `cabt` engine
shipped with `kaggle-environments==1.33.3` are bound in `vendor/cg/api.py`.
The binding was recovered from the compiled library and verified with
contained child-process experiments.

Environment used for all measurements:

| Item | Value |
|---|---|
| OS / arch | Linux x86-64 (`6.8.0-106-generic`) |
| CPU | AMD EPYC-Milan, 6 vCPUs (shared VM) |
| Python | 3.12.3 (`ptcg-ai-battle/.venv`) |
| Engine | `kaggle-environments==1.33.3`, `libcg.so` (1,458,504 bytes) |
| Symbols | `AgentStart`, `SearchBegin`, `SearchStep`, `SearchEnd`, `SearchRelease`, `AllCard`, `AllAttack` |

For comparison: the docs are at
<https://matsuoinstitute.github.io/cabt/api.html>.  The wheel ships
`cg/sim.py`, `cg/game.py`, `libcg.so`, `libcg.dylib`, `libcg-arm64.so` and
`cg.dll`, but **not** `cg/api.py`.

---

## 1. Recovered native signatures

The official Python API has eight logical arguments.  The C entry points take
the engine object plus the encoded state (or the node id) explicitly.  The
recovered x86-64 prototypes are:

```c
void *AgentStart(void);

char *SearchBegin(void *agent,                 /* rdi — object from AgentStart */
                  const char *input,           /* rsi — search_begin_input  */
                  int input_len,               /* edx — strlen(input)       */
                  const int *your_deck,        /* rcx                       */
                  const int *your_prize,       /* r8                        */
                  const int *opponent_deck,    /* r9                        */
                  const int *opponent_prize,   /* stack +8  (7th arg)       */
                  const int *opponent_hand,    /* stack +16 (8th arg)       */
                  const int *opponent_active,  /* stack +24 (9th arg)       */
                  int manual_coin);            /* stack +32 (10th arg)      */

char *SearchStep(void *agent, int search_id, const int *picks, int pick_count);

void SearchEnd(void *agent);
void SearchRelease(void *agent, int search_id);
```

`SearchBegin` / `SearchStep` return a **JSON `ApiResult`** string, not a C
struct:

```json
{"state": {"observation": {...}, "searchId": 0}, "error": 0}
```

On failure the `state` is `null` (e.g. `{"state":null,"error":30}`).

### Why the indices are what they are

`objdump -d` of this build:

- `AgentStart` is a one-instruction tail jump to `ApiAgentStart` (`0x13760`).
  `ApiAgentStart` allocates a 0x70c8-byte zeroed object, seeds its RNG from
  `std::random_device`, and sets the mode word:
  `movl $0x2,0x6f98(%r12)` (`0x139c1`).  `BattleStart` sets the same word to
  `1` (`0x601a0`).  This is the object mode: **1 = battle, 2 = search**.
- `SearchBegin` (`0xd680`) checks `cmpl $0x2,0x6f98(%rdi)` and returns
  `error 30` if the object is not in search mode.  That is exactly what
  happens if you call it with the pointer returned by `BattleStart` instead
  of `AgentStart`.  This was the first failed experiment:
  `{"state":null,"error":30}`.
- `SearchBegin` saves `%rdi` as the engine object, reads the 7th–10th stack
  arguments at `0x130(%rsp)`, `0x138(%rsp)`, `0x140(%rsp)`, `0x148(%rsp)`
  after its 6-register/`0xf8`-byte prologue (296 bytes, so those offsets map
  to stack arguments +8, +16, +24, +32).  The first six integer arguments are
  therefore the object, input pointer, input length, and the first three card
  lists.
- It copies the input into the object's `std::string` at `0x7060`, calls
  `BinaryReader::fromBase64` (`0x1f840`), then `State::deserialize`
  (`0x20e50`).  So the second argument is the ASCII `search_begin_input`
  blob and the third is its length.
- Six `CopyIdPtr(int *src, std::vector<int> &dst, int count, int &error)`
  calls (`0xe182`, `0xe1c5`, `0xe1f8`, `0xe22d`, `0xe651`, `0xe6cd`) load the
  arrays into `SearchStartConfig` vector slots `0x58`, `0x70`, `0x88`, `0xa0`,
  `0xb8`, `0xd0`.  The `count` is read from the engine's own state
  (`player[...].deckCount`, `prize` size, `handCount`, active count), not from
  the caller.  Then `Search::start(config, state)` is called at `0x4ffc0`.
- `SearchStep` (`0xc770`) uses `%rsi` as the search id (`mov %rsi,%r13`),
  `%rdx` as the pick pointer, and `%ecx` as the pick count (it loops
  `lea 0x4(%rdx,%rax,4),%r14`).  It looks the id up in the vector at
  `0x6fa8`, clones the node with `Search::alloc` (`0x22b90`), applies
  `State::checkPlayerSelect` (`0x3baa0`) and `State::step` (`0x122f0`), and
  returns the new id (vector size − 1) in the JSON.
- `SearchEnd` (`0x7790`) clears the search-node vectors and returns nodes to
  the pool.  `SearchRelease` (`0x83c0`) checks the id against the vector at
  `0x6fa8` and pushes that node onto the free list at `0x6fc0`.
- `AllCard` (`0x9aa0`) and `AllAttack` (`0x9ae0`) return JSON strings.  They
  are only bound to reconstruct `all_card_data()` / `all_attack()`.

### Important engine-object rule

`AgentStart()` is **required before the first search call**.  It is a separate
engine object from `BattleStart()`, so a process can run one battle and one
search object simultaneously.  `search_begin` in `vendor/cg/api.py` allocates
the search object lazily and reuses it.

---

## 2. How the Python wrapper maps the documented arguments

```python
search_begin(agent_observation,
             your_deck, your_prize,
             opponent_deck, opponent_prize,
             opponent_hand, opponent_active,
             manual_coin=False) -> SearchState
```

`agent_observation` may be a raw observation dict or the `Observation`
returned by `to_observation_class`.  The wrapper reads
`observation.search_begin_input`, encodes it as ASCII, and passes:

| Python argument | C argument | Array length used by the engine |
|---|---|---|
| `agent_observation` | `input`, `input_len` | `len(search_begin_input)` |
| `your_deck` | 4th (`rcx`) | your `deckCount` (ignored if `select.deck != None`) |
| `your_prize` | 5th (`r8`) | number of your prize cards |
| `opponent_deck` | 6th (`r9`) | opponent `deckCount` |
| `opponent_prize` | 7th (stack +8) | number of opponent prize cards |
| `opponent_hand` | 8th (stack +16) | opponent `handCount` |
| `opponent_active` | 9th (stack +24) | 1 only when the opponent's Active is face-down |
| `manual_coin` | 10th (stack +32) | 0 / 1 |

The array lengths are read from the engine's own state, so the wrapper does
**not** pass lengths.  It pads every array to at least 80 `int`s (with a valid
card id / basic Pokémon) before the call.  The engine only reads its own
count.  This is a deliberate safety net: a caller that supplies a short belief
cannot make the native code read past a ctypes buffer and segfault.  Callers
that pass the documented exact lengths get exactly the documented behavior.

`search_step(search_id, pick)` accepts a list/tuple of option indices (or an
int) and calls `SearchStep(agent, id, picks, len(picks))`.  Empty lists are
legal when `select.minCount == 0`.

Errors are surfaced as `RuntimeError` with the native code:

| error | Meaning |
|---|---|
| 1 | invalid search id |
| 2 | invalid selection |
| 3 | search state already finished |
| 5 | illegal selection for this node (`checkPlayerSelect` failed) |
| 30 | search API not initialised (object not from `AgentStart`) |

`search_end()` calls `SearchEnd(agent)` and recycles node memory;
`search_release(id)` calls `SearchRelease(agent, id)` for one node.

---

## 3. Verification

All experiments ran in child processes (`/tmp/cg_probe/`), so a wrong guess
could only kill that process.  The final wrapper is exercised by
`scripts/probe_search.py`.

### Q1 — `search_begin` accepts a belief

A real battle was started with two 60-card decks, advanced to a mid-game MAIN
decision, then converted with `to_observation_class`.  The hidden zones were
filled from a coherent belief built from visible cards plus the 60-card lists
(no engine truth was read).  `search_begin` returned:

```
searchId = 0
observation.select.type = MAIN (0), context = MAIN (0), 5–9 options
observation.current.turn = 5
```

`search_begin` takes about **0.33–0.44 ms** after the first call (the first
call also builds the card-metadata cache used for the safe padding and costs
~20 ms).  Repeating `search_begin` without `search_end()` appends a new root;
after `search_end()` the next root id is 0 again.

A second check used a state where `obs.select.deck` is non-null (a deck-search
effect: context 7, options `type=3, area=1, index=k`).  `search_begin` succeeded
even when called with an empty `your_deck`, confirming the documented
"ignored if `select.deck != None`" behavior.

### Q2 — a random rollout reaches terminal

From the Q1 root, a legal random pick at every node reached a terminal state:

| run | steps | terminal result |
|---|---:|---|
| default vs default | 63 | 1 |
| meta_top vs default | 204 | 1 |
| dragapult vs default | 132 | 1 |
| lucario vs default | 72 | 1 |

Random rollouts use the documented `minCount`/`maxCount` bounds and distinct
option indices; they never triggered an illegal-selection error.

### Q3 — branching is a real tree

From the same root (`searchId=0`), two different legal picks produced:

```
root -> pick 0 : searchId=1, select type=1 (CARD), context=8 (DISCARD)
root -> pick 1 : searchId=2, select type=0 (MAIN), context=0 (MAIN)
```

The ids are distinct and the observations differ, so the second call is not a
linear continuation of the first.  Continuing each branch for 12 more random
steps produced divergence at step 1–2 in every measured run.

One caveat, confirmed experimentally: re-playing the same pick from the same
root is **not byte-identical** when that pick draws/search cards.  The engine's
RNG advances on each `SearchStep`, so the *downstream draw order* can differ
even though the root node itself is unchanged.  The tree shape is real; exact
replay of a stochastic branch is not.  This is consistent with the engine's
documented lack of seed control.

### Q4 — throughput

Measured with `scripts/probe_search.py` (including JSON parsing,
`to_observation_class`, legal-pick sampling and `search_release` per node):

| matchup | rollouts | mean steps/rollout | rollouts/s | steps/s |
|---|---:|---:|---:|---:|
| default vs default (seed 0) | 50 | 24.8 | 186.5 | 4,618 |
| meta_top vs default (seed 1) | 100 | 116.7 | 38.7 | 4,517 |
| dragapult vs default (seed 1) | 100 | 131.9 | 25.6 | 3,369 |
| lucario vs default (seed 1) | 100 | 72.5 | 55.5 | 4,025 |

Interpretation: the per-node cost is ~0.18–0.30 ms, i.e. **3.4k–5.5k search
nodes/s** on this shared 6-vCPU VM.  Rollouts/s depends heavily on how long the
sampled position lasts: additional default-deck runs across seeds produced
32–506 rollouts/s as the mean rollout length varied from 135 to 11 steps, while
steps/s stayed in the same 3.4k–5.5k band.  Report steps/s when comparing
machines.  For a 600 s overage budget, 3–5k nodes/s is enough for shallow
deterministic search (hundreds of nodes per decision at ~50–100 ms), not for
deep MCTS.

`search_release` is cheap: releasing 123 nodes took 0.25 ms total.  Releasing
each rollout's nodes keeps memory bounded; `search_end()` resets the tree and
the next root id returns to 0.

### Smoke test of a public agent

Downloaded unchanged:

- `https://raw.githubusercontent.com/tuannm3812/kaggle-pokemon-tcg-ai-battle/main/agent/main.py`
- `https://raw.githubusercontent.com/tuannm3812/kaggle-pokemon-tcg-ai-battle/main/agent/deck.csv`

into `/tmp/search_agent/`, and ran it through
`scripts/search_smoke_public.py` (which puts `vendor/` on `sys.path` before
importing the downloaded module) against `agents/greedy`:

```
direct import + PYTHONPATH=vendor, 40 games, seat-swapped by arena.py
public agent wins 35 / 40 = 87.5%  (Wilson 95% CI 73.9%–94.5%)
illegal: 0   errors: 0   crashes: 0
avg decision: 0.159 ms   max decision: 5.2 ms

via scripts/search_smoke_public.py, 20 games
public agent wins 18 / 20 = 90.0%
illegal: 0   errors: 0   crashes: 0
```

Earlier 20-game runs scored 16/20 and 17/20; 20 games is noisy (±~10
points), so the 40-game number is the one to quote.

Note: that public agent imports `OptionType`, `SelectContext`, `SelectType` and
`to_observation_class` but **does not call `search_begin`**.  The smoke test
therefore validates the SDK shim, enums and observation conversion under the
real Kaggle contract; the search binding itself is validated by the Q1–Q4
probe above.

---

## 4. Limits / things that will bite

1. **Process-global engine.**  One `BattleStart` and one search object per
   process.  Do not run two battles or two threads searching at once.
   `vendor/cg/api.py` serialises search calls with an `RLock`, but the battle
   API and search API still share the same library.
2. **`AgentStart()` is mandatory.**  Calling `SearchBegin` on a `BattleStart`
   pointer returns error 30.  The wrapper handles this lazily.
3. **Belief lengths are enforced by the engine, not by the caller.**  The
   engine reads `deckCount` / prize count / `handCount` integers from each
   pointer.  The wrapper pads to 80 ints to avoid OOB; do not rely on padding
   for correctness, because the extra cards are placeholders.
4. **`select.deck != None` means your deck is already known.**  The engine
   ignores `your_deck` in that case.  This occurs on deck-search effects and is
   common: context 7 (`EVOLVE`) decisions are mostly deck searches, and their
   options are `{"type": 3, "area": 1, "index": k}` where
   `obs.select.deck[k].id` is the card.  Resolve those through
   `select.deck`, not through your hand.
5. **`opponent_active` is only read when the opponent's Active is face-down.**
   When `obs.current.players[1-yours].active[0] is None`, pass one basic
   Pokémon card id; otherwise an empty list is fine.
6. **No seed control.**  `AgentStart` seeds its RNG from
   `std::random_device`.  Re-playing a stochastic branch is not reproducible.
7. **Terminal nodes.**  Stepping a node whose `current.result >= 0` (or whose
   result is otherwise finished) returns error 3.  Stop when the returned
   observation is terminal.
8. **Illegal picks are fatal to the call, not to the process.**  Error 5 is
   raised as `RuntimeError`; in an agent, clamp picks to
   `[minCount, maxCount]` and to distinct option indices.
9. **Root ids and release.**  Ids are indices into the engine's node vector,
   not pointers.  `search_end()` invalidates all ids; `search_release(id)`
   only frees that node (children are separate nodes).  Call `search_end()`
   at the end of each decision to keep memory bounded.
10. **Memory.**  A search node is ~0x5880 bytes.  A 150-step rollout allocates
    ~1.3 MB; release per rollout or call `search_end()` frequently.
11. **Platform coverage.**  Only the x86-64 Linux `libcg.so` was executed.
    `libcg-arm64.so`, `libcg.dylib` and `cg.dll` export the same names
    (`AgentStart`, `SearchBegin`, `SearchStep`, `SearchEnd`, `SearchRelease`,
    `AllCard`, `AllAttack`), and the C prototypes should be ABI-identical, but
    they were not run here.
12. **`manual_coin=True`** was verified to return a valid state, but its
    strategic semantics (which coin side is chosen, and how the engine
    consumes the choice) were not tested.

---

## 5. Residual uncertainty

- The official `cg/api.py` source is not distributed in the wheel and no
  public copy was found.  The binding matches the public docs and the
  disassembly, but error-to-exception mapping (`RuntimeError` vs an
  `ApiResult` return) is our design choice; an agent that expects
  `search_begin` to return an `ApiResult` with `error != 0` instead of raising
  would need a thin adapter.
- The exact set of native error codes beyond 1/2/3/5/30 is unknown; unknown
  codes are reported verbatim in the exception text.
- The mapping of the six card arrays was confirmed empirically by passing
  distinct lists and observing the resulting prize/hand/deck contents.  The
  only unverified subtlety is the exact behavior when a caller passes a list
  longer than the engine's own count: the engine reads the first `count`
  entries, which is what the wrapper assumes.
- `AgentStart` allocates an engine object that is never explicitly destroyed.
  It is a process-lifetime singleton, like the battle object; no `AgentFinish`
  symbol is exported.  This is harmless for an agent process but means a
  long-lived process that repeatedly calls `AgentStart` would leak.
- Search node memory is recycled by `SearchEnd`/`SearchRelease`; the exact
  high-water mark under thousands of live nodes was not measured.
- Throughput numbers are for this shared VM and include Python conversion.
  A C++/Cython client or a raw-JSON loop would be faster.

---

## 6. Using the shim

```bash
cd ptcg-ai-battle
PYTHONPATH=vendor .venv/bin/python scripts/probe_search.py \
    --deck decks/default.csv --opp-deck decks/default.csv --rollouts 100
```

From an agent:

```python
from cg.api import search_begin, search_step, search_end, to_observation_class

obs = to_observation_class(obs_dict)
root = search_begin(obs, my_deck, my_prize,
                    opp_deck, opp_prize, opp_hand, opp_active)
node = search_step(root.searchId, [0])
# ... evaluate / roll out ...
search_end()
```

`cg.sim` and `cg.game` are re-exports of the installed engine modules, so
`from cg.game import battle_start, battle_select, battle_finish` works
unchanged.
