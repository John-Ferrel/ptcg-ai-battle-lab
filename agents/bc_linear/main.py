"""bc_linear -- a linear behavior-cloning policy trained on playground replays.

Self-contained submission agent (stdlib only):
    main.py          this file
    bc_features.py   pure-stdlib feature extractor (identical to training)
    weights.json     exported linear weights, list of [feature_name, weight]
    card_meta.json   compact card/attack properties used by the features
    deck.csv         60 card ids (decks/meta/03_Dragapult_ex.csv)

The scorer ranks the offered options; the top `maxCount` are returned.  Any
error, missing file or odd observation falls back to legal indices, so the
agent can never return an out-of-range or illegal index.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bc_features  # noqa: E402  (same directory, stdlib only)


def _read_json(name):
    with open(os.path.join(_HERE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _read_deck():
    with open(os.path.join(_HERE, "deck.csv"), "r", encoding="utf-8") as f:
        return [int(x) for x in f.read().split()]


DECK = _read_deck()

try:
    _W = _read_json("weights.json")
    WEIGHTS = {str(k): float(v) for k, v in _W.get("weights", [])}
    INTERCEPT = float(_W.get("intercept", 0.0) or 0.0)
except Exception:  # noqa: BLE001 -- a missing weights file must not crash a game
    WEIGHTS, INTERCEPT = {}, 0.0

try:
    _M = _read_json("card_meta.json")
    META = {
        "c": {int(k): v for k, v in (_M.get("c") or {}).items()},
        "a": {int(k): v for k, v in (_M.get("a") or {}).items()},
    }
except Exception:  # noqa: BLE001
    META = {"c": {}, "a": {}}


def _score(feats):
    w = WEIGHTS
    out = []
    for d in feats:
        s = 0.0
        for name, val in d.items():
            wt = w.get(name)
            if wt is not None:
                s += wt * val
        out.append(s)
    return out


def agent(obs):
    if not obs.get("select"):
        return DECK
    sel = obs["select"]
    options = sel.get("option") or []
    try:
        lo = int(sel.get("minCount") or 0)
    except (TypeError, ValueError):
        lo = 0
    try:
        hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
    except (TypeError, ValueError):
        hi = 1
    hi = min(hi, len(options))
    if not options or hi <= 0:
        return []
    lo = max(0, min(lo, hi))

    order = None
    if WEIGHTS:
        try:
            scores = _score(bc_features.build_features(obs, META))
            if len(scores) == len(options):
                order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
        except Exception:  # noqa: BLE001 -- never crash, fall back to first legal
            order = None
    if order is None:
        order = list(range(len(options)))

    k = hi if hi > lo else lo
    k = max(lo, min(k, hi))
    return [int(i) for i in order[:k]]
