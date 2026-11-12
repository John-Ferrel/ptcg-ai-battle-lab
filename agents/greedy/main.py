"""Greedy baseline: legal, fast, no card database.

Priority on MAIN: attack > ability > evolve > attach > play > retreat > end.
Other contexts: prefer the first option (or fill the required count).
This is the "does not lose to itself" engineering baseline for Phase 2.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _deck():
    with open(os.path.join(_HERE, "deck.csv")) as f:
        return [int(x) for x in f.read().split()]


DECK = _deck()

# OptionType
YES, NO, CARD = 1, 2, 3
PLAY, ATTACH, EVOLVE, ABILITY = 7, 8, 9, 10
RETREAT, ATTACK, END = 12, 13, 14
MAIN_ORDER = {ATTACK: 0, ABILITY: 1, EVOLVE: 2, ATTACH: 3, PLAY: 4, RETREAT: 6, END: 9}


def agent(obs: dict) -> list[int]:
    if not obs.get("select"):
        return DECK
    sel = obs["select"]
    options = sel.get("option") or []
    lo = int(sel.get("minCount") or 0)
    hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
    hi = min(hi, len(options))
    if not options or hi <= 0:
        return []

    def score(i: int) -> int:
        t = options[i].get("type")
        return -MAIN_ORDER.get(t, 5)

    ranked = sorted(range(len(options)), key=lambda i: (score(i), i), reverse=True)
    k = hi if hi > lo else lo
    return ranked[:k]
