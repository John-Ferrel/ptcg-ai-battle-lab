"""Card / attack database access for the local cabt engine.

The `kaggle-environments` cabt package ships the compiled engine (`libcg.so`) but
does not bind `AllCard`/`AllAttack`.  Those symbols exist in the shared library,
so we bind them ourselves with ctypes and cache the result as JSON.

Licensed competition data: the dump is kept under `data/` (git-ignored) and is
never committed.  Run `python scripts/build_card_db.py` once per environment.
"""
from __future__ import annotations

import ctypes
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CARDS_PATH = DATA_DIR / "cards.json"
ATTACKS_PATH = DATA_DIR / "attacks.json"

# CardType
POKEMON, ITEM, TOOL, SUPPORTER, STADIUM, BASIC_ENERGY, SPECIAL_ENERGY = range(7)
# EnergyType
COLORLESS, GRASS, FIRE, WATER, LIGHTNING, PSYCHIC, FIGHTING, DARKNESS, METAL, DRAGON, RAINBOW, TEAM_ROCKET = range(12)


def _lib():
    from kaggle_environments.envs.cabt.cg.sim import lib

    lib.AllCard.restype = ctypes.c_char_p
    lib.AllCard.argtypes = []
    lib.AllAttack.restype = ctypes.c_char_p
    lib.AllAttack.argtypes = []
    return lib


def dump_card_db() -> tuple[list[dict], list[dict]]:
    """Extract card and attack tables straight from the engine."""
    lib = _lib()
    cards = json.loads(lib.AllCard())
    attacks = json.loads(lib.AllAttack())
    return cards, attacks


def build_cache() -> None:
    cards, attacks = dump_card_db()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CARDS_PATH.write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")))
    ATTACKS_PATH.write_text(json.dumps(attacks, ensure_ascii=False, separators=(",", ":")))


@lru_cache(maxsize=1)
def card_db() -> dict[int, dict[str, Any]]:
    if not CARDS_PATH.exists():
        build_cache()
    cards = json.loads(CARDS_PATH.read_text())
    return {c["cardId"]: c for c in cards}


@lru_cache(maxsize=1)
def attack_db() -> dict[int, dict[str, Any]]:
    if not ATTACKS_PATH.exists():
        build_cache()
    attacks = json.loads(ATTACKS_PATH.read_text())
    return {a["attackId"]: a for a in attacks}


def card(card_id: int) -> dict[str, Any]:
    return card_db().get(int(card_id), {})


def attack(attack_id: int) -> dict[str, Any]:
    return attack_db().get(int(attack_id), {})


def name(card_id: int) -> str:
    return card(card_id).get("name", f"#{card_id}")


def basic_energy_ids() -> set[int]:
    return {cid for cid, c in card_db().items() if c.get("cardType") == BASIC_ENERGY}
