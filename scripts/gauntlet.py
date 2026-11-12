"""Evaluate one agent against a weighted opponent pool (a local gauntlet).

The pool mirrors the real meta composition we measured from 1,694 replays, but
uses local pilots (we do not have the original agents' code).

Config example (`configs/gauntlet.json`):
{
  "opponents": [
    {"agent": "agents/greedy", "deck": "decks/meta/03_Dragapult_ex.csv", "weight": 30},
    {"agent": "agents/greedy", "deck": "decks/meta/01_Mega_Excadrill_ex.csv", "weight": 40}
  ]
}

Usage:
  python scripts/gauntlet.py --agent agents/heuristic_v1 --deck decks/meta/03_Dragapult_ex.csv \
      --config configs/gauntlet.json --games 400 --workers 4
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402
from ptcg_ai.harness import play_game  # noqa: E402

_CACHE: dict[str, object] = {}


def load_agent(path: str):
    if path in _CACHE:
        return _CACHE[path]
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    spec = importlib.util.spec_from_file_location(f"g_{abs(hash(str(p)))}", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    _CACHE[path] = mod.agent
    return mod.agent


def _one(job: dict) -> dict:
    me = load_agent(job["agent"])
    opp = load_agent(job["opp_agent"])
    md = decklib.load_deck(job["deck"])
    od = decklib.load_deck(job["opp_deck"])
    if job["i_am_p0"]:
        r = play_game(me, opp, md, od, names=("me", job["opp_name"]))
        won = r.winner == 0
    else:
        r = play_game(opp, me, od, md, names=(job["opp_name"], "me"))
        won = r.winner == 1
    return {
        "won": int(won),
        "draw": int(r.winner == 2),
        "opponent": job["opp_name"],
        "illegal": r.illegal,
        "error": r.error,
        "turns": r.turns,
        "think_ms": r.think_ms,
        "decisions": r.decisions,
        "max_ms": r.max_decision_ms,
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
    ap.add_argument("--agent", required=True)
    ap.add_argument("--deck", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    opps = cfg["opponents"]
    rng = random.Random(cfg.get("seed", 7))
    jobs = []
    # deterministic weighted allocation (largest remainder)
    weights = [o.get("weight", 1) for o in opps]
    total_w = sum(weights)
    quotas = [args.games * w / total_w for w in weights]
    counts = [int(q) for q in quotas]
    for i in sorted(range(len(opps)), key=lambda i: -(quotas[i] - counts[i])):
        if sum(counts) >= args.games:
            break
        counts[i] += 1
    gi = 0
    for o, c in zip(opps, counts):
        for _ in range(c):
            jobs.append({
                "i_am_p0": gi % 2 == 0,
                "agent": args.agent,
                "deck": args.deck,
                "opp_agent": o["agent"],
                "opp_deck": o["deck"],
                "opp_name": o.get("name", Path(o["agent"]).name),
                "game": gi,
            })
            gi += 1
    rng.shuffle(jobs)

    t0 = time.perf_counter()
    rows = []
    if args.workers <= 1:
        rows = [_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(_one, jobs, chunksize=1))
    wall = time.perf_counter() - t0

    wins = sum(r["won"] for r in rows)
    draws = sum(r["draw"] for r in rows)
    n = len(rows)
    lo, hi = wilson(wins, n)
    per: dict[str, list[int]] = {}
    for r in rows:
        per.setdefault(r["opponent"], [0, 0])
        per[r["opponent"]][0] += r["won"]
        per[r["opponent"]][1] += 1
    summary = {
        "agent": args.agent,
        "deck": args.deck,
        "games": n,
        "wins": wins,
        "losses": n - wins - draws,
        "draws": draws,
        "winrate": wins / n,
        "ci95": [round(lo, 4), round(hi, 4)],
        "illegal": sum(r["illegal"] for r in rows),
        "errors": sum(1 for r in rows if r["error"]),
        "avg_turns": round(statistics.mean(r["turns"] for r in rows), 1),
        "avg_decision_ms": round(statistics.mean(r["think_ms"] / max(r["decisions"], 1) for r in rows), 3),
        "p95_decision_ms": round(sorted(r["max_ms"] for r in rows)[int(n * 0.95)], 1) if n else 0,
        "wall_s": round(wall, 1),
        "by_opponent": {k: {"wins": v[0], "games": v[1], "winrate": v[0] / v[1]} for k, v in per.items()},
    }
    print(json.dumps(summary, indent=2))
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
