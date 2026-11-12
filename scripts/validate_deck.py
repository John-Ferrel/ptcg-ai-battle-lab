"""Validate one or more deck files and print a composition summary."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decks", nargs="+")
    args = ap.parse_args()
    bad = 0
    for d in args.decks:
        ids = decklib.load_deck(d)
        problems = decklib.validate_deck(ids)
        info = decklib.describe_deck(ids)
        print(f"== {d}: {'OK' if not problems else 'INVALID'}")
        print(json.dumps(info, indent=2, ensure_ascii=False))
        for p in problems:
            print("  !", p)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
