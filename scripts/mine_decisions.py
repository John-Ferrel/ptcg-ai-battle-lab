"""Mine decision statistics from episode replays.

Examples:
  python scripts/mine_decisions.py <dir> --limit 50          # quick stats
  python scripts/mine_decisions.py <dir> --dump results/dec # compact JSONL
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import replay  # noqa: E402


def mine_file(path: str) -> dict:
    ep = replay.load_episode(path)
    ds = replay.decisions(ep)
    ctx = collections.Counter()
    nopt = []
    for d in ds:
        sel = d["obs"]["select"]
        ctx[(sel.get("context"), sel.get("type"))] += 1
        nopt.append(len(sel.get("option") or []))
    return {"n": len(ds), "ctx": dict(ctx), "opts": nopt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--dump", default="")
    args = ap.parse_args()

    files = sorted(Path(args.episodes).glob("*.json"))
    if args.limit:
        files = files[: args.limit]
    print(f"files: {len(files)}")

    ctx = collections.Counter()
    total = 0
    opts = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(mine_file, [str(f) for f in files], chunksize=8):
            total += r["n"]
            ctx.update(r["ctx"])
            opts.extend(r["opts"])

    print(f"decisions: {total}")
    for k, v in ctx.most_common(20):
        print(f"  ctx={k[0]:3d} type={k[1]:2d}  {v:7d}  {v/max(total,1):.1%}")
    opts.sort()
    if opts:
        print(f"options/decision: mean={sum(opts)/len(opts):.2f} p50={opts[len(opts)//2]} p95={opts[int(len(opts)*.95)]} max={opts[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
