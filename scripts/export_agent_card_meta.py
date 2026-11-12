#!/usr/bin/env python
"""Export a compact card/attack table for a self-contained submission agent.

The Kaggle runtime only gets `main.py` + `deck.csv` (+ whatever data we ship in
the same directory), so a submission cannot import `ptcg_ai` or query the engine.
This script dumps the *numeric* card facts a policy needs into a small JSON file:

    { "<cardId>": {n,hp,t,w,r,rc,a,b,s1,s2,ex,mega,ef,sk,et}, ... }

Field meanings (all optional on the agent side, unknown ids degrade gracefully):
    n    card name
    hp   HP (Pokemon)
    t    card type (0 Pokemon, 1 Item, 2 Tool, 3 Supporter, 4 Stadium,
                     5 Basic Energy, 6 Special Energy)
    w    weakness energy type (or null)
    r    resistance energy type (or null)
    rc   retreat cost
    a    attacks: [[attackId, [cost types], damage, text], ...]
    b    1 if Basic Pokemon
    s1   1 if Stage 1
    s2   1 if Stage 2
    ex   1 if Pokemon ex
    mega 1 if Mega Evolution
    ef   evolvesFrom card name (or null)
    sk   skills: [[name, text], ...]
    et   energy type (Pokemon/Energy cards)

Usage:
    .venv/bin/python scripts/export_agent_card_meta.py \
        --out agents/heuristic_v1/card_meta.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import cards as cardlib  # noqa: E402


def _trim(text: str, limit: int = 200) -> str:
    text = " ".join((text or "").split())
    return text[:limit]


def build_meta() -> dict[str, dict]:
    card_db = cardlib.card_db()
    attacks = cardlib.attack_db()
    out: dict[str, dict] = {}
    for cid, c in card_db.items():
        atk = []
        for aid in c.get("attacks") or []:
            a = attacks.get(aid) or {}
            atk.append(
                [
                    int(aid),
                    [int(e) for e in (a.get("energies") or [])],
                    int(a.get("damage") or 0),
                    _trim(a.get("text") or ""),
                ]
            )
        skills = [[s.get("name") or "", _trim(s.get("text") or "")] for s in (c.get("skills") or [])]
        row = {
            "n": c.get("name") or f"#{cid}",
            "hp": int(c.get("hp") or 0),
            "t": int(c.get("cardType") if c.get("cardType") is not None else -1),
            "w": c.get("weakness"),
            "r": c.get("resistance"),
            "rc": int(c.get("retreatCost") or 0),
            "a": atk,
            "b": 1 if c.get("basic") else 0,
            "s1": 1 if c.get("stage1") else 0,
            "s2": 1 if c.get("stage2") else 0,
            "ex": 1 if c.get("ex") else 0,
            "mega": 1 if c.get("megaEx") else 0,
            "ef": c.get("evolvesFrom"),
            "sk": skills,
            "et": int(c.get("energyType") or 0),
        }
        out[str(int(cid))] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "agents" / "heuristic_v1" / "card_meta.json"))
    args = ap.parse_args()
    meta = build_meta()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    size_kb = out.stat().st_size / 1024.0
    print(f"wrote {out} ({len(meta)} cards, {size_kb:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
