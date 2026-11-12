"""Random-legal baseline: samples uniformly among the legality constraints.

Used as the sanity floor of the arena, never as a submission candidate.
"""
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))


def _deck():
    with open(os.path.join(_HERE, "deck.csv")) as f:
        return [int(x) for x in f.read().split()]


DECK = _deck()


def agent(obs: dict) -> list[int]:
    if not obs.get("select"):
        return DECK
    sel = obs["select"]
    n = len(sel["option"])
    lo = int(sel.get("minCount") or 0)
    hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
    hi = min(hi, n)
    k = random.randint(lo, hi) if hi > lo else hi
    return random.sample(range(n), k)
