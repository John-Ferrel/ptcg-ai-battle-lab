"""Offline comparison of BC vs rule-based agents on held-out replay decisions.

For every decision in the valid episodes (same filters as the extractor), we ask
each agent what it would play and compare its top-1 index with the human/agent
action recorded in the replay.  This is *agreement with the replay pilot*, not
a win rate.

Usage:
    .venv/bin/python scripts/bc_offline_compare.py --data data/bc \
        --agents agents/greedy agents/heuristic_v1
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "agents" / "bc_linear"))

from ptcg_ai import replay  # noqa: E402

import bc_features  # noqa: E402

CTX_NAMES = {0: "MAIN", 7: "EVOLVE"}


def load_agent(path: Path):
    p = path / "main.py" if path.is_dir() else path
    spec = importlib.util.spec_from_file_location(f"cmp_{p.parent.name}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def load_meta(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return {
        "c": {int(k): v for k, v in raw["c"].items()},
        "a": {int(k): v for k, v in raw["a"].items()},
    }


def bc_bundle():
    w = json.loads((ROOT / "agents" / "bc_linear" / "weights.json").read_text())
    weights = {str(k): float(v) for k, v in w["weights"]}
    meta = load_meta(ROOT / "agents" / "bc_linear" / "card_meta.json")

    def score(obs):
        feats = bc_features.build_features(obs, meta)
        return [sum(weights.get(k, 0.0) * v for k, v in d.items()) for d in feats]

    return score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "bc"))
    ap.add_argument("--agents", nargs="*", default=["agents/greedy"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    data_dir = Path(args.data)
    meta = json.loads((data_dir / "meta.json").read_text())
    ep_dir = Path(meta["episodes_dir"])
    bc_score = bc_bundle()

    agents = {}
    for a in args.agents:
        p = ROOT / a
        if not (p / "main.py").exists():
            print(f"[skip] {a}: no main.py")
            continue
        try:
            agents[p.name] = load_agent(p)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {a}: {exc}")
    print(f"agents: bc_linear + {sorted(agents)}")

    eps = meta["splits"]["valid"]
    if args.limit:
        eps = eps[: args.limit]
    names = ["bc_linear"] + list(agents)
    correct = {n: 0 for n in names}
    by_ctx = {n: defaultdict(lambda: [0, 0]) for n in names}
    agree = defaultdict(int)
    errors = {n: 0 for n in names}
    timing = {n: 0.0 for n in names}
    total = 0
    t0 = time.perf_counter()
    for eid in eps:
        path = ep_dir / f"{eid}.json"
        if not path.exists():
            continue
        ep = replay.load_episode(path)
        steps = ep.get("steps") or []
        for d in replay.decisions(ep):
            sel = d["obs"].get("select")
            if not sel:
                continue
            if sel.get("maxCount") != 1 or (sel.get("minCount") or 0) > 1:
                continue
            if not 1 <= len(sel.get("option") or []) <= 40:
                continue
            act = d["action"]
            if len(act) != 1:
                continue
            chosen = int(act[0])
            if not 0 <= chosen < len(sel["option"]):
                continue
            ctx = int(sel.get("context") or 0)
            total += 1
            preds = {}
            t = time.perf_counter()
            try:
                sc = bc_score(d["obs"])
                preds["bc_linear"] = int(max(range(len(sc)), key=lambda i: sc[i]))
            except Exception:  # noqa: BLE001
                errors["bc_linear"] += 1
                preds["bc_linear"] = -1
            timing["bc_linear"] += time.perf_counter() - t
            for name, fn in agents.items():
                t = time.perf_counter()
                try:
                    out = fn(d["obs"])
                    preds[name] = int(out[0]) if out else -1
                except Exception:  # noqa: BLE001
                    errors[name] += 1
                    preds[name] = -1
                timing[name] += time.perf_counter() - t
            for name, pred in preds.items():
                ok = pred == chosen
                correct[name] += int(ok)
                c = CTX_NAMES.get(ctx, "others")
                by_ctx[name][c][0] += int(ok)
                by_ctx[name][c][1] += 1
            for a in names:
                for b in names:
                    if a < b:
                        agree[(a, b)] += int(preds[a] == preds[b])

    print(f"\ndecisions: {total} over {len(eps)} held-out episodes "
          f"({time.perf_counter() - t0:.0f}s)")
    print(f"{'policy':14s} {'top1':>7s} {'MAIN':>7s} {'EVOLVE':>7s} {'others':>7s} "
          f"{'ms/dec':>7s} {'errors':>6s}")
    for n in names:
        row = by_ctx[n]
        def rate(k):
            a, b = row.get(k, [0, 0])
            return a / b if b else 0.0
        print(
            f"{n:14s} {correct[n]/max(total,1):7.3f} {rate('MAIN'):7.3f} "
            f"{rate('EVOLVE'):7.3f} {rate('others'):7.3f} "
            f"{1000*timing[n]/max(total,1):7.3f} {errors[n]:6d}"
        )
    for (a, b), k in sorted(agree.items()):
        print(f"agreement {a} vs {b}: {k/max(total,1):.3f}")

    out = {
        "episodes": len(eps),
        "decisions": total,
        "top1": {n: correct[n] / max(total, 1) for n in names},
        "by_context": {
            n: {k: (v[0] / v[1] if v[1] else 0.0) for k, v in by_ctx[n].items()}
            for n in names
        },
        "error_counts": errors,
        "ms_per_decision": {n: 1000 * timing[n] / max(total, 1) for n in names},
        "agreement": {f"{a}|{b}": k / max(total, 1) for (a, b), k in agree.items()},
    }
    (data_dir / "offline_compare.json").write_text(json.dumps(out, indent=2))
    print("wrote", data_dir / "offline_compare.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
