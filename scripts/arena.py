"""Run a batch of local games between two agents and report win rates.

Example:
    .venv/bin/python scripts/arena.py \
        --agent-a agents/heuristic_v1 --deck-a decks/dipplin.csv \
        --agent-b agents/random_legal --deck-b decks/dipplin.csv \
        --games 200 --workers 8 --out results/h1_vs_random.jsonl
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402
from ptcg_ai.harness import play_game  # noqa: E402

_AGENT_CACHE: dict[str, object] = {}


def load_agent(path: str):
    path = str(path)
    if path in _AGENT_CACHE:
        return _AGENT_CACHE[path]
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    spec = importlib.util.spec_from_file_location(f"agent_{abs(hash(str(p.resolve())))}", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if fn is None:
        raise SystemExit(f"{p} has no agent(obs) function")
    _AGENT_CACHE[path] = fn
    return fn


def _run_one(job: dict) -> dict:
    a_fn = load_agent(job["agent_a"])
    b_fn = load_agent(job["agent_b"])
    deck_a = decklib.load_deck(job["deck_a"])
    deck_b = decklib.load_deck(job["deck_b"])
    a_is_p0 = job["a_is_p0"]
    if a_is_p0:
        r = play_game(a_fn, b_fn, deck_a, deck_b, names=(job["name_a"], job["name_b"]))
    else:
        r = play_game(b_fn, a_fn, deck_b, deck_a, names=(job["name_b"], job["name_a"]))
    a_won = (r.winner == 0) if a_is_p0 else (r.winner == 1)
    row = r.as_dict()
    row.update(
        {
            "game": job["game"],
            "a_is_p0": a_is_p0,
            "a_won": int(a_won),
            "draw": int(r.winner == 2),
            "name_a": job["name_a"],
            "name_b": job["name_b"],
        }
    )
    return row


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
    ap.add_argument("--name-a", default="A")
    ap.add_argument("--name-b", default="B")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--out", default="")
    ap.add_argument("--start", type=int, default=0, help="game index offset (for sharding)")
    args = ap.parse_args()

    for d in (args.deck_a, args.deck_b):
        problems = decklib.validate_deck(decklib.load_deck(d))
        if problems:
            raise SystemExit(f"{d}: " + "; ".join(problems))

    jobs = [
        {
            "game": args.start + i,
            "a_is_p0": (args.start + i) % 2 == 0,
            "agent_a": args.agent_a,
            "agent_b": args.agent_b,
            "deck_a": args.deck_a,
            "deck_b": args.deck_b,
            "name_a": args.name_a,
            "name_b": args.name_b,
        }
        for i in range(args.games)
    ]

    t0 = time.perf_counter()
    rows: list[dict] = []
    if args.workers <= 1:
        for j in jobs:
            rows.append(_run_one(j))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_run_one, jobs, chunksize=1):
                rows.append(r)
    wall = time.perf_counter() - t0

    wins = sum(r["a_won"] for r in rows)
    draws = sum(r["draw"] for r in rows)
    n = len(rows)
    lo, hi = wilson(wins, n)
    illegal = sum(1 for r in rows if r["illegal"])
    errors = [r["error"] for r in rows if r["error"]]
    turns = [r["turns"] for r in rows]
    summary = {
        "agent_a": args.name_a,
        "agent_b": args.name_b,
        "deck_a": args.deck_a,
        "deck_b": args.deck_b,
        "games": n,
        "a_wins": wins,
        "b_wins": n - wins - draws,
        "draws": draws,
        "a_winrate": wins / n if n else 0.0,
        "ci95": [round(lo, 4), round(hi, 4)],
        "illegal": illegal,
        "errors": len(errors),
        "error_sample": errors[:3],
        "avg_turns": round(statistics.mean(turns), 1) if turns else 0,
        "avg_decision_ms": round(statistics.mean([r["think_ms"] / max(r["decisions"], 1) for r in rows]), 3) if rows else 0,
        "max_decision_ms": round(max((r["max_decision_ms"] for r in rows), default=0), 1),
        "wall_s": round(wall, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    print(json.dumps(summary, indent=2))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        summary_path = out.with_suffix(".summary.json")
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"wrote {out} and {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
