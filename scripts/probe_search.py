#!/usr/bin/env python
"""Probe the recovered cabt forward-search API.

Run with the project venv::

    .venv/bin/python scripts/probe_search.py --deck decks/default.csv \
        --opp-deck decks/default.csv --rollouts 100

The probe answers four questions:

Q1  Can ``search_begin`` accept a *belief* (hidden zones guessed from the
    visible observation) and return a valid ``SearchState``?
Q2  Can a random rollout from that root reach a terminal state?
Q3  Are two picks from the same node independent (a real tree, not a linear
    replay)?
Q4  How many random rollouts per second can we run?

It never modifies the engine, and it keeps all experiments in one process
(the cabt engine is a process-global singleton).
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
sys.path.insert(0, str(ROOT / "src"))

from cg.api import (  # noqa: E402
    Observation,
    SelectContext,
    SelectType,
    search_begin,
    search_end,
    search_release,
    search_step,
    to_observation_class,
)
from cg.game import battle_finish, battle_select, battle_start  # noqa: E402
from ptcg_ai import cards, deck as decklib  # noqa: E402


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _first_legal(sel: dict) -> list[int]:
    """A deterministic legal selection: the first ``maxCount`` options."""
    options = sel.get("option") or []
    n = len(options)
    lo = int(sel.get("minCount") or 0)
    hi = min(int(sel.get("maxCount") or 1), n)
    count = hi if hi > lo else lo
    return list(range(min(max(count, 0), n)))


def _pick_count(sel, rng: random.Random) -> int:
    n = len(sel.option)
    lo = int(sel.minCount or 0)
    hi = min(int(sel.maxCount or 1), n)
    if hi <= 0:
        return 0
    lo = min(max(lo, 0), hi)
    # Prefer a non-empty pick when the selection is optional: it makes the
    # rollout exercise more of the engine.
    if lo == 0:
        lo = 1
    return rng.randint(lo, hi)


def _random_picks(sel, rng: random.Random) -> list[int]:
    n = len(sel.option)
    count = _pick_count(sel, rng)
    return rng.sample(range(n), min(count, n))


def _visible_ids(player) -> list[int]:
    """Card ids we can see in one player's zones (for belief construction)."""
    ids: list[int] = []

    def add_card(card) -> None:
        if card is not None:
            ids.append(int(card.id))

    def add_pokemon(pokemon) -> None:
        if pokemon is None:
            return
        ids.append(int(pokemon.id))
        for card in pokemon.energyCards or []:
            add_card(card)
        for card in pokemon.tools or []:
            add_card(card)

    for pokemon in player.active or []:
        add_pokemon(pokemon)
    for pokemon in player.bench or []:
        add_pokemon(pokemon)
    for card in player.discard or []:
        add_card(card)
    for card in player.hand or []:
        add_card(card)
    return ids


def _remaining_pool(full_deck: list[int], visible: list[int]) -> list[int]:
    """Multiset subtraction of visible cards from the 60-card deck list."""
    pool = collections.Counter(full_deck)
    for card_id in visible:
        if pool[card_id] > 0:
            pool[card_id] -= 1
    return list(pool.elements())


def _take(pool: list[int], count: int, fallback: list[int]) -> list[int]:
    """Take ``count`` cards from a shuffled pool, padding if the belief is short."""
    out = pool[:count]
    if len(out) < count:
        extra = list(fallback)
        index = 0
        while len(out) < count and extra:
            out.append(int(extra[index % len(extra)]))
            index += 1
    return out


def build_belief(obs: Observation, deck: list[int], opp_deck: list[int], rng: random.Random):
    """Build a coherent belief for every hidden zone.

    Your own hand/board/discard and the opponent's visible board are removed
    from the 60-card lists, then the remaining multiset is shuffled and split
    into deck / prizes / (opponent) hand.  This is what a real agent would have
    to infer; the probe deliberately does not read the engine's hidden truth.
    """
    me = obs.current.players[obs.current.yourIndex]
    opp = obs.current.players[1 - obs.current.yourIndex]

    my_pool = _remaining_pool(deck, _visible_ids(me))
    rng.shuffle(my_pool)
    my_deck_count = int(me.deckCount or 0)
    my_prize_count = len(me.prize or []) or 6
    your_deck = _take(my_pool, my_deck_count, deck)
    your_prize = _take(my_pool[my_deck_count:], my_prize_count, deck)

    opp_pool = _remaining_pool(opp_deck, _visible_ids(opp))
    rng.shuffle(opp_pool)
    opp_deck_count = int(opp.deckCount or 0)
    opp_prize_count = len(opp.prize or []) or 6
    opp_hand_count = int(opp.handCount or 0)
    opponent_deck = _take(opp_pool, opp_deck_count, opp_deck)
    opponent_prize = _take(opp_pool[opp_deck_count:], opp_prize_count, opp_deck)
    opponent_hand = _take(
        opp_pool[opp_deck_count + opp_prize_count:], opp_hand_count, opp_deck
    )

    opponent_active: list[int] = []
    if opp.active and opp.active[0] is None:
        basics = [cid for cid in opp_deck if cards.card(cid).get("basic")]
        opponent_active = [basics[0] if basics else opp_deck[0]]

    return {
        "your_deck": your_deck,
        "your_prize": your_prize,
        "opponent_deck": opponent_deck,
        "opponent_prize": opponent_prize,
        "opponent_hand": opponent_hand,
        "opponent_active": opponent_active,
    }


def _signature(obs: Observation | None) -> dict:
    """A structural fingerprint of a search node (ignores volatile log text)."""
    if obs is None or obs.current is None:
        return {"terminal": True, "select": None}
    select = obs.select
    me = obs.current.players[obs.current.yourIndex]
    opp = obs.current.players[1 - obs.current.yourIndex]
    return {
        "turn": obs.current.turn,
        "turnActionCount": obs.current.turnActionCount,
        "yourIndex": obs.current.yourIndex,
        "result": obs.current.result,
        "select": None
        if select is None
        else {
            "type": int(select.type),
            "context": int(select.context),
            "min": select.minCount,
            "max": select.maxCount,
            "options": [
                [int(option.type), option.area, option.index, option.inPlayArea,
                 option.inPlayIndex, option.attackId, option.cardId]
                for option in select.option
            ],
        },
        "me": [me.handCount, me.deckCount, len(me.prize or []), len(me.bench or [])],
        "opp": [opp.handCount, opp.deckCount, len(opp.prize or []), len(opp.bench or [])],
        "active_hp": [
            (me.active[0].hp if me.active and me.active[0] else None),
            (opp.active[0].hp if opp.active and opp.active[0] else None),
        ],
    }


def _full_signature(obs: Observation | None) -> str | None:
    """Canonical JSON of every field in an observation (Q3 divergence check)."""
    if obs is None:
        return None

    def default(value):
        if hasattr(value, "__dict__"):
            return value.__dict__
        return str(value)

    return json.dumps(obs.__dict__, sort_keys=True, default=default)


def _terminal(node) -> tuple[bool, int | None]:
    obs = node.observation
    if obs is None or obs.current is None:
        return True, None
    result = int(obs.current.result)
    if result >= 0:
        return True, result
    if obs.select is None:
        return True, result
    return False, result


def _rollout(root, rng: random.Random, max_steps: int):
    """Random rollout from ``root``; returns (node, steps, terminal, ids)."""
    node = root
    ids: list[int] = []
    for step in range(max_steps):
        done, _ = _terminal(node)
        if done:
            return node, step, True, ids
        node = search_step(node.searchId, _random_picks(node.observation.select, rng))
        ids.append(node.searchId)
    return node, max_steps, False, ids


def _advance_to_decision(deck: list[int], opp_deck: list[int], min_turn: int):
    """Start a battle and stop at a usable decision state.

    Prefer our first MAIN decision at/after ``min_turn``.  Games are stochastic
    and a fast first-legal policy can end a game before that turn, so fall back
    to the latest MAIN decision we saw, then to any decision.  The encoded
    ``search_begin_input`` remains valid after the battle object goes away, so
    no second battle is needed.
    """
    obs, start = battle_start(deck, opp_deck)
    if obs is None:
        raise RuntimeError("battle_start failed")
    main_fallback = None
    any_fallback = None
    for _ in range(4000):
        sel = obs.get("select")
        current = obs.get("current") or {}
        if sel is None:
            obs = battle_select(deck)
            continue
        if current.get("result", -1) >= 0:
            break
        if current.get("yourIndex") == 0:
            observation = to_observation_class(obs)
            if observation.select is not None:
                if observation.select.context == SelectContext.MAIN:
                    if observation.current.turn >= min_turn:
                        return observation
                    if (main_fallback is None
                            or observation.current.turn > main_fallback.current.turn):
                        main_fallback = observation
                elif any_fallback is None:
                    any_fallback = observation
        obs = battle_select(_first_legal(sel))
    if main_fallback is not None:
        return main_fallback
    if any_fallback is not None:
        return any_fallback
    raise RuntimeError("could not reach a decision state")


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", default=str(ROOT / "decks" / "default.csv"))
    parser.add_argument("--opp-deck", default=str(ROOT / "decks" / "default.csv"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-turn", type=int, default=4)
    parser.add_argument("--rollouts", type=int, default=100)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--branch-depth", type=int, default=12)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    deck = decklib.load_deck(args.deck)
    opp_deck = decklib.load_deck(args.opp_deck)
    for path, cards_ in ((args.deck, deck), (args.opp_deck, opp_deck)):
        problems = decklib.validate_deck(cards_)
        if problems:
            raise SystemExit(f"{path}: " + "; ".join(problems))

    rng = random.Random(args.seed)
    obs = _advance_to_decision(deck, opp_deck, args.min_turn)
    belief = build_belief(obs, deck, opp_deck, rng)

    me = obs.current.players[obs.current.yourIndex]
    opp = obs.current.players[1 - obs.current.yourIndex]
    print("decision: turn=%d yourIndex=%d select=%s/%s options=%d"
          % (obs.current.turn, obs.current.yourIndex, obs.select.type, obs.select.context,
             len(obs.select.option)))
    print("visible: me deck=%d prize=%d hand=%d | opp deck=%d prize=%d hand=%d"
          % (me.deckCount, len(me.prize or []), me.handCount,
             opp.deckCount, len(opp.prize or []), opp.handCount))
    print("belief sizes: your_deck=%d your_prize=%d opp_deck=%d opp_prize=%d opp_hand=%d opp_active=%d"
          % (len(belief["your_deck"]), len(belief["your_prize"]),
             len(belief["opponent_deck"]), len(belief["opponent_prize"]),
             len(belief["opponent_hand"]), len(belief["opponent_active"])))

    report: dict = {
        "decision": {
            "turn": obs.current.turn,
            "yourIndex": obs.current.yourIndex,
            "select_type": int(obs.select.type),
            "select_context": int(obs.select.context),
            "options": len(obs.select.option),
            "visible": {
                "me": [me.deckCount, len(me.prize or []), me.handCount],
                "opp": [opp.deckCount, len(opp.prize or []), opp.handCount],
            },
        },
        "belief_sizes": {key: len(value) for key, value in belief.items()},
    }

    # ---- Q1: search_begin from a belief -----------------------------------
    begin_times = []
    root = None
    for _ in range(5):
        t0 = time.perf_counter()
        root = search_begin(obs, **belief)
        begin_times.append((time.perf_counter() - t0) * 1000.0)
        if root.observation is None:
            break
        search_end()
    t0 = time.perf_counter()
    root = search_begin(obs, **belief)
    begin_ms = (time.perf_counter() - t0) * 1000.0
    ok1 = root.observation is not None and root.searchId >= 0
    report["q1"] = {
        "ok": ok1,
        "search_id": root.searchId,
        "turn": root.observation.current.turn if root.observation and root.observation.current else None,
        "select_type": int(root.observation.select.type) if root.observation and root.observation.select else None,
        "select_context": int(root.observation.select.context) if root.observation and root.observation.select else None,
        "options": len(root.observation.select.option) if root.observation and root.observation.select else 0,
        "begin_ms": round(begin_ms, 3),
        "begin_ms_median": round(statistics.median(begin_times), 3),
    }
    print("Q1 search_begin: %s id=%s turn=%s options=%d (%.2f ms)"
          % ("OK" if ok1 else "FAIL", root.searchId,
             report["q1"]["turn"], report["q1"]["options"], begin_ms))
    if not ok1:
        print("Q1 failed; not running Q2-Q4", file=sys.stderr)
        search_end()
        battle_finish()
        if args.json_out:
            path = Path(args.json_out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2))
        return 1

    # ---- Q2: one random rollout to terminal -------------------------------
    end_node, steps, terminal, rollout_ids = _rollout(root, rng, args.max_steps)
    result = end_node.observation.current.result if end_node.observation and end_node.observation.current else None
    report["q2"] = {
        "ok": terminal,
        "steps": steps,
        "terminal": terminal,
        "result": result,
    }
    print("Q2 rollout: %s steps=%d result=%s"
          % ("terminal" if terminal else "MAX_STEPS", steps, result))
    for search_id in rollout_ids:
        search_release(search_id)

    # ---- Q3: branching from the same node ---------------------------------
    select = root.observation.select
    n_options = len(select.option)
    count = min(max(1, int(select.minCount or 0)), n_options) if n_options else 0

    def pick_for(index: int) -> list[int]:
        if n_options == 0:
            return []
        others = [other for other in range(n_options) if other != index]
        return [index] + others[: max(0, count - 1)]

    # Try candidate pairs until two *different* picks produce different states.
    # Two distinct option objects can still normalize to the same state (e.g.
    # two identical copies of the same card), so we check the full observation.
    candidate_pairs = [
        (i, j) for i in range(n_options) for j in range(i + 1, n_options)
    ][:24]
    pair = candidate_pairs[0] if candidate_pairs else (0, min(1, max(0, n_options - 1)))
    branch_a = branch_b = None
    discarded_ids: list[int] = []
    for candidate in candidate_pairs:
        left = search_step(root.searchId, pick_for(candidate[0]))
        right = search_step(root.searchId, pick_for(candidate[1]))
        if (left.searchId != right.searchId
                and _full_signature(left.observation) != _full_signature(right.observation)):
            pair, branch_a, branch_b = candidate, left, right
            break
        discarded_ids.extend([left.searchId, right.searchId])

    if branch_a is None:
        branch_a = search_step(root.searchId, pick_for(pair[0]))
        branch_b = search_step(root.searchId, pick_for(pair[1]))

    picks = [pick_for(pair[0]), pick_for(pair[1])]
    sig_a, sig_b = _signature(branch_a.observation), _signature(branch_b.observation)
    diverged = (
        branch_a.searchId != branch_b.searchId
        and _full_signature(branch_a.observation) != _full_signature(branch_b.observation)
    )

    # Re-taking branch A after B proves the root was not consumed by B.  Exact
    # replay is not guaranteed when the branch draws cards, so this is reported
    # as a diagnostic rather than a pass/fail condition.
    replay_a = search_step(root.searchId, picks[0])
    independent_replay = _signature(replay_a.observation) == sig_a

    # Continue both branches and compare their final fingerprints.
    node_a, node_b = branch_a, branch_b
    ids_extra = [*discarded_ids, branch_a.searchId, branch_b.searchId, replay_a.searchId]
    differ_at = None
    for depth in range(args.branch_depth):
        done_a, _ = _terminal(node_a)
        done_b, _ = _terminal(node_b)
        if done_a or done_b:
            break
        node_a = search_step(node_a.searchId, _random_picks(node_a.observation.select, rng))
        node_b = search_step(node_b.searchId, _random_picks(node_b.observation.select, rng))
        ids_extra.extend([node_a.searchId, node_b.searchId])
        if differ_at is None and _signature(node_a.observation) != _signature(node_b.observation):
            differ_at = depth + 1

    report["q3"] = {
        "ok": diverged,
        "pair": list(pair),
        "branch_ids": [branch_a.searchId, branch_b.searchId],
        "diverged": diverged,
        "independent_replay": independent_replay,
        "deep_divergence_step": differ_at,
    }
    print("Q3 branch: pair=%s ids=%s diverged=%s independent_replay=%s deep_diff=%s"
          % (pair, report["q3"]["branch_ids"], diverged, independent_replay, differ_at))

    for search_id in ids_extra:
        search_release(search_id)

    # ---- Q4: rollout throughput ------------------------------------------
    n_rollouts = max(1, args.rollouts)
    total_steps = 0
    terminals = 0
    t0 = time.perf_counter()
    for _ in range(n_rollouts):
        node, n_steps, is_terminal, ids = _rollout(root, rng, args.max_steps)
        total_steps += n_steps
        terminals += int(is_terminal)
        for search_id in ids:
            search_release(search_id)
    wall = time.perf_counter() - t0
    report["q4"] = {
        "ok": total_steps > 0,
        "rollouts": n_rollouts,
        "steps": total_steps,
        "terminal_rollouts": terminals,
        "terminal_rate": round(terminals / n_rollouts, 4),
        "wall_s": round(wall, 3),
        "rollouts_per_s": round(n_rollouts / wall, 2),
        "steps_per_s": round(total_steps / wall, 1),
        "mean_steps_per_rollout": round(total_steps / n_rollouts, 1),
    }
    print("Q4 throughput: %.1f rollouts/s, %.0f steps/s, mean %.1f steps, terminal %.0f%% (%.2fs)"
          % (report["q4"]["rollouts_per_s"], report["q4"]["steps_per_s"],
             report["q4"]["mean_steps_per_rollout"], 100 * report["q4"]["terminal_rate"], wall))

    search_end()
    battle_finish()

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2))
        print(f"wrote {path}")

    return 0 if all(report[key]["ok"] for key in ("q1", "q2", "q3", "q4")) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - a probe should fail cleanly
        print(f"probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
