"""Piloting-gap analysis: where does our v3 model disagree with top pilots?

Feed real replay observations to the public v3 agent (same model, same deck) and
compare its semantic action with the recorded action. Bucket by select context
and game state, decode card/attack names, and print the dominant patterns.

Usage:
  PYTHONPATH=vendor .venv/bin/python scripts/piloting_gap.py \
      --episodes data/datasets/episodes-2026-11-12 \
      --manifest data/datasets/episodes-2026-11-12/manifest.csv \
      --agent /tmp/v3_pult8 --archetype "Dragapult ex / Blaziken ex" \
      --min-score 1300 --episodes-limit 40 --decisions-limit 600 \
      --out docs/PILOT_GAP_PULT8.md
"""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ptcg_ai import cards, replay  # noqa: E402
from divergence import CTX_LABELS, _area_card, label, semantic  # noqa: E402

DB = cards.card_db()


def headline(deck: list[int]) -> str:
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

    names = []
    for cid in sorted(poke, key=key, reverse=True):
        n = DB[cid]["name"]
        if n not in names:
            names.append(n)
        if len(names) == 2:
            break
    return " / ".join(names) or "?"


def load_agent(agent_dir: Path):
    spec = importlib.util.spec_from_file_location("v3main", agent_dir / "main.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.SA


def describe_opt(obs: dict, opt: dict) -> str:
    t = opt.get("type")
    if t == 13:
        return "ATTACK " + cards.attack(opt.get("attackId")).get("name", str(opt.get("attackId")))
    if t == 14:
        return "END"
    if t in (1, 2):
        return "YES" if t == 1 else "NO"
    if t == 0:
        return f"COUNT {opt.get('number')}"
    if t == 7:
        h = obs["current"]["players"][obs["current"]["yourIndex"]].get("hand") or []
        i = opt.get("index", -1)
        return "PLAY " + (cards.name(h[i]["id"]) if 0 <= i < len(h) else "?")
    if t in (3, 4, 5, 11):
        cid = _area_card(obs, opt.get("area"), opt.get("index", -1),
                         opt.get("playerIndex", obs["current"]["yourIndex"]))
        return cards.name(cid) if isinstance(cid, int) else f"CARD(t{t})"
    if t in (8, 9):
        if opt.get("area") == 1:
            cid = _area_card(obs, 1, opt.get("index", -1), obs["current"]["yourIndex"])
        else:
            h = obs["current"]["players"][obs["current"]["yourIndex"]].get("hand") or []
            i = opt.get("index", -1)
            cid = h[i]["id"] if 0 <= i < len(h) else None
        return ("ATTACH " if t == 8 else "EVOLVE ") + (cards.name(cid) if isinstance(cid, int) else "?")
    if t == 10:
        cid = _area_card(obs, opt.get("area"), opt.get("index", -1),
                         opt.get("playerIndex", obs["current"]["yourIndex"]))
        return "ABILITY " + (cards.name(cid) if isinstance(cid, int) else "?")
    return label(semantic(obs, opt))


def state_summary(obs: dict) -> str:
    st = obs["current"]
    me = st["yourIndex"]
    p, o = st["players"][me], st["players"][1 - me]
    a, oa = (p.get("active") or [None])[0], (o.get("active") or [None])[0]
    def hp(x):
        return f"{x['id']}:{x['hp']}/{x['maxHp']}" if x else "-"
    return (
        f"turn {st['turn']} | my prizes {len(p.get('prize') or [])} "
        f"opp {len(o.get('prize') or [])} | hand {p.get('handCount')} "
        f"deck {p.get('deckCount')} | active {hp(a)} vs {hp(oa)} | bench {len(p.get('bench') or [])}/{len(o.get('bench') or [])}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--manifest", default="")
    ap.add_argument("--agent", required=True, help="v3 agent dir (main.py + cg/ + model.pt)")
    ap.add_argument("--archetype", default="", help="substring filter on the replay deck's headline")
    ap.add_argument("--min-score", type=float, default=1300)
    ap.add_argument("--episodes-limit", type=int, default=40)
    ap.add_argument("--decisions-limit", type=int, default=600)
    ap.add_argument("--out", default="docs/PILOT_GAP.md")
    args = ap.parse_args()

    scores = {}
    if args.manifest:
        for r in csv.DictReader(open(args.manifest)):
            scores[r["episode_id"]] = float(r["min_score"])
    files = sorted(Path(args.episodes).glob("*.json"))
    print(f"candidate files: {len(files)}")

    SA = load_agent(Path(args.agent))
    n_ep = n_dec = n_agree = 0
    ctx = collections.Counter()
    ctx_agree = collections.Counter()
    pairs = collections.Counter()
    examples = []
    decks_seen = collections.Counter()
    blz = collections.Counter()
    dmg = collections.Counter()

    for f in files:
        sc = scores.get(f.stem)
        if sc is not None and sc < args.min_score:
            continue
        if n_ep >= args.episodes_limit or n_dec >= args.decisions_limit:
            break
        try:
            ep = replay.load_episode(f)
            dec = replay.decisions(ep)
            if not dec:
                continue
            p = dec[0]["player"]
            deck = list(ep["steps"][1][p]["action"])
            if len(deck) != 60:
                continue
            arch = headline(deck)
            if args.archetype and args.archetype.lower() not in arch.lower():
                continue
            SA.deck = deck
            SA.agent({"select": None, "current": None, "logs": []})  # reset tracker
            used = False
            for d in dec:
                if d["player"] != p:
                    continue
                sel = d["obs"].get("select")
                if not sel or sel.get("maxCount") != 1 or int(sel.get("minCount") or 0) > 1:
                    continue
                opts = sel.get("option") or []
                if len(opts) < 2 or len(opts) > 40 or not d["action"]:
                    continue
                theirs_idx = d["action"][0]
                if not (0 <= theirs_idx < len(opts)):
                    continue
                try:
                    ours = SA.agent(d["obs"])
                except Exception:
                    continue
                if not isinstance(ours, list) or len(ours) != 1 or not (0 <= ours[0] < len(opts)):
                    continue
                ours_k = semantic(d["obs"], opts[ours[0]])
                theirs_k = semantic(d["obs"], opts[theirs_idx])
                c = sel.get("context")
                n_dec += 1
                used = True
                ctx[c] += 1
                if ours_k == theirs_k:
                    n_agree += 1
                    ctx_agree[c] += 1
                else:
                    ours_l = describe_opt(d["obs"], opts[ours[0]])
                    theirs_l = describe_opt(d["obs"], opts[theirs_idx])
                    if ours_l == "ABILITY Blaziken ex":
                        me = d["obs"]["current"]["yourIndex"]
                        disc = d["obs"]["current"]["players"][me].get("discard") or []
                        e = sum(1 for x in disc if DB.get(x["id"], {}).get("cardType") == 5)
                        has_drak = any(describe_opt(d["obs"], o) == "ABILITY Drakloak" for o in opts)
                        blz[(e > 0, has_drak)] += 1
                    if c in (13, 14, 15):
                        tgt = opts[theirs_idx]
                        cid = _area_card(d["obs"], tgt.get("area"), tgt.get("index", -1),
                                         tgt.get("playerIndex", d["obs"]["current"]["yourIndex"]))
                        hp = DB.get(cid, {}).get("hp", 0) if isinstance(cid, int) else 0
                        dmg[(c, hp <= 120, hp)] += 1
                    pairs[(c, describe_opt(d["obs"], opts[ours[0]]),
                           describe_opt(d["obs"], opts[theirs_idx]))] += 1
                    if len(examples) < 40:
                        examples.append({
                            "episode": f.stem, "step": d["step"], "ctx": CTX_LABELS.get(c, c),
                            "ours": describe_opt(d["obs"], opts[ours[0]]),
                            "theirs": describe_opt(d["obs"], opts[theirs_idx]),
                            "state": state_summary(d["obs"]),
                        })
                if n_dec >= args.decisions_limit:
                    break
            if used:
                n_ep += 1
                decks_seen[arch] += 1
        except Exception as exc:
            print(f"skip {f.name}: {type(exc).__name__}: {exc}")
            continue

    lines = []
    lines.append(f"# Piloting gap — {args.agent} vs top pilots\n")
    lines.append(f"Episodes: {n_ep}; decisions compared: {n_dec}; semantic agreement: "
                 f"**{n_agree/max(n_dec,1):.1%}**.\n")
    lines.append("## By context\n")
    lines.append("| Context | n | Agreement |")
    lines.append("|---|---:|---:|")
    for c, n in ctx.most_common(12):
        lines.append(f"| {CTX_LABELS.get(c, c)} | {n} | {ctx_agree[c]/n:.1%} |")
    lines.append("\n## Top disagreement patterns\n")
    lines.append("| Context | ours | theirs | n |")
    lines.append("|---|---|---|---:|")
    for (c, ours, theirs), n in pairs.most_common(25):
        lines.append(f"| {CTX_LABELS.get(c, c)} | {ours} | {theirs} | {n} |")
    lines.append("\n## Blaziken ability context (ours=Blaziken, theirs!=Blaziken)\n")
    lines.append("| has energy in discard | Drakloak ability available | n |")
    lines.append("|---|---|---:|")
    for (has_e, has_d), n in blz.most_common():
        lines.append(f"| {has_e} | {has_d} | {n} |")
    lines.append("\n## Damage-counter target HP (theirs)\n")
    for (c, low, hp), n in dmg.most_common(10):
        lines.append(f"- ctx {CTX_LABELS.get(c, c)}: target hp {hp} (low={low}) x{n}")
    lines.append("\n## Examples\n")
    for e in examples[:20]:
        lines.append(f"- `{e['episode']}` step {e['step']} **{e['ctx']}** — ours `{e['ours']}` vs theirs `{e['theirs']}`  \n  {e['state']}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines[:35]))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
