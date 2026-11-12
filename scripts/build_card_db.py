"""Dump the engine's card/attack tables to data/*.json (run once)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import cards  # noqa: E402


def main() -> int:
    cards.build_cache()
    print(f"cards: {len(cards.card_db())} -> {cards.CARDS_PATH}")
    print(f"attacks: {len(cards.attack_db())} -> {cards.ATTACKS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
