"""Match-level (BO3) arena using the real Kaggle `cabt` environment.

`scripts/arena.py` plays BO1 through the fast ctypes harness. The ladder plays
BO3, so this script runs full matches with `make("cabt")` (default `bo=3`) and
reports the match win rate. It is slower; use it for the final validation.

Usage:
  PYTHONPATH=vendor .venv/bin/python scripts/bo3_arena.py \
      --agent-a agents/search_v1 --deck-a decks/meta/03_Dragapult_ex.csv \
      --agent-b agents/heuristic_v1 --deck-b decks/meta/03_Dragapult_ex.csv \
      --matches 30 --workers 2
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))

from ptcg_ai import deck as decklib  # noqa: E402


def _load(path: str):
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    spec = importlib.util.spec_from_file_location(f"bo3_{abs(hash(str(p)))}", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.agent


def _match(job: dict) -> dict:
    from kaggle_environments import make

    a = _load(job["agent_a"])
    b = _load(job["agent_b"])
    env = make("cabt")  # default bo=3
    seats = [a, b] if job["a_p0"] else [b, a]
    env.run(seats)
    last = env.steps[-1]
    rewards = [last[0].reward, last[1].reward]
    statuses = [last[0].status, last[1].status]
    a_reward = rewards[0] if job["a_p0"] else rewards[1]
    return {
        "match": job["match"],
        "a_p0": job["a_p0"],
        "rewards": rewards,
        "statuses": statuses,
        "a_win": a_reward == 1,
        "draw": a_reward == 0,
        "steps": len(env.steps),
    }


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-a", required=True)
    ap.add_argument("--deck-a", required=True)
    ap.add_argument("--agent-b", required=True)
    ap.add_argument("--deck-b", required=True)
    ap.add_argument("--matches", type=int, default=30)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    for d in (args.deck_a, args.deck_b):
        problems = decklib.validate_deck(decklib.load_deck(d))
        if problems:
            raise SystemExit(f"{d}: " + "; ".join(problems))

    jobs = [
        {"match": i, "a_p0": i % 2 == 0, "agent_a": args.agent_a, "agent_b": args.agent_b}
        for i in range(args.matches)
    ]
    t0 = time.perf_counter()
    if args.workers <= 1:
        rows = [_match(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(_match, jobs, chunksize=1))
    wins = sum(r["a_win"] for r in rows)
    draws = sum(r["draw"] for r in rows)
    n = len(rows)
    lo, hi = wilson(wins, n)
    summary = {
        "agent_a": args.agent_a,
        "agent_b": args.agent_b,
        "matches": n,
        "a_wins": wins,
        "b_wins": n - wins - draws,
        "draws": draws,
        "a_match_winrate": wins / n,
        "ci95": [round(lo, 4), round(hi, 4)],
        "bad_statuses": sum(1 for r in rows if any(s != "DONE" for s in r["statuses"])),
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    print(json.dumps(summary, indent=2))
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"summary": summary, "matches": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
