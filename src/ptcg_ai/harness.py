"""Local battle harness built on the cabt ctypes engine.

The engine is a *process-global* singleton (one battle at a time), so parallel
evaluation must use separate processes.  `scripts/arena.py` does that.

The harness mirrors the Kaggle contract:
  * `agent(obs) -> list[int]`
  * `obs["select"] is None`  ->  return the 60-card deck
  * an exception / illegal selection / timeout is a loss (Kaggle marks the
    player INVALID and the opponent wins).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

Agent = Callable[[dict], list[int]]

MAX_DECISIONS = 6000
MAX_TURNS = 200


@dataclass
class Decision:
    who: int
    context: int
    select_type: int
    n_options: int
    action: list[int]
    ms: float


@dataclass
class GameResult:
    winner: int  # 0 / 1 / 2 (draw)
    reason: str = ""
    turns: int = 0
    decisions: int = 0
    think_ms: float = 0.0
    wall_ms: float = 0.0
    max_decision_ms: float = 0.0
    illegal: bool = False
    error: str = ""
    error_player: int = -1
    seats: tuple[str, str] = ("", "")
    deck_ids: tuple[list[int], list[int]] = field(default_factory=lambda: ([], []))
    trace: list[Decision] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d.pop("trace", None)
        d["deck_ids"] = list(self.deck_ids)
        return d


def _validate(action: Any, sel: dict) -> tuple[list[int] | None, str]:
    if not isinstance(action, (list, tuple)):
        return None, f"action is {type(action).__name__}, not list"
    try:
        action = [int(a) for a in action]
    except Exception:
        return None, "non-integer action"
    n = len(sel.get("option") or [])
    lo = int(sel.get("minCount") or 0)
    hi = int(sel.get("maxCount") if sel.get("maxCount") is not None else 1)
    if len(action) < lo or len(action) > hi:
        return None, f"bad count {len(action)} not in [{lo},{hi}]"
    if len(set(action)) != len(action):
        return None, "duplicate option indices"
    for a in action:
        if a < 0 or a >= n:
            return None, f"index {a} out of range (n={n})"
    return action, ""


def play_game(
    agent0: Agent,
    agent1: Agent,
    deck0: list[int],
    deck1: list[int],
    names: tuple[str, str] = ("p0", "p1"),
    keep_trace: bool = False,
    decision_budget_s: float = 600.0,
) -> GameResult:
    """Play one single game (BO1) and return the result."""
    # Imported lazily so tooling that never plays a game does not need the SDK.
    from kaggle_environments.envs.cabt.cg.game import battle_finish, battle_select, battle_start

    res = GameResult(winner=2, seats=names, deck_ids=(list(deck0), list(deck1)))
    t_start = time.perf_counter()
    obs, start = battle_start(list(deck0), list(deck1))
    if obs is None or getattr(start, "errorPlayer", -1) >= 0:
        res.error = f"battle_start failed: errorPlayer={getattr(start, 'errorPlayer', '?')}"
        res.error_player = int(getattr(start, "errorPlayer", -1))
        res.winner = 1 if getattr(start, "errorPlayer", 0) == 0 else 0
        res.illegal = True
        return res

    agents = (agent0, agent1)
    spent = [0.0, 0.0]
    n_dec = 0
    try:
        while True:
            sel = obs.get("select")
            cur = obs.get("current")
            if sel is None:
                obs = battle_select(list(deck0))
                continue
            if cur is None:
                break
            if cur.get("result", -1) != -1:
                res.winner = int(cur["result"])
                break
            who = int(cur["yourIndex"])
            n_dec += 1
            if n_dec > MAX_DECISIONS:
                res.error = "too many decisions"
                res.error_player = who
                res.winner = 1 - who
                break
            t0 = time.perf_counter()
            try:
                action = agents[who](obs)
            except Exception as exc:  # noqa: BLE001
                res.error = f"agent {who} raised {type(exc).__name__}: {exc}"
                res.error_player = who
                res.winner = 1 - who
                res.illegal = True
                break
            ms = (time.perf_counter() - t0) * 1000.0
            res.max_decision_ms = max(res.max_decision_ms, ms)
            res.think_ms += ms
            spent[who] += ms / 1000.0
            action, why = _validate(action, sel)
            if action is None:
                res.error = f"agent {who} illegal: {why}"
                res.error_player = who
                res.winner = 1 - who
                res.illegal = True
                break
            if keep_trace:
                res.trace.append(Decision(who, int(sel.get("context", -1)), int(sel.get("type", -1)), len(sel.get("option") or []), action, ms))
            if spent[who] > decision_budget_s:
                res.error = f"agent {who} exceeded {decision_budget_s:.0f}s of thinking time"
                res.error_player = who
                res.winner = 1 - who
                break
            obs = battle_select(action)
        else:  # pragma: no cover
            res.error = "loop exited unexpectedly"
    finally:
        try:
            res.turns = int(((obs or {}).get("current") or {}).get("turn", 0))
        except Exception:
            pass
        res.decisions = n_dec
        res.wall_ms = (time.perf_counter() - t_start) * 1000.0
        try:
            battle_finish()
        except Exception:
            pass
    return res
