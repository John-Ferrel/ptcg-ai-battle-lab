"""Generate the README figures from committed result tables.

All numbers are derived statistics (no card database / engine data).
Run: .venv/bin/python scripts/make_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})

BLUE, GREEN, ORANGE, GRAY, RED = "#2f6feb", "#2a9d8f", "#e76f51", "#8d99ae", "#c1121f"


def ladder_noise():
    """Observed publicScore snapshots; x is snapshot order, not continuous time."""
    series = {
        "v3 + Lopunny (first run)": [600, 687.6, 879.5, 1102.5],
        "v3 + Lopunny (reactivated)": [600, 749.8, 692.5, 793.9, 671.0, 815.5, 827.8, 843.1],
        "v3 + Dragapult/Blaziken (core)": [600, 966.5, 987.5, 943.7, 938.0, 916.6, 886.7],
        "from-scratch search_v1": [600, 491.1, 336.9, 180.3],
    }
    colors = [ORANGE, RED, BLUE, GRAY]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (name, ys), c in zip(series.items(), colors):
        ax.plot(range(len(ys)), ys, marker="o", linewidth=2, markersize=5, label=name, color=c)
    ax.axhline(600, color=GRAY, linestyle="--", linewidth=1, alpha=0.6)
    ax.annotate("1102.5 (best observed)", xy=(3, 1102.5), xytext=(3.2, 1140),
                fontsize=9, color=ORANGE, arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1))
    ax.set_xlabel("observed snapshot index (not continuous time)")
    ax.set_ylabel("official publicScore")
    ax.set_title("Ladder snapshots — the same artifact moves by >400 points")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "ladder_noise.png", dpi=170)
    plt.close(fig)


def meta_1112():
    rows = [
        ("Excadrill / Genesect", 35.9, 0.407),
        ("Dragapult / Blaziken", 25.7, 0.565),
        ("Dragapult / Drakloak", 12.4, 0.543),
        ("Lopunny / Froslass", 10.3, 0.508),
        ("Kangaskhan / Ogerpon", 6.1, 0.628),
        ("Kangaskhan / Latias", 2.8, 0.601),
        ("Clefairy / Banette", 2.7, 0.250),
        ("Blaziken / Dragapult", 2.6, 0.471),
    ]
    names = [r[0] for r in rows][::-1]
    shares = np.array([r[1] for r in rows])[::-1]
    wr = np.array([r[2] for r in rows])[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1]})
    axes[0].barh(names, shares, color=BLUE)
    for i, v in enumerate(shares):
        axes[0].text(v + 0.4, i, f"{v:.1f}%", va="center", fontsize=8)
    axes[0].set_xlabel("share of deck slots")
    axes[0].set_title("2026-11-12 meta share")
    axes[0].set_xlim(0, max(shares) * 1.2)
    colors = [RED if v < 0.4 else GREEN if v >= 0.55 else GRAY for v in wr]
    axes[1].barh(names, wr, color=colors)
    for i, v in enumerate(wr):
        axes[1].text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=8)
    axes[1].axvline(0.5, color="black", linewidth=1, alpha=0.5)
    axes[1].set_xlabel("field-weighted match win rate")
    axes[1].set_title("field-weighted WR (green >= 0.55)")
    axes[1].set_xlim(0, 0.75)
    fig.suptitle("Current meta: Excadrill is falling; Dragapult/Lopunny/Kangaskhan are the top responses", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "meta_1112.png", dpi=170)
    plt.close(fig)


def climb_path():
    bands = ["1000-1200", "1200-1400", "1400+"]
    series = {
        "Dragapult / Blaziken (pult8)": [0.571, 0.540, 0.382],
        "Dragapult / Drakloak": [0.548, 0.515, 0.542],
        "Mega Lopunny": [0.512, 0.497, 0.412],
        "Mega Excadrill": [0.413, 0.418, np.nan],
    }
    colors = [BLUE, GREEN, ORANGE, GRAY]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for (name, ys), c in zip(series.items(), colors):
        ax.plot(bands, ys, marker="o", linewidth=2, markersize=7, label=name, color=c)
    ax.axhline(0.5, color="black", linewidth=1, alpha=0.4)
    ax.set_ylabel("field-weighted match win rate")
    ax.set_xlabel("rating band (both players above the lower bound)")
    ax.set_title("Climb path — pult8 wins the lower bands; Drakloak wins the top")
    ax.legend(fontsize=8)
    ax.set_ylim(0.35, 0.60)
    fig.tight_layout()
    fig.savefig(OUT / "climb_path.png", dpi=170)
    plt.close(fig)


def matchup_heatmap():
    labels = ["Excadrill", "Pult8", "Drakloak", "Lopunny", "Kang/Oger", "Kang/Latias", "Clefairy", "Blaziken/Pult"]
    M = np.full((8, 8), np.nan)
    # row win rate vs column, from docs/META_1112.md (11-12, all ratings)
    values = {
        (0, 1): .23, (0, 2): .48, (0, 3): .59, (0, 4): .35, (0, 5): .17, (0, 6): .57, (0, 7): .21,
        (1, 0): .77, (1, 2): .42, (1, 3): .40, (1, 4): .18, (1, 5): .55, (1, 6): .80, (1, 7): .74,
        (2, 0): .52, (2, 1): .58, (2, 3): .74, (2, 4): .36,
        (3, 0): .41, (3, 1): .60, (3, 2): .26, (3, 4): .88, (3, 5): .89,
        (4, 0): .65, (4, 1): .82, (4, 2): .64, (4, 3): .12,
        (5, 0): .83, (5, 1): .45, (5, 3): .11,
        (6, 0): .43, (6, 1): .20,
        (7, 0): .79, (7, 1): .26,
    }
    for (i, j), v in values.items():
        M[i, j] = v
    fig, ax = plt.subplots(figsize=(8.6, 6.6))
    cmap = plt.cm.RdBu.copy()
    cmap.set_bad("#eeeeee")
    im = ax.imshow(np.ma.masked_invalid(M), cmap=cmap, vmin=0.2, vmax=0.8)
    for i in range(8):
        for j in range(8):
            if i == j:
                ax.text(j, i, "mirror", ha="center", va="center", fontsize=7, color="#888")
            elif not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i,j]:.0%}", ha="center", va="center", fontsize=8,
                        color="white" if abs(M[i, j] - 0.5) > 0.2 else "black")
    ax.set_xticks(range(8), labels, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(8), labels, fontsize=8)
    ax.set_title("11-12 matchup matrix (row win rate vs column) — a non-transitive cycle")
    ax.set_xlabel("opponent")
    ax.set_ylabel("deck")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(OUT / "matchup_1112.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    ladder_noise()
    meta_1112()
    climb_path()
    matchup_heatmap()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
