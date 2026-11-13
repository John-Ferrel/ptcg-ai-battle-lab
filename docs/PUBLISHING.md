# Publishing checklist

## Suggested GitHub metadata

- **Repo name:** `ptcg-ai-battle-lab`
- **Description:** `Pokémon TCG AI battle lab: ctypes harness, replay/meta mining, determinized search, public PPO baseline, and honest ladder experiments.`
- **Topics:** `pokemon-tcg`, `kaggle`, `game-ai`, `reinforcement-learning`, `behavior-cloning`, `mcts`, `simulation`, `python`
- **Social preview:** `docs/figures/meta_1112.png` (or `ladder_noise.png`)
- **Release tag:** `v1.0.0-research`

## What is safe to publish

- All code in `src/`, `scripts/`, `agents/`, `tests/`, `kaggle/finetune/`.
- Documentation and **derived statistics** in `docs/` (`META_*`, `LADDER.md`, `METAGAME.md`, `PILOT_GAP.md`, `FINETUNE.md`).
- Small deck lists in `decks/` / `agents/*/deck.csv` (derived from CC0 replays or public lists, attributed).
- Figures in `docs/figures/` (derived statistics only).
- `LICENSE` (MIT) and `THIRD_PARTY_NOTICES.md`.

## What must NOT be published

- `data/` — the card database, official engine source, downloaded competition data, raw replay files.
- `vendor/cg/` — the official `cg` SDK / compiled engine (competition-use-only).
- `submissions/*.tar.gz` — they contain the licensed engine and/or the public model.
- `agents/*/card_meta.json`, `data/public_v3/`, `model.pt`, `model_ft.pt`.
- Raw Kaggle episode JSONs or the public PPO bundle (including its `cg/`).

The `.gitignore` already excludes all of the above. Before pushing, run:

```bash
git ls-files | grep -E "vendor/cg|card_meta\.json|model\.pt|EN_Card|libcg|\.npy$" || echo "clean"
```

## Push with a deploy key

1. Create an **empty** GitHub repository (no README, no .gitignore).
2. Settings → **Deploy keys** → Add deploy key:
   - paste the **public** key;
   - enable **Allow write access**.
3. Provide the **private key path** and the SSH URL to the agent:
   `git@github.com:<owner>/<repo>.git`.
4. Push:

```bash
cd /home/john/pufi/ptcg-ai-battle
git remote add origin git@github.com:<owner>/<repo>.git
GIT_SSH_COMMAND="ssh -i <private_key> -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
  git push -u origin main
```

A deploy key is repo-scoped and write-enabled; a PAT over HTTPS is equivalent.

## Release notes (`v1.0.0-research`)

```markdown
# v1.0.0-research — PTCG AI Battle Lab

A reproducible research lab for the Kaggle PTCG AI Battle Challenge Playground.

## Included
- ctypes cabt harness (~10 ms/game), seat-swapped arena with Wilson CIs.
- Meta/replay mining (1,694 + 1,625 matches), matchup matrices, climb path.
- heuristic_v1, search_v1 (recovered native search ABI), bc_linear.
- Public PPO v3 baseline (MIT, credited) + deck re-optimization.
- Real ladder submissions: best observed 1102.5; stable core 886.7.
- Honest negative results: BC, search overlay, hand reranker, BC fine-tune.

## Not included
Engine/card data/official SDK/raw replays/public model — competition-use-only
or third-party; see THIRD_PARTY_NOTICES.md.

## Caveat
The ladder is noisy (±100+ points for the same artifact). 1102.5 is a best
observation, not a stable strength estimate.
```

## Things to avoid

- Do not present `1102.5` as a stable score or a top-rank claim; label it
  "best observed / high-variance".
- Do not hide the negative results; they are part of the research value.
- Do not add `data/`, `vendor/cg/`, `model.pt`, or submission tarballs "for
  convenience".
- Do not publish raw replay files or the public PPO bundle.
