import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck  # noqa: E402


def test_default_deck_is_legal():
    ids = deck.load_deck(ROOT / "decks" / "default.csv")
    assert len(ids) == 60
    assert deck.validate_deck(ids) == []


def test_short_deck_is_rejected():
    ids = deck.load_deck(ROOT / "decks" / "default.csv")[:59]
    assert any("60" in p for p in deck.validate_deck(ids))


def test_meta_deck_is_legal():
    p = ROOT / "decks" / "meta" / "03_Dragapult_ex.csv"
    ids = deck.load_deck(p)
    assert deck.validate_deck(ids) == []


def test_composition_summary():
    ids = deck.load_deck(ROOT / "decks" / "meta" / "03_Dragapult_ex.csv")
    info = deck.describe_deck(ids)
    assert info["cards"] == 60
    assert info["pokemon"] > 0 and info["trainers"] > 0 and info["energy"] > 0
