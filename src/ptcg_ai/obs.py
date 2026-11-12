"""Small, dependency-free helpers for reading cabt observations.

All functions take the *raw observation dict* that the engine hands to an agent,
so the same code can be copy-pasted into a submission `main.py`.
"""
from __future__ import annotations

from typing import Any

# SelectType
MAIN, CARD, ATTACHED_CARD, CARD_OR_ATTACHED_CARD, ENERGY, SKILL, ATTACK_SEL, EVOLVE_SEL, COUNT, YES_NO, SPECIAL_CONDITION = range(11)
# SelectContext (subset that matters)
CTX_MAIN = 0
CTX_SETUP_ACTIVE = 1
CTX_SETUP_BENCH = 2
CTX_SWITCH = 3
CTX_TO_ACTIVE = 4
CTX_TO_BENCH = 5
CTX_TO_HAND = 7
CTX_DISCARD = 8
CTX_TO_DECK = 9
CTX_TO_DECK_BOTTOM = 10
CTX_TO_PRIZE = 11
CTX_DAMAGE_COUNTER = 13
CTX_DAMAGE_COUNTER_ANY = 14
CTX_DAMAGE = 15
CTX_HEAL = 17
CTX_ATTACH_FROM = 21
CTX_ATTACH_TO = 22
CTX_LOOK = 24
CTX_EFFECT_TARGET = 25
CTX_DISCARD_ENERGY = 30
CTX_SKILL_ORDER = 34
CTX_ATTACK = 35
CTX_IS_FIRST = 41
CTX_MULLIGAN = 42
CTX_ACTIVATE = 43
CTX_COIN_HEAD = 46

# OptionType
OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_TOOL_CARD, OPT_ENERGY_CARD, OPT_ENERGY, OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY, OPT_DISCARD, OPT_RETREAT, OPT_ATTACK, OPT_END, OPT_SKILL, OPT_SPECIAL = range(17)

# AreaType
AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH, AREA_PRIZE, AREA_STADIUM, AREA_ENERGY, AREA_TOOL = range(1, 10)


def select(obs: dict) -> dict | None:
    return obs.get("select")


def state(obs: dict) -> dict | None:
    return obs.get("current")


def me_index(obs: dict) -> int:
    return obs["current"]["yourIndex"]


def me(obs: dict) -> dict:
    s = obs["current"]
    return s["players"][s["yourIndex"]]


def opp(obs: dict) -> dict:
    s = obs["current"]
    return s["players"][1 - s["yourIndex"]]


def active(p: dict) -> dict | None:
    a = p.get("active") or []
    return a[0] if a else None


def bench(p: dict) -> list[dict]:
    return [x for x in (p.get("bench") or []) if x]


def hand(obs: dict) -> list[dict]:
    return me(obs).get("hand") or []


def hand_card(obs: dict, index: int) -> dict | None:
    h = hand(obs)
    return h[index] if 0 <= index < len(h) else None


def in_play(p: dict) -> list[dict]:
    out = []
    a = active(p)
    if a:
        out.append(a)
    out.extend(bench(p))
    return out


def prize_count(p: dict) -> int:
    return len(p.get("prize") or [])


def energies(pokemon: dict) -> list[int]:
    return list(pokemon.get("energies") or [])


def energy_count(pokemon: dict) -> int:
    return len(energies(pokemon))


def has_energy(pokemon: dict, etype: int) -> bool:
    es = energies(pokemon)
    if etype in es:
        return True
    # RAINBOW satisfies everything, TEAM_ROCKET = psychic/darkness
    if 10 in es:
        return True
    if 11 in es and etype in (5, 7):
        return True
    return False


def can_pay(cost: list[int], pokemon: dict) -> bool:
    """Approximate energy cost check (counts units, ignores per-type colour)."""
    if len(energies(pokemon)) < len(cost):
        return False
    for c in cost:
        if c != 0 and not has_energy(pokemon, c):
            return False
    return True


def card_id_of_option(obs: dict, option: dict) -> int | None:
    """Best-effort card id for a CARD / PLAY / EVOLVE option."""
    t = option.get("type")
    if t == OPT_PLAY:
        c = hand_card(obs, option.get("index", -1))
        return c.get("id") if c else None
    if t in (OPT_CARD, OPT_DISCARD):
        area = option.get("area")
        idx = option.get("index", -1)
        owner = option.get("playerIndex", me_index(obs))
        p = obs["current"]["players"][owner]
        if area == AREA_HAND:
            c = (p.get("hand") or [None])[idx] if p.get("hand") else None
            return c.get("id") if c else None
        if area == AREA_ACTIVE:
            a = active(p)
            return a.get("id") if a else None
        if area == AREA_BENCH:
            b = bench(p)
            return b[idx].get("id") if 0 <= idx < len(b) else None
        if area == AREA_DISCARD:
            d = p.get("discard") or []
            return d[idx].get("id") if 0 <= idx < len(d) else None
        if area == AREA_PRIZE:
            c = (p.get("prize") or [None])[idx]
            return c.get("id") if c else None
        if area == AREA_STADIUM:
            return (obs["current"].get("stadium") or [{}])[0].get("id")
    if t in (OPT_EVOLVE, OPT_ATTACH):
        area = option.get("area")
        idx = option.get("index", -1)
        p = obs["current"]["players"][me_index(obs)]
        if area == AREA_HAND:
            c = (p.get("hand") or [None])[idx] if p.get("hand") else None
            return c.get("id") if c else None
    return option.get("cardId")


def option_target(obs: dict, option: dict) -> dict | None:
    """Resolve the in-play Pokemon an option points at (ATTACH / damage / etc.)."""
    area = option.get("inPlayArea", option.get("area"))
    idx = option.get("inPlayIndex", option.get("index", 0))
    owner = option.get("playerIndex", me_index(obs))
    p = obs["current"]["players"][owner]
    if area == AREA_ACTIVE:
        return active(p)
    if area == AREA_BENCH:
        b = bench(p)
        return b[idx] if 0 <= idx < len(b) else None
    return None
