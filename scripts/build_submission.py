"""Build a Kaggle submission tarball and verify it end-to-end.

Kaggle expects a .tar.gz with `main.py` at the TOP LEVEL (not nested) and a
`deck.csv`.  Extra files are allowed; we only add `card_meta.json` when present.

Usage:
  .venv/bin/python scripts/build_submission.py --agent agents/heuristic_v1 \
      --out submissions/heuristic_v1.tar.gz --verify 20
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402
from ptcg_ai.harness import play_game  # noqa: E402

ALLOWED_EXTRA = ("card_meta.json", "cards.json")


def extra_files(agent_dir: Path) -> list[Path]:
    """Bundle helper modules and data (including subdirs such as meta/)."""
    out = []
    for p in sorted(agent_dir.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(agent_dir)
        if len(rel.parts) == 1 and p.name in ("main.py", "deck.csv"):
            continue
        if p.name.startswith(".") or p.suffix not in (".py", ".json", ".csv"):
            continue
        out.append(p)
    return out



def build(agent_dir: Path, out: Path) -> list[str]:
    main = agent_dir / "main.py"
    deck = agent_dir / "deck.csv"
    if not main.exists() or not deck.exists():
        raise SystemExit(f"{agent_dir} needs main.py and deck.csv")
    problems = decklib.validate_deck(decklib.load_deck(deck))
    if problems:
        raise SystemExit("deck invalid: " + "; ".join(problems))

    files = [main, deck]
    files.extend(extra_files(agent_dir))

    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz", format=tarfile.GNU_FORMAT) as tf:
        for p in files:
            arcname = p.name if p.parent == agent_dir else p.relative_to(agent_dir).as_posix()
            info = tf.gettarinfo(str(p), arcname=arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with p.open("rb") as fh:
                tf.addfile(info, fh)
    return [p.name for p in files]


def verify(archive: Path, games: int, opponent: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(archive) as tf:
            names = tf.getnames()
            if "main.py" not in names or "deck.csv" not in names:
                raise SystemExit(f"bad archive layout: {names}")
            tf.extractall(td)
        spec = importlib.util.spec_from_file_location("submission_main", Path(td) / "main.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        deck = decklib.load_deck(Path(td) / "deck.csv")

        spec2 = importlib.util.spec_from_file_location("opp_main", opponent / "main.py")
        opp = importlib.util.module_from_spec(spec2)
        assert spec2 and spec2.loader
        spec2.loader.exec_module(opp)
        opp_deck = decklib.load_deck(opponent / "deck.csv")

        wins = 0
        illegal = 0
        for i in range(games):
            if i % 2 == 0:
                r = play_game(mod.agent, opp.agent, deck, opp_deck, names=("sub", "opp"))
                win = r.winner == 0
            else:
                r = play_game(opp.agent, mod.agent, opp_deck, deck, names=("opp", "sub"))
                win = r.winner == 1
            wins += win
            illegal += r.illegal
        return {"games": games, "wins": wins, "winrate": wins / games, "illegal": illegal}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--verify", type=int, default=0)
    ap.add_argument("--opponent", default="agents/random_legal")
    args = ap.parse_args()

    agent_dir = Path(args.agent)
    out = Path(args.out) if args.out else ROOT / "submissions" / f"{agent_dir.name}.tar.gz"
    names = build(agent_dir, out)
    print(json.dumps({"archive": str(out), "bytes": out.stat().st_size, "files": names}, indent=2))
    if args.verify:
        result = verify(out, args.verify, ROOT / args.opponent)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
