"""Train the linear behavior-cloning scorer and export submission weights.

Input:  data/bc/{shard_*.npz, meta.json} (from scripts/bc_extract.py)
Output: agents/bc_linear/weights.json, data/bc/metrics.json

The model is a binary "is this option the one the pilot picked?" linear scorer,
trained with logistic loss on option rows.  At inference the option with the
highest score wins (i.e. a pointwise ranker, not a calibrated softmax).

Metrics on held-out episodes:
  * per-decision top-1 accuracy and log-loss (softmax over the offered options)
  * per-context breakdown (MAIN=0 / EVOLVE=7 / others)
  * baselines: random option, first option, majority option type, row majority

Usage:
    .venv/bin/python scripts/train_bc.py --data data/bc --epochs 5
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.linear_model import SGDClassifier

ROOT = Path(__file__).resolve().parents[1]


def load_split(meta: dict, split: str, data_dir: Path):
    """Concatenate shards, keeping only games in `split`, padded to full width."""
    width = len(meta["feature_names"])
    mats, labels, ctxs, weights = [], [], [], []
    ptr_parts = []
    total = 0
    for shard in meta["shards"]:
        keep = [i for i, s in enumerate(shard["split"]) if s == split]
        if not keep:
            continue
        X = sparse.load_npz(data_dir / shard["file"]).tocsr()
        z = np.load(data_dir / shard["meta"])
        dec_ptr = z["ptr"]
        game = z["game"]
        dec_keep = np.isin(game, keep)
        starts = dec_ptr[:-1][dec_keep]
        ends = dec_ptr[1:][dec_keep]
        row_mask = np.zeros(X.shape[0], dtype=bool)
        for a, b in zip(starts, ends):
            row_mask[a:b] = True
        Xk = X[row_mask]
        if Xk.shape[1] < width:
            Xk = sparse.hstack(
                [Xk, sparse.csr_matrix((Xk.shape[0], width - Xk.shape[1]))],
                format="csr",
            )
        mats.append(Xk)
        labels.append(z["labels"][dec_keep])
        sizes = (ends - starts).astype(np.int64)
        ptr_parts.append(np.concatenate([[0], np.cumsum(sizes)]).astype(np.int64) + total)
        ctxs.append(z["ctx"][dec_keep])
        weights.append(z["weight"][game[dec_keep]])
        total += int(sizes.sum())
    if not mats:
        raise SystemExit(f"no shards for split={split}")
    ptr = np.concatenate([ptr_parts[0]] + [p[1:] for p in ptr_parts[1:]])
    X = sparse.vstack(mats, format="csr").astype(np.float32)
    return {
        "X": X,
        "labels": np.concatenate(labels),
        "ptr": ptr,
        "ctx": np.concatenate(ctxs),
        "weight": np.concatenate(weights),
    }


def decision_scores(X, coef, ptr):
    scores = X @ coef
    return scores


def top1_and_logloss(scores, data, ptr, labels, mask=None):
    """Per-decision top-1 and softmax log-loss over the options of each decision."""
    n_dec = len(labels)
    idx = np.arange(n_dec)
    if mask is not None:
        idx = idx[mask]
    correct = 0
    ll = 0.0
    rows_total = 0
    for i in idx:
        a, b = ptr[i], ptr[i + 1]
        s = scores[a:b]
        n = b - a
        m = s.max()
        softmax = np.exp(s - m)
        z = softmax.sum()
        chosen = labels[i]
        ll -= float(math.log(max(softmax[chosen] / z, 1e-12)))
        correct += int(int(np.argmax(s)) == int(chosen))
        rows_total += n
    n = len(idx)
    return {
        "decisions": int(n),
        "top1": correct / n if n else 0.0,
        "logloss": ll / n if n else 0.0,
        "mean_options": rows_total / n if n else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "bc"))
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--alpha", type=float, default=1e-6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "agents" / "bc_linear" / "weights.json"))
    ap.add_argument("--no-score-weight", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data)
    meta = json.loads((data_dir / "meta.json").read_text())
    names = meta["feature_names"]
    print(f"features={len(names)} shards={len(meta['shards'])}")
    t0 = time.perf_counter()
    tr = load_split(meta, "train", data_dir)
    va = load_split(meta, "valid", data_dir)
    print(
        f"train: {len(tr['labels'])} decisions / {tr['X'].shape[0]} rows "
        f"({tr['X'].nnz} nnz)   valid: {len(va['labels'])} / {va['X'].shape[0]}"
    )

    # -.  training target: the chosen option row vs all other option rows -----
    def expand(data):
        y = np.zeros(data["X"].shape[0], dtype=np.int8)
        row_w = np.ones(data["X"].shape[0], dtype=np.float32)
        for i in range(len(data["labels"])):
            a = data["ptr"][i]
            y[a + data["labels"][i]] = 1
            row_w[a : data["ptr"][i + 1]] = data["weight"][i]
        return y, row_w

    y_tr, w_tr = expand(tr)
    print(
        f"label balance: {y_tr.sum()} positives / {len(y_tr)} option rows "
        f"({y_tr.mean():.3%}); mean n_options={tr['X'].shape[0]/len(tr['labels']):.2f}"
    )
    t1 = time.perf_counter()
    clf = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=args.alpha,
        average=True,
        max_iter=args.epochs,
        tol=None,
        shuffle=True,
        random_state=args.seed,
        verbose=0,
    )
    clf.fit(
        tr["X"],
        y_tr,
        sample_weight=None if args.no_score_weight else w_tr,
    )
    t2 = time.perf_counter()
    print(f"fit {t2 - t1:.1f}s ({args.epochs} epochs)")

    coef = clf.coef_[0]  # class 1 = "this option was chosen"
    intercept = float(clf.intercept_[0])

    # -.  held-out metrics -----------------------------------------------------
    sv = decision_scores(va["X"], coef, va["ptr"]) + intercept
    st = decision_scores(tr["X"], coef, tr["ptr"]) + intercept
    ev = top1_and_logloss(sv, va, va["ptr"], va["labels"])
    et = top1_and_logloss(st, tr, tr["ptr"], tr["labels"])
    print(f"train {et}\nvalid {ev}")

    # per-context
    by_ctx = {}
    for name, c in (("MAIN", 0), ("EVOLVE", 7)):
        mask = va["ctx"] == c
        by_ctx[name] = top1_and_logloss(sv, va, va["ptr"], va["labels"], mask)
    others = ~np.isin(va["ctx"], [0, 7])
    by_ctx["others"] = top1_and_logloss(sv, va, va["ptr"], va["labels"], others)
    for k, v in by_ctx.items():
        print(f"  valid {k:7s} {v}")

    # baselines
    base = {}
    n = len(va["labels"])
    sizes = np.diff(va["ptr"])
    base["random_top1"] = float(np.mean(1.0 / sizes))
    base["random_logloss"] = float(np.mean(np.log(sizes)))
    base["first_option_top1"] = float(np.mean(va["labels"] == 0))
    base["first_option_logloss"] = float(np.mean(np.log(sizes)))
    # majority option type per context (fit on train labels, evaluated on valid)
    ot_names = {}
    for j, nm in enumerate(names):
        if nm.startswith("ot="):
            ot_names[j] = int(nm[3:])
    # recover chosen option's type from the feature rows
    def option_types(mat, ot_map):
        """type id of each option row."""
        cols = sorted(ot_map)
        sub = mat[:, cols].tocsr()
        am = np.asarray(sub.argmax(axis=1)).ravel()
        tvals = np.array([ot_map[c] for c in cols])
        return tvals[am]

    tr_types = option_types(tr["X"], ot_names)
    va_types = option_types(va["X"], ot_names)
    maj = {}
    for c in np.unique(tr["ctx"]):
        mask = tr["ctx"] == c
        cnt = Counter()
        for i in np.where(mask)[0]:
            a = tr["ptr"][i]
            cnt[int(tr_types[a + tr["labels"][i]])] += 1
        maj[int(c)] = cnt.most_common(1)[0][0]
    correct = 0
    ll = 0.0
    for i in range(len(va["labels"])):
        a, b = va["ptr"][i], va["ptr"][i + 1]
        want = maj.get(int(va["ctx"][i]), -1)
        opts = np.where(va_types[a:b] == want)[0]
        pred = int(opts[0]) if len(opts) else 0
        correct += int(pred == va["labels"][i])
        ll += math.log(b - a)
    base["majority_type_top1"] = correct / len(va["labels"])
    base["majority_type_logloss"] = ll / len(va["labels"])
    # option-row majority class: predict "not chosen" for every option row
    base["row_majority_accuracy"] = 1.0 - len(va["labels"]) / va["X"].shape[0]
    print("baselines:", json.dumps(base, indent=2))

    # -.  export compact weights ----------------------------------------------
    entries = [
        [nm, round(float(w), 4)]
        for nm, w in zip(names, coef)
        if abs(w) >= 1e-4
    ]
    entries.sort(key=lambda kv: -abs(kv[1]))
    payload = {
        "format": 1,
        "objective": "binary log-loss on option rows; argmax over options",
        "trained": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "episodes": {
            "train": len(meta["splits"]["train"]),
            "valid": len(meta["splits"]["valid"]),
        },
        "decisions": {
            "train": int(len(tr["labels"])),
            "valid": int(len(va["labels"])),
        },
        "features": len(names),
        "epochs": args.epochs,
        "alpha": args.alpha,
        "intercept": round(intercept, 4),
        "weights": entries,
        "valid_metrics": {
            "top1": round(ev["top1"], 4),
            "logloss": round(ev["logloss"], 4),
            "by_context": {
                k: {"top1": round(v["top1"], 4), "logloss": round(v["logloss"], 4)}
                for k, v in by_ctx.items()
            },
            "baselines": {k: round(v, 4) for k, v in base.items()},
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {out} ({len(entries)} non-zero weights, {out.stat().st_size/1024:.0f} KB)")

    metrics = {
        "dataset": meta["counts"],
        "train": et,
        "valid": ev,
        "valid_by_context": by_ctx,
        "baselines": base,
        "fit_s": round(t2 - t1, 1),
        "total_s": round(time.perf_counter() - t0, 1),
        "config": vars(args),
    }
    mpath = data_dir / "metrics.json"
    mpath.write_text(json.dumps(metrics, indent=2, default=str))
    print("wrote", mpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
