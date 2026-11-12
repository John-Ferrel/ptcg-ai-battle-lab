#!/usr/bin/env python
"""Legality self-test for the heuristic_v1 submission agent.

Feeds synthetic observations covering every select context we have seen in
practice (plus unknown/malformed ones) and asserts that the agent always
returns a legal list of option indices.  Run:

    .venv/bin/python scripts/policy_selftest.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "agents" / "heuristic_v1" / "main.py"


def load_agent():
    spec = importlib.util.spec_from_file_location("heuristic_v1", AGENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.agent


def card(cid, serial=1, owner=0, **kw):
    d = {"id": cid, "serial": serial, "playerIndex": owner}
    d.update(kw)
    return d


def pokemon(cid, hp=80, maxhp=100, energies=(), serial=1, owner=0, tools=(), pre=()):
    return {
        "id": cid,
        "serial": serial,
        "playerIndex": owner,
        "hp": hp,
        "maxHp": maxhp,
        "appearThisTurn": False,
        "energies": list(energies),
        "energyCards": [],
        "tools": [{"id": t, "serial": 100 + i, "playerIndex": owner} for i, t in enumerate(tools)],
        "preEvolution": [card(p, serial=200 + i, owner=owner) for i, p in enumerate(pre)],
    }


def state(me_active=None, me_bench=(), me_hand=(), me_discard=(), op_active=None, op_bench=(),
          op_hand=6, me_prize=6, op_prize=6, your=0, stadium=()):
    players = [
        {
            "active": [me_active] if your == 0 else ([op_active] if op_active else [None]),
            "bench": list(me_bench) if your == 0 else list(op_bench),
            "benchMax": 5,
            "deckCount": 40,
            "discard": list(me_discard) if your == 0 else [],
            "prize": [None] * me_prize if your == 0 else [None] * op_prize,
            "handCount": len(me_hand) if your == 0 else op_hand,
            "hand": list(me_hand) if your == 0 else None,
            "poisoned": False,
            "burned": False,
            "asleep": False,
            "paralyzed": False,
            "confused": False,
            "win": 0,
        },
        {
            "active": [op_active] if your == 0 else ([me_active] if me_active else [None]),
            "bench": list(op_bench) if your == 0 else list(me_bench),
            "benchMax": 5,
            "deckCount": 40,
            "discard": [],
            "prize": [None] * op_prize if your == 0 else [None] * me_prize,
            "handCount": op_hand if your == 0 else len(me_hand),
            "hand": None,
            "poisoned": False,
            "burned": False,
            "asleep": False,
            "paralyzed": False,
            "confused": False,
            "win": 0,
        },
    ]
    return {
        "turn": 4,
        "turnActionCount": 2,
        "yourIndex": your,
        "firstPlayer": 0,
        "supporterPlayed": False,
        "stadiumPlayed": False,
        "energyAttached": False,
        "retreated": False,
        "result": -1,
        "draw": 0,
        "round": 1,
        "stadium": list(stadium),
        "looking": None,
        "players": players,
    }


def obs(sel, cur):
    return {"select": sel, "current": cur, "logs": [], "search_begin_input": ""}


def sel(ctx, typ, options, lo=1, hi=1, deck=None):
    d = {
        "type": typ,
        "context": ctx,
        "minCount": lo,
        "maxCount": hi,
        "remainDamageCounter": 0,
        "remainEnergyCost": 0,
        "option": options,
        "contextCard": None,
        "effect": None,
    }
    if deck is not None:
        d["deck"] = deck
    return d


def opt(t, area=None, index=0, owner=0, **kw):
    d = {"type": t}
    if area is not None:
        d["area"] = area
    if area is not None:
        d["index"] = index
    d["playerIndex"] = owner
    d.update(kw)
    return d


def check(fn, name, o, expect_n=None):
    action = fn(o)
    s = o["select"]
    n = len(s["option"])
    lo = int(s.get("minCount") or 0)
    hi = int(s.get("maxCount") if s.get("maxCount") is not None else 1)
    hi = min(hi, n)
    assert isinstance(action, list), f"{name}: not a list: {action!r}"
    assert all(isinstance(a, int) for a in action), f"{name}: non-int: {action!r}"
    assert len(action) == len(set(action)), f"{name}: duplicates: {action!r}"
    assert all(0 <= a < n for a in action), f"{name}: out of range: {action!r} n={n}"
    assert lo <= len(action) <= hi, f"{name}: count {len(action)} not in [{lo},{hi}] for {action!r}"
    if expect_n is not None:
        assert len(action) == expect_n, f"{name}: expected {expect_n}, got {action!r}"
    print(f"ok  {name:38s} -> {action}")
    return action


def main() -> int:
    agent = load_agent()
    assert len(agent({"select": None})) == 60, "deck phase must return 60 cards"

    me_active = pokemon(93, hp=80, maxhp=80, energies=[1])
    me_bench = [pokemon(42, hp=40, maxhp=40, serial=2), pokemon(89, hp=70, maxhp=70, serial=3)]
    me_hand = [card(1152, 10), card(93, 11), card(1245, 12), card(1, 13)]
    op_active = pokemon(676, hp=110, maxhp=110, energies=[6], serial=30, owner=1)
    op_bench = [pokemon(674, hp=150, maxhp=150, serial=31, owner=1)]
    cur = state(me_active, me_bench, me_hand, me_discard=[card(1, 20), card(42, 21)],
                op_active=op_active, op_bench=op_bench, stadium=[card(1245, 40)])

    # MAIN
    check(agent, "MAIN attack/play/attach/end", obs(sel(0, 0, [
        {"type": 13, "attackId": 115},
        {"type": 7, "index": 0},
        {"type": 8, "area": 2, "index": 3, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 14},
    ]), cur))

    # Setup
    check(agent, "SETUP_ACTIVE", obs(sel(1, 1, [opt(3, 2, 0), opt(3, 2, 1)]), cur))
    check(agent, "SETUP_BENCH", obs(sel(2, 1, [opt(3, 2, 0), opt(3, 2, 1)], 0, 2), cur))

    # Switching / promotion
    check(agent, "SWITCH", obs(sel(3, 1, [opt(3, 5, i) for i in range(2)]), cur))
    check(agent, "TO_ACTIVE", obs(sel(4, 1, [opt(3, 5, i) for i in range(2)]), cur))

    # Search to bench / hand, revealed deck
    deck = [card(42, 50), card(89, 51), card(1, 52), card(1245, 53)]
    check(agent, "TO_BENCH (Poffin)", obs(sel(5, 1, [opt(3, 1, 0), opt(3, 1, 1)], 0, 2, deck=deck), cur))
    check(agent, "TO_HAND (search)", obs(sel(7, 1, [opt(3, 1, 0), opt(3, 1, 3)], 0, 1, deck=deck), cur))

    # Discard
    check(agent, "DISCARD x2", obs(sel(8, 1, [opt(3, 2, i) for i in range(3)], 2, 2), cur), 2)
    check(agent, "TO_DECK", obs(sel(9, 1, [opt(3, 3, i) for i in range(2)], 1, 2), cur))
    check(agent, "TO_DECK_BOTTOM", obs(sel(10, 1, [opt(3, 2, i) for i in range(2)], 1, 1), cur))
    check(agent, "TO_PRIZE", obs(sel(11, 1, [opt(3, 2, i) for i in range(2)], 1, 1), cur))

    # Damage / heal
    check(agent, "DAMAGE_COUNTER", obs(sel(13, 1, [opt(3, 4, 0, 1), opt(3, 5, 0, 1)]), cur))
    check(agent, "DAMAGE_COUNTER_ANY", obs(sel(14, 1, [opt(3, 4, 0, 1), opt(3, 5, 0, 1)]), cur))
    check(agent, "DAMAGE", obs(sel(15, 1, [opt(3, 4, 0, 1), opt(3, 5, 0, 1)]), cur))
    check(agent, "REMOVE_DAMAGE_COUNTER", obs(sel(17, 1, [opt(3, 4, 0, 0)]), cur))

    # Attach selections
    check(agent, "ATTACH_FROM", obs(sel(21, 1, [opt(3, 4, 0, 0), opt(3, 5, 0, 0)]), cur))
    check(agent, "ATTACH_TO", obs(sel(22, 1, [opt(3, 4, 0, 0), opt(3, 5, 0, 0)], 0, 1), cur))
    check(agent, "DISCARD_TOOL", obs(sel(27, 2, [opt(4, 5, 0, 0, toolIndex=0)], 1, 2), cur))
    check(agent, "DISCARD_ENERGY", obs(sel(30, 4, [opt(6, 4, 0, 0, energyIndex=0)], 1, 1), cur))
    check(agent, "ENERGY select 33", obs(sel(33, 4, [opt(6, 4, 0, 0, energyIndex=0),
                                                    opt(6, 4, 0, 0, energyIndex=1)], 1, 1), cur))
    check(agent, "ATTACHED_CARD switch 26", obs(sel(26, 2, [opt(5, 5, 0, 0, energyIndex=0)], 0, 2), cur))

    # Skills / attacks / yes-no / counts / special
    check(agent, "SKILL_ORDER", obs(sel(34, 5, [opt(15), opt(15), opt(15)], 2, 3), cur), 3)
    check(agent, "ATTACK select", obs(sel(35, 6, [{"type": 13, "attackId": 115}], 0, 1), cur), 1)
    check(agent, "ATTACK select (forced)", obs(sel(36, 6, [{"type": 13, "attackId": 115}], 1, 1), cur), 1)
    check(agent, "EVOLVE select", obs(sel(37, 7, [opt(9, 2, 1, 0, inPlayArea=5, inPlayIndex=0)], 1, 1), cur))
    check(agent, "IS_FIRST", obs(sel(41, 9, [{"type": 1}, {"type": 2}], 1, 1), cur))
    check(agent, "MULLIGAN", obs(sel(42, 9, [{"type": 1}, {"type": 2}], 1, 1), cur))
    check(agent, "YES_NO / ACTIVATE", obs(sel(43, 9, [{"type": 1}, {"type": 2}], 1, 1), cur))
    check(agent, "COUNT numbers", obs(sel(38, 8, [{"type": 0, "number": 0}, {"type": 0, "number": 1}], 1, 1), cur))
    check(agent, "DRAW COUNT", obs(sel(40, 8, [{"type": 0, "number": 1}, {"type": 0, "number": 3}], 1, 1), cur))
    check(agent, "SPECIAL_CONDITION", obs(sel(39, 10, [{"type": 0}, {"type": 1}], 1, 1), cur))
    check(agent, "COIN_HEAD", obs(sel(46, 8, [{"type": 0, "number": 0}, {"type": 0, "number": 1}], 1, 1), cur))

    # Unknown context, optional / forced
    check(agent, "UNKNOWN min0", obs(sel(99, 1, [opt(3, 2, 0), opt(3, 2, 1)], 0, 2), cur))
    check(agent, "UNKNOWN forced", obs(sel(98, 1, [opt(3, 2, 0), opt(3, 2, 1)], 2, 2), cur), 2)
    check(agent, "maxCount 0", obs(sel(0, 0, [{"type": 14}], 0, 0), cur), 0)

    # Malformed observations must still be legal.
    check(agent, "malformed/no current", {"select": sel(0, 0, [{"type": 14}], 1, 1)})
    check(agent, "empty options", obs(sel(0, 0, [], 0, 0), {}), 0)
    check(agent, "option index 0 only", obs(sel(1, 1, [opt(3, 2, 0)], 1, 1), cur), 1)

    print("\nall synthetic context checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
