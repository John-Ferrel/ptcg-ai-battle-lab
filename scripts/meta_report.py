"""Meta report from Darren Sheehan's parsed playground ladder dataset.

Input (kaggle.com/datasets/darrensheehan/ptcg-playground-ladder-matches):
  matches.csv, games.csv, decks.csv, deck_cards.csv

Computes, for a day window and rating band:
  * archetype shares and match win rates,
  * a match-level matchup matrix with Wilson CIs,
  * field-weighted win rate and the best-response deck,
  * turn-order value (game level),
  * same-team multi-deck comparisons (pilot confound check),
  * a fictitious-play equilibrium mix and replicator drift.

Usage:
  python scripts/meta_report.py --data data/datasets/darren \
      --days 2026-11-11 --out docs/META_1111.md
  python scripts/meta_report.py --data data/datasets/darren \
      --days 2026-11-09,2026-11-10,2026-11-11 --min-rating 1200 \
      --out docs/META_ROLLING_1200.md
"""
from __future__ import annotations

import argparse
import collections
import csv
import math
from pathlib import Path

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def load(data: Path, days: set[str], min_rating: float, max_rating: float | None):
    matches = []
    with (data / "matches.csv").open() as f:
        for r in csv.DictReader(f):
            if days and r["day"] not in days:
                continue
            low = float(r["rating_low"])
            if low < min_rating:
                continue
            if max_rating is not None and low > max_rating:
                continue
            if not r["result_0"] or not r["result_1"]:
                continue
            try:
                r0, r1 = float(r["result_0"]), float(r["result_1"])
            except ValueError:
                continue
            if r0 == r1:
                continue
            matches.append((r["archetype_0"], r["archetype_1"], r0 > r1, r["team_0"], r["team_1"], r["deck_0"], r["deck_1"], r["episode_id"]))
    games = []
    ids = {m[7] for m in matches}
    with (data / "games.csv").open() as f:
        for r in csv.DictReader(f):
            if r["episode_id"] not in ids:
                continue
            w = int(r["winner"]) if r["winner"] not in ("", "None") else -1
            if w not in (0, 1):
                continue
            games.append((int(r["first_player"]), w, r["archetype_0"], r["archetype_1"]))
    return matches, games


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/datasets/darren")
    ap.add_argument("--days", default="", help="comma-separated days; empty = all")
    ap.add_argument("--min-rating", type=float, default=0)
    ap.add_argument("--max-rating", type=float, default=None)
    ap.add_argument("--min-games", type=int, default=40)
    ap.add_argument("--out", default="docs/META_REPORT.md")
    args = ap.parse_args()

    data = Path(args.data)
    days = set(x.strip() for x in args.days.split(",") if x.strip())
    matches, games = load(data, days, args.min_rating, args.max_rating)

    seats = collections.Counter()
    wins = collections.Counter()
    M = collections.defaultdict(lambda: [0, 0])
    for a, b, aw, *_ in matches:
        seats[a] += 1
        seats[b] += 1
        wins[a] += aw
        wins[b] += not aw
        M[(a, b)][0] += aw
        M[(a, b)][1] += 1
        M[(b, a)][0] += not aw
        M[(b, a)][1] += 1

    keep = {a for a, n in seats.items() if n >= args.min_games}
    archs = [a for a, _ in seats.most_common() if a in keep]
    idx = {a: i for i, a in enumerate(archs)}
    k = len(archs)
    A = np.full((k, k), np.nan)
    N = np.zeros((k, k))
    for (a, b), (w, n) in M.items():
        if a in idx and b in idx:
            A[idx[a], idx[b]] = w / n
            N[idx[a], idx[b]] = n
    total = sum(seats[a] for a in archs)
    shares = np.array([seats[a] / total for a in archs])
    Af = np.nan_to_num(A, nan=0.5)
    np.fill_diagonal(Af, 0.5)
    field_wr = Af @ shares
    best = int(np.argmax(field_wr))

    # turn order (game level)
    first_w = sum(1 for f, w, *_ in games if f == w)
    second_w = len(games) - first_w
    # same-team multi-deck comparison
    team_deck = collections.defaultdict(lambda: [0, 0])
    for a, b, aw, t0, t1, d0, d1, _ in matches:
        team_deck[(t0, d0, a)][0] += 1
        team_deck[(t0, d0, a)][1] += aw
        team_deck[(t1, d1, b)][0] += 1
        team_deck[(t1, d1, b)][1] += not aw
    by_team = collections.defaultdict(list)
    for (t, d, a), (n, w) in team_deck.items():
        if n >= 20:
            by_team[t].append((n, w / n, a, d))
    multi = [(t, v) for t, v in by_team.items() if len(v) >= 2]

    # equilibrium
    counts = np.zeros(k)
    avg = np.full(k, 1.0 / k)
    for _ in range(20001):
        br = int(np.argmax(Af @ avg))
        counts[br] += 1
        avg = counts / counts.sum()
    value = float(avg @ Af @ avg)
    x = np.full(k, 1.0 / k)
    traj = []
    for _ in range(200):
        x = x * (Af @ x)
        x = x / x.sum()
        traj.append(x.copy())
    drift = float(np.linalg.norm(traj[-1] - traj[-50]))

    lines = []
    lines.append("# Meta report — parsed ladder dataset\n")
    lines.append(f"Days: {', '.join(sorted(days)) if days else 'all'}; "
                 f"rating_low >= {args.min_rating}" + (f" and <= {args.max_rating}" if args.max_rating else ""))
    lines.append(f"\n**{len(matches):,} matches**, **{len(games):,} games**, "
                 f"{len(seats):,} archetype-seats, {k} archetypes with >= {args.min_games} seats.\n")
    lines.append("## Shares / field-weighted win rate\n")
    lines.append("| Archetype | Seats | Share | Match WR | Field-weighted WR |")
    lines.append("|---|---:|---:|---:|---:|")
    for i, a in enumerate(archs):
        lo, hi = wilson(wins[a], seats[a])
        lines.append(f"| {a} | {seats[a]:,} | {shares[i]:.1%} | {wins[a]/seats[a]:.3f} "
                     f"({lo:.0%}-{hi:.0%}) | {field_wr[i]:.3f} |")
    lines.append(f"\n**Best response to this field: `{archs[best]}` ({field_wr[best]:.3f}).**\n")
    lines.append("## Matchup matrix (row match win rate vs column; cells with < 20 games = `-`)\n")
    lines.append("| | " + " | ".join(str(i + 1) for i in range(k)) + " |")
    lines.append("|---|" + "---|" * k)
    for i, a in enumerate(archs):
        cells = []
        for j in range(k):
            if i != j and not np.isnan(A[i, j]) and N[i, j] >= 20:
                cells.append(f"{A[i,j]:.0%} ({int(N[i,j])})")
            else:
                cells.append("-")
        lines.append(f"| {i+1}. {a} | " + " | ".join(cells) + " |")
    lines.append(f"\n## Turn order (game level)\n")
    lines.append(f"- going first: **{first_w/len(games):.1%}** ({first_w:,} / {len(games):,})")
    lines.append(f"- going second: **{second_w/len(games):.1%}** ({second_w:,} / {len(games):,})\n")
    lines.append("## Same-team multi-deck comparisons (pilot confound)\n")
    if multi:
        lines.append("| Team | Deck A | WR | Deck B | WR |")
        lines.append("|---|---|---:|---|---:|")
        for t, v in sorted(multi, key=lambda x: -sum(z[0] for z in x[1]))[:15]:
            v = sorted(v, reverse=True)
            lines.append(f"| {t} | {v[0][2]} | {v[0][1]:.1%} (n={v[0][0]}) | {v[1][2]} | {v[1][1]:.1%} (n={v[1][0]}) |")
    else:
        lines.append("No team with two decks and >=20 matches each in this window.")
    lines.append("\n## Equilibrium (fictitious play, symmetric zero-sum deck game)\n")
    lines.append("| Archetype | Equilibrium mix |")
    lines.append("|---|---:|")
    for i in np.argsort(-avg):
        if avg[i] > 0.01:
            lines.append(f"| {archs[i]} | {avg[i]:.1%} |")
    lines.append(f"\nGame value: **{value:.3f}**; replicator drift over 50 iterations: {drift:.3f} "
                 + ("(settling)" if drift < 0.01 else "(still moving / cycling)") + ".\n")
    lines.append("## Caveats\n")
    lines.append("- Observational: deck WR mixes deck strength, pilot skill and matchmaking.")
    lines.append("- Cells with <20 games are hidden; CIs are wide at this sample size.")
    lines.append("- Non-transitive game: the pure best response is a snapshot, not a permanent optimum.")
    lines.append("- Ladder ratings are noisy; this is a prior, not a guarantee.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines[:35]))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
