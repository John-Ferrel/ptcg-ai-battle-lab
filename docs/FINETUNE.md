# Fine-tune experiment — BC on 2026-11-12 top-field replays

**Result: NO-GO.** Offline action agreement improved a lot; online win rate did
not. The fine-tuned model is not submitted.

## Setup

- Base: public v3 PPO checkpoint (`model.pt`, 20 MB, d=256/4 layers/8 heads).
- Data: 2026-11-12 raw replays, `min_score >= 1200`, single-pick decisions
  (the same decision filter as the serving agent).
- Train / valid: **104,694 / 12,000** decisions (split by episode, every 10th
  episode held out).
- Input: the model's own encoder, `OBS_SIZE = 10,944`.
- Training: 2 epochs, AdamW lr 1e-4, batch 512, T4 GPU; Kaggle kernel
  `johnferrel/ptcg-v3-finetune`; artifacts in the kernel output.

## Offline

| Model | Valid top-1 |
|---|---:|
| Base v3 | 53.48% |
| Fine-tuned | **65.04%** |
| Delta | **+11.57 pts** |

The train loss was ~1.5e7, i.e. the model's logits are on a very large scale.
The optimizer still sharpened the correct actions on the held-out episodes, but
the loss scale is a red flag for BC stability.

## Online (same engine, seat-swapped, 200 games each, 0 illegal / 0 errors)

| Matchup | Fine-tuned WR | CI95 |
|---|---:|---|
| pult8_08 vs base pult8_08 | **51.5%** (103/200) | 44.6–58.3% |
| Lopunny_05 vs base Lopunny_05 | **37.0%** (74/200) | 30.6–43.9% |

So the +11.6-point offline gain became +1.5 points online (inside noise) on the
fine-tune's own deck, and **-13 points** on Lopunny. The model overfit the
11-12 top-field action distribution and lost general piloting strength.

## Why it failed

1. **Offline top-1 is not win rate.** Top-pilot actions are not uniquely optimal;
   imitating them can lower the expected value of the policy.
2. **The loss was unstable** (logits ~1e7). A scale-normalized CE (or a smaller
   LR / logit temperature) would be the next thing to try, but it does not fix
   the distribution-shift problem.
3. **No value/advantage signal.** BC only says "what a pilot did", not "what
   wins". DAgger/self-play/PPO with a value head is the proper next step.
4. **Meta-specific overfit.** The 11-12 data is pult8/Excadrill-heavy; the
   fine-tuned model got worse on Lopunny.

## Go/no-go

| Gate | Threshold | Result |
|---|---|---|
| Offline top-1 | > base + 2 pts | PASS (+11.6) |
| Online pult8 | > 53% | **FAIL (51.5%)** |
| Online other deck | not worse than base | **FAIL (37.0%)** |

Decision: **do not submit**; keep the active pair (pult8 916.6 + Lopunny 815.5)
and the base model. The experiment is recorded as a negative result.

## Artifacts

- `kaggle/finetune/train.py` — extraction + BC training script.
- `kaggle/finetune/kernel-metadata.json` — private Kaggle GPU kernel.
- `johnferrel/ptcg-v3-bundle` — private Kaggle dataset with the base bundle.
- `model_ft.pt`, `metrics.json`, `train_rows.npy`, `valid_rows.npy` — in the
  kernel output (downloaded locally; not committed).

## What would be worth trying next

A **DAgger/self-play** loop with the value head and a scale-normalized policy
loss, using the v3 model as the initial policy; or a newer checkpoint. Pure BC
on top-pilot actions is not enough.
