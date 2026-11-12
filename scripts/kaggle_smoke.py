"""Smoke-test a submission tarball inside the real Kaggle `cabt` environment.

The direct ctypes harness is fast, but Kaggle wraps it with BO3, statuses and
timeouts. This script extracts the tarball, loads `main.py`, and runs
`make("cabt")` with `bo=1` for a few games against a local opponent.

Usage:
  python scripts/kaggle_smoke.py submissions/heuristic_v1.tar.gz --games 3 \
      --opponent agents/greedy
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402


def _load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--opponent", default="agents/greedy")
    args = ap.parse_args()

    from kaggle_environments import make

    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(args.archive) as tf:
            names = tf.getnames()
            assert "main.py" in names and "deck.csv" in names, names
            tf.extractall(td)
        sub = _load(Path(td) / "main.py", "submission_main")
        my_deck = decklib.load_deck(Path(td) / "deck.csv")

        opp_dir = ROOT / args.opponent
        opp = _load(opp_dir / "main.py", "opp_main")
        opp_deck = decklib.load_deck(opp_dir / "deck.csv")

        results = []
        for i in range(args.games):
            env = make("cabt", configuration={"bo": 1})
            agents = [sub.agent, opp.agent] if i % 2 == 0 else [opp.agent, sub.agent]
            env.run(agents)
            r = [env.steps[-1][0].reward, env.steps[-1][1].reward]
            statuses = [env.steps[-1][0].status, env.steps[-1][1].status]
            me_reward = r[0] if i % 2 == 0 else r[1]
            results.append(
                {
                    "game": i,
                    "seat": 0 if i % 2 == 0 else 1,
                    "rewards": r,
                    "statuses": statuses,
                    "steps": len(env.steps),
                    "win": me_reward == 1,
                }
            )
        wins = sum(x["win"] for x in results)
        print(json.dumps({"archive": args.archive, "games": args.games, "wins": wins, "results": results}, indent=2))
        bad = [x for x in results if any(s not in ("DONE",) for s in x["statuses"])]
        if bad:
            print("WARNING: non-DONE statuses:", json.dumps(bad, indent=2), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
