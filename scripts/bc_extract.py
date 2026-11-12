"""Mine real playground replays into a sparse behavior-cloning design matrix.

Each *decision* (one select with maxCount == 1) becomes a small multiclass
problem: one row per legal option, the chosen option labelled 1.  Rows are
stored, not decisions, so a linear scorer can rank options at inference time.

Outputs (git-ignored, under data/bc/):
    shard_XXXX.npz   scipy sparse CSR + decision bookkeeping
    meta.json        feature names, episode split, filter/count statistics

Also writes `agents/bc_linear/card_meta.json` (compact card/attack table used by
both the extractor and the submission agent, so features are identical).

Usage:
    .venv/bin/python scripts/bc_extract.py \
        --episodes /path/to/playground/versions/1 \
        --out data/bc --min-score 1200 --workers 3
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "agents" / "bc_linear"))

from ptcg_ai import replay  # noqa: E402

import bc_features  # noqa: E402  (agents/bc_linear/bc_features.py -- stdlib only)

META_GLOBAL: dict = {}


def compact_meta(cards: list[dict], attacks: list[dict]) -> dict:
    """Small {card: [hp, cardType, retreat, flags], attack: [cost, damage]} table."""
    cmeta = {}
    for c in cards:
        flags = (
            (1 if c.get("basic") else 0)
            | (2 if c.get("stage1") else 0)
            | (4 if c.get("stage2") else 0)
            | (8 if c.get("ex") else 0)
            | (16 if c.get("megaEx") else 0)
        )
        cmeta[str(c["cardId"])] = [
            int(c.get("hp") or 0),
            int(c.get("cardType") or 0),
            int(c.get("retreatCost") or 0),
            flags,
        ]
    ameta = {
        str(a["attackId"]): [len(a.get("energies") or []), int(a.get("damage") or 0)]
        for a in attacks
    }
    return {"c": cmeta, "a": ameta}


def load_meta(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return {
        "c": {int(k): v for k, v in raw["c"].items()},
        "a": {int(k): v for k, v in raw["a"].items()},
    }


def _init_worker(meta_path: str) -> None:
    global META_GLOBAL
    META_GLOBAL = load_meta(Path(meta_path))


def process_file(job: tuple[str, float]) -> dict:
    """Extract all usable decisions from one replay file."""
    path, min_score = job
    t0 = time.perf_counter()
    ep = replay.load_episode(path)
    ds = replay.decisions(ep)
    steps = ep.get("steps") or []
    names: list[str] = []
    local: dict[str, int] = {}
    indptr = [0]
    indices: list[int] = []
    values: list[float] = []
    labels: list[int] = []
    sizes: list[int] = []
    ctxs: list[int] = []
    kept = 0
    seen = len(ds)
    skipped = Counter()
    for d in ds:
        sel = d["obs"].get("select")
        if not sel:
            skipped["deck_or_no_select"] += 1
            continue  # deck selection
        if sel.get("maxCount") != 1:
            skipped["maxCount!=1"] += 1
            continue
        if (sel.get("minCount") or 0) > 1:
            skipped["minCount>1"] += 1
            continue
        options = sel.get("option") or []
        if not 1 <= len(options) <= 40:
            skipped["n_options"] += 1
            continue
        # replay.decisions() already enforces ACTIVE + non-empty action; these
        # checks are a belt-and-braces guard against future parser changes.
        try:
            status = steps[d["step"]][d["player"]].get("status")
        except (IndexError, KeyError):
            skipped["no_step"] += 1
            continue
        if status != "ACTIVE":
            skipped["stale_inactive"] += 1
            continue
        act = d["action"]
        if not act and int(sel.get("minCount") or 0) > 0:
            skipped["unanswered"] += 1
            continue
        if len(act) != 1:
            skipped["not_single"] += 1
            continue
        chosen = int(act[0])
        if not 0 <= chosen < len(options):
            skipped["out_of_range"] += 1
            continue
        feats = bc_features.build_features(d["obs"], META_GLOBAL)
        if len(feats) != len(options):
            continue
        for fd in feats:
            row: dict[str, int] = {}
            for name, val in fd.items():
                if not val:
                    continue
                j = local.get(name)
                if j is None:
                    j = len(names)
                    local[name] = j
                    names.append(name)
                row[j] = row.get(j, 0) + 1
            for j, n in row.items():
                indices.append(j)
                values.append(float(n))
            indptr.append(len(indices))
        labels.append(chosen)
        sizes.append(len(options))
        ctxs.append(int(sel.get("context") or 0))
        kept += 1
    return {
        "episode": Path(path).stem,
        "min_score": min_score,
        "names": names,
        "indptr": indptr,
        "indices": indices,
        "values": values,
        "labels": labels,
        "sizes": sizes,
        "ctx": ctxs,
        "kept": kept,
        "seen": seen,
        "skipped": dict(skipped),
        "elapsed": time.perf_counter() - t0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--out", default=str(ROOT / "data" / "bc"))
    ap.add_argument("--min-score", type=float, default=1200.0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard-games", type=int, default=40)
    args = ap.parse_args()

    import numpy as np
    from scipy import sparse

    ep_dir = Path(args.episodes)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- cards / attacks -> compact metadata shared with the agent -------------
    cards_path = ROOT / "data" / "cards.json"
    attacks_path = ROOT / "data" / "attacks.json"
    if not (cards_path.exists() and attacks_path.exists()):
        raise SystemExit("data/cards.json missing -- run scripts/build_card_db.py first")
    meta = compact_meta(
        json.loads(cards_path.read_text()), json.loads(attacks_path.read_text())
    )
    agent_meta = ROOT / "agents" / "bc_linear" / "card_meta.json"
    agent_meta.parent.mkdir(parents=True, exist_ok=True)
    agent_meta.write_text(json.dumps(meta, separators=(",", ":")))

    # --- episode pool: manifest scores, top ~64% by rating ---------------------
    scores: dict[str, float] = {}
    manifest = ep_dir / "manifest.csv"
    if manifest.exists():
        for row in csv.DictReader(manifest.open()):
            eid = str(row.get("episode_id") or "").strip()
            try:
                scores[eid] = float(row.get("min_score") or 0)
            except ValueError:
                pass
    jobs = []
    for p in sorted(ep_dir.glob("*.json")):
        sid = p.stem
        score = scores.get(sid)
        if score is None:
            # manifest numeric episode_id must equal the filename
            continue
        if score < args.min_score:
            continue
        jobs.append((str(p), score))
    if args.limit:
        jobs = jobs[: args.limit]
    if not jobs:
        raise SystemExit("no episodes selected")

    # deterministic 80/20 episode split (no decision of a game leaks across)
    ids = [Path(p).stem for p, _ in jobs]
    order = sorted(range(len(ids)), key=lambda i: int(ids[i]) if ids[i].isdigit() else ids[i])
    valid_idx = {i for k, i in enumerate(order) if k % 5 == 4}
    split = {ids[i]: ("valid" if i in valid_idx else "train") for i in range(len(ids))}
    print(
        f"episodes: {len(jobs)} (train={sum(1 for v in split.values() if v == 'train')}, "
        f"valid={sum(1 for v in split.values() if v == 'valid')}) min_score>={args.min_score}"
    )

    vocab: dict[str, int] = {}
    feature_names: list[str] = []
    shards = []
    buf = {"X": [], "labels": [], "sizes": [], "ctx": [], "game": [], "games": []}
    counts = {"seen": 0, "kept": 0, "ctx": {}}
    files_done = 0
    t0 = time.perf_counter()

    def flush() -> None:
        if not buf["labels"]:
            return
        width = len(feature_names)
        blocks = []
        for b in buf["X"]:
            if b.shape[1] < width:
                b = sparse.hstack(
                    [
                        b,
                        sparse.csr_matrix(
                            (b.shape[0], width - b.shape[1]), dtype=b.dtype
                        ),
                    ],
                    format="csr",
                )
            blocks.append(b)
        mat = sparse.vstack(blocks, format="csr")
        mat = mat.astype(np.float32)
        idx = len(shards)
        fname = f"shard_{idx:04d}.npz"
        labels = np.asarray(buf["labels"], dtype=np.int32)
        sizes = np.asarray(buf["sizes"], dtype=np.int32)
        ptr = np.concatenate([[0], np.cumsum(sizes)]).astype(np.int32)
        assert ptr[-1] == mat.shape[0], (ptr[-1], mat.shape)
        games = buf["games"]
        game_arr = np.asarray(buf["game"], dtype=np.int32)
        weights = np.asarray(
            [max(0.5, min(2.0, (g["score"] - 1100.0) / 300.0)) for g in games],
            dtype=np.float32,
        )
        sparse.save_npz(out_dir / fname, mat)
        np.savez_compressed(
            out_dir / f"{fname[:-4]}.meta.npz",
            labels=labels,
            ptr=ptr,
            ctx=np.asarray(buf["ctx"], dtype=np.int16),
            game=game_arr,
            weight=weights,
        )
        shards.append(
            {
                "file": fname,
                "meta": f"{fname[:-4]}.meta.npz",
                "games": [g["id"] for g in games],
                "split": [split[g["id"]] for g in games],
                "scores": [g["score"] for g in games],
                "n_decisions": int(len(labels)),
                "n_option_rows": int(mat.shape[0]),
            }
        )
        buf["X"].clear()
        buf["labels"].clear()
        buf["sizes"].clear()
        buf["ctx"].clear()
        buf["game"].clear()
        buf["games"].clear()

    def add_result(res: dict) -> None:
        nonlocal files_done
        names = res["names"]
        remap = np.empty(len(names), dtype=np.int64)
        for j, name in enumerate(names):
            g = vocab.get(name)
            if g is None:
                g = len(feature_names)
                vocab[name] = g
                feature_names.append(name)
            remap[j] = g
        mat = sparse.csr_matrix(
            (
                np.asarray(res["values"], dtype=np.float64),
                remap[np.asarray(res["indices"], dtype=np.int64)],
                np.asarray(res["indptr"], dtype=np.int64),
            ),
            shape=(len(res["indptr"]) - 1, len(names)),
        )
        mat.sort_indices()
        buf["X"].append(mat)
        buf["labels"].extend(res["labels"])
        buf["sizes"].extend(res["sizes"])
        buf["ctx"].extend(res["ctx"])
        buf["game"].extend([len(buf["games"])] * len(res["labels"]))
        buf["games"].append(
            {"id": res["episode"], "score": res["min_score"]}
        )
        counts["seen"] += res["seen"]
        counts["kept"] += res["kept"]
        for reason, n in (res.get("skipped") or {}).items():
            counts["skipped_" + reason] = counts.get("skipped_" + reason, 0) + n
        for c in res["ctx"]:
            counts["ctx"][str(c)] = counts["ctx"].get(str(c), 0) + 1
        files_done += 1
        if len(buf["games"]) >= args.shard_games:
            flush()
        if files_done % 50 == 0:
            print(
                f"  {files_done}/{len(jobs)} games  {counts['kept']} decisions  "
                f"{len(feature_names)} features  {time.perf_counter() - t0:.0f}s",
                flush=True,
            )

    if args.workers <= 1:
        _init_worker(str(agent_meta))
        for job in jobs:
            add_result(process_file(job))
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_init_worker,
            initargs=(str(agent_meta),),
        ) as ex:
            for res in ex.map(process_file, jobs, chunksize=2):
                add_result(res)
    flush()

    meta_out = {
        "format": 1,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "episodes_dir": str(ep_dir),
        "min_score": args.min_score,
        "filters": {
            "select_not_null": True,
            "maxCount": 1,
            "minCount<=": 1,
            "1<=n_options<=": 40,
            "player_status": "ACTIVE",
            "action_len": 1,
        },
        "feature_names": feature_names,
        "splits": {
            "train": [i for i in ids if split[i] == "train"],
            "valid": [i for i in ids if split[i] == "valid"],
        },
        "counts": {
            "episodes": len(jobs),
            "decisions_seen": counts["seen"],
            "decisions_kept": counts["kept"],
            "option_rows": int(sum(s["n_option_rows"] for s in shards)),
            "features": len(feature_names),
            "by_context": counts["ctx"],
            "skipped": {
                k[len("skipped_") :]: v
                for k, v in counts.items()
                if k.startswith("skipped_")
            },
        },
        "shards": shards,
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta_out))
    print(
        f"done: {len(shards)} shards, {counts['kept']} decisions, "
        f"{meta_out['counts']['option_rows']} option rows, "
        f"{len(feature_names)} features, {meta_out['elapsed_s']}s"
    )
    contexts = sorted(counts["ctx"].items(), key=lambda kv: -kv[1])[:8]
    print("top contexts:", ", ".join(f"ctx{k}={v}" for k, v in contexts))
    print("decision options mean:", round(meta_out["counts"]["option_rows"] / max(counts["kept"], 1), 2))
    print("wrote", out_dir / "meta.json", "and", agent_meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
