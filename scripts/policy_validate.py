#!/usr/bin/env python
"""Run the standard heuristic_v1 validation suite (seat-swapped arena).

Examples:
    .venv/bin/python scripts/policy_validate.py
    .venv/bin/python scripts/policy_validate.py --games 400 --workers 3

Writes one `.jsonl` + `.summary.json` per matchup under results/ and a combined
`results/policy_v1_table.json`, then prints a Markdown table with Wilson CIs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = "agents/heuristic_v1"
DECK = "decks/deck_dipplin.csv"

MATCHUPS = [
    ("random", "agents/random_legal", "random_legal"),
    ("first", "agents/first_legal", "first_legal"),
    ("greedy", "agents/greedy", "greedy"),
    ("mirror", AGENT, "heuristic_v1_mirror"),
]


def run(tag: str, opponent: str, opp_name: str, games: int, workers: int) -> dict:
    out_tag = "policy_v1_mirror" if tag == "mirror" else f"policy_v1_vs_{tag}"
    out = ROOT / "results" / f"{out_tag}.jsonl"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "arena.py"),
        "--agent-a", AGENT,
        "--deck-a", DECK,
        "--agent-b", opponent,
        "--deck-b", DECK,
        "--games", str(games),
        "--workers", str(workers),
        "--name-a", "heuristic_v1",
        "--name-b", opp_name,
        "--out", str(out),
    ]
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    summary_path = out.with_suffix(".summary.json")
    return json.loads(summary_path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    rows = {}
    for name, opponent, opp_name in MATCHUPS:
        rows[name] = run(name, opponent, opp_name, args.games, args.workers)

    table_path = ROOT / "results" / "policy_v1_table.json"
    table_path.write_text(json.dumps(rows, indent=2))

    print("\n| opponent | games | win rate | 95% CI | illegal | errors | avg ms | max ms |")
    print("|---|---:|---:|---|---:|---:|---:|---:|")
    for name, r in rows.items():
        lo, hi = r["ci95"]
        print(
            f"| {name} | {r['games']} | {r['a_winrate'] * 100:.1f}% | "
            f"[{lo * 100:.1f}, {hi * 100:.1f}] | {r['illegal']} | {r['errors']} | "
            f"{r['avg_decision_ms']:.3f} | {r['max_decision_ms']:.1f} |"
        )
    print(f"\nwrote {table_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
