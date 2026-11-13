"""Fine-tune the public v3 PPO model by behavior cloning on top-field replays.

Runs on a Kaggle GPU notebook. Inputs (attached datasets):
  /kaggle/input/ptcg-v3-bundle/                     model.pt, ptcg/, data/, cg/
  /kaggle/input/the-pokemon-company-ptcg-ai-battle-challenge-playground-episodes-2026-11-12/

Outputs in /kaggle/working:
  model_ft.pt, metrics.json
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

print("INPUT ROOT:", os.listdir("/kaggle/input"), flush=True)
for _p in Path("/kaggle/input").iterdir():
    try:
        print(" ", _p, [x.name for x in list(_p.iterdir())[:12]], flush=True)
    except Exception as _e:
        print(" ", _p, _e, flush=True)
ROOT_IN = Path("/kaggle/input/datasets")
V3 = ROOT_IN / "johnferrel/ptcg-v3-bundle"
EP = ROOT_IN / "kaggle/the-pokemon-company-ptcg-ai-battle-challenge-playground-episodes-2026-11-12"
print("V3 exists", V3.exists(), "EP exists", EP.exists(), flush=True)
if V3.exists():
    print("V3 files", [x.name for x in list(V3.iterdir())[:12]], flush=True)
OUT = Path("/kaggle/working")
sys.path.insert(0, str(V3))

from ptcg.rl.buffers import OBS_SIZE, MAX_OPTIONS, STOP  # noqa: E402
from ptcg.rl.encoder import encode  # noqa: E402
from ptcg.rl.model import PTCGTransformer, arch_from_state_dict  # noqa: E402
from ptcg.tracker import InfoTracker  # noqa: E402

MIN_SCORE = 1200.0
MAX_TRAIN = 120_000
MAX_VALID = 12_000
VALID_EVERY = 10          # every 10th episode is validation
EPOCHS = 2
BATCH = 512
LR = 1e-4
HEADS = 8
SEED = 7


def decisions(ep: dict):
    """(obs, action, player) for the ACTIVE player; action at t+1 answers obs at t."""
    steps = ep.get("steps") or []
    out = []
    for t in range(len(steps) - 1):
        for p in (0, 1):
            try:
                if steps[t][p].get("status") != "ACTIVE":
                    continue
                obs = steps[t][p]["observation"]
                sel = obs.get("select")
                if not sel or (obs.get("current") or {}).get("yourIndex") != p:
                    continue
                act = steps[t + 1][p].get("action")
                if not isinstance(act, list):
                    continue
                if not act and int(sel.get("minCount") or 0) > 0:
                    continue
                out.append((obs, [int(a) for a in act], p))
            except Exception:
                continue
    return out


def build():
    manifest = {}
    for r in csv.DictReader(open(EP / "manifest.csv")):
        manifest[r["episode_id"]] = float(r["min_score"])
    files = sorted(EP.glob("*.json"))
    import random as _random
    _random.Random(SEED).shuffle(files)
    tr_rows = np.empty((MAX_TRAIN, OBS_SIZE), dtype=np.float16)
    tr_labels = np.empty(MAX_TRAIN, dtype=np.int16)
    va_rows = np.empty((MAX_VALID, OBS_SIZE), dtype=np.float16)
    va_labels = np.empty(MAX_VALID, dtype=np.int16)
    nt = nv = 0
    n_ep = 0
    t0 = time.time()
    for f in files:
        if nt >= MAX_TRAIN and nv >= MAX_VALID:
            break
        sc = manifest.get(f.stem)
        if sc is not None and sc < MIN_SCORE:
            continue
        try:
            ep = json.loads(f.read_text())
            dec = decisions(ep)
            if not dec:
                continue
            p = dec[0][2]
            deck = list(ep["steps"][1][p]["action"])
            if len(deck) != 60:
                continue
            tracker = InfoTracker(deck)
            valid_ep = (n_ep % VALID_EVERY == 0)
            used = False
            for obs, act, who in dec:
                if who != p:
                    continue
                tracker.update(obs)
                sel = obs.get("select")
                if not sel or sel.get("maxCount") != 1 or int(sel.get("minCount") or 0) > 1:
                    continue
                opts = sel.get("option") or []
                if len(opts) < 2 or len(opts) > 62 or not act:
                    continue
                a = act[0]
                if not (0 <= a < len(opts)):
                    continue
                row = np.zeros(OBS_SIZE, dtype=np.float32)
                try:
                    encode(row, obs, [], False, 0, tracker)
                except Exception:
                    continue
                if valid_ep:
                    if nv >= MAX_VALID:
                        continue
                    va_rows[nv] = row.astype(np.float16)
                    va_labels[nv] = a
                    nv += 1
                else:
                    if nt >= MAX_TRAIN:
                        continue
                    tr_rows[nt] = row.astype(np.float16)
                    tr_labels[nt] = a
                    nt += 1
                used = True
            if used:
                n_ep += 1
                if n_ep % 50 == 0:
                    print(f"{n_ep} episodes, train={nt}, valid={nv}, {time.time()-t0:.0f}s", flush=True)
        except Exception as exc:
            print(f"skip {f.name}: {type(exc).__name__}: {exc}", flush=True)
            continue
    print(f"done: train={nt}, valid={nv}, episodes={n_ep}, {time.time()-t0:.0f}s", flush=True)
    np.save(OUT / "train_rows.npy", tr_rows[:nt])
    np.save(OUT / "train_labels.npy", tr_labels[:nt])
    np.save(OUT / "valid_rows.npy", va_rows[:nv])
    np.save(OUT / "valid_labels.npy", va_labels[:nv])
    return tr_rows[:nt], tr_labels[:nt], va_rows[:nv], va_labels[:nv]


def load_model(device):
    sd = torch.load(V3 / "model.pt", map_location="cpu")
    model = PTCGTransformer(**arch_from_state_dict(sd, heads=HEADS))
    model.load_state_dict({k.replace("module.", ""): v for k, v in sd.items()})
    model.to(device)
    model.freeze_tables()
    model.eval()
    return model


def top1(model, rows, labels, device, bs=1024):
    model.eval()
    correct = 0
    with torch.no_grad():
        for i in range(0, len(rows), bs):
            x = torch.from_numpy(rows[i:i + bs].astype(np.float32)).to(device)
            y = torch.from_numpy(labels[i:i + bs].astype(np.int64)).to(device)
            logits = model.forward_policy(x)
            correct += int((logits.argmax(dim=-1) == y).sum())
    return correct / max(len(rows), 1)


def main():
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device", device, "OBS_SIZE", OBS_SIZE, flush=True)
    tr, tr_y, va, va_y = build()
    print(f"train {tr.shape} valid {va.shape}", flush=True)

    base = load_model(device)
    base_top1 = top1(base, va, va_y, device)
    print("BASE valid top1", base_top1, flush=True)

    model = load_model(device)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-2)
    best = base_top1
    best_state = None
    for epoch in range(EPOCHS):
        perm = np.random.permutation(len(tr))
        tot = 0.0
        n = 0
        t0 = time.time()
        for i in range(0, len(perm), BATCH):
            idx = perm[i:i + BATCH]
            x = torch.from_numpy(tr[idx].astype(np.float32)).to(device)
            y = torch.from_numpy(tr_y[idx].astype(np.int64)).to(device)
            logits = model.forward_policy(x)
            loss = F.cross_entropy(logits, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += float(loss)
            n += 1
            if n % 100 == 0:
                print(f"epoch {epoch} {n}/{len(perm)//BATCH} loss {tot/n:.4f} {time.time()-t0:.0f}s", flush=True)
        v = top1(model, va, va_y, device)
        print(f"epoch {epoch} train_loss {tot/max(n,1):.4f} valid_top1 {v:.4f}", flush=True)
        if v > best:
            best = v
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}

    if best_state is None:
        best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save(best_state, OUT / "model_ft.pt")
    metrics = {
        "train_rows": int(len(tr)), "valid_rows": int(len(va)),
        "base_valid_top1": base_top1, "ft_valid_top1": best,
        "delta": best - base_top1, "epochs": EPOCHS, "lr": LR,
        "min_score": MIN_SCORE, "obs_size": int(OBS_SIZE),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
