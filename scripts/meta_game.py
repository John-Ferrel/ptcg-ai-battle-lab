"""Metagame analysis: shares, matchup matrix, best response, equilibrium.

Input: `results/meta_1109/episodes.jsonl` (or any episodes.jsonl produced by
scripts/analyze_episodes.py), plus the optional manifest for rating filters.

Output: a markdown report with
  * archetype shares and field-weighted win rates,
  * the best-response deck to the current field,
  * the best counter to the most common deck,
  * a fictitious-play approximation of the zero-sum equilibrium mix,
  * a pilot-confound check (same team playing several decks).

Usage:
  python scripts/meta_game.py results/meta_1109/episodes.jsonl \
      --manifest <episodes_dir>/manifest.csv --min-score 1200 \
      --out docs/META_GAME.md --min-games 30
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import cards  # noqa: E402

DB = cards.card_db()


def headline(deck: list[int]) -> str:
    """Proper archetype label: Mega ex first, then ex with >=2 copies,
    then the highest evolution stage, then most copies."""
    c = collections.Counter(deck)
    poke = [cid for cid in c if DB.get(cid, {}).get("cardType") == 0]

    def key(cid):
        x = DB[cid]
        return (
            c[cid] >= 2,
            bool(x.get("megaEx")),
            bool(x.get("ex")),
            2 if x.get("stage2") else 1 if x.get("stage1") else 0,
            c[cid],
            x.get("hp", 0),
        )

    names: list[str] = []
    for cid in sorted(poke, key=key, reverse=True):
        n = DB[cid]["name"]
        if n not in names:
            names.append(n)
        if len(names) == 2:
            break
    return " / ".join(names) or "?"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def load_rows(path: Path, manifest: Path | None, min_score: float) -> list[dict]:
    scores = {}
    if manifest and manifest.exists():
        for r in csv.DictReader(manifest.open()):
            scores[r["episode_id"]] = float(r["min_score"])
    rows = []
    for line in path.open():
        e = json.loads(line)
        if scores:
            sc = scores.get(str(e["episode"]))
            if sc is None or sc < min_score:
                continue
            e["min_score"] = sc
        e["arch"] = [headline(d) for d in e["decks"]]
        rows.append(e)
    return rows


def build(rows: list[dict], min_games: int):
    seats = collections.Counter()
    for e in rows:
        for a in e["arch"]:
            seats[a] += 1
    total = sum(seats.values())
    # keep archetypes with enough appearances; map the rest to "other"
    keep = {a for a, n in seats.items() if n >= min_games}
    rows = [dict(e, arch=[a if a in keep else "other" for a in e["arch"]]) for e in rows]
    seats = collections.Counter()
    wins = collections.Counter()
    M = collections.defaultdict(lambda: [0, 0])  # (a,b) -> wins for a, games
    for e in rows:
        a = e["arch"]
        r = e["rewards"]
        if r[0] == r[1]:
            continue
        w = 0 if r[0] > r[1] else 1
        for i in (0, 1):
            seats[a[i]] += 1
            wins[a[i]] += (i == w)
            M[(a[i], a[1 - i])][1] += 1
            M[(a[i], a[1 - i])][0] += (i == w)
    archs = [a for a, _ in seats.most_common() if a != "other"]
    idx = {a: i for i, a in enumerate(archs)}
    A = np.full((len(archs), len(archs)), np.nan)
    N = np.zeros_like(A)
    for (a, b), (w, n) in M.items():
        if a in idx and b in idx:
            A[idx[a], idx[b]] = w / n
            N[idx[a], idx[b]] = n
    return rows, seats, total, archs, A, N


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--min-score", type=float, default=0)
    ap.add_argument("--min-games", type=int, default=30)
    ap.add_argument("--out", default="docs/META_GAME.md")
    args = ap.parse_args()

    rows = load_rows(Path(args.episodes), Path(args.manifest) if args.manifest else None, args.min_score)
    rows, seats, total, archs, A, N = build(rows, args.min_games)
    k = len(archs)
    shares = np.array([seats[a] / total for a in archs])
    # missing cells -> 0.5, but remember they are unmeasured
    Af = np.nan_to_num(A, nan=0.5)
    np.fill_diagonal(Af, 0.5)
    field_wr = Af @ shares
    best = int(np.argmax(field_wr))
    top = int(np.argmax(shares))
    # best counter to the top deck
    counters = [(archs[i], Af[i, top], N[i, top]) for i in range(k) if i != top and N[i, top] >= 10]
    counters.sort(key=lambda x: -x[1])

    # fictitious play on the symmetric zero-sum deck game
    counts = np.zeros(k)
    avg = np.full(k, 1.0 / k)
    for t in range(1, 20001):
        br = int(np.argmax(Af @ avg))
        counts[br] += 1
        avg = counts / counts.sum()
    value = float(avg @ Af @ avg)

    # replicator dynamics from uniform: does the meta cycle or settle?
    x = np.full(k, 1.0 / k)
    traj = []
    for _ in range(200):
        fit = Af @ x
        x = x * fit
        x = x / x.sum()
        traj.append(x.copy())
    drift = float(np.linalg.norm(traj[-1] - traj[-50]))

    lines = []
    lines.append("# Metagame analysis\n")
    lines.append(f"Source: `{args.episodes}`" + (f", min_score >= {args.min_score}" if args.min_score else ""))
    lines.append(f"\n{len(rows)} matches, {int(total)} deck slots, {k} archetypes with >= {args.min_games} seats.\n")
    lines.append("## Shares and field-weighted win rate\n")
    lines.append("| Archetype | Seats | Share | Field-weighted WR |")
    lines.append("|---|---:|---:|---:|")
    for i, a in enumerate(archs):
        lines.append(f"| {a} | {seats[a]} | {shares[i]:.1%} | {field_wr[i]:.3f} |")
    lines.append(f"\n**Best response to this field: `{archs[best]}` ({field_wr[best]:.3f}).**\n")
    lines.append("## Matchup matrix (row win rate vs column; cells with <10 games = `-`)\n")
    lines.append("| | " + " | ".join(str(i + 1) for i in range(k)) + " |")
    lines.append("|---|" + "---|" * k)
    for i, a in enumerate(archs):
        cells = []
        for j in range(k):
            cells.append(f"{A[i,j]:.0%}" if not np.isnan(A[i, j]) and N[i, j] >= 10 and i != j else "-")
        lines.append(f"| {i+1}. {a} | " + " | ".join(cells) + " |")
    lines.append("\n**Best counters to the most common deck (`" + archs[top] + f"`, {shares[top]:.1%} share):**\n")
    for name, wr, n in counters[:5]:
        lines.append(f"- `{name}`: {wr:.1%} over {int(n)} matches")
    lines.append("\n## Equilibrium (fictitious play, symmetric zero-sum deck game)\n")
    lines.append("| Archetype | Equilibrium mix |")
    lines.append("|---|---:|")
    for i in np.argsort(-avg):
        if avg[i] > 0.01:
            lines.append(f"| {archs[i]} | {avg[i]:.1%} |")
    lines.append(f"\nGame value: **{value:.3f}** (expected win rate of the equilibrium mix vs itself).\n")
    lines.append(f"Replicator dynamics drift over 50 iterations: {drift:.3f} "
                 + ("(settling)" if drift < 0.01 else "(still moving / cycling)") + ".\n")
    lines.append("## Caveats\n")
    lines.append("- The matrix is **observational**: pilots differ. A deck's win rate mixes deck strength, pilot skill and matchmaking.")
    lines.append("- Cells with few games have wide CIs; only >=10-game cells are shown.")
    lines.append("- The game is non-transitive. A pure best response can be punished if the field shifts; the equilibrium is a mix, not a deck.")
    lines.append("- The ladder rating is noisy; this analysis is a prior for deck choice, not a guarantee.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines[:40]))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
