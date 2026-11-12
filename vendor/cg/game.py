"""Re-export of the installed cabt battle API (``cg.game``).

The ``kaggle-environments`` wheel ships this module in full.  The official
SDK's module has the same names, so re-exporting keeps public agents source
compatible::

    from cg.game import battle_start, battle_select, battle_finish
"""
from __future__ import annotations

from kaggle_environments.envs.cabt.cg.game import (  # noqa: F401
    _get_battle_data,
    battle_finish,
    battle_select,
    battle_start,
    visualize_data,
)
from kaggle_environments.envs.cabt.cg.sim import Battle, StartData  # noqa: F401

__all__ = [
    "Battle",
    "StartData",
    "battle_finish",
    "battle_select",
    "battle_start",
    "visualize_data",
]
