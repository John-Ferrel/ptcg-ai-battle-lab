"""Fetch the strong public PPO baseline and build a submission from it.

Source (public Kaggle notebook output, MIT-licensed code + weights):
  - policy/weights: Dipam Chakraborty, github.com/dipamc/kaggle-ptcg-ai-battle
    at commit a176778d99da74a44b495bf19299b4795faf12f2
  - new-card port, seat/BO3 fixes, packaged output:
    busyaprime, "LB 1074.1 - Same Agent as Public #1, Better Deck"
    kaggle.com/code/busyaprime/lb-1074-1-same-agent-as-public-1-better-deck

The notebook output `submission.tar.gz` is downloaded with the Kaggle CLI
(credentials required), extracted, re-decked, validated and optionally packed.

Usage:
  python scripts/fetch_public_v3.py \
      --deck decks/meta/05_Mega_Lopunny_ex.csv \
      --out data/public_v3 \
      --pack submissions/public_v3_lop.tar.gz
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck as decklib  # noqa: E402

KERNEL = "busyaprime/lb-1074-1-same-agent-as-public-1-better-deck"
REQUIRED = ("main.py", "deck.csv", "model.pt", "ptcg")


def fetch(out: Path) -> Path:
    if (out / "main.py").exists() and (out / "model.pt").exists():
        print(f"already present: {out}")
        return out
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [sys.executable, "-m", "kaggle", "kernels", "output", KERNEL, "-p", td],
            check=True,
        )
        archive = Path(td) / "submission.tar.gz"
        if not archive.exists():
            raise SystemExit(f"notebook output did not contain submission.tar.gz: {list(Path(td).iterdir())}")
        with tarfile.open(archive) as tf:
            tf.extractall(out)
    return out


def redeck(agent_dir: Path, deck_path: Path) -> list[int]:
    ids = decklib.load_deck(deck_path)
    problems = decklib.validate_deck(ids)
    if problems:
        raise SystemExit("invalid deck: " + "; ".join(problems))
    shutil.copyfile(deck_path, agent_dir / "deck.csv")
    return ids


def pack(agent_dir: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz", format=tarfile.GNU_FORMAT) as tf:
        for p in sorted(agent_dir.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            rel = p.relative_to(agent_dir).as_posix()
            info = tf.gettarinfo(str(p), arcname=rel)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with p.open("rb") as fh:
                tf.addfile(info, fh)
    print(f"packed {archive} ({archive.stat().st_size/1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default="decks/meta/05_Mega_Lopunny_ex.csv")
    ap.add_argument("--out", default="data/public_v3")
    ap.add_argument("--pack", default="")
    args = ap.parse_args()

    agent_dir = fetch(Path(args.out))
    missing = [x for x in REQUIRED if not (agent_dir / x).exists()]
    if missing:
        raise SystemExit(f"bundle missing {missing}")
    ids = redeck(agent_dir, Path(args.deck))
    print(json.dumps({"agent_dir": str(agent_dir), "deck": args.deck, "cards": len(ids)}, indent=2))
    if args.pack:
        pack(agent_dir, Path(args.pack))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
