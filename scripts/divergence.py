"""Measure where our policy disagrees with the top human/agent pilots.

For every recorded decision we run our agent on the same observation and compare
the *semantic* choice (card id / attack id / option type), not the raw index, so
two identical energy copies are not counted as a disagreement.

Usage:
  python scripts/divergence.py <episodes_dir> --agent agents/heuristic_v1 \
      --min-score 1200 --limit 300 --workers 4 --top 15
"""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import cards, replay  # noqa: E402

_AGENT = None

CTX_LABELS = {
    0: "MAIN", 1: "SETUP_ACTIVE", 2: "SETUP_BENCH", 3: "SWITCH", 4: "TO_ACTIVE",
    5: "TO_BENCH", 7: "EVOLVE/SEARCH", 8: "DISCARD", 13: "DMG_COUNTER",
    14: "DMG_COUNTER_ANY", 15: "DAMAGE", 21: "ATTACH_FROM", 22: "ATTACH_TO",
    30: "DISCARD_ENERGY", 41: "IS_FIRST",
}


def load_agent(path: str):
    global _AGENT
    if _AGENT is not None:
        return _AGENT
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    spec = importlib.util.spec_from_file_location("div_agent", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    _AGENT = mod.agent
    return _AGENT


def _area_card(obs: dict, area, index, player):
    st = obs["current"]
    p = st["players"][player]
    if area == 1:  # DECK (revealed only when the effect looks at it)
        d = (obs.get("select") or {}).get("deck") or []
        return d[index]["id"] if 0 <= index < len(d) else None
    if area == 2:  # HAND
        h = p.get("hand") or []
        return h[index]["id"] if 0 <= index < len(h) else None
    if area == 3:  # DISCARD
        d = p.get("discard") or []
        return d[index]["id"] if 0 <= index < len(d) else None
    if area == 4:  # ACTIVE
        a = p.get("active") or []
        return a[0]["id"] if a and a[0] else None
    if area == 5:  # BENCH
        b = p.get("bench") or []
        return b[index]["id"] if 0 <= index < len(b) else None
    if area == 12:  # LOOKING
        lk = st.get("looking") or []
        c = lk[index] if 0 <= index < len(lk) else None
        return c["id"] if c else None
    return None


def semantic(obs: dict, opt: dict) -> tuple:
    """Return a comparable key for an option."""
    t = opt.get("type")
    if t == 13:
        return ("attack", opt.get("attackId"))
    if t == 14:
        return ("end",)
    if t in (1, 2):
        return ("yesno", t)
    if t == 0:
        return ("number", opt.get("number"))
    if t in (3, 4, 5, 11):
        player = opt.get("playerIndex", obs["current"]["yourIndex"])
        cid = _area_card(obs, opt.get("area"), opt.get("index", -1), player)
        return ("card", cid if cid is not None else f"t{t}a{opt.get('area')}")
    if t == 7:
        h = obs["current"]["players"][obs["current"]["yourIndex"]].get("hand") or []
        i = opt.get("index", -1)
        return ("play", h[i]["id"] if 0 <= i < len(h) else None)
    if t in (8, 9):
        if opt.get("area") == 1:
            cid = _area_card(obs, 1, opt.get("index", -1), obs["current"]["yourIndex"])
            return ("card", cid)
        h = obs["current"]["players"][obs["current"]["yourIndex"]].get("hand") or []
        i = opt.get("index", -1)
        return ("card", h[i]["id"] if 0 <= i < len(h) else None)
    if t == 10:
        return ("ability", opt.get("area"), opt.get("index"))
    return (f"type{t}",)


def label(key: tuple) -> str:
    if key[0] == "card":
        return cards.name(key[1]) if isinstance(key[1], int) else str(key[1])
    if key[0] == "play":
        return f"PLAY {cards.name(key[1])}" if isinstance(key[1], int) else "PLAY ?"
    if key[0] == "attack":
        return f"ATTACK {cards.attack(key[1]).get('name', key[1])}"
    if key[0] == "ability":
        return "ABILITY"
    return "/".join(str(x) for x in key)


def mine_file(args) -> dict:
    path, agent_path = args
    agent = load_agent(agent_path)
    ep = replay.load_episode(path)
    out = {"n": 0, "agree": 0, "ctx": collections.Counter(), "ctx_agree": collections.Counter(),
           "pairs": collections.Counter(), "semantic": True}
    for d in replay.decisions(ep):
        sel = d["obs"]["select"]
        if not d["action"] or sel.get("maxCount") != 1 or sel.get("minCount", 0) > 1:
            continue
        opts = sel.get("option") or []
        if not opts or len(opts) > 40:
            continue
        try:
            act = agent(d["obs"])
        except Exception:
            continue
        if not isinstance(act, list) or len(act) != 1 or not (0 <= act[0] < len(opts)):
            continue
        ctx = sel.get("context")
        theirs_idx = d["action"][0]
        if not (0 <= theirs_idx < len(opts)):
            continue
        ours = semantic(d["obs"], opts[act[0]])
        theirs = semantic(d["obs"], opts[theirs_idx])
        out["n"] += 1
        out["ctx"][ctx] += 1
        if ours == theirs:
            out["agree"] += 1
            out["ctx_agree"][ctx] += 1
        else:
            out["pairs"][(ctx, label(ours), label(theirs))] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes")
    ap.add_argument("--agent", default="agents/heuristic_v1")
    ap.add_argument("--min-score", type=float, default=1200)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="results/divergence.json")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    manifest_path = Path(args.episodes) / "manifest.csv"
    allow = None
    if manifest_path.exists():
        allow = {r["episode_id"] for r in csv.DictReader(manifest_path.open()) if float(r["min_score"]) >= args.min_score}
    files = [p for p in sorted(Path(args.episodes).glob("*.json")) if (allow is None or p.stem in allow)]
    if args.limit:
        files = files[: args.limit]
    print(f"files: {len(files)} (min_score >= {args.min_score})")

    total = collections.Counter()
    agree = collections.Counter()
    pairs = collections.Counter()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(mine_file, [(str(f), args.agent) for f in files], chunksize=4):
            total.update(r["ctx"])
            agree.update(r["ctx_agree"])
            pairs.update(r["pairs"])

    n = sum(total.values())
    a = sum(agree.values())
    print(f"decisions: {n}  semantic agreement: {a}/{n} = {a/max(n,1):.1%}")
    print(f"{'ctx':>4} {'n':>8} {'agree':>7}  label")
    for ctx, c in total.most_common(16):
        print(f"{ctx:>4} {c:>8} {agree[ctx]/c:>7.1%}  {CTX_LABELS.get(ctx, '')}")
    print("\nTop MAIN disagreements (ours -> theirs):")
    for (ctx, ours, theirs), c in pairs.most_common(200):
        if ctx == 0:
            print(f"  {c:5d}  {ours:34s} -> {theirs}")
            if c < 30:
                break
    print("\nTop EVOLVE/SEARCH disagreements:")
    shown = 0
    for (ctx, ours, theirs), c in pairs.most_common(400):
        if ctx == 7:
            print(f"  {c:5d}  {ours:28s} -> {theirs}")
            shown += 1
            if shown >= args.top:
                break

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "decisions": n, "agreement": a / max(n, 1),
        "by_context": {str(k): {"n": v, "agree": agree[k]} for k, v in total.items()},
        "pairs": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in pairs.most_common(300)},
    }, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
