# Official `cg` SDK — not included

The competition's `cg` SDK and the `ptcgProgram` engine are
**competition-use-only** (see the license file shipped with the competition
Data):

- use them only to build and test competition entries, while the competition is
  running;
- do **not** redistribute them, post them publicly, or use them outside the
  competition;
- delete local copies when the competition ends.

Therefore this public repository does **not** ship `vendor/cg/`. To run the
search arm locally, download the competition Data page and copy the official
SDK here:

```bash
# Competition Data -> sample_submission/.../cg/
cp -r /path/to/comp_data/sample_submission/*/cg vendor/cg
```

`scripts/probe_search.py`, `agents/search_v1` and the local search overlay
import `cg.api` from this directory. `docs/SEARCH_API.md` documents the recovered
ABI for reference; it is not a redistribution of the engine.

The public PPO v3 bundle used for the ladder baseline is also **not** committed;
`scripts/fetch_public_v3.py` downloads the public notebook output and applies the
deck, and the bundle's `cg/` directory is likewise not redistributed here.
