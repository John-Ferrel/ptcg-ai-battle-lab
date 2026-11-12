"""search_v1 — determinized forward-search overlay on heuristic_v1.

The base policy (``base_policy.py``, a verbatim copy of
``agents/heuristic_v1/main.py``) is used for:

* the legal fallback action,
* ranking the current MAIN / ATTACK options,
* the rollout policy inside the search tree.

Search is only used for MAIN and ATTACK decisions.  Each decision builds one
hidden-information belief, asks the engine for a determinized root
(``search_begin``), steps the top-K candidates, rolls each candidate out with
the base policy for at most ``MAX_STEPS`` nodes or until the turn changes, and
picks the action with the best average board/prize score.

Everything is wrapped in a hard per-decision budget.  On any exception or when
the budget is exhausted the base action is returned.  The agent never raises
and always returns a legal list.

Environment knobs (all optional; defaults are the evaluated configuration):

    SEARCH_V1_MODE=search|one_ply|heuristic
    SEARCH_V1_BUDGET_S=0.22
    SEARCH_V1_TOP_K=4
    SEARCH_V1_ROLLOUTS=2
    SEARCH_V1_MAX_STEPS=8
    SEARCH_V1_BELIEFS=1
    SEARCH_V1_TELEMETRY_DIR=<dir>   # one <pid>.jsonl per worker

The Kaggle sandbox provides ``cg.api``; locally run with ``PYTHONPATH=vendor``.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import Counter

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # Kaggle's loader exec()s main.py without __file__
    _HERE = os.getcwd() if os.path.exists(os.path.join(os.getcwd(), "deck.csv")) else "/kaggle_simulations/agent"
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import base_policy as base  # noqa: E402

try:  # The official SDK is present in the Kaggle sandbox; vendor/ locally.
    from cg.api import search_begin, search_end, search_step, to_observation_class

    _HAS_SEARCH = True
except Exception:  # pragma: no cover - exercised when only base_policy exists
    search_begin = search_end = search_step = to_observation_class = None
    _HAS_SEARCH = False


DECK = list(base.DECK)

# Option / select type constants mirrored from the base policy.
OPT_END = 14
SEL_MAIN = 0
SEL_ATTACK = 6

MODE = os.environ.get("SEARCH_V1_MODE", "search").strip().lower()
BUDGET_S = float(os.environ.get("SEARCH_V1_BUDGET_S", "0.22"))
TOP_K = max(1, int(os.environ.get("SEARCH_V1_TOP_K", "4")))
ROLLOUTS = max(1, int(os.environ.get("SEARCH_V1_ROLLOUTS", "2")))
MAX_STEPS = max(0, int(os.environ.get("SEARCH_V1_MAX_STEPS", "8")))
BELIEFS = max(1, int(os.environ.get("SEARCH_V1_BELIEFS", "1")))
MARGIN = float(os.environ.get("SEARCH_V1_MARGIN", "200"))
TELEMETRY_DIR = os.environ.get("SEARCH_V1_TELEMETRY_DIR", "")

_RNG = random.Random()
if os.environ.get("SEARCH_V1_SEED"):
    try:
        _RNG.seed(int(os.environ["SEARCH_V1_SEED"]))
    except Exception:
        pass

_TELEMETRY_FH = None


# ---------------------------------------------------------------------------
# Small generic helpers (raw dicts and cg.api dataclasses)
# ---------------------------------------------------------------------------


def _g(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _cid(item):
    if item is None:
        return None
    if isinstance(item, dict):
        value = item.get("id")
    else:
        value = getattr(item, "id", None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _raw_obj(obj):
    """Recursively convert cg.api dataclasses / objects into plain dicts."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_raw_obj(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _raw_obj(value) for key, value in obj.items()}
    if hasattr(obj, "__dict__"):
        return {
            key: _raw_obj(value)
            for key, value in vars(obj).items()
            if not key.startswith("_")
        }
    return obj


def _raw_obs(obs):
    if isinstance(obs, dict):
        return obs
    return _raw_obj(obs)


def _visible_ids(player) -> list[int]:
    """Ids of cards visible in hand / board / discard / attachments."""
    ids: list[int] = []

    def add(item):
        cid = _cid(item)
        if cid is not None:
            ids.append(cid)

    def add_pokemon(pokemon):
        if pokemon is None:
            return
        add(pokemon)
        for card in _g(pokemon, "energyCards") or []:
            add(card)
        for card in _g(pokemon, "tools") or []:
            add(card)

    for pokemon in _g(player, "active") or []:
        add_pokemon(pokemon)
    for pokemon in _g(player, "bench") or []:
        add_pokemon(pokemon)
    for card in _g(player, "discard") or []:
        add(card)
    for card in _g(player, "hand") or []:
        add(card)
    return ids


def _take(pool: list[int], count: int, fallback: list[int]) -> list[int]:
    """Return exactly ``count`` ids, padding from ``fallback`` if needed."""
    count = max(0, int(count))
    out = [int(cid) for cid in pool[:count]]
    if len(out) < count and fallback:
        index = 0
        while len(out) < count:
            out.append(int(fallback[index % len(fallback)]))
            index += 1
    return out


def _counts_without(cards: list[int], visible: list[int]) -> list[int]:
    counts = Counter(int(cid) for cid in cards)
    for cid in visible:
        if counts.get(cid, 0) > 0:
            counts[cid] -= 1
    return list(counts.elements())


def _basic_from(ids: list[int]) -> int | None:
    for cid in ids:
        try:
            if base._is_basic(int(cid)):
                return int(cid)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Meta priors and belief construction
# ---------------------------------------------------------------------------


def _load_prior(name: str) -> list[int]:
    path = os.path.join(_HERE, "meta", name)
    try:
        with open(path) as handle:
            ids = [int(token) for token in handle.read().split()]
        return ids if len(ids) == 60 else []
    except Exception:
        return []


PRIORS = [
    prior
    for prior in (
        _load_prior("01_Mega_Excadrill_ex.csv"),
        _load_prior("03_Dragapult_ex.csv"),
        _load_prior("05_Mega_Lopunny_ex.csv"),
    )
    if prior
] or [list(DECK)]

_FORCED_PRIOR = os.environ.get("SEARCH_V1_PRIOR_INDEX", "").strip()


def _choose_prior(revealed: list[int], rng: random.Random) -> tuple[list[int], int]:
    """Pick the meta prior with the most overlap with revealed opponent cards.

    Cards that appear in only one prior are weighted more heavily than common
    staples, so a single archetype-specific Pokémon or trainer identifies the
    opponent faster.  Returns ``(deck, prior_index)``.
    """
    if _FORCED_PRIOR:
        try:
            index = int(_FORCED_PRIOR)
            return list(PRIORS[index]), index
        except Exception:
            pass
    if not revealed:
        index = rng.randrange(len(PRIORS))
        return list(PRIORS[index]), index

    revealed_counts = Counter(revealed)
    presence = [
        {cid for cid in revealed_counts if cid in set(prior)} for prior in PRIORS
    ]
    best_score = -1e9
    best: list[int] = []
    for index, prior in enumerate(PRIORS):
        counts = Counter(prior)
        score = 0.0
        for cid, count in revealed_counts.items():
            overlap = min(counts.get(cid, 0), count)
            if overlap <= 0:
                continue
            in_priors = sum(1 for present in presence if cid in present)
            # Exclusive cards get weight 3; shared staples get weight 1.
            score += overlap * (4.0 - in_priors)
        if score > best_score:
            best_score, best = score, [index]
        elif score == best_score:
            best.append(index)
    index = rng.choice(best or list(range(len(PRIORS))))
    return list(PRIORS[index]), index


def _build_belief(obs, rng: random.Random) -> dict:
    """Create one determinization of all hidden zones.

    Own deck/prizes are sampled from the 60-card decklist minus visible cards.
    Opponent deck/prizes/hand are sampled from a meta prior minus revealed
    cards.  ``select.deck`` is used exactly when the engine exposes it.
    """
    current = _g(obs, "current")
    if current is None:
        raise ValueError("no current state")
    players = _g(current, "players") or []
    if len(players) != 2:
        raise ValueError("players != 2")
    your_index = int(_g(current, "yourIndex", 0) or 0)
    me = players[your_index]
    opponent = players[1 - your_index]

    deck_count = int(_g(me, "deckCount", 0) or 0)
    prize_count = len(_g(me, "prize") or []) or 6
    opp_deck_count = int(_g(opponent, "deckCount", 0) or 0)
    opp_prize_count = len(_g(opponent, "prize") or []) or 6
    opp_hand_count = int(_g(opponent, "handCount", 0) or 0)

    own_pool = _counts_without(DECK, _visible_ids(me))

    select = _g(obs, "select")
    select_deck = _g(select, "deck") if select is not None else None
    exact_deck = None
    if isinstance(select_deck, list) and select_deck:
        exact = []
        for card in select_deck:
            if _g(card, "playerIndex", your_index) != your_index:
                continue
            cid = _cid(card)
            if cid is not None:
                exact.append(cid)
        if len(exact) == deck_count:
            exact_deck = exact
            own_pool = _counts_without(own_pool, exact)

    rng.shuffle(own_pool)
    if exact_deck is not None:
        your_deck = list(exact_deck)
        your_prize = _take(own_pool, prize_count, DECK)
    else:
        your_deck = _take(own_pool[:deck_count], deck_count, DECK)
        your_prize = _take(own_pool[deck_count:], prize_count, DECK)

    revealed = _visible_ids(opponent)
    prior, prior_index = _choose_prior(revealed, rng)
    opp_pool = _counts_without(prior, revealed)
    rng.shuffle(opp_pool)

    opponent_deck = _take(opp_pool[:opp_deck_count], opp_deck_count, prior)
    offset = opp_deck_count
    opponent_prize = _take(
        opp_pool[offset : offset + opp_prize_count], opp_prize_count, prior
    )
    offset += opp_prize_count
    opponent_hand = _take(
        opp_pool[offset : offset + opp_hand_count], opp_hand_count, prior
    )

    if opponent_deck and not any(base._is_basic(cid) for cid in opponent_deck):
        basic = _basic_from(prior) or _basic_from(opponent_deck)
        if basic is not None:
            opponent_deck[0] = basic

    opponent_active: list[int] = []
    active = _g(opponent, "active") or []
    if active and active[0] is None:
        basic = _basic_from(opponent_deck) or _basic_from(prior)
        if basic is not None:
            opponent_active = [basic]

    return {
        "your_deck": your_deck,
        "your_prize": your_prize,
        "opponent_deck": opponent_deck,
        "opponent_prize": opponent_prize,
        "opponent_hand": opponent_hand,
        "opponent_active": opponent_active,
        "_prior": prior_index,
    }


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


def _dedupe(candidates: list[tuple[int, float]]) -> list[tuple[int, float]]:
    seen = set()
    out = []
    for index, score in candidates:
        if index in seen:
            continue
        seen.add(index)
        out.append((index, float(score)))
    return out


def _main_candidates(raw: dict, select: dict) -> tuple[list[tuple[int, float]], list[int]]:
    view = base.View(raw)
    options = select.get("option") or []
    scores = []
    for option in options:
        try:
            scores.append(float(base._score_main(view, option)))
        except Exception:
            scores.append(0.0)

    order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
    chosen = [(i, scores[i]) for i in order[:TOP_K]]

    end_index = next(
        (i for i, option in enumerate(options) if option.get("type") == OPT_END),
        None,
    )
    if end_index is not None:
        chosen.append((end_index, scores[end_index]))

    base_action = base._choose_main(view, options) or []
    base_index = base_action[0] if base_action else (order[0] if order else 0)
    chosen.append((base_index, scores[base_index] if 0 <= base_index < len(scores) else 0.0))
    return _dedupe(chosen), base_action


def _attack_candidates(raw: dict, select: dict) -> tuple[list[tuple[int, float]], list[int]]:
    view = base.View(raw)
    options = select.get("option") or []
    scores = []
    for option in options:
        try:
            scores.append(
                float(
                    base._score_attack(
                        view, {"type": 13, "attackId": option.get("attackId")}
                    )
                )
            )
        except Exception:
            scores.append(100.0)

    order = sorted(range(len(options)), key=lambda i: (-scores[i], i))
    chosen = [(i, scores[i]) for i in order[:TOP_K]]

    base_action = base._choose_attack_select(view, options) or []
    if base_action:
        base_index = base_action[0]
        chosen.append((base_index, scores[base_index] if 0 <= base_index < len(scores) else 0.0))
    elif base._min_count(select, len(options)) == 0:
        # Legal "decline to attack" candidate.
        chosen.append((-1, 100.0))
    return _dedupe(chosen), base_action


# ---------------------------------------------------------------------------
# Rollout and state scoring
# ---------------------------------------------------------------------------


def _random_legal(select: dict, rng: random.Random) -> list[int]:
    options = select.get("option") or []
    n = len(options)
    if n == 0:
        return []
    lo = base._min_count(select, n)
    hi = base._max_count(select, n)
    if hi <= 0:
        return []
    if lo == 0:
        lo = 1
    count = rng.randint(min(lo, hi), hi)
    return rng.sample(range(n), min(count, n))


def _rollout_action(raw: dict, rng: random.Random) -> list[int]:
    select = raw.get("select") or {}
    try:
        action = base._choose(raw)
        action = base._clamp(action, select)
        if action or base._min_count(select, len(select.get("option") or [])) == 0:
            return action
    except Exception:
        pass
    return _random_legal(select, rng)


def _rollout(node, root_turn: int, rng: random.Random, deadline: float):
    end = node
    steps = 0
    while steps < MAX_STEPS:
        if time.perf_counter() >= deadline:
            break
        obs = end.observation
        current = _g(obs, "current")
        if current is None:
            break
        try:
            if int(_g(current, "result", -1)) >= 0:
                break
        except Exception:
            pass
        if _g(obs, "select") is None:
            break
        try:
            if int(_g(current, "turn", root_turn)) != root_turn:
                break
        except Exception:
            pass
        try:
            end = search_step(end.searchId, _rollout_action(_raw_obs(obs), rng))
        except Exception:
            break
        steps += 1
    return end, steps


def _score_state(root_index: int, obs) -> float:
    """Board/prize evaluation from ``root_index``'s point of view."""
    if obs is None:
        return 0.0
    raw = _raw_obs(obs)
    current = raw.get("current")
    if current is None:
        return 0.0
    try:
        result = int(current.get("result", -1))
    except Exception:
        result = -1
    if result >= 0:
        if result == root_index:
            return 1e7
        if result == 2:
            return 0.0
        return -1e7

    try:
        if int(current.get("yourIndex", 0) or 0) != root_index:
            current = dict(current)
            current["yourIndex"] = root_index
            raw = dict(raw)
            raw["current"] = current
        view = base.View(raw)
        me = view.players[root_index]
        opponent = view.players[1 - root_index]
        prize = (
            len(opponent.get("prize") or []) - len(me.get("prize") or [])
        ) * 500.0
        my_value = sum(
            base._battle_value(view, pokemon, owner=0)
            for pokemon in base.View.in_play(me)
        )
        opp_value = sum(
            base._battle_value(view, pokemon, owner=1)
            for pokemon in base.View.in_play(opponent)
        )
        hand = me.get("hand")
        hand_count = len(hand) if isinstance(hand, list) else int(me.get("handCount") or 0)
        energy = sum(
            len(pokemon.get("energies") or [])
            for pokemon in base.View.in_play(me)
        )
        return prize + my_value - opp_value + hand_count * 1.5 + energy * 8.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Search decision
# ---------------------------------------------------------------------------


def _search_choice(raw: dict):
    """Return ``(action, meta)``.  ``action`` is already a search choice."""
    select = raw.get("select") or {}
    select_type = select.get("type")
    fallback_action = base.agent(raw)

    def fallback(error: str = ""):
        return fallback_action, {
            "searched": False,
            "candidates": 0,
            "rollouts": 0,
            "beliefs": 0,
            "fallback": True,
            "override": False,
            "error": error,
        }

    if not _HAS_SEARCH or MODE == "heuristic":
        return fallback("search disabled")
    if select_type not in (SEL_MAIN, SEL_ATTACK):
        return fallback("")

    options = select.get("option") or []
    n = len(options)
    if n <= 1:
        return fallback("")
    lo = base._min_count(select, n)
    hi = base._max_count(select, n)
    if hi != 1:
        return fallback("multi-pick selection")

    if select_type == SEL_MAIN:
        candidates, base_action = _main_candidates(raw, select)
    else:
        candidates, base_action = _attack_candidates(raw, select)
    if len(candidates) <= 1:
        return fallback("")

    try:
        observation = to_observation_class(raw)
    except Exception as exc:
        return fallback(f"to_observation_class: {exc}")
    current = _g(observation, "current")
    if current is None:
        return fallback("no current state")

    root_turn = int(_g(current, "turn", 0) or 0)
    root_index = int(_g(current, "yourIndex", 0) or 0)
    deadline = time.perf_counter() + BUDGET_S
    scores: dict[int, list[float]] = {}
    total_rollouts = 0
    beliefs_done = 0
    search_active = False
    last_prior = -1
    error = ""

    try:
        for _belief_index in range(BELIEFS):
            if time.perf_counter() >= deadline:
                break
            try:
                belief = _build_belief(observation, _RNG)
                prior_index = int(belief.pop("_prior", -1))
                root = search_begin(observation, **belief)
            except Exception as exc:
                error = f"search_begin: {exc}"
                break
            search_active = True
            beliefs_done += 1
            last_prior = prior_index

            for index, _candidate_score in candidates:
                if time.perf_counter() >= deadline:
                    break
                try:
                    node = search_step(root.searchId, [] if index < 0 else [index])
                except Exception as exc:
                    error = f"search_step: {exc}"
                    continue

                samples: list[float] = []
                if MODE == "one_ply" or MAX_STEPS == 0:
                    samples.append(_score_state(root_index, node.observation))
                else:
                    for _ in range(ROLLOUTS):
                        if time.perf_counter() >= deadline:
                            break
                        end, _steps = _rollout(node, root_turn, _RNG, deadline)
                        samples.append(_score_state(root_index, end.observation))
                        total_rollouts += 1
                if samples:
                    scores.setdefault(index, []).extend(samples)
    finally:
        if search_active:
            try:
                search_end()
            except Exception:
                pass

    if not scores:
        return fallback(error or "no candidate evaluated")

    candidate_scores = dict(candidates)
    averages = {
        index: sum(values) / len(values) for index, values in scores.items()
    }
    base_key = base_action[0] if base_action else -1

    def quality(index: int):
        return (
            averages[index],
            candidate_scores.get(index, -1e9),
            index == base_key,
        )

    best_index = max(scores, key=quality)
    best_score = averages[best_index]
    base_score = averages.get(base_key)
    margin = best_score - base_score if base_score is not None else None
    gated = False
    if (
        MARGIN > 0.0
        and best_index != base_key
        and base_score is not None
        and margin < MARGIN
    ):
        chosen = list(base_action)
        override = False
        gated = True
    else:
        chosen = [] if best_index < 0 else [best_index]
        override = list(chosen) != list(base_action)
    return chosen, {
        "searched": True,
        "candidates": len(scores),
        "rollouts": total_rollouts,
        "beliefs": beliefs_done,
        "fallback": False,
        "override": override,
        "error": error,
        "best_index": best_index,
        "base_index": base_key,
        "best_score": round(best_score, 2),
        "base_score": None if base_score is None else round(base_score, 2),
        "margin": None if margin is None else round(margin, 2),
        "gated": gated,
        "prior": last_prior,
    }


# ---------------------------------------------------------------------------
# Telemetry / entry point
# ---------------------------------------------------------------------------


def _record(meta: dict, ms: float, select: dict) -> None:
    if not TELEMETRY_DIR:
        return
    global _TELEMETRY_FH
    try:
        if _TELEMETRY_FH is None:
            os.makedirs(TELEMETRY_DIR, exist_ok=True)
            _TELEMETRY_FH = open(
                os.path.join(TELEMETRY_DIR, f"{os.getpid()}.jsonl"),
                "a",
                buffering=1,
            )
        row = {
            "pid": os.getpid(),
            "ms": round(float(ms), 3),
            "type": select.get("type"),
            "context": select.get("context"),
            "searched": bool(meta.get("searched")),
            "candidates": int(meta.get("candidates", 0)),
            "rollouts": int(meta.get("rollouts", 0)),
            "beliefs": int(meta.get("beliefs", 0)),
            "fallback": bool(meta.get("fallback")),
            "override": bool(meta.get("override")),
            "gated": bool(meta.get("gated")),
            "best_index": meta.get("best_index"),
            "base_index": meta.get("base_index"),
            "best_score": meta.get("best_score"),
            "base_score": meta.get("base_score"),
            "margin": meta.get("margin"),
            "prior": meta.get("prior", -1),
            "error": str(meta.get("error", ""))[:120],
        }
        _TELEMETRY_FH.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:
        pass


def agent(obs: dict) -> list[int]:
    """Kaggle entry point.  Never raises; always returns a legal list."""
    started = time.perf_counter()
    if not isinstance(obs, dict):
        return list(DECK)
    select = obs.get("select")
    if not select:
        return list(DECK)

    try:
        action, meta = _search_choice(obs)
    except Exception as exc:  # noqa: BLE001 - fallback is the whole point
        try:
            action = base.agent(obs)
        except Exception:
            action = []
        meta = {
            "searched": False,
            "candidates": 0,
            "rollouts": 0,
            "beliefs": 0,
            "fallback": True,
            "override": False,
            "error": f"agent: {exc}",
        }

    try:
        action = base._clamp(action, select)
    except Exception:
        action = []

    _record(meta, (time.perf_counter() - started) * 1000.0, select)
    return action


__all__ = ["agent", "DECK"]
