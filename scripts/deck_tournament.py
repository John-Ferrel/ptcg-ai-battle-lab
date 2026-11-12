"""Deck round-robin tournament with the pilot held fixed.

Two stages:
    stage1: every pair of candidate decks, seat-swapped, N games per pair.
    stage2: the top-K decks from stage1, seat-swapped, M games per pair.

The pilot (`--agent`) is identical on both sides; only the 60-card list changes.
Raw per-game JSONL goes to the output directory, aggregate tables to CSV. Games
that hit the harness decision cap (`error="too many decisions"`) are reported as
`aborted` and excluded from win rates rather than awarded to either side.

Example (real-meta pool):
    .venv/bin/python scripts/deck_tournament.py stage1 \
        --candidates decks/candidates_meta --agent agents/greedy \
        --games 60 --workers 2 --out-dir results/deck_stage1_meta
    .venv/bin/python scripts/deck_tournament.py stage2 \
        --summary results/deck_stage1_meta/summary.csv --agent agents/greedy \
        --top 6 --games 200 --workers 2 --out-dir results/deck_stage2_meta \
        --csv-out results/deck_tournament_stage2.csv
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402
from ptcg_ai.harness import play_game  # noqa: E402

_AGENT = None
_AGENT_PATH: str | None = None


def load_agent(path: str):
    """Load an `agent(obs)` callable from a directory or a main.py path."""
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    spec = importlib.util.spec_from_file_location(f"agent_{abs(hash(str(p.resolve())))}", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if fn is None:
        raise SystemExit(f"{p} has no agent(obs) function")
    return fn


def _init_worker(agent_path: str) -> None:
    global _AGENT, _AGENT_PATH
    _AGENT_PATH = agent_path
    _AGENT = load_agent(agent_path)


def _run_chunk(job: dict) -> list[dict]:
    """Play a contiguous chunk of games between two decks, alternating seats."""
    fn = _AGENT
    assert fn is not None
    deck_a = decklib.load_deck(job["deck_a"])
    deck_b = decklib.load_deck(job["deck_b"])
    rows: list[dict] = []
    for game in job["games"]:
        a_is_p0 = game % 2 == 0
        if a_is_p0:
            r = play_game(fn, fn, deck_a, deck_b, names=(job["name_a"], job["name_b"]))
        else:
            r = play_game(fn, fn, deck_b, deck_a, names=(job["name_b"], job["name_a"]))
        a_won = (r.winner == 0) if a_is_p0 else (r.winner == 1)
        rows.append(
            {
                "game": game,
                "a_is_p0": a_is_p0,
                "a_won": int(a_won),
                "draw": int(r.winner == 2),
                "winner": r.winner,
                "turns": r.turns,
                "decisions": r.decisions,
                "think_ms": round(r.think_ms, 3),
                "illegal": int(r.illegal),
                "error": r.error,
                "name_a": job["name_a"],
                "name_b": job["name_b"],
                "deck_a": job["deck_a"],
                "deck_b": job["deck_b"],
            }
        )
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def run_round_robin(
    decks: list[dict],
    agent_path: str,
    games: int,
    workers: int,
    out_dir: Path,
    chunk: int = 10,
    resume: bool = False,
) -> list[dict]:
    """Play a full round robin and write raw JSONL + aggregate CSVs.

    With ``resume``, a pair whose JSONL already has exactly ``games`` rows is
    reused instead of replayed (used to keep a previously measured control arm).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(i, j) for i in range(len(decks)) for j in range(i + 1, len(decks))]
    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    expected = {f"{decks[i]['id']}__VS__{decks[j]['id']}": games for i, j in pairs}
    jobs: list[dict] = []
    for i, j in pairs:
        key = f"{decks[i]['id']}__VS__{decks[j]['id']}"
        raw = out_dir / f"{_safe(key)}.jsonl"
        if resume and raw.exists():
            rows = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
            if len(rows) == games:
                # A reused pair may have been recorded with the opposite A/B
                # orientation; normalise it to this run's ordering.
                if rows and rows[0]["name_a"] == decks[j]["id"] and rows[0]["name_b"] == decks[i]["id"]:
                    for r in rows:
                        r["a_won"] = 1 - r["a_won"] - r["draw"]
                        r["name_a"], r["name_b"] = r["name_b"], r["name_a"]
                        r["deck_a"], r["deck_b"] = r["deck_b"], r["deck_a"]
                        r["a_is_p0"] = not r["a_is_p0"]
                by_pair[key] = rows
                continue
            print(f"resume: {key} has {len(rows)}/{games} rows, replaying")
        for start in range(0, games, chunk):
            end = min(start + chunk, games)
            jobs.append(
                {
                    "deck_a": decks[i]["path"],
                    "deck_b": decks[j]["path"],
                    "name_a": decks[i]["id"],
                    "name_b": decks[j]["id"],
                    "games": list(range(start, end)),
                }
            )

    started = {(j["name_a"], j["name_b"]) for j in jobs}
    reused = len(pairs) - len(started)
    if reused:
        print(f"resume: reused {reused} completed pair(s) from {out_dir}")
    seen: dict[str, int] = defaultdict(int)
    t0 = time.perf_counter()
    done = reused

    if workers <= 1:
        _init_worker(agent_path)
        for job in jobs:
            rows = _run_chunk(job)
            key = f"{job['name_a']}__VS__{job['name_b']}"
            by_pair[key].extend(rows)
            seen[key] += len(rows)
            if seen[key] == expected[key]:
                _write_rows(out_dir / f"{_safe(key)}.jsonl", by_pair[key])
                done += 1
                _progress(done, len(pairs), t0, key)
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker, initargs=(agent_path,)
        ) as ex:
            futures = {ex.submit(_run_chunk, job): job for job in jobs}
            for fut in as_completed(futures):
                job = futures[fut]
                rows = fut.result()
                key = f"{job['name_a']}__VS__{job['name_b']}"
                by_pair[key].extend(rows)
                seen[key] += len(rows)
                if seen[key] == expected[key]:
                    _write_rows(out_dir / f"{_safe(key)}.jsonl", by_pair[key])
                    done += 1
                    _progress(done, len(pairs), t0, key)

    all_rows = [r for key in expected for r in by_pair.get(key, [])]
    stats = aggregate(decks, by_pair)
    _write_aggregates(decks, stats, by_pair, out_dir)
    print(f"round robin done: {len(all_rows)} games in {time.perf_counter() - t0:.1f}s")
    return stats


def _progress(done: int, total: int, t0: float, key: str) -> None:
    elapsed = time.perf_counter() - t0
    print(f"[{done}/{total}] {key} ({elapsed:.0f}s)", flush=True)


def aggregate(decks: list[dict], by_pair: dict[tuple[str, str], list[dict]]) -> list[dict]:
    stats: dict[str, dict] = {d["id"]: defaultdict(int) for d in decks}
    for key, rows in by_pair.items():
        a, b = key.split("__VS__")
        for r in rows:
            stats[a]["games"] += 1
            stats[b]["games"] += 1
            if r.get("error"):
                # Non-terminating game (decision cap). Uninformative for deck
                # strength; counted separately rather than awarded to either side.
                stats[a]["aborted"] += 1
                stats[b]["aborted"] += 1
                continue
            if r["draw"]:
                stats[a]["draws"] += 1
                stats[b]["draws"] += 1
            elif r["a_won"]:
                stats[a]["wins"] += 1
                stats[b]["losses"] += 1
            else:
                stats[b]["wins"] += 1
                stats[a]["losses"] += 1
    out: list[dict] = []
    for d in decks:
        s = stats[d["id"]]
        dec = s["wins"] + s["losses"]
        lo, hi = wilson(s["wins"], dec)
        out.append(
            {
                "deck": d["id"],
                "archetype": d.get("archetype", ""),
                "path": d["path"],
                "games": s["games"],
                "completed": s["games"] - s["aborted"],
                "wins": s["wins"],
                "losses": s["losses"],
                "draws": s["draws"],
                "aborted": s["aborted"],
                "winrate": round(s["wins"] / dec, 4) if dec else 0.0,
                "ci_low": round(lo, 4),
                "ci_high": round(hi, 4),
                "wilson_low": round(lo, 4),
                "avg_turns": 0.0,
            }
        )
    # average turns per deck over completed games only
    turns: dict[str, list[int]] = defaultdict(list)
    for key, rows in by_pair.items():
        a, b = key.split("__VS__")
        for r in rows:
            if r.get("error"):
                continue
            turns[a].append(r["turns"])
            turns[b].append(r["turns"])
    for row in out:
        ts = turns.get(row["deck"], [])
        row["avg_turns"] = round(statistics.mean(ts), 1) if ts else 0.0
    out.sort(key=lambda r: (-r["winrate"], -r["wilson_low"], r["deck"]))
    return out


def _write_aggregates(
    decks: list[dict],
    stats: list[dict],
    by_pair: dict[tuple[str, str], list[dict]],
    out_dir: Path,
) -> None:
    with (out_dir / "summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats[0].keys()))
        w.writeheader()
        w.writerows(stats)
    (out_dir / "summary.json").write_text(json.dumps(stats, indent=2))

    # candidate composition table
    try:
        from ptcg_ai import cards  # noqa: F401

        comp_rows = []
        for d in decks:
            desc = decklib.describe_deck(decklib.load_deck(d["path"]))
            lines = "; ".join(f"{n}x{c}" for n, c in desc["pokemon_lines"][:8])
            comp_rows.append(
                {
                    "deck": d["id"],
                    "archetype": d.get("archetype", ""),
                    "pokemon": desc["pokemon"],
                    "trainers": desc["trainers"],
                    "energy": desc["energy"],
                    "unique": desc["unique"],
                    "pokemon_lines": lines,
                }
            )
        with (out_dir / "composition.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(comp_rows[0].keys()))
            w.writeheader()
            w.writerows(comp_rows)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: composition table skipped: {exc}")

    # head-to-head matrix (non-terminating games excluded from the win rate)
    h2h = []
    for key, rows in sorted(by_pair.items()):
        a, b = key.split("__VS__")
        ok = [r for r in rows if not r.get("error")]
        aw = sum(r["a_won"] for r in ok)
        dr = sum(r["draw"] for r in ok)
        bw = len(ok) - aw - dr
        h2h.append(
            {
                "deck_a": a,
                "deck_b": b,
                "games": len(rows),
                "completed": len(ok),
                "a_wins": aw,
                "b_wins": bw,
                "draws": dr,
                "aborted": len(rows) - len(ok),
                "a_winrate": round(aw / (aw + bw), 4) if aw + bw else 0.0,
            }
        )
    with (out_dir / "head_to_head.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(h2h[0].keys()))
        w.writeheader()
        w.writerows(h2h)


def _load_candidates(candidates: Path, explicit: list[str]) -> tuple[list[dict], list[dict]]:
    paths = [Path(p) for p in explicit] if explicit else sorted(candidates.glob("*.csv"))
    decks: list[dict] = []
    validation: list[dict] = []
    for p in paths:
        d = decklib.load_deck(p)
        problems = decklib.validate_deck(d)
        entry = {
            "path": str(p),
            "id": p.stem,
            "archetype": p.stem.split("_", 1)[1] if "_" in p.stem else p.stem,
            "legal": int(not problems),
            "reason": "; ".join(problems),
        }
        validation.append(entry)
        if problems:
            print(f"DROP {p.name}: {'; '.join(problems)}")
        else:
            decks.append(entry)
    return decks, validation


def _write_validation(validation: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "validation.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(validation[0].keys()))
        w.writeheader()
        w.writerows(validation)
    kept = sum(v["legal"] for v in validation)
    print(f"legality: {kept}/{len(validation)} lists legal")


def cmd_stage1(args) -> int:
    decks, validation = _load_candidates(Path(args.candidates), args.deck)
    if len(decks) < 2:
        raise SystemExit("need at least 2 legal decks")
    out_dir = Path(args.out_dir)
    _write_validation(validation, out_dir)
    stats = run_round_robin(
        decks, args.agent, args.games, args.workers, out_dir,
        chunk=args.chunk, resume=args.resume,
    )
    print("\nStage 1 ranking (winrate over decisive games, Wilson 95% CI):")
    for r in stats:
        print(
            f"  {r['deck']:<24} {r['wins']:>4}W-{r['losses']:<4}L "
            f"{r['aborted']:>4} abort  "
            f"{r['winrate']*100:5.1f}%  [{r['ci_low']*100:4.1f},{r['ci_high']*100:5.1f}]"
        )
    return 0


def cmd_stage2(args) -> int:
    summary_path = Path(args.summary)
    rows = list(csv.DictReader(summary_path.open()))
    rows.sort(key=lambda r: (-float(r["winrate"]), -float(r["wilson_low"])))
    top = rows[: args.top]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    decks = [
        {
            "id": r["deck"],
            "archetype": r.get("archetype", ""),
            "path": r["path"],
        }
        for r in top
    ]
    print("Stage 2 decks:")
    for d in decks:
        print(f"  {d['id']} ({d['path']})")
    stats = run_round_robin(
        decks, args.agent, args.games, args.workers, out_dir,
        chunk=args.chunk, resume=args.resume,
    )
    dest = Path(args.csv_out)
    if dest != out_dir / "summary.csv":
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(stats[0].keys()))
            w.writeheader()
            w.writerows(stats)
    print(f"\nStage 2 ranking -> {dest}")
    for r in stats:
        print(
            f"  {r['deck']:<24} {r['wins']:>4}W-{r['losses']:<4}L "
            f"{r['aborted']:>4} abort  "
            f"{r['winrate']*100:5.1f}%  [{r['ci_low']*100:4.1f},{r['ci_high']*100:5.1f}]"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("stage1", help="full round robin over candidate decks")
    p1.add_argument("--candidates", default="decks/candidates")
    p1.add_argument("--deck", action="append", default=[], help="explicit deck path (repeatable)")
    p1.add_argument("--agent", default="agents/greedy")
    p1.add_argument("--games", type=int, default=60)
    p1.add_argument("--workers", type=int, default=2)
    p1.add_argument("--chunk", type=int, default=10)
    p1.add_argument("--resume", action="store_true", help="reuse complete per-pair JSONL")
    p1.add_argument("--out-dir", default="results/deck_stage1")
    p1.set_defaults(func=cmd_stage1)

    p2 = sub.add_parser("stage2", help="round robin over the top-K decks from stage 1")
    p2.add_argument("--summary", default="results/deck_stage1/summary.csv")
    p2.add_argument("--agent", default="agents/greedy")
    p2.add_argument("--top", type=int, default=6)
    p2.add_argument("--games", type=int, default=200)
    p2.add_argument("--workers", type=int, default=2)
    p2.add_argument("--chunk", type=int, default=20)
    p2.add_argument("--resume", action="store_true", help="reuse complete per-pair JSONL")
    p2.add_argument("--out-dir", default="results/deck_stage2")
    p2.add_argument("--csv-out", default="results/deck_tournament_stage2.csv")
    p2.set_defaults(func=cmd_stage2)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
