"""Regenerate the git-ignored runtime data files for the agents.

`card_meta.json` is derived from the licensed engine data, so it is not
committed.  Run this once after cloning / after `build_card_db.py`.

Usage: python scripts/prepare_agents.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["agents/heuristic_v1", "agents/search_v1", "agents/bc_linear"]


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_card_db.py")], check=True)
    src = ROOT / "agents" / "heuristic_v1" / "card_meta.json"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export_agent_card_meta.py"), "--out", str(src)], check=True)
    for t in TARGETS:
        dst = ROOT / t / "card_meta.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.resolve() != src.resolve():
            shutil.copyfile(src, dst)
        print(f"ready {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
