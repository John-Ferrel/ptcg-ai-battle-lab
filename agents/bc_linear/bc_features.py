"""Pure-stdlib feature extraction for the BC linear policy.

This file is the *contract* between training (`scripts/bc_extract.py`) and the
submission agent (`agents/bc_linear/main.py`): both call `build_features` with
the same raw observation and the same compact card metadata, so the feature
names/values are identical at train and inference time.

Feature names are strings; the training pipeline maps them to columns and the
agent looks up weights by name.  Keep this file dependency-free.

Card metadata format (see `card_meta.json`):
    {"c": {card_id: [hp, cardType, retreatCost, flags]},
     "a": {attack_id: [n_energy_cost, damage]}}
Flags are bit-packed: 1=basic pokemon, 2=stage1, 4=stage2, 8=ex, 16=megaEx.
cardType: 0 pokemon, 1 item, 2 tool, 3 supporter, 4 stadium, 5 basic energy,
          6 special energy.
"""
from __future__ import annotations

# SelectType
_MAIN_TYPE = 0
# SelectContext
_CTX_MAIN = 0
# OptionType
OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_TOOL_CARD, OPT_ENERGY_CARD = range(6)
OPT_ENERGY, OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY = range(6, 11)
OPT_DISCARD, OPT_RETREAT, OPT_ATTACK, OPT_END, OPT_SKILL, OPT_SPECIAL = range(11, 17)

# AreaType
AREA_ACTIVE, AREA_BENCH, AREA_HAND = 4, 5, 2

_FLAG_BASIC, _FLAG_STAGE1, _FLAG_STAGE2, _FLAG_EX, _FLAG_MEGA = 1, 2, 4, 8, 16
_CTYPE_POKEMON, _CTYPE_ITEM, _CTYPE_TOOL, _CTYPE_SUPPORTER = 0, 1, 2, 3
_CTYPE_STADIUM, _CTYPE_BASIC_ENERGY, _CTYPE_SPECIAL_ENERGY = 4, 5, 6


def _hash_bucket(value: int, buckets: int) -> int:
    """Stable, dependency-free multiplicative hash (same result in any Python)."""
    return (int(value) * 2654435761) % buckets


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _active(player: dict):
    a = player.get("active") or []
    return a[0] if a else None


def _bench(player: dict) -> list:
    return [x for x in (player.get("bench") or []) if x]


def _hp_frac(pkmn) -> float:
    if not pkmn:
        return 0.0
    hp = pkmn.get("hp") or 0
    mx = pkmn.get("maxHp") or 0
    return _clip(hp / mx) if mx else 0.0


def _energy_n(pkmn) -> int:
    return len((pkmn or {}).get("energies") or [])


def _card_at(st: dict, player_index: int, area, index) -> int | None:
    """Best-effort card id at an area/index for a player."""
    players = st.get("players") or []
    if not (0 <= player_index < len(players)):
        return None
    p = players[player_index] or {}
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None
    if idx < 0:
        return None
    if area == AREA_HAND:
        hand = p.get("hand") or []
        if idx < len(hand) and hand[idx]:
            return hand[idx].get("id")
    elif area == AREA_ACTIVE:
        a = _active(p)
        return a.get("id") if a else None
    elif area == AREA_BENCH:
        b = _bench(p)
        if idx < len(b):
            return b[idx].get("id")
    elif area == 3:  # discard
        d = p.get("discard") or []
        if idx < len(d) and d[idx]:
            return d[idx].get("id")
    elif area == 6:  # prize
        pr = p.get("prize") or []
        if idx < len(pr) and pr[idx]:
            return pr[idx].get("id")
    elif area == 7:  # stadium / lost zone -- handled by caller usually
        stad = st.get("stadium") or []
        if stad and stad[0]:
            return stad[0].get("id")
    return None


def _option_card_id(obs: dict, opt: dict, sel: dict | None = None) -> int | None:
    """Card id an option refers to, or None.

    Handles deck-search options (`area == 1`): the index points into
    `select["deck"]`, the ordered remaining deck, not into a player's board.
    """
    st = obs.get("current") or {}
    me_idx = st.get("yourIndex", 0)
    t = opt.get("type")
    # Deck search: area 1 = DECK, index into select.deck (as ordered by the engine)
    if opt.get("area") == 1 and sel is not None and sel.get("deck") is not None:
        deck = sel.get("deck") or []
        try:
            idx = int(opt.get("index", -1))
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(deck) and deck[idx]:
            return deck[idx].get("id")
        return None
    if t in (OPT_PLAY, OPT_ATTACH, OPT_EVOLVE) or t == OPT_ENERGY_CARD:
        # index = hand index; area is normally HAND (2)
        area = opt.get("area", AREA_HAND)
        owner = opt.get("playerIndex", me_idx)
        return _card_at(st, owner, area, opt.get("index"))
    if t in (OPT_CARD, OPT_TOOL_CARD, OPT_DISCARD, OPT_SPECIAL, OPT_SKILL):
        area = opt.get("area")
        owner = opt.get("playerIndex", me_idx)
        if area is not None:
            return _card_at(st, owner, area, opt.get("index"))
    if t in (OPT_ABILITY, OPT_ATTACK):
        # in-play Pokemon (ability) or cardId (rare attack option)
        if opt.get("cardId"):
            return opt.get("cardId")
        area = opt.get("inPlayArea", opt.get("area"))
        owner = opt.get("playerIndex", me_idx)
        if area is not None:
            return _card_at(st, owner, area, opt.get("inPlayIndex", opt.get("index")))
    if opt.get("cardId"):
        return opt.get("cardId")
    return None


def _option_target(obs: dict, opt: dict):
    """Resolve the in-play Pokemon an option targets (or None)."""
    st = obs.get("current") or {}
    me_idx = st.get("yourIndex", 0)
    area = opt.get("inPlayArea")
    idx = opt.get("inPlayIndex", opt.get("index", 0))
    if area in (AREA_ACTIVE, AREA_BENCH):
        owner = opt.get("playerIndex", me_idx)
        players = st.get("players") or []
        if not (0 <= owner < len(players)):
            return None
        p = players[owner] or {}
        if area == AREA_ACTIVE:
            return _active(p)
        b = _bench(p)
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None
        return b[idx] if 0 <= idx < len(b) else None
    area = opt.get("area")
    if area in (AREA_ACTIVE, AREA_BENCH):
        owner = opt.get("playerIndex", me_idx)
        players = st.get("players") or []
        if not (0 <= owner < len(players)):
            return None
        p = players[owner] or {}
        if area == AREA_ACTIVE:
            return _active(p)
        b = _bench(p)
        try:
            idx = int(opt.get("index", 0))
        except (TypeError, ValueError):
            return None
        return b[idx] if 0 <= idx < len(b) else None
    return None


def _target_owner(obs: dict, opt: dict) -> int | None:
    """Which player owns the option target (0/1), or None if not a target."""
    st = obs.get("current") or {}
    me_idx = st.get("yourIndex", 0)
    if opt.get("inPlayArea") in (AREA_ACTIVE, AREA_BENCH) or opt.get("area") in (
        AREA_ACTIVE,
        AREA_BENCH,
    ):
        return int(opt.get("playerIndex", me_idx))
    return None


def _card_props(meta: dict, card_id) -> dict:
    table = (meta or {}).get("c") or {}
    info = table.get(card_id) if card_id is not None else None
    if not info:
        return {}
    hp, ctype, retreat, flags = info
    out = {
        "cp_hp": _clip((hp or 0) / 350.0),
        "cp_retreat": _clip((retreat or 0) / 4.0),
        "cp_basic": 1.0 if flags & _FLAG_BASIC else 0.0,
        "cp_stage1": 1.0 if flags & _FLAG_STAGE1 else 0.0,
        "cp_stage2": 1.0 if flags & _FLAG_STAGE2 else 0.0,
        "cp_ex": 1.0 if flags & _FLAG_EX else 0.0,
        "cp_megaex": 1.0 if flags & _FLAG_MEGA else 0.0,
        "cp_pokemon": 1.0 if ctype == _CTYPE_POKEMON else 0.0,
        "cp_item": 1.0 if ctype == _CTYPE_ITEM else 0.0,
        "cp_tool": 1.0 if ctype == _CTYPE_TOOL else 0.0,
        "cp_supporter": 1.0 if ctype == _CTYPE_SUPPORTER else 0.0,
        "cp_stadium": 1.0 if ctype == _CTYPE_STADIUM else 0.0,
        "cp_energy": 1.0
        if ctype in (_CTYPE_BASIC_ENERGY, _CTYPE_SPECIAL_ENERGY)
        else 0.0,
    }
    return {k: v for k, v in out.items() if v}


def _prize_value(meta: dict, card_id) -> float:
    table = (meta or {}).get("c") or {}
    info = table.get(card_id) if card_id is not None else None
    if not info:
        return 1.0
    flags = info[3]
    return 2.0 if flags & (_FLAG_EX | _FLAG_MEGA) else 1.0


def _state_features(obs: dict) -> dict:
    st = obs.get("current") or {}
    players = st.get("players") or [{}, {}]
    me_idx = int(st.get("yourIndex", 0) or 0)
    me = players[me_idx] if me_idx < len(players) else {}
    opp = players[1 - me_idx] if 1 - me_idx < len(players) else {}
    me = me or {}
    opp = opp or {}
    my_active = _active(me)
    opp_active = _active(opp)
    f = {
        "s_turn": _clip((st.get("turn") or 0) / 20.0),
        "s_turn_action": _clip((st.get("turnActionCount") or 0) / 10.0),
        "s_my_prize": _clip(len(me.get("prize") or []) / 6.0),
        "s_opp_prize": _clip(len(opp.get("prize") or []) / 6.0),
        "s_hand": _clip(len(me.get("hand") or []) / 10.0),
        "s_deck": _clip((me.get("deckCount") or 0) / 40.0),
        "s_bench": _clip(len(_bench(me)) / 5.0),
        "s_opp_bench": _clip(len(_bench(opp)) / 5.0),
        "s_my_active": 1.0 if my_active else 0.0,
        "s_opp_active": 1.0 if opp_active else 0.0,
        "s_my_active_hp": _hp_frac(my_active),
        "s_opp_active_hp": _hp_frac(opp_active),
        "s_my_active_energy": _clip(_energy_n(my_active) / 5.0),
        "s_supporter": 1.0 if st.get("supporterPlayed") else 0.0,
        "s_energy_attached": 1.0 if st.get("energyAttached") else 0.0,
        "s_stadium": 1.0 if (st.get("stadium") or []) else 0.0,
    }
    for name, key in (
        ("poisoned", "poisoned"),
        ("burned", "burned"),
        ("asleep", "asleep"),
        ("paralyzed", "paralyzed"),
        ("confused", "confused"),
    ):
        f[f"s_me_{name}"] = 1.0 if me.get(key) else 0.0
        f[f"s_opp_{name}"] = 1.0 if opp.get(key) else 0.0
    return {k: v for k, v in f.items() if v}


def _option_features(
    obs: dict, opt: dict, state: dict, meta: dict, sel: dict | None = None
) -> dict:
    f: dict = {}
    t = opt.get("type")
    f[f"ot={t}"] = 1.0
    if t == OPT_NUMBER:
        try:
            f["o_number"] = _clip(int(opt.get("number") or 0) / 10.0)
        except (TypeError, ValueError):
            pass
    is_deck_search = bool(
        opt.get("area") == 1 and sel is not None and sel.get("deck") is not None
    )
    if is_deck_search:
        f["o_deck_search"] = 1.0
    card_id = _option_card_id(obs, opt, sel)
    if card_id:
        f[f"card={_hash_bucket(card_id, 512)}"] = 1.0
        f.update(_card_props(meta, card_id))
    if t == OPT_ATTACK:
        aid = opt.get("attackId")
        if aid:
            f[f"atk={_hash_bucket(aid, 256)}"] = 1.0
            attacks = (meta or {}).get("a") or {}
            info = attacks.get(aid)
            if info:
                f["ap_cost"] = _clip((info[0] or 0) / 4.0)
                f["ap_damage"] = _clip((info[1] or 0) / 300.0)
    tgt = _option_target(obs, opt)
    ctx = int((sel or {}).get("context") or 0)
    if tgt:
        f["t_hp"] = _hp_frac(tgt)
        f["t_energy"] = _clip(_energy_n(tgt) / 5.0)
        tgt_id = tgt.get("id")
        f["t_prize"] = _prize_value(meta, tgt_id) / 2.0
        owner = _target_owner(obs, opt)
        me_idx = int((obs.get("current") or {}).get("yourIndex", 0) or 0)
        if owner is not None:
            f["t_mine"] = 1.0 if owner == me_idx else 0.0
            f["t_opp"] = 1.0 if owner != me_idx else 0.0
        area = opt.get("inPlayArea", opt.get("area"))
        f["t_active"] = 1.0 if area == AREA_ACTIVE else 0.0
        f["t_retreat"] = _clip(
            float(((meta or {}).get("c") or {}).get(tgt_id, [0, 0, 0, 0])[2] or 0) / 4.0
        )
        # Damage-counter placement (ctx 13 / 14): would this KO, and where?
        counters = int((sel or {}).get("remainDamageCounter") or 0)
        if counters > 0 and ctx in (13, 14):
            hp = (tgt.get("hp") or 0) - counters * 10
            dmg = counters * 10
            f["d_dmg"] = _clip(dmg / 100.0)
            f["d_ko"] = 1.0 if hp <= 0 else 0.0
            f["d_hp_after"] = _clip(max(hp, 0) / max(tgt.get("maxHp") or 1, 1))
            f["d_on_opp"] = f.get("t_opp", 0.0)
            f["d_on_ex"] = 1.0 if f["t_prize"] >= 1.0 else 0.0
    # explicit interactions with the global state
    opp_hp = state.get("s_opp_active_hp", 0.0)
    turn = state.get("s_turn", 0.0)
    hand = state.get("s_hand", 0.0)
    if t == OPT_ATTACK:
        f["x_attack_opphp"] = opp_hp
    if t == OPT_EVOLVE:
        f["x_evolve_turn"] = turn
    if t == OPT_PLAY:
        f["x_play_lowhand"] = 1.0 if hand < 0.5 else 0.0
    if t == OPT_ATTACH:
        f["x_attach_target_hp"] = f.get("t_hp", 0.0)
    return {k: v for k, v in f.items() if v}


def build_features(obs: dict, meta: dict) -> list[dict]:
    """Return one feature dict per option of the current select."""
    sel = obs.get("select") or {}
    state = _state_features(obs)
    ctx = int(sel.get("context") or 0)
    stype = int(sel.get("type") or 0)
    state[f"ctx={ctx}"] = 1.0
    state[f"stype={stype}"] = 1.0
    state["s_n_options"] = _clip(len(sel.get("option") or []) / 10.0)
    out = []
    for opt in sel.get("option") or []:
        d = dict(state)
        try:
            d.update(_option_features(obs, opt, state, meta, sel))
        except Exception:  # noqa: BLE001 -- features must never crash a decision
            pass
        out.append(d)
    return out
