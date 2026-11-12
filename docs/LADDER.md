# Real ladder submissions (2026-11-12)

Scores are **dynamic** (simulation ladder, Elo-like). This file records what was
submitted and what the official API reported at the time of reading. No score is
presented as final or converged.

| Ref | Artifact | Status | Official score (observed) | Notes |
|---:|---|---|---:|---|
| 58273092 | `public_v3_lop.tar.gz` — public PPO v3 (Dipam, MIT) + Mega Lopunny #5 | COMPLETE | **687.6** at 12:47 UTC | Started at 600.0; first public episode won vs `(ノ◡ <)` (Q-learning baseline). Score will move as more matches complete. |
| 58273114 | `search_v1_full.tar.gz` — from-scratch search_v1 + Dragapult | ERROR | — | `NameError: name '__file__' is not defined` from the Kaggle loader; see below. |
| 58273236 | `search_v1_full_v2.tar.gz` — same, fixed loader guard | PENDING (validation) | — | Resubmitted after the fix. |

## The `__file__` loader bug

The Kaggle runner `exec()`s `main.py` **without defining `__file__`**:

```
File "/kaggle_simulations/agent/main.py", line 41, in <module>
    _HERE = os.path.dirname(os.path.abspath(__file__))
NameError: name '__file__' is not defined
```

The public v3 bundle handles it with a `try/except NameError` and falls back to
cwd / `/kaggle_simulations/agent`. Our agents did not, so the first from-scratch
submission was rejected (`SubmissionStatus.ERROR`) while the public bundle ran
fine. All agents in `agents/` now use:

```python
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.getcwd() if os.path.exists(os.path.join(os.getcwd(), "deck.csv")) else "/kaggle_simulations/agent"
```

This also means **local arena success is not sufficient**: the loader environment
must be simulated (`exec(code, {})` with cwd = agent dir) before submitting.

## What is being measured

- The public PPO bundle's public score was 1074.1 in October with its Alakazam
  list. The meta has since moved to Lopunny/Dragapult/Excadrill (Alakazam is
  1.9% of 2026-11-09 seats), so the first submission tests whether the deck swap
  transfers to the real ladder.
- The from-scratch `search_v1` submission is the real-ladder measurement of the
  heuristic + determinized search arm. Its local BO1 edge over `heuristic_v1`
  was 54.2% (Dragapult) / 61.3% (Lopunny).

## Reading the score

The public score is an Elo-like rating seeded at 600. A single first match can
move it by tens of points; it is not a stable estimate until many rated episodes
complete. The leaderboard shows the team's highest active submission; only the
latest two submissions are active.

Check:

```bash
kaggle competitions submissions -c the-pokemon-company-ptcg-ai-battle-challenge-playground
kaggle competitions episodes <submission_id>
kaggle competitions replay <episode_id> -p /tmp/ep
```
