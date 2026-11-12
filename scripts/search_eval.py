#!/usr/bin/env python
"""Run a seat-swapped search_v1 evaluation and aggregate telemetry.

Example::

    PYTHONPATH=vendor .venv/bin/python scripts/search_eval.py \
        --agent-b agents/search_v1/base_policy.py \
        --name-b heuristic_v1_same_deck \
        --deck agents/search_v1/deck.csv --games 200 --workers 2

The script runs ``scripts/arena.py``, then reads the per-worker telemetry
written by ``agents/search_v1/main.py`` (``SEARCH_V1_TELEMETRY_DIR``) and
reports p50/p95/max decision latency, the search coverage and override rate.

Use ``--deck`` with a different deck file to test a second list; the script
temporarily installs it as ``agents/search_v1/deck.csv`` so the agent's
internal deck belief matches the harness deck, then restores the original.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DECK = ROOT / "agents" / "search_v1" / "deck.csv"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
    return ordered[index]


def aggregate(telemetry_dir: str) -> dict:
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(telemetry_dir, "*.jsonl"))):
        with open(path) as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    if not rows:
        return {"decisions": 0}

    ms = [float(row["ms"]) for row in rows]
    searched = [row for row in rows if row.get("searched")]
    searched_ms = [float(row["ms"]) for row in searched]
    errors = [row for row in rows if row.get("error")]
    searched_errors = [row for row in searched if row.get("error")]
    overrides = sum(1 for row in searched if row.get("override"))
    fallbacks = sum(1 for row in rows if row.get("fallback"))

    return {
        "decisions": len(rows),
        "searched": len(searched),
        "searched_rate": round(len(searched) / len(rows), 4),
        "fallback": fallbacks,
        "fallback_rate": round(fallbacks / len(rows), 4),
        "errors": len(errors),
        "error_samples": [row.get("error") for row in errors[:5]],
        "override_count": overrides,
        "override_rate": round(overrides / len(searched), 4) if searched else 0.0,
        "mean_candidates": round(statistics.mean(row["candidates"] for row in searched), 2) if searched else 0,
        "mean_rollouts": round(statistics.mean(row["rollouts"] for row in searched), 2) if searched else 0,
        "mean_beliefs": round(statistics.mean(row["beliefs"] for row in searched), 2) if searched else 0,
        "ms": {
            "mean": round(statistics.mean(ms), 2),
            "p50": round(percentile(ms, 0.50), 2),
            "p95": round(percentile(ms, 0.95), 2),
            "p99": round(percentile(ms, 0.99), 2),
            "max": round(max(ms), 2),
        },
        "searched_ms": {
            "mean": round(statistics.mean(searched_ms), 2) if searched_ms else 0,
            "p50": round(percentile(searched_ms, 0.50), 2),
            "p95": round(percentile(searched_ms, 0.95), 2),
            "p99": round(percentile(searched_ms, 0.99), 2),
            "max": round(max(searched_ms), 2) if searched_ms else 0,
        },
        "searched_errors": len(searched_errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-a", default="agents/search_v1")
    parser.add_argument("--agent-b", required=True)
    parser.add_argument("--name-a", default="search_v1")
    parser.add_argument("--name-b", default="opponent")
    parser.add_argument("--deck", default=str(AGENT_DECK))
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--mode", default="search", choices=["search", "one_ply", "heuristic"])
    parser.add_argument("--budget-s", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--rollouts", type=int, default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--beliefs", type=int, default=None)
    parser.add_argument("--margin", type=float, default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    deck = Path(args.deck).resolve()
    if not deck.exists():
        raise SystemExit(f"deck not found: {deck}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_name = args.out or f"results/search_v1_{args.name_b.replace(' ', '_')}_{stamp}"
    out_path = Path(run_name)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    telemetry_dir = out_path.parent / f"{out_path.stem}_telemetry"
    if telemetry_dir.exists():
        shutil.rmtree(telemetry_dir)
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "vendor") + os.pathsep + env.get("PYTHONPATH", "")
    env["SEARCH_V1_TELEMETRY_DIR"] = str(telemetry_dir)
    env["SEARCH_V1_MODE"] = args.mode
    for key, value in (
        ("SEARCH_V1_BUDGET_S", args.budget_s),
        ("SEARCH_V1_TOP_K", args.top_k),
        ("SEARCH_V1_ROLLOUTS", args.rollouts),
        ("SEARCH_V1_MAX_STEPS", args.max_steps),
        ("SEARCH_V1_BELIEFS", args.beliefs),
        ("SEARCH_V1_MARGIN", args.margin),
    ):
        if value is not None:
            env[key] = str(value)

    backup = None
    try:
        if deck != AGENT_DECK.resolve():
            backup = AGENT_DECK.read_text()
            AGENT_DECK.write_text(deck.read_text())
            print(f"temporarily installed {deck} as {AGENT_DECK}")

        command = [
            sys.executable,
            str(ROOT / "scripts" / "arena.py"),
            "--agent-a", args.agent_a,
            "--deck-a", str(deck),
            "--agent-b", args.agent_b,
            "--deck-b", str(deck),
            "--games", str(args.games),
            "--workers", str(args.workers),
            "--name-a", args.name_a,
            "--name-b", args.name_b,
            "--out", str(out_path),
        ]
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=3600,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode

        summary_path = out_path.with_suffix(".summary.json")
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        report = {
            "summary": summary,
            "telemetry": aggregate(str(telemetry_dir)),
            "config": {
                "mode": args.mode,
                "budget_s": args.budget_s,
                "top_k": args.top_k,
                "rollouts": args.rollouts,
                "max_steps": args.max_steps,
                "beliefs": args.beliefs,
                "margin": args.margin,
                "deck": str(deck),
                "agent_b": args.agent_b,
            },
        }
        report_path = out_path.with_suffix(".report.json")
        report_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report["telemetry"], indent=2))
        print(f"wrote {out_path}, {summary_path}, {report_path}")
        return 0
    finally:
        if backup is not None:
            AGENT_DECK.write_text(backup)
            print(f"restored {AGENT_DECK}")


if __name__ == "__main__":
    raise SystemExit(main())
