"""Analyse a folder of Kaggle playground episode replays.

Extracts, per episode: both decks, team names, winner, turns, and derives an
archetype label from the deck's Pokémon lines.  Aggregates archetype share,
win rate and a matchup matrix.

Usage:
  python scripts/analyze_episodes.py <episodes_dir> --out results/meta_1109 [--workers 6]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_cards() -> dict:
    p = ROOT / "data" / "cards.json"
    return {c["cardId"]: c for c in json.loads(p.read_text())}


def archetype_of(deck: list[int], cards: dict) -> tuple[str, tuple[str, ...]]:
    """Name a deck by its most valuable Pokémon line(s)."""
    counts = collections.Counter(deck)
    mons = []
    for cid, n in counts.items():
        c = cards.get(cid)
        if not c or c.get("cardType") != 0:
            continue
        value = c.get("hp", 0) + (60 if c.get("ex") else 0) + (120 if c.get("megaEx") else 0)
        # prefer the highest evolution stage in a line
        if c.get("stage2"):
            value += 40
        elif c.get("stage1"):
            value += 20
        mons.append((value, n, c.get("name", str(cid))))
    mons.sort(reverse=True)
    if not mons:
        return "unknown", ()
    top = mons[0][2]
    key = tuple(sorted(m[2] for m in mons[:3]))
    return top, key


def read_episode(path: str) -> dict | None:
    try:
        d = json.loads(Path(path).read_text())
        steps = d["steps"]
        decks = [list(steps[1][0]["action"]), list(steps[1][1]["action"])]
        rewards = d.get("rewards") or [0, 0]
        names = (d.get("info") or {}).get("TeamNames") or ["p0", "p1"]
        vis = (steps[0][0].get("visualize") or [])
        turns = len(vis)
        return {
            "episode": Path(path).stem,
            "names": list(names),
            "rewards": list(rewards),
            "decks": decks,
            "turns": turns,
            "seed": (d.get("configuration") or {}).get("seed"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"episode": Path(path).stem, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes")
    ap.add_argument("--out", default="results/meta")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cards = load_cards()
    files = sorted(Path(args.episodes).glob("*.json"))
    if args.limit:
        files = files[: args.limit]
    print(f"episodes: {len(files)}")

    rows = []
    if args.workers <= 1:
        for f in files:
            r = read_episode(str(f))
            if r:
                rows.append(r)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(read_episode, [str(f) for f in files], chunksize=4):
                if r:
                    rows.append(r)

    errors = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]

    # dedupe exact deck-pair repeats? keep all games.
    deck_counts: collections.Counter = collections.Counter()
    deck_names: dict = {}
    deck_arch: dict = {}
    for r in rows:
        for d in r["decks"]:
            h = tuple(sorted(collections.Counter(d).items()))
            deck_counts[h] += 1
            if h not in deck_names:
                deck_arch[h] = archetype_of(d, cards)
                deck_names[h] = deck_arch[h][0]

    arch_games = collections.Counter()
    arch_wins = collections.Counter()
    matchups = collections.Counter()
    for r in rows:
        archs = []
        for i, d in enumerate(r["decks"]):
            h = tuple(sorted(collections.Counter(d).items()))
            archs.append(deck_names[h])
        if r["rewards"][0] > r["rewards"][1]:
            w = 0
        elif r["rewards"][1] > r["rewards"][0]:
            w = 1
        else:
            w = -1
        for a in archs:
            arch_games[a] += 1
        if w >= 0:
            arch_wins[archs[w]] += 1
        if w >= 0:
            matchups[(archs[0], archs[1], w)] += 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "episodes.jsonl").open("w") as f:
        for r in rows:
            r = dict(r)
            r["archetypes"] = [deck_names[tuple(sorted(collections.Counter(d).items()))] for d in r["decks"]]
            f.write(json.dumps(r) + "\n")

    summary = {
        "episodes": len(rows),
        "errors": len(errors),
        "unique_decks": len(deck_counts),
        "avg_turns": sum(r["turns"] for r in rows) / max(len(rows), 1),
        "archetypes": [
            {
                "archetype": a,
                "games": arch_games[a],
                "wins": arch_wins[a],
                "winrate": arch_wins[a] / max(arch_games[a], 1),
                "share": arch_games[a] / max(2 * len(rows), 1),
            }
            for a in arch_games
        ],
    }
    summary["archetypes"].sort(key=lambda x: -x["games"])
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    # top decks
    top_decks = []
    for h, n in deck_counts.most_common(30):
        top_decks.append({"count": n, "archetype": deck_names[h], "deck": [c for c, k in h for _ in range(k)]})
    (out / "top_decks.json").write_text(json.dumps(top_decks, indent=2))

    # matchup matrix
    archs = [a["archetype"] for a in summary["archetypes"]][:20]
    mat = {a: {b: [0, 0] for b in archs} for a in archs}
    for (a, b, w), n in matchups.items():
        if a in mat and b in mat[a]:
            mat[a][b][0] += n if w == 0 else 0
            mat[a][b][1] += n
            mat[b][a][0] += n if w == 1 else 0
            mat[b][a][1] += n
    (out / "matchups.json").write_text(json.dumps(mat, indent=2))

    print(json.dumps(summary, indent=2)[:4000])
    print(f"wrote {out}/episodes.jsonl summary.json top_decks.json matchups.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
