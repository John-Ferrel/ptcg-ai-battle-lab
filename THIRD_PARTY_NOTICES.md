# Third-party notices

This repository contains original code and analysis. It intentionally does not
redistribute the competition engine, the card database, the official SDK, the
raw replay files, or the public PPO checkpoint.

| Component | Owner / source | License / terms | Included here? |
|---|---|---|---|
| `ptcgProgram` engine, card data, official `cg` SDK | Pokémon / Nintendo / Creatures / GAME FREAK / HEROZ / Matsuo Institute; Kaggle competition Data | **Competition-use only** (see the license shipped with the engine). No redistribution, no public posting, delete after the competition. | **No** |
| Kaggle playground replay datasets | Kaggle (`kaggle/the-pokemon-company-...-episodes-*`) | CC0-1.0 on the dataset pages | No; only derived statistics are committed |
| Parsed ladder dataset | Darren Sheehan (`kaggle.com/datasets/darrensheehan/ptcg-playground-ladder-matches`) | CC0-1.0 | No; only derived statistics are committed |
| Public PPO v3 code/weights | Dipam Chakraborty, `github.com/dipamc/kaggle-ptcg-ai-battle`, commit `a176778d99da74a44b495bf19299b4795faf12f2` | MIT | No; `scripts/fetch_public_v3.py` downloads the public notebook output |
| v3 packaging / new-card port / seat fixes | busyaprime, `kaggle.com/code/busyaprime/lb-1074-1-same-agent-as-public-1-better-deck` | Public Kaggle notebook; see the notebook | No |
| Public agent ideas / deck lists | `MaliciousMusic/pokemon-tcg-ai-battle`, `wmh/ptcg-abc`, `hotorch/ptcg-ai-battle-strategy`, `SiamRahman29/pokemon-tcg-agent`, `shreyas463/pokemon-tcg-agent` | Their respective repositories (MIT where stated) | Only small deck lists / citations, with attribution |
| `kaggle-environments`, `torch`, `numpy`, `scikit-learn` | Respective projects | Their own licenses | Not vendored; installed as dependencies |

## Pokémon trademarks

Pokémon and Pokémon TCG are trademarks of Nintendo / Creatures / GAME FREAK.
Card names and game facts are used nominatively for competition analysis. No
trademark or patent license is granted.

## Competition rules

The binding terms are the official Competition Rules accepted on Kaggle:
<https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/rules>.
Where this notice and the Rules differ, the Rules govern.
