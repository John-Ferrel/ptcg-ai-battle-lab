# Real ladder submissions (2026-11-12)

Scores are **dynamic** (simulation ladder, Elo-like). This file records what was
submitted and what the official API reported at the time of reading. No score is
presented as final or converged.

| Ref | Artifact | Status | Official score (observed) | Notes |
|---:|---|---|---:|---|
| 58273092 | `public_v3_lop.tar.gz` — public PPO v3 (Dipam, MIT) + Mega Lopunny #5 | COMPLETE | **879.5** at 12:56 UTC | 600.0 → 687.6 → 879.5 over three public episodes. Still not converged. |
| 58273114 | `search_v1_full.tar.gz` — from-scratch search_v1 + Dragapult | ERROR | — | `NameError: name '__file__' is not defined` from the Kaggle loader; see below. |
| 58273236 | `search_v1_full_v2.tar.gz` — same, fixed loader guard | COMPLETE | **491.1** at 12:56 UTC | Real-ladder measurement of the from-scratch arm; it lost more than it won. |
| 58273532 | `public_v3_pult8.tar.gz` — public v3 + Dragapult/Blaziken #8 | PENDING | — | Field-weighted best deck vs the 2026-11-09 meta; submitted after the Lopunny result. |

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

## Observed trajectory (12:40–12:56 UTC)

| Time | v3+Lopunny | search_v1 (from scratch) |
|---|---:|---:|
| 12:47 | 687.6 | — |
| 12:56 | **879.5** | **491.1** |

The public PPO base is ~390 rating points above the from-scratch search agent
after the first few matches. The v3+Lopunny score was still rising when the
third candidate (v3 + Dragapult/Blaziken) was submitted; only the latest two
submissions are active, so v3+Lopunny may become inactive until resubmitted.

## Why the third candidate is Dragapult/Blaziken, not Lopunny

Real 2026-11-09 match-level matrix (1,694 matches, proper archetype labels):

| Deck | Field-weighted WR | Key matchup |
|---|---:|---|
| **Dragapult / Blaziken** | **51.3%** | beats Excadrill **68.3%** (189 games) |
| Mega Lopunny / Froslass | 48.6% | loses to Excadrill **34.8%** (132 games) |
| Mega Excadrill / Genesect | 48.3% | 39.5% of the field |
| Dragapult / Drakloak | 39.4% | loses to Excadrill 36.8% |

Lopunny looked best in same-model self-play (63.4% round-robin), but the real
field is Excadrill-heavy and Lopunny is its prey. Dragapult/Blaziken is the
counter to the most common archetype, and under the v3 model it is even with
Lopunny (49.2%, 120 games) and slightly ahead of Dragapult/Drakloak (51.7%,
120 games). That is why it is the third submission.
