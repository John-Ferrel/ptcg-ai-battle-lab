"""Collect experiment result JSONs into a markdown table.

Scans results/ for *.summary.json (arena) and *.json (gauntlet) and prints a
compact table.  Used to keep EXPERIMENTS.md honest (copy the generated rows).

Usage: python scripts/report.py [results_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    rows = []
    for p in sorted(d.rglob("*.json")):
        try:
            j = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(j, dict) or "games" not in j:
            continue
        if "agent_a" in j:  # arena
            rows.append(
                (
                    p.relative_to(d).as_posix(),
                    f"{j['agent_a']} vs {j['agent_b']}",
                    j["games"],
                    f"{j['a_winrate']*100:.1f}%",
                    f"{j['ci95'][0]*100:.1f}-{j['ci95'][1]*100:.1f}%",
                    j.get("illegal", "?"),
                    j.get("errors", "?"),
                    f"{j.get('avg_decision_ms', 0):.2f}",
                )
            )
        elif "agent" in j:  # gauntlet
            rows.append(
                (
                    p.relative_to(d).as_posix(),
                    j["agent"],
                    j["games"],
                    f"{j['winrate']*100:.1f}%",
                    f"{j['ci95'][0]*100:.1f}-{j['ci95'][1]*100:.1f}%",
                    j.get("illegal", "?"),
                    j.get("errors", "?"),
                    f"{j.get('avg_decision_ms', 0):.2f}",
                )
            )
    print("| file | matchup | games | win rate | CI95 | illegal | errors | ms/dec |")
    print("|---|---|---:|---:|---|---:|---:|---:|")
    for r in rows:
        print("| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(*r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
