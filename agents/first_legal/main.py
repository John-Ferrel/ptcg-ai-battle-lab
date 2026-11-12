"""First-legal baseline: always takes the first legal option (min count)."""
import os

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # Kaggle's loader exec()s main.py without __file__
    _HERE = os.getcwd() if os.path.exists(os.path.join(os.getcwd(), "deck.csv")) else "/kaggle_simulations/agent"


def _deck():
    with open(os.path.join(_HERE, "deck.csv")) as f:
        return [int(x) for x in f.read().split()]


DECK = _deck()


def agent(obs: dict) -> list[int]:
    if not obs.get("select"):
        return DECK
    sel = obs["select"]
    lo = int(sel.get("minCount") or 0)
    return list(range(lo))
