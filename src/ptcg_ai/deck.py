"""Deck loading / validation helpers."""
from __future__ import annotations

import collections
from pathlib import Path

from . import cards

ROOT = Path(__file__).resolve().parents[2]
DECKS_DIR = ROOT / "decks"


class DeckError(ValueError):
    pass


def load_deck(path: str | Path) -> list[int]:
    """Read a deck file (one card id per line, or whitespace separated)."""
    p = Path(path)
    ids: list[int] = []
    for line in p.read_text().splitlines():
        line = line.split("#", 1)[0].strip().rstrip(",")
        if not line:
            continue
        for tok in line.replace(",", " ").split():
            ids.append(int(tok))
    return ids


def save_deck(path: str | Path, deck: list[int]) -> None:
    p = Path(path)
    p.write_text("\n".join(str(i) for i in deck) + "\n")


def validate_deck(deck: list[int], min_basics: int = 1) -> list[str]:
    """Return a list of problems; empty list means the deck is legal."""
    problems: list[str] = []
    if len(deck) != 60:
        problems.append(f"deck has {len(deck)} cards, expected 60")
    db = cards.card_db()
    counts = collections.Counter(deck)
    basic_energy = cards.basic_energy_ids()
    for cid, n in counts.items():
        if cid not in db:
            problems.append(f"unknown card id {cid}")
            continue
        c = db[cid]
        if n > 4 and cid not in basic_energy:
            problems.append(f"{n}x {c.get('name', cid)} (#{cid}) exceeds 4-copy limit")
    basics = [cid for cid in deck if db.get(cid, {}).get("basic")]
    if len(basics) < min_basics:
        problems.append(f"only {len(basics)} basic Pokemon (need >= {min_basics})")
    return problems


def describe_deck(deck: list[int]) -> dict:
    db = cards.card_db()
    counts = collections.Counter(deck)
    pokemon = [(cid, n) for cid, n in counts.items() if db.get(cid, {}).get("cardType") == cards.POKEMON]
    trainers = [(cid, n) for cid, n in counts.items() if db.get(cid, {}).get("cardType") in (cards.ITEM, cards.TOOL, cards.SUPPORTER, cards.STADIUM)]
    energy = [(cid, n) for cid, n in counts.items() if db.get(cid, {}).get("cardType") in (cards.BASIC_ENERGY, cards.SPECIAL_ENERGY)]
    return {
        "cards": len(deck),
        "unique": len(counts),
        "pokemon": sum(n for _, n in pokemon),
        "trainers": sum(n for _, n in trainers),
        "energy": sum(n for _, n in energy),
        "pokemon_lines": [(db[cid].get("name", cid), n) for cid, n in sorted(pokemon, key=lambda x: -x[1])],
    }
