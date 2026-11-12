"""heuristic_v1 — card-data-aware Pokémon TCG policy (stdlib only).

Design goals
------------
* **Legal by construction**: every return is clamped to the offered option
  indices and to ``[minCount, maxCount]``.  ``agent()`` never raises.
* **Self contained**: only the Python stdlib, ``deck.csv`` and the optional
  ``card_meta.json`` next to this file are used.
* **Fast**: a decision is a handful of dict lookups; target < 2 ms.

The policy is a one-ply heuristic over the *current* observation:

MAIN is scored by expected value of the action (KO / prizes / damage / setup /
draw / energy efficiency), with the TCG turn order encoded in the scores:
develop (search, evolve, attach, play) → attack → end.  Sub-selections (which
card to search, which Pokémon to damage, which energy to discard, ...) use a
small set of value functions and context-aware direction (maximise for
beneficial choices, minimise for costs).

Missing ``card_meta.json`` is not fatal: scores degrade to type-agnostic
priorities and the legality wrapper still guarantees a legal action.
"""
from __future__ import annotations

import json
import os
import re

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # Kaggle's loader exec()s main.py without __file__
    _HERE = os.getcwd() if os.path.exists(os.path.join(os.getcwd(), "deck.csv")) else "/kaggle_simulations/agent"

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------


def _load_deck() -> list[int]:
    try:
        with open(os.path.join(_HERE, "deck.csv")) as f:
            deck = [int(x) for x in f.read().split()]
        return deck if deck else []
    except Exception:  # pragma: no cover - submission deck is shipped with us
        return []


def _load_meta() -> dict:
    path = os.path.join(_HERE, "card_meta.json")
    try:
        with open(path) as f:
            raw = json.load(f)
        out = {}
        for k, v in raw.items():
            try:
                out[int(k)] = v
            except Exception:
                continue
        return out
    except Exception:
        return {}


DECK = _load_deck()
META = _load_meta()
ATT: dict[int, tuple] = {}
for _c in META.values():
    for _a in _c.get("a") or []:
        try:
            ATT[int(_a[0])] = (tuple(int(x) for x in (_a[1] or [])), int(_a[2] or 0), str(_a[3] or ""))
        except Exception:
            continue

# Card types
T_POKEMON, T_ITEM, T_TOOL, T_SUPPORTER, T_STADIUM, T_BASIC_ENERGY, T_SPECIAL_ENERGY = range(7)

# Option types
OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_TOOL_CARD, OPT_ENERGY_CARD = 0, 1, 2, 3, 4, 5
OPT_ENERGY, OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY, OPT_DISCARD = 6, 7, 8, 9, 10, 11
OPT_RETREAT, OPT_ATTACK, OPT_END, OPT_SKILL = 12, 13, 14, 15

# Select types
SEL_MAIN, SEL_CARD, SEL_ATTACHED, SEL_CARD_OR_ATT, SEL_ENERGY, SEL_SKILL = 0, 1, 2, 3, 4, 5
SEL_ATTACK, SEL_EVOLVE, SEL_COUNT, SEL_YES_NO, SEL_SPECIAL = 6, 7, 8, 9, 10

# Select contexts (observed values; unknown contexts use the generic path)
C_MAIN = 0
C_SETUP_ACTIVE = 1
C_SETUP_BENCH = 2
C_SWITCH = 3
C_TO_ACTIVE = 4
C_TO_BENCH = 5
C_TO_HAND = 7
C_DISCARD = 8
C_TO_DECK = 9
C_TO_DECK_BOTTOM = 10
C_TO_PRIZE = 11
C_DAMAGE_COUNTER = 13
C_DAMAGE_COUNTER_ANY = 14
C_DAMAGE = 15
C_HEAL = 17
C_ATTACH_FROM = 21
C_ATTACH_TO = 22
C_DISCARD_TOOL = 27
C_DISCARD_ENERGY = 30
C_SKILL_ORDER = 34
C_ATTACK = 35
C_IS_FIRST = 41
C_MULLIGAN = 42
C_ACTIVATE = 43
C_COIN_HEAD = 46

_YES_TYPES = (OPT_YES,)
_NUM_RE = re.compile(r"\d+")
_FESTIVAL = "festival grounds"
_RULE_BOX_RE = re.compile(r"rule box", re.I)


def _card(cid):
    if cid is None:
        return None
    try:
        return META.get(int(cid))
    except Exception:
        return None


def _attr(cid, key, default=None):
    c = _card(cid)
    if not c:
        return default
    v = c.get(key, default)
    return default if v is None else v


def _ctype(cid):
    return _attr(cid, "t", -1)


def _name(cid):
    return str(_attr(cid, "n", "") or "")


def _text(cid) -> str:
    c = _card(cid)
    if not c:
        return ""
    parts = []
    for sk in c.get("sk") or []:
        try:
            parts.append(str(sk[1]))
        except Exception:
            continue
    for a in c.get("a") or []:
        try:
            parts.append(str(a[3]))
        except Exception:
            continue
    return " ".join(parts).lower()


def _skill_names(cid) -> str:
    c = _card(cid)
    if not c:
        return ""
    return " ".join(str(sk[0]).lower() for sk in (c.get("sk") or []) if sk)


def _is_pokemon(cid):
    return _ctype(cid) == T_POKEMON


def _is_energy(cid):
    return _ctype(cid) in (T_BASIC_ENERGY, T_SPECIAL_ENERGY)


def _is_basic(cid):
    return bool(_attr(cid, "b", 0))


def _is_ex(cid):
    c = _card(cid)
    return bool(c and (c.get("ex") or c.get("mega")))


def _energy_type(cid) -> int:
    return int(_attr(cid, "et", 0) or 0)


def _first_int(text: str) -> int:
    m = _NUM_RE.search(text or "")
    return int(m.group()) if m else 0


# ---------------------------------------------------------------------------
# Observation view
# ---------------------------------------------------------------------------


class View:
    """Cheap, exception-tolerant view over the raw observation dict."""

    __slots__ = ("obs", "cur", "sel", "yi", "players", "me", "op", "logs", "stadium", "hand")

    def __init__(self, obs: dict):
        self.obs = obs
        sel = obs.get("select") or {}
        cur = obs.get("current") or {}
        self.sel = sel
        self.cur = cur
        try:
            self.yi = int(cur.get("yourIndex", 0) or 0)
        except Exception:
            self.yi = 0
        players = cur.get("players") or [{}, {}]
        if not isinstance(players, list) or len(players) < 2:
            players = [{}, {}]
        self.players = players
        self.me = players[self.yi] if isinstance(players[self.yi], dict) else {}
        self.op = players[1 - self.yi] if isinstance(players[1 - self.yi], dict) else {}
        self.logs = obs.get("logs") or []
        st = cur.get("stadium") or []
        self.stadium = st if isinstance(st, list) else []
        h = self.me.get("hand")
        self.hand = h if isinstance(h, list) else []

    # -- zones -----------------------------------------------------------
    @staticmethod
    def active_of(p):
        a = p.get("active") or []
        return a[0] if a and isinstance(a[0], dict) else None

    @staticmethod
    def bench_of(p):
        return [x for x in (p.get("bench") or []) if isinstance(x, dict)]

    @staticmethod
    def in_play(p):
        out = []
        a = View.active_of(p)
        if a:
            out.append(a)
        out.extend(View.bench_of(p))
        return out

    def my_active(self):
        return self.active_of(self.me)

    def op_active(self):
        return self.active_of(self.op)

    def my_bench(self):
        return self.bench_of(self.me)

    def op_bench(self):
        return self.bench_of(self.op)

    def card_in_hand(self, idx):
        if 0 <= idx < len(self.hand):
            return self.hand[idx]
        return None

    def deck_cards(self):
        d = self.sel.get("deck")
        return d if isinstance(d, list) else []

    def looking_cards(self):
        lk = self.cur.get("looking")
        return lk if isinstance(lk, list) else []

    def stadium_card(self):
        for s in self.stadium:
            if isinstance(s, dict):
                return s.get("id")
        return None

    def stadium_is_festival(self) -> bool:
        sid = self.stadium_card()
        return bool(sid) and (_FESTIVAL in _name(sid).lower() or _FESTIVAL in _text(sid))

    def hand_ids(self):
        return [c.get("id") for c in self.hand if isinstance(c, dict)]

    def discard_ids(self):
        return [c.get("id") for c in (self.me.get("discard") or []) if isinstance(c, dict)]

    def prize_left(self):
        return len(self.me.get("prize") or [])

    def op_prize_left(self):
        return len(self.op.get("prize") or [])

    def bench_slots(self):
        try:
            return max(0, int(self.me.get("benchMax") or 5) - len(self.my_bench()))
        except Exception:
            return max(0, 5 - len(self.my_bench()))

    # -- hand / deck belief ---------------------------------------------
    def known_counts(self):
        """Multiset of our cards not visible in hand/discard/in play.

        This still includes the six prizes, so it is an upper bound on the
        deck; when ``sel.deck`` is revealed we use the exact list instead.
        """
        counts = {}
        for cid in DECK:
            counts[cid] = counts.get(cid, 0) + 1
        seen = list(self.hand_ids()) + self.discard_ids()
        for p in self.in_play(self.me):
            seen.append(p.get("id"))
        for cid in seen:
            if counts.get(cid, 0) > 0:
                counts[cid] -= 1
        return {k: v for k, v in counts.items() if v > 0}

    def remaining_deck_ids(self):
        d = self.deck_cards()
        if d:
            out = []
            for c in d:
                if isinstance(c, dict) and c.get("playerIndex", self.yi) == self.yi:
                    out.append(c.get("id"))
            if out:
                return out
        out = []
        for cid, n in self.known_counts().items():
            out.extend([cid] * n)
        return out

    def has_card_in_deck(self, predicate) -> bool:
        for cid in self.remaining_deck_ids():
            if predicate(cid):
                return True
        return False


# ---------------------------------------------------------------------------
# Energy / attack math
# ---------------------------------------------------------------------------


def _can_pay(cost, energies) -> bool:
    if len(cost) > len(energies):
        return False
    pool = list(energies)
    for need in cost:
        if not pool:
            return False
        if need == 0:
            pool.pop(0)
            continue
        if need in pool:
            pool.remove(need)
        elif 10 in pool:  # rainbow
            pool.remove(10)
        elif 11 in pool and need in (5, 7):  # team rocket
            pool.remove(11)
        else:
            return False
    return True


def _attack_info(aid):
    try:
        return ATT.get(int(aid))
    except Exception:
        return None


def _damage_estimate(attacker_id, info, defender_id, attacker, bench_n, hand_n, opp_side) -> int:
    """Expected damage of `info` from `attacker_id` into `defender_id`.

    Only modifiers we can read from card data are modelled: scaling text
    (bench / energy / hand), Brave-Bangle style flat bonuses, weakness and
    resistance.  Unknown text falls back to the printed damage.
    """
    cost, base, text = info
    t = (text or "").lower()
    dmg = base
    if "for each" in t:
        n = _first_int(t)
        if n and "benched" in t:
            dmg = n * bench_n
        elif n and "energy attached to this" in t:
            dmg = n * len(attacker.get("energies") or [])
        elif n and "card in your hand" in t:
            dmg = n * hand_n
        elif n and "energy attached to all" in t:
            dmg = n * len(attacker.get("energies") or [])
    elif "for each of your benched" in t:
        dmg = _first_int(t) * bench_n

    # Flat tool bonuses, e.g. Brave Bangle (+30 vs ex, no Rule Box attacker).
    attacker_card = _card(attacker_id) or {}
    for tool in attacker.get("tools") or []:
        tid = tool.get("id") if isinstance(tool, dict) else tool
        ttext = _text(tid)
        if "more damage" in ttext and "ex" in ttext:
            if _is_ex(defender_id) and not attacker_card.get("ex") and not attacker_card.get("mega"):
                bonus = _first_int(ttext) or 30
                dmg += bonus

    if dmg <= 0:
        return 0
    if "don\u2019t apply weakness and resistance" in t and "benched" in t:
        # Snipe attacks: the options tell us the target later; keep nominal.
        pass
    ac = _card(attacker_id) or {}
    dc = _card(defender_id) or {}
    etype = int(ac.get("et") or 0)
    if etype and dc.get("w") is not None and int(dc.get("w")) == etype:
        dmg *= 2
    if etype and dc.get("r") is not None and int(dc.get("r")) == etype:
        dmg -= 30
    return max(0, int(dmg))


def _best_affordable(view: View, p, defender_id, owner=0):
    """(damage, attack_id, cost_len) for the best attack payable right now."""
    if not isinstance(p, dict):
        return (0, None, 0)
    cid = p.get("id")
    c = _card(cid)
    if not c or not c.get("a"):
        return (0, None, 0)
    energies = p.get("energies") or []
    bench_n = len(view.my_bench()) if owner == 0 else len(view.op_bench())
    hand_n = len(view.hand) if owner == 0 else int(view.op.get("handCount") or 0)
    best = (0, None, 0)
    for a in c.get("a") or []:
        try:
            aid = int(a[0])
            cost = tuple(int(x) for x in (a[1] or []))
            base = int(a[2] or 0)
            text = str(a[3] or "")
        except Exception:
            continue
        if not _can_pay(cost, energies):
            continue
        dmg = _damage_estimate(cid, (cost, base, text), defender_id, p, bench_n, hand_n, owner == 1)
        if dmg > best[0]:
            best = (dmg, aid, len(cost))
    return best


def _max_damage_potential(view: View, p, defender_id, owner=0, extra_energy=1):
    """Best damage if the attacker got one extra (wildcard) energy."""
    if not isinstance(p, dict):
        return 0
    c = _card(p.get("id"))
    if not c or not c.get("a"):
        return 0
    energies = list(p.get("energies") or [])
    best = _best_affordable(view, p, defender_id, owner)[0]
    # try each energy type that appears in a cost (cheap: <= 10 attempts)
    types = set()
    for a in c.get("a") or []:
        for e in (a[1] or []):
            types.add(int(e))
    for t in types:
        p2 = dict(p)
        p2["energies"] = energies + [t]
        d = _best_affordable(view, p2, defender_id, owner)[0]
        if d > best:
            best = d
    return best


def _is_doomed(view: View, p, owner=0) -> bool:
    """True when the opposing active can KO `p` (with one extra energy)."""
    if not isinstance(p, dict):
        return True
    hp = int(p.get("hp") or 0)
    if hp <= 0:
        return True
    if owner == 0:
        attacker = view.op_active()
        defender_id = p.get("id")
        dmg = _max_damage_potential(view, attacker, defender_id, owner=1, extra_energy=1)
    else:
        attacker = view.my_active()
        defender_id = p.get("id")
        dmg = _max_damage_potential(view, attacker, defender_id, owner=0, extra_energy=1)
    return dmg >= hp


def _prize_value(cid) -> int:
    return 2 if _is_ex(cid) else 1


# ---------------------------------------------------------------------------
# Card value models
# ---------------------------------------------------------------------------


def _evo_cards_for(view: View, pokemon_id):
    """Evolution cards that can evolve `pokemon_id` (from hand + deck belief)."""
    nm = _name(pokemon_id)
    if not nm:
        return []
    out = []
    for cid in view.hand_ids():
        c = _card(cid)
        if c and c.get("ef") == nm:
            out.append((cid, "hand"))
    for cid in view.remaining_deck_ids():
        c = _card(cid)
        if c and c.get("ef") == nm:
            out.append((cid, "deck"))
    return out


def _evolution_needed(view: View) -> int:
    """How many in-play Pokémon have an evolution available in hand/deck."""
    n = 0
    for p in view.in_play(view.me):
        if _evo_cards_for(view, p.get("id")):
            n += 1
    return n


def _unenergized_attackers(view: View) -> int:
    n = 0
    for p in view.in_play(view.me):
        c = _card(p.get("id"))
        if not c or not c.get("a"):
            continue
        if not (p.get("energies") or []):
            n += 1
    return n


def _energy_in_hand(view: View) -> int:
    return sum(1 for cid in view.hand_ids() if _is_energy(cid))


def _has_festival_line(view: View) -> bool:
    for p in view.in_play(view.me):
        if "festival lead" in _skill_names(p.get("id")):
            return True
    for cid in view.hand_ids():
        if "festival lead" in _skill_names(cid):
            return True
    return False


def _festival_in_deck(view: View) -> bool:
    return view.has_card_in_deck(lambda cid: "festival lead" in _skill_names(cid))


def _card_utility(view: View, cid, for_search=True) -> float:
    """Rough value of a card to us right now (higher = keep / pick)."""
    c = _card(cid)
    if not c:
        return 50.0
    t = c.get("t", -1)
    if t == T_POKEMON:
        hp = float(c.get("hp") or 0)
        val = 90.0 + hp * 0.7
        if c.get("b"):
            if view.bench_slots() > 0:
                val += 110.0
            evos = _evo_cards_for(view, cid)
            if any(src == "hand" for _, src in evos):
                val += 130.0
            elif evos:
                val += 60.0
        else:
            nm = str(c.get("n") or "")
            pre_in_play = any(_name(p.get("id")) == c.get("ef") for p in view.in_play(view.me))
            if pre_in_play:
                val += 230.0
            elif any(_name(h) == c.get("ef") for h in view.hand_ids()):
                val += 120.0
        if c.get("ex") or c.get("mega"):
            val += 70.0
        # attacks are worth something even without energy
        for a in c.get("a") or []:
            val += min(80.0, float(a[2] or 0) * 0.5)
        if "festival lead" in _skill_names(cid):
            val += 60.0
        return val
    if t in (T_BASIC_ENERGY, T_SPECIAL_ENERGY):
        val = 65.0
        if _unenergized_attackers(view) > 0:
            val += 110.0
        if view.hand and len(view.hand) <= 4:
            val += 25.0
        return val
    if t == T_SUPPORTER:
        val = 110.0
        if not view.cur.get("supporterPlayed"):
            val += 90.0
        if len(view.hand) <= 5:
            val += 40.0
        return val
    if t == T_STADIUM:
        val = 95.0
        if _FESTIVAL in _name(cid).lower() or _FESTIVAL in _text(cid):
            if not view.stadium_is_festival():
                val += 240.0
        return val
    if t == T_ITEM:
        text = _text(cid)
        val = 90.0
        if "search your deck" in text or "look at the top" in text:
            val += 70.0
        if "draw" in text:
            val += 30.0
        return val
    if t == T_TOOL:
        val = 75.0
        if "more damage" in _text(cid):
            val += 45.0
        return val
    return 60.0


def _search_pick_value(view: View, cid) -> float:
    """Value of a card in a deck-search / reveal-to-hand prompt.

    Priority order (from replay divergence mining): missing evolution piece,
    draw/search engine, energy for an unpowered attacker, then win conditions.
    """
    if cid is None:
        return 20.0
    c = _card(cid)
    if not c:
        return 40.0
    v = _card_utility(view, cid)
    t = c.get("t", -1)
    if t == T_POKEMON:
        pre_in_play = any(_name(p.get("id")) == c.get("ef") for p in view.in_play(view.me))
        if c.get("ef") and pre_in_play:
            v += 260.0  # the missing evolution piece, usable immediately
            if "festival lead" in _skill_names(cid):
                v += 60.0
            if c.get("s2"):
                v += 40.0
        elif c.get("b"):
            evos = _evo_cards_for(view, cid)
            if any(src == "hand" for _, src in evos):
                v += 100.0
            if view.bench_slots() > 0:
                v += 40.0
        else:
            # Evolution card with no pre-evolution in play/hand is not usable yet.
            if not pre_in_play and not any(_name(h) == c.get("ef") for h in view.hand_ids()):
                v -= 60.0
        if c.get("ex") or c.get("mega"):
            v += 40.0
        if "festival lead" in _skill_names(cid):
            v += 80.0
    elif t == T_SUPPORTER:
        text = _text(cid)
        if not view.cur.get("supporterPlayed") and ("draw" in text or "shuffle your hand" in text):
            v += 120.0 if len(view.hand) <= 5 else 30.0
        if "search your deck" in text:
            v += 80.0
    elif t == T_ITEM:
        text = _text(cid)
        if "search your deck" in text or "look at the top" in text:
            v += 70.0
        if "draw" in text:
            v += 30.0
    elif t in (T_BASIC_ENERGY, T_SPECIAL_ENERGY):
        if _unenergized_attackers(view) > 0:
            v += 100.0
        if _energy_in_hand(view) == 0:
            v += 30.0
    elif t == T_STADIUM:
        if _FESTIVAL in _name(cid).lower() and not view.stadium_is_festival():
            v += 150.0
    return v


def _supporter_score(view: View, cid) -> float:
    text = _text(cid)
    if "shuffle your hand into your deck" in text:
        hand = len(view.hand)
        if hand <= 3:
            score = 820.0
        elif hand <= 5:
            score = 680.0
        elif hand <= 7:
            score = 460.0
        else:
            score = 300.0
        if view.prize_left() == 6:
            score += 120.0
        # Lillie removes our hand: discount key evolution pieces.
        evo_hand = sum(1 for h in view.hand_ids() if _attr(h, "s1", 0) or _attr(h, "s2", 0))
        return score - 45.0 * evo_hand
    if "until they have 3 cards" in text:
        return 620.0 if int(view.op.get("handCount") or 0) >= 5 else 150.0
    if "search your deck for a basic pok" in text and "stage 2" in text:
        return 720.0 if _evolution_needed(view) >= 2 else 360.0
    if "draw" in text:
        return 520.0
    return 420.0


def _item_score(view: View, cid) -> float:
    text = _text(cid)
    if "search your deck" in text:
        if "up to 2 basic pok" in text:
            ok = view.bench_slots() > 0 and view.has_card_in_deck(
                lambda c: _is_pokemon(c) and _is_basic(c) and int(_attr(c, "hp", 999)) <= 70
            )
            return 720.0 if ok else 110.0
        if "doesn\u2019t have a rule box" in text or "doesn't have a rule box" in text:
            useful = view.bench_slots() > 0 or _evolution_needed(view) > 0 or _unenergized_attackers(view) > 0
            return 620.0 if useful else 320.0
        if "basic pok" in text and "stage 1" in text and "stage 2" in text:
            return 660.0 if _evolution_needed(view) >= 2 else 330.0
        return 520.0
    if "look at the top" in text:
        if "supporter" in text:
            if view.cur.get("supporterPlayed"):
                return 120.0
            sup_in_hand = any(_ctype(h) == T_SUPPORTER for h in view.hand_ids())
            return 520.0 if not sup_in_hand else 240.0
        if "{g}" in text:
            return 680.0 if (view.bench_slots() > 0 or _unenergized_attackers(view) > 0) else 300.0
        return 420.0
    if "from your discard pile into your hand" in text:
        useful = any(_is_pokemon(c) or _is_energy(c) for c in view.discard_ids())
        return 520.0 if useful else 120.0
    if "shuffle up to" in text and "from your discard" in text:
        mons = sum(1 for c in view.discard_ids() if _is_pokemon(c))
        return 330.0 if mons >= 2 else 110.0
    if "tools" in text and "discard" in text:
        opp_tools = any(p.get("tools") for p in view.in_play(view.op))
        return 300.0 if opp_tools else 70.0
    if "shuffles their hand into their deck" in text:
        return 620.0 if len(view.hand) <= 4 and int(view.op.get("handCount") or 0) >= 4 else 300.0
    if "draw" in text:
        return 430.0
    return 330.0


def _tool_score(view: View, cid) -> float:
    text = _text(cid)
    if "more damage" in text and "ex" in text:
        opp = view.op_active()
        attacker = view.my_active()
        if opp and _is_ex(opp.get("id")) and attacker and not _is_ex(attacker.get("id")):
            return 650.0
        return 170.0
    return 260.0


def _stadium_score(view: View, cid) -> float:
    name = _name(cid).lower()
    if _FESTIVAL in name or _FESTIVAL in _text(cid):
        if view.stadium_is_festival():
            return 40.0
        return 1000.0
    return 320.0 if not view.stadium else 240.0


def _ability_score(view: View, opt) -> float:
    p = _option_pokemon(view, opt)
    cid = p.get("id") if p else _option_card_id(view, opt)
    names = _skill_names(cid)
    if "flip the script" in names:
        return 660.0 if _recent_self_ko(view) else 120.0
    if "boom boom groove" in names:
        act = view.my_active()
        return 620.0 if act and "festival lead" in _skill_names(act.get("id")) else 80.0
    text = _text(cid)
    if "you may" in text and "discard" in text:
        return 300.0
    return 500.0


def _recent_self_ko(view: View) -> bool:
    for lg in view.logs[-40:]:
        try:
            if (
                int(lg.get("type", -1)) == 6
                and int(lg.get("playerIndex", -1)) == view.yi
                and int(lg.get("fromArea", -1)) in (4, 5)
                and int(lg.get("toArea", -1)) == 3
            ):
                return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Option resolution
# ---------------------------------------------------------------------------


def _option_card_id(view: View, opt: dict):
    """Best-effort card id for an option (deck/hand/discard/play/looking)."""
    if not isinstance(opt, dict):
        return None
    area = opt.get("area")
    idx = opt.get("index", 0)
    owner = opt.get("playerIndex", view.yi)
    try:
        idx = int(idx)
        owner = int(owner)
    except Exception:
        idx = 0
        owner = view.yi
    if area == 1:  # deck (revealed list when the effect exposes it)
        d = view.deck_cards()
        if 0 <= idx < len(d) and isinstance(d[idx], dict):
            return d[idx].get("id")
        return None
    if area == 2:  # hand
        if owner == view.yi:
            c = view.card_in_hand(idx)
            return c.get("id") if c else None
        return None
    if area == 3:  # discard
        p = view.players[owner] if 0 <= owner < 2 else {}
        d = p.get("discard") or []
        if 0 <= idx < len(d) and isinstance(d[idx], dict):
            return d[idx].get("id")
        return None
    if area in (4, 5):  # active / bench
        p = view.players[owner] if 0 <= owner < 2 else {}
        pk = _option_pokemon(view, opt)
        return pk.get("id") if pk else None
    if area == 6:  # prize
        p = view.players[owner] if 0 <= owner < 2 else {}
        pr = p.get("prize") or []
        if 0 <= idx < len(pr) and isinstance(pr[idx], dict):
            return pr[idx].get("id")
        return None
    if area == 7:  # stadium
        sid = view.stadium_card()
        return sid
    if area == 9:  # tool on a pokemon
        pk = _option_pokemon(view, opt)
        ti = opt.get("toolIndex", 0)
        if pk:
            tools = pk.get("tools") or []
            if isinstance(ti, int) and 0 <= ti < len(tools) and isinstance(tools[ti], dict):
                return tools[ti].get("id")
        return None
    if area == 12:  # looking / revealed
        lk = view.looking_cards()
        if 0 <= idx < len(lk) and isinstance(lk[idx], dict):
            return lk[idx].get("id")
        return None
    if area == 8:  # attached energy
        pk = _option_pokemon(view, opt)
        ei = opt.get("energyIndex", 0)
        if pk:
            cards = pk.get("energyCards") or []
            if isinstance(ei, int) and 0 <= ei < len(cards) and isinstance(cards[ei], dict):
                return cards[ei].get("id")
            es = pk.get("energies") or []
            if isinstance(ei, int) and 0 <= ei < len(es):
                return es[ei]
    return opt.get("cardId")


def _option_pokemon(view: View, opt: dict):
    if not isinstance(opt, dict):
        return None
    area = opt.get("inPlayArea", opt.get("area"))
    idx = opt.get("inPlayIndex", opt.get("index", 0))
    owner = opt.get("playerIndex", view.yi)
    try:
        idx = int(idx)
        owner = int(owner)
    except Exception:
        return None
    if owner < 0 or owner > 1:
        owner = view.yi
    p = view.players[owner]
    if area == 4:
        a = p.get("active") or []
        return a[0] if a and isinstance(a[0], dict) else None
    if area == 5:
        b = p.get("bench") or []
        if 0 <= idx < len(b) and isinstance(b[idx], dict):
            return b[idx]
        return None
    return None


def _option_owner(view: View, opt: dict) -> int:
    try:
        return int(opt.get("playerIndex", view.yi))
    except Exception:
        return view.yi


# ---------------------------------------------------------------------------
# MAIN scoring
# ---------------------------------------------------------------------------


def _score_attack(view: View, opt: dict) -> float:
    aid = opt.get("attackId")
    info = _attack_info(aid)
    active = view.my_active()
    opp = view.op_active()
    if not info or not active:
        return 380.0
    cost, base, text = info
    t = (text or "").lower()
    bench_n = len(view.my_bench())
    dmg = _damage_estimate(
        active.get("id"), info, opp.get("id") if opp else None, active, bench_n, len(view.hand), False
    )
    if not opp:
        return 250.0
    opp_hp = int(opp.get("hp") or 0)
    if dmg > 0 and dmg >= opp_hp:
        score = 2600.0 + 320.0 * _prize_value(opp.get("id"))
        if view.prize_left() <= 2:
            score += 180.0
        if view.prize_left() <= 1:
            score += 3000.0  # this KO takes our last prize
        if not view.op_bench():
            score += 2000.0  # game win
        return score
    if dmg == 0:
        if "search your deck" in t or "draw" in t or "put" in t:
            return 300.0
        if "damage" in t and "to 1 of your opponent" in t:
            # fixed snipe: treat as useful chip
            return 320.0 + float(_first_int(t)) * 1.5
        return 40.0
    score = 280.0 + float(dmg) * 4.0
    if "for each of your benched" in t and bench_n < 3:
        score -= 120.0  # develop the bench first
    if dmg >= opp_hp * 0.7:
        score += 80.0
    if view.prize_left() < view.op_prize_left():
        score += 30.0  # ahead: keep the pressure
    # A non-lethal attack ends the turn.  Free development (attach, play,
    # evolve, ability) should happen first, so cap the attack below those.
    if score > 380.0:
        score = 380.0
    return score


def _score_evolve(view: View, opt: dict) -> float:
    cid = _option_card_id(view, opt)
    target = _option_pokemon(view, opt)
    if not cid:
        return 580.0
    c = _card(cid) or {}
    hp = int(c.get("hp") or 0)
    score = 690.0 + float(hp) * 0.8
    if c.get("s2"):
        score += 80.0
    if c.get("ex") or c.get("mega"):
        score += 40.0
    if target is view.my_active() or (target and view.my_active() and target.get("serial") == view.my_active().get("serial")):
        score += 130.0
        # Evolve the active Applin/attacker so it can attack immediately.
        for a in c.get("a") or []:
            if int(a[2] or 0) > 0:
                score += 60.0
                break
    if "festival lead" in _skill_names(cid):
        score += 180.0
        if not view.stadium_is_festival():
            score += 60.0
    if "boom boom groove" in _skill_names(cid):
        score += 70.0
    # Evolving a damaged Pokémon is fine (damage stays) but makes it a target.
    if target is not None:
        try:
            dmg = int(target.get("maxHp") or 0) - int(target.get("hp") or 0)
            score -= dmg * 0.4
        except Exception:
            pass
    return score


def _energy_attach_value(view: View, cid, target) -> float:
    """Value of attaching energy `cid` to `target` (negative = waste)."""
    if not isinstance(target, dict) or not _is_pokemon(target.get("id")):
        return -200.0
    c = _card(target.get("id")) or {}
    attacks = c.get("a") or []
    if not attacks:
        return 20.0
    energies = list(target.get("energies") or [])
    etype = _energy_type(cid)
    after = energies + [etype]
    opp = view.op_active()
    did = opp.get("id") if opp else None
    bench_n = len(view.my_bench())
    hand_n = len(view.hand)

    def best(energy_list):
        out = (0, None, 0)
        for a in attacks:
            try:
                cost = tuple(int(x) for x in (a[1] or []))
                base = int(a[2] or 0)
                text = str(a[3] or "")
            except Exception:
                continue
            if not _can_pay(cost, energy_list):
                continue
            d = _damage_estimate(target.get("id"), (cost, base, text), did, target, bench_n, hand_n, False)
            if d > out[0] or (d == out[0] and len(cost) > out[2]):
                out = (d, a[0], len(cost))
        return out

    now = best(energies)
    aft = best(after)
    # Best printed attack (the "chosen" attack for overfill purposes).
    chosen_len = 0
    for a in attacks:
        chosen_len = max(chosen_len, len(a[1] or []))
    if len(energies) >= chosen_len and now[0] >= aft[0]:
        # Already over/at the chosen attack's cost.
        base = -520.0 if len(energies) > 0 else -80.0
    elif aft[0] > now[0]:
        base = 480.0 + float(aft[0] - now[0]) * 3.2
    elif len(energies) < chosen_len:
        base = 210.0 + 30.0 * (chosen_len - len(energies))
    else:
        base = 40.0

    active = view.my_active()
    is_active = active is not None and target.get("serial") == active.get("serial")
    if is_active:
        if _is_doomed(view, target, owner=0):
            base -= 150.0
        else:
            base += 80.0
    else:
        # Developing a benched future attacker is good, but below active.
        base -= 40.0
        if target.get("appearThisTurn"):
            base -= 20.0
    # Do not invest in a benched Pokémon that cannot evolve and cannot attack.
    if not is_active and not _evo_cards_for(view, target.get("id")) and not c.get("a"):
        base -= 80.0
    return base


def _score_attach(view: View, opt: dict) -> float:
    if view.cur.get("energyAttached"):
        return -540.0
    cid = _option_card_id(view, opt)
    target = _option_pokemon(view, opt)
    if not cid:
        return 200.0
    if not _is_energy(cid):
        # Tool / other attached card: prefer an attacker, especially active.
        score = _tool_score(view, cid)
        p = target
        if isinstance(p, dict):
            c = _card(p.get("id")) or {}
            if "more damage" in _text(cid):
                if view.my_active() is p:
                    score += 130.0
                if c.get("a"):
                    score += 40.0
                if not (c.get("ex") or c.get("mega")):
                    score += 30.0
            else:
                score += _battle_value(view, p, owner=0) * 0.15
        return score
    return _energy_attach_value(view, cid, target)


def _score_play(view: View, opt: dict) -> float:
    cid = _option_card_id(view, opt)
    if cid is None:
        return 220.0
    t = _ctype(cid)
    if t == T_POKEMON:
        c = _card(cid) or {}
        if not c.get("b"):
            # Engine normally offers EVOLVE, but be tolerant.
            return 500.0
        if view.bench_slots() <= 0:
            return 20.0
        score = 360.0 + float(c.get("hp") or 0) * 0.45
        evos = _evo_cards_for(view, cid)
        if any(src == "hand" for _, src in evos):
            score += 140.0
        elif evos:
            score += 70.0
        if view.bench_slots() >= 2:
            score += 90.0
        if "festival lead" in _skill_names(cid):
            score += 40.0
        return score
    if t == T_ITEM:
        return _item_score(view, cid)
    if t == T_TOOL:
        return _tool_score(view, cid)
    if t == T_SUPPORTER:
        if view.cur.get("supporterPlayed"):
            return -540.0
        return _supporter_score(view, cid)
    if t == T_STADIUM:
        if view.cur.get("stadiumPlayed"):
            return -540.0
        return _stadium_score(view, cid)
    if t in (T_BASIC_ENERGY, T_SPECIAL_ENERGY):
        return 180.0
    return 250.0


def _battle_value(view: View, p, owner=0) -> float:
    if not isinstance(p, dict):
        return -999.0
    cid = p.get("id")
    c = _card(cid) or {}
    hp = float(p.get("hp") or 0)
    opp = view.op_active() if owner == 0 else view.my_active()
    dmg = _best_affordable(view, p, opp.get("id") if opp else None, owner=owner)[0]
    val = hp * 0.55 + float(dmg) * 1.9 + len(p.get("energies") or []) * 24.0
    if c.get("ex") or c.get("mega"):
        val += 40.0
    if owner == 0 and view.my_active() is p:
        val += 25.0
    if owner == 1:
        val += 90.0 * _prize_value(cid)
        val += float(dmg) * 0.5
    return val


def _score_retreat(view: View, opt: dict) -> float:
    if view.cur.get("retreated"):
        return -700.0
    active = view.my_active()
    bench = view.my_bench()
    if not active or not bench:
        return -700.0
    best = max(bench, key=lambda p: _battle_value(view, p, owner=0))
    ready = _best_affordable(view, best, view.op_active().get("id") if view.op_active() else None, 0)[0]
    active_val = _battle_value(view, active, owner=0)
    best_val = _battle_value(view, best, owner=0)
    doomed = _is_doomed(view, active, owner=0)
    status = any(view.me.get(s) for s in ("asleep", "paralyzed", "confused", "burned"))
    if (doomed or status) and best_val > active_val + 20:
        # Retreating needs energy on the active; if it cannot pay, skip.
        rc = int(_attr(active.get("id"), "rc", 0) or 0)
        if len(active.get("energies") or []) >= rc and ready > 0:
            return 760.0 + min(200.0, ready * 1.5)
        return 120.0
    if ready > 0 and active_val + 60 < best_val:
        return 150.0
    return -700.0


def _score_main(view: View, opt: dict) -> float:
    t = opt.get("type")
    if t == OPT_ATTACK:
        return _score_attack(view, opt)
    if t == OPT_EVOLVE:
        return _score_evolve(view, opt)
    if t == OPT_ATTACH:
        return _score_attach(view, opt)
    if t == OPT_PLAY:
        return _score_play(view, opt)
    if t == OPT_ABILITY:
        return _ability_score(view, opt)
    if t == OPT_RETREAT:
        return _score_retreat(view, opt)
    if t == OPT_DISCARD:
        return -420.0
    if t == OPT_END:
        return -50.0
    return 60.0


# ---------------------------------------------------------------------------
# Sub-selection scoring
# ---------------------------------------------------------------------------


def _setup_active_value(view: View, cid) -> float:
    if not _is_pokemon(cid) or not _is_basic(cid):
        return -100.0
    c = _card(cid) or {}
    hp = float(c.get("hp") or 0)
    val = hp * 1.15 + 40.0
    evos = _evo_cards_for(view, cid)
    if any(src == "hand" for _, src in evos):
        val += 190.0
    elif evos:
        val += 110.0
    for a in c.get("a") or []:
        cost = a[1] or []
        if len(cost) == 0:
            val += 55.0  # free attack
        elif int(a[2] or 0) >= 30 and len(cost) <= 1:
            val += 35.0
    if "festival lead" in _skill_names(cid):
        val += 50.0
    if c.get("ex") or c.get("mega"):
        val += 30.0
    return val


def _bench_dev_value(view: View, cid) -> float:
    c = _card(cid) or {}
    if not _is_pokemon(cid) or not _is_basic(cid):
        return -50.0
    val = 60.0 + float(c.get("hp") or 0) * 0.9
    evos = _evo_cards_for(view, cid)
    if any(src == "hand" for _, src in evos):
        val += 150.0
    elif evos:
        val += 80.0
    if c.get("ex") or c.get("mega"):
        val += 50.0
    if "festival lead" in _skill_names(cid):
        val += 60.0
    for a in c.get("a") or []:
        val += min(50.0, float(a[2] or 0) * 0.6)
    return val


def _damage_target_value(view: View, opt: dict, dmg: int) -> float:
    p = _option_pokemon(view, opt)
    if not p:
        return -50.0
    owner = _option_owner(view, opt)
    cid = p.get("id")
    hp = int(p.get("hp") or 0)
    maxhp = int(p.get("maxHp") or hp)
    if owner != view.yi:
        val = 90.0 * _prize_value(cid) + float(maxhp - hp)
        if dmg > 0 and dmg >= hp:
            val += 1200.0 + 260.0 * _prize_value(cid)
        else:
            val += min(float(dmg), float(hp)) * 2.2
        val += float(_best_affordable(view, p, view.my_active().get("id") if view.my_active() else None, owner=1)[0]) * 0.5
        return val
    # Our Pokémon: used for "remove damage" (want damaged/high value) or for
    # choosing a victim (want low value).
    val = float(maxhp - hp) * 1.4 + 40.0 * _prize_value(cid)
    if view.my_active() is p:
        val += 40.0
    return val


def _discard_value(view: View, opt: dict, duplicate: bool) -> float:
    cid = _option_card_id(view, opt)
    if cid is None:
        return 40.0
    val = _card_utility(view, cid, for_search=False)
    t = _ctype(cid)
    if t == T_POKEMON:
        if _attr(cid, "s1", 0) or _attr(cid, "s2", 0):
            nm = _name(cid)
            if any(_name(p.get("id")) == (_attr(cid, "ef") or "") for p in view.in_play(view.me)):
                val += 80.0
        if "festival lead" in _skill_names(cid):
            val += 90.0
    if t in (T_BASIC_ENERGY, T_SPECIAL_ENERGY):
        if len(view.in_play(view.me)) <= 2:
            val += 30.0
    if duplicate:
        val -= 55.0
    return val


def _discard_energy_cost(view: View, opt: dict) -> float:
    """Cost of losing the energy selected by `opt` (lower = discard it)."""
    p = _option_pokemon(view, opt)
    if not p:
        return 0.0
    eidx = opt.get("energyIndex", 0)
    try:
        eidx = int(eidx)
    except Exception:
        eidx = 0
    etype = None
    cards = p.get("energyCards") or []
    if 0 <= eidx < len(cards) and isinstance(cards[eidx], dict):
        cid = cards[eidx].get("id")
        etype = _energy_type(cid)
    if etype is None:
        es = p.get("energies") or []
        if 0 <= eidx < len(es):
            etype = int(es[eidx])
    if etype is None:
        etype = 0
    owner = _option_owner(view, opt)
    c = _card(p.get("id")) or {}
    attacks = c.get("a") or []
    energies = list(p.get("energies") or [])
    after = list(energies)
    try:
        after.remove(etype)
    except ValueError:
        pass
    opp = view.op_active() if owner == view.yi else view.my_active()
    did = opp.get("id") if opp else None
    before_best = _best_affordable(view, p, did, owner=0 if owner == view.yi else 1)[0]
    p2 = dict(p)
    p2["energies"] = after
    after_best = _best_affordable(view, p2, did, owner=0 if owner == view.yi else 1)[0]
    cost = 60.0
    if before_best > after_best:
        cost += 500.0 + float(before_best - after_best) * 2.0
    if owner == view.yi:
        if view.my_active() is p:
            cost += 120.0
        if _is_doomed(view, p, owner=0):
            cost -= 80.0
    else:
        # Removing an opponent energy is valuable.
        cost = -cost - float(before_best) * 2.0
    return cost


def _attach_select_value(view: View, opt: dict) -> float:
    p = _option_pokemon(view, opt)
    if p:
        cid = p.get("id")
        c = _card(cid) or {}
        if not c.get("a"):
            return 20.0
        energies = p.get("energies") or []
        opp = view.op_active()
        dmg = _best_affordable(view, p, opp.get("id") if opp else None, owner=0)[0]
        val = 160.0 + (90.0 if not energies else 0.0)
        if view.my_active() is p:
            val += 90.0
            if _is_doomed(view, p, owner=0):
                val -= 150.0
        if _evo_cards_for(view, cid):
            val += 40.0
        if dmg == 0 and not c.get("a"):
            val -= 50.0
        return val
    cid = _option_card_id(view, opt)
    if cid is None:
        return 30.0
    val = _card_utility(view, cid)
    if _is_energy(cid):
        val = 120.0 + (80.0 if _unenergized_attackers(view) > 0 else 0.0)
    return val


def _context_values(view: View, ctx: int):
    """Return (indices, ascending?, count) for a non-MAIN card context."""
    n = len(view.sel.get("option") or [])
    lo = _min_count(view.sel, n)
    hi = _max_count(view.sel, n)
    opts = view.sel.get("option") or []
    ids = [_option_card_id(view, o) for o in opts]

    if ctx == C_SETUP_ACTIVE:
        vals = [_setup_active_value(view, cid) if cid else 0.0 for cid in ids]
        return vals, False, max(1, min(hi, lo or 1))
    if ctx == C_SETUP_BENCH:
        slots = max(1, view.bench_slots())
        k = min(hi, n, slots)
        vals = [_bench_dev_value(view, cid) if cid else 0.0 for cid in ids]
        return vals, False, max(lo, k)
    if ctx == C_TO_BENCH:
        slots = max(0, view.bench_slots())
        k = min(hi, n, slots) if slots else lo
        vals = [_bench_dev_value(view, cid) if cid else 0.0 for cid in ids]
        return vals, False, max(lo, k)
    if ctx == C_TO_HAND:
        k = max(lo, min(hi, n))
        vals = [_search_pick_value(view, cid) if cid else 20.0 for cid in ids]
        return vals, False, k
    if ctx == C_DISCARD:
        k = max(lo, min(hi, n))
        hand_ids = view.hand_ids()
        vals = []
        for cid in ids:
            dup = cid is not None and hand_ids.count(cid) > 1
            vals.append(_discard_value(view, opts[len(vals)], dup))
        return vals, True, k
    if ctx == C_TO_DECK:
        k = max(lo, min(hi, n))
        vals = [_card_utility(view, cid) if cid else 0.0 for cid in ids]
        return vals, False, k
    if ctx == C_TO_DECK_BOTTOM:
        k = max(lo, min(hi, n))
        vals = [_card_utility(view, cid) if cid else 0.0 for cid in ids]
        return vals, True, k
    if ctx == C_TO_PRIZE:
        k = max(lo, min(hi, n))
        vals = [_card_utility(view, cid) if cid else 0.0 for cid in ids]
        return vals, True, k
    if ctx in (C_DAMAGE_COUNTER, C_DAMAGE_COUNTER_ANY, C_DAMAGE):
        k = max(lo, 1)
        dmg = 0
        try:
            dmg = int(view.sel.get("remainDamageCounter") or 0) * 10
        except Exception:
            dmg = 0
        if dmg <= 0:
            dmg = 60 if ctx == C_DAMAGE else 30
        vals = [_damage_target_value(view, o, dmg) for o in opts]
        return vals, False, k
    if ctx in (C_HEAL, 16):  # heal / remove damage counter
        k = max(lo, min(hi, n))
        vals = [_damage_target_value(view, o, 0) for o in opts]
        return vals, False, k
    if ctx == C_ATTACH_FROM:
        k = max(lo, 1)
        vals = []
        for o in opts:
            p = _option_pokemon(view, o)
            if p:
                vals.append(-_discard_energy_cost(view, o))
            else:
                cid = _option_card_id(view, o)
                vals.append(-(_card_utility(view, cid) if cid else 0.0))
        return vals, False, k
    if ctx == C_ATTACH_TO:
        k = max(lo, min(hi, n))
        vals = [_attach_select_value(view, o) for o in opts]
        return vals, False, k
    if ctx == C_DISCARD_TOOL:
        vals = []
        for o in opts:
            owner = _option_owner(view, o)
            p = _option_pokemon(view, o)
            tool_id = None
            ti = o.get("toolIndex", 0)
            if p:
                tools = p.get("tools") or []
                try:
                    ti = int(ti)
                    if 0 <= ti < len(tools) and isinstance(tools[ti], dict):
                        tool_id = tools[ti].get("id")
                except Exception:
                    tool_id = None
            tv = _card_utility(view, tool_id) if tool_id else 60.0
            if owner != view.yi:
                vals.append(1000.0 + tv)  # remove their tool first
            else:
                vals.append(-tv)  # remove our least useful tool
        k = max(lo, min(hi, n))
        return vals, False, k
    if ctx == C_DISCARD_ENERGY:
        k = max(lo, min(hi, n))
        vals = [_discard_energy_cost(view, o) for o in opts]
        return vals, True, k
    if ctx in (25, 26, 33):  # other attached-energy selections
        k = max(lo, min(hi, n))
        vals = [_discard_energy_cost(view, o) for o in opts]
        return vals, True, k
    return None


# ---------------------------------------------------------------------------
# Selection entry points
# ---------------------------------------------------------------------------


def _min_count(sel: dict, n: int) -> int:
    try:
        lo = int(sel.get("minCount") or 0)
    except Exception:
        lo = 0
    return max(0, min(lo, n))


def _max_count(sel: dict, n: int) -> int:
    try:
        hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
    except Exception:
        hi = 1
    hi = max(0, min(hi, n))
    return max(hi, _min_count(sel, n))


def _rank_action(vals, indices, ascending, k):
    order = sorted(indices, key=lambda i: (vals[i] if ascending else -vals[i]))
    out = order[:k]
    if len(out) < k:
        for i in indices:
            if i not in out:
                out.append(i)
                if len(out) >= k:
                    break
    return out


def _choose_by_values(view: View, vals, ascending, k):
    n = len(vals)
    if n == 0:
        return []
    k = max(0, min(int(k), n))
    return sorted(
        range(n),
        key=lambda i: ((vals[i] if ascending else -vals[i]), i),
    )[:k]


def _effect_text(view: View) -> str:
    cid = None
    eff = view.sel.get("effect")
    if isinstance(eff, dict):
        cid = eff.get("id")
    if cid is None:
        cc = view.sel.get("contextCard")
        if isinstance(cc, dict):
            cid = cc.get("id")
    if cid is None:
        for lg in reversed(view.logs[-20:]):
            if isinstance(lg, dict) and lg.get("cardId"):
                cid = lg.get("cardId")
                break
    if cid is None:
        return ""
    return _text(cid)


def _choose_attack_select(view: View, opts) -> list[int]:
    lo = _min_count(view.sel, len(opts))
    best_i, best_s = -1, -1e9
    for i, o in enumerate(opts):
        aid = o.get("attackId") if isinstance(o, dict) else None
        info = _attack_info(aid)
        if not info:
            s = 100.0
        else:
            # Reuse MAIN attack scoring by synthesising a MAIN-like option.
            s = _score_attack(view, {"type": OPT_ATTACK, "attackId": aid})
        if s > best_s:
            best_s, best_i = s, i
    if best_i < 0:
        return []
    if lo == 0 and best_s < 120.0:
        return []
    return [best_i]


def _choose_yes_no(view: View, opts) -> list[int]:
    # Prefer an explicit YES option; otherwise the first option.
    for i, o in enumerate(opts):
        if isinstance(o, dict) and o.get("type") == OPT_YES:
            return [i]
    return [0]


def _choose_count(view: View, opts) -> list[int]:
    nums = []
    for i, o in enumerate(opts):
        v = o.get("number") if isinstance(o, dict) else None
        try:
            nums.append((i, int(v)))
        except Exception:
            nums.append((i, i))
    text = _effect_text(view)
    want_max = True
    if "discard" in text and "up to" in text and "damage" not in text:
        want_max = False
    if "remove" in text or "heal" in text or "draw" in text or "damage" in text:
        want_max = True
    pick = max(nums, key=lambda x: x[1]) if want_max else min(nums, key=lambda x: x[1])
    return [pick[0]]


def _choose_special(view: View, opts) -> list[int]:
    # Special-condition choices: take the required number, preferring later
    # (engine orders the harsher conditions later in practice).
    n = len(opts)
    lo = _min_count(view.sel, n)
    hi = _max_count(view.sel, n)
    k = max(lo, min(hi, n))
    return list(range(min(k, n)))


def _choose_evolve_select(view: View, opts) -> list[int]:
    vals = []
    for o in opts:
        cid = _option_card_id(view, o)
        target = _option_pokemon(view, o)
        v = 500.0
        if cid:
            c = _card(cid) or {}
            v += float(c.get("hp") or 0) * 0.8
            if "festival lead" in _skill_names(cid):
                v += 150.0
            if target is view.my_active() or (
                target and view.my_active() and target.get("serial") == view.my_active().get("serial")
            ):
                v += 120.0
        vals.append(v)
    return _choose_by_values(view, vals, False, _min_count(view.sel, len(opts)) or 1)


def _choose_card_context(view: View, ctx: int, opts) -> list[int]:
    n = len(opts)
    lo = _min_count(view.sel, n)
    hi = _max_count(view.sel, n)
    if n == 0:
        return []
    # Explicit contexts with bespoke ranking.
    if ctx == C_SETUP_ACTIVE:
        vals = []
        for o in opts:
            cid = _option_card_id(view, o)
            vals.append(_setup_active_value(view, cid) if cid else 0.0)
        return _choose_by_values(view, vals, False, 1)
    if ctx == C_SWITCH or ctx == C_TO_ACTIVE:
        owner = _option_owner(view, opts[0])
        vals = []
        for o in opts:
            p = _option_pokemon(view, o)
            if p:
                vals.append(_battle_value(view, p, owner=0 if owner == view.yi else 1))
            else:
                cid = _option_card_id(view, o)
                vals.append(_bench_dev_value(view, cid) if cid else 0.0)
        return _choose_by_values(view, vals, False, max(1, lo or 1))
    if ctx in (C_DAMAGE_COUNTER, C_DAMAGE_COUNTER_ANY, C_DAMAGE):
        dmg = 0
        try:
            dmg = int(view.sel.get("remainDamageCounter") or 0) * 10
        except Exception:
            dmg = 0
        if dmg <= 0:
            dmg = 60 if ctx == C_DAMAGE else 30
        # If the options are ours, this is a negative effect: pick the least
        # valuable victim.  If they are theirs, hit the best target.
        owner = _option_owner(view, opts[0])
        vals = [_damage_target_value(view, o, dmg) for o in opts]
        if owner == view.yi:
            return _choose_by_values(view, vals, True, max(lo, 1))
        return _choose_by_values(view, vals, False, max(lo, 1))
    if ctx == C_HEAL or ctx == 16:
        vals = [_damage_target_value(view, o, 0) for o in opts]
        return _choose_by_values(view, vals, False, max(lo, min(hi, n)))
    if ctx == C_ATTACH_FROM:
        vals = []
        for o in opts:
            p = _option_pokemon(view, o)
            if p:
                vals.append(-_discard_energy_cost(view, o))
            else:
                cid = _option_card_id(view, o)
                vals.append(-(_card_utility(view, cid) if cid else 0.0))
        return _choose_by_values(view, vals, False, max(lo, 1))
    if ctx == C_ATTACH_TO:
        vals = [_attach_select_value(view, o) for o in opts]
        return _choose_by_values(view, vals, False, max(lo, min(hi, n)))
    if ctx == C_DISCARD_ENERGY:
        vals = [_discard_energy_cost(view, o) for o in opts]
        return _choose_by_values(view, vals, True, max(lo, min(hi, n)))
    if ctx in (25, 26, 33):
        vals = [_discard_energy_cost(view, o) for o in opts]
        return _choose_by_values(view, vals, True, max(lo, min(hi, n)))
    if ctx == C_DISCARD_TOOL:
        vals = []
        for o in opts:
            owner = _option_owner(view, o)
            p = _option_pokemon(view, o)
            tool_id = None
            ti = o.get("toolIndex", 0)
            if p:
                tools = p.get("tools") or []
                try:
                    ti = int(ti)
                    if 0 <= ti < len(tools) and isinstance(tools[ti], dict):
                        tool_id = tools[ti].get("id")
                except Exception:
                    tool_id = None
            tv = _card_utility(view, tool_id) if tool_id else 60.0
            vals.append(1000.0 + tv if owner != view.yi else -tv)
        k = max(lo, min(hi, n))
        # Do not burn our own tools if nothing of the opponent is offered.
        if all(_option_owner(view, o) == view.yi for o in opts) and lo <= 1:
            k = max(lo, 1)
        return _choose_by_values(view, vals, False, k)
    if ctx == C_DISCARD:
        hand_ids = view.hand_ids()
        vals = []
        for i, o in enumerate(opts):
            cid = _option_card_id(view, o)
            dup = cid is not None and hand_ids.count(cid) > 1
            vals.append(_discard_value(view, o, dup))
        return _choose_by_values(view, vals, True, max(lo, min(hi, n)))
    if ctx == C_TO_DECK_BOTTOM or ctx == C_TO_PRIZE:
        vals = [_card_utility(view, _option_card_id(view, o)) for o in opts]
        vals = [v if v is not None else 0.0 for v in vals]
        return _choose_by_values(view, vals, True, max(lo, min(hi, n)))
    if ctx == C_TO_DECK:
        vals = []
        for o in opts:
            cid = _option_card_id(view, o)
            v = _card_utility(view, cid) if cid else 0.0
            if cid is not None and _is_pokemon(cid) and view.remaining_deck_ids():
                v += 40.0
            vals.append(v)
        return _choose_by_values(view, vals, False, max(lo, min(hi, n)))
    if ctx == C_TO_BENCH:
        slots = max(0, view.bench_slots())
        k = max(lo, min(hi, n, slots)) if slots else lo
        vals = [_bench_dev_value(view, _option_card_id(view, o)) for o in opts]
        return _choose_by_values(view, vals, False, k)
    # Generic beneficial choice: highest card utility, take the allowed count.
    vals = []
    beneficial = False
    for o in opts:
        cid = _option_card_id(view, o)
        p = _option_pokemon(view, o)
        owner = _option_owner(view, o)
        area = o.get("area") if isinstance(o, dict) else None
        if owner != view.yi or area in (1, 3, 12):
            beneficial = True
        if cid is not None:
            vals.append(_card_utility(view, cid))
        elif p is not None:
            vals.append(_battle_value(view, p, owner=0 if owner == view.yi else 1))
        else:
            vals.append(0.0)
    if lo > 0:
        k = max(lo, min(hi, n))
    else:
        k = max(lo, min(hi, n)) if beneficial else 0
    return _choose_by_values(view, vals, False, k)


def _attack_is_lethal(view: View, opt: dict) -> bool:
    """True when this MAIN attack would KO the opposing Active right now."""
    info = _attack_info(opt.get("attackId"))
    active = view.my_active()
    opp = view.op_active()
    if not info or not active or not opp:
        return False
    dmg = _damage_estimate(
        active.get("id"),
        info,
        opp.get("id"),
        active,
        len(view.my_bench()),
        len(view.hand),
        False,
    )
    return dmg > 0 and dmg >= int(opp.get("hp") or 0)


def _choose_main(view: View, opts) -> list[int]:
    n = len(opts)
    if n == 0:
        return []
    best_i, best_s = 0, -1e9
    best_atk_i, best_atk_s = -1, -1e9
    best_dev_i, best_dev_s = -1, -1e9
    lethal = False
    for i, o in enumerate(opts):
        try:
            s = _score_main(view, o if isinstance(o, dict) else {})
        except Exception:
            s = 0.0
        if s > best_s:
            best_s, best_i = s, i
        if isinstance(o, dict) and o.get("type") == OPT_ATTACK:
            if s > best_atk_s:
                best_atk_s, best_atk_i = s, i
            if _attack_is_lethal(view, o):
                lethal = True
        else:
            if s > best_dev_s:
                best_dev_s, best_dev_i = s, i
    # MAIN is a sequential menu and ATTACK ends the turn.  Lethal attacks are
    # taken immediately; otherwise exhaust positive development (PLAY /
    # ABILITY / EVOLVE / ATTACH / useful RETREAT) before attacking.  END stays
    # the last fallback when nothing positive is available.
    if lethal and best_atk_i >= 0:
        return [best_atk_i]
    if best_dev_i >= 0 and best_dev_s > 0.0:
        return [best_dev_i]
    if best_atk_i >= 0:
        return [best_atk_i]
    return [best_i]


def _choose(obs: dict) -> list[int]:
    view = View(obs)
    sel = view.sel
    opts = sel.get("option") or []
    n = len(opts)
    lo = _min_count(sel, n)
    hi = _max_count(sel, n)
    if n == 0 or hi == 0:
        return []
    typ = sel.get("type")
    ctx = sel.get("context")

    if typ == SEL_MAIN:
        return _choose_main(view, opts)
    if typ == SEL_ATTACK:
        return _choose_attack_select(view, opts)
    if typ == SEL_YES_NO:
        return _choose_yes_no(view, opts)
    if typ == SEL_COUNT:
        return _choose_count(view, opts)
    if typ == SEL_SPECIAL:
        return _choose_special(view, opts)
    if typ == SEL_EVOLVE:
        return _choose_evolve_select(view, opts)

    if ctx == C_IS_FIRST or ctx == C_MULLIGAN or ctx == C_ACTIVATE:
        return _choose_yes_no(view, opts)
    if ctx == C_COIN_HEAD:
        return _choose_count(view, opts)
    if ctx == C_SKILL_ORDER:
        # Ordering of simultaneous skills: keep the offered order, take all.
        k = max(lo, min(hi, n))
        return list(range(k))

    # General card / target contexts.
    special = _context_values(view, ctx)
    if special is not None:
        vals, ascending, k = special
        return _choose_by_values(view, vals, ascending, k)
    return _choose_card_context(view, ctx, opts)


# ---------------------------------------------------------------------------
# Legality wrapper
# ---------------------------------------------------------------------------


def _clamp(action, sel: dict) -> list[int]:
    opts = sel.get("option") or []
    n = len(opts)
    lo = _min_count(sel, n)
    hi = _max_count(sel, n)
    if n == 0 or hi == 0:
        return []
    seen = set()
    out = []
    try:
        for a in action:
            try:
                a = int(a)
            except Exception:
                continue
            if 0 <= a < n and a not in seen:
                seen.add(a)
                out.append(a)
    except Exception:
        out = []
    if len(out) > hi:
        out = out[:hi]
    i = 0
    while len(out) < lo and i < n:
        if i not in seen:
            seen.add(i)
            out.append(i)
        i += 1
    return out


def agent(obs: dict) -> list[int]:
    """Kaggle entry point.  Never raises; always returns a legal list."""
    try:
        if not isinstance(obs, dict):
            return list(DECK)
        sel = obs.get("select")
        if not sel:
            return list(DECK)
        try:
            action = _choose(obs)
        except Exception:
            action = []
        return _clamp(action, sel)
    except Exception:
        # Last-resort legal fallback: the minimum number of first options.
        try:
            if not isinstance(obs, dict):
                return []
            sel = obs.get("select")
            if not sel:
                return list(DECK) if sel is None else []
            n = len(sel.get("option") or [])
            lo = int(sel.get("minCount") or 0)
            hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
            k = max(0, min(lo, hi, n))
            return list(range(k))
        except Exception:
            return []
