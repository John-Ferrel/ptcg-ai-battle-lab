"""Parse Kaggle cabt episode replays into (observation, action) decisions.

Off-by-one rule (verified on 1,694 replays):
  the action recorded at step t+1 for player p answers the observation that p
  saw at step t.  We verified this by checking legality: next-step actions are
  valid for the current-step select in 100% of cases; same-step actions are not.

Only the *acting* player (the one whose observation has a non-null `select`) is
paired.  Deck-selection steps (select is None) are skipped.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_episode(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def decisions(ep: dict) -> list[dict]:
    """Return [{'obs', 'action', 'player', 'step', 'score'}] in chronological order."""
    steps = ep.get("steps") or []
    info = ep.get("info") or {}
    names = info.get("TeamNames") or ["p0", "p1"]
    rewards = ep.get("rewards") or [0, 0]
    out: list[dict] = []
    for t in range(len(steps) - 1):
        step = steps[t]
        for p in (0, 1):
            try:
                obs = step[p]["observation"]
                sel = obs.get("select")
                if not sel:
                    continue
                if (obs.get("current") or {}).get("yourIndex") != p:
                    continue
                # next step must be this player's answer
                nxt = steps[t + 1][p]
                if nxt.get("status") not in ("ACTIVE", "INACTIVE"):
                    continue
                act = nxt.get("action")
                if not isinstance(act, list):
                    continue
                out.append(
                    {
                        "obs": obs,
                        "action": [int(a) for a in act],
                        "player": p,
                        "step": t,
                        "names": names,
                        "rewards": rewards,
                        "episode": ep.get("id"),
                        "seed": (ep.get("configuration") or {}).get("seed"),
                    }
                )
            except Exception:  # noqa: BLE001 -- a replay must never crash the miner
                continue
    return out


def iter_episodes(directory: str | Path):
    for p in sorted(Path(directory).glob("*.json")):
        try:
            yield p, load_episode(p)
        except Exception:
            continue
