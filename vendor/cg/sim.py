"""Re-export of the installed cabt engine bindings (``cg.sim``).

Public agents written against the official SDK do ``from cg.game import ...``
and occasionally touch ``cg.sim.Battle`` / ``cg.sim.lib``.  The
``kaggle-environments`` wheel already contains a working ``sim`` module, so we
re-export it instead of keeping a second copy of the ctypes definitions.  Both
names then point at the *same* ``Battle`` singleton and the same ``CDLL``.
"""
from __future__ import annotations

from kaggle_environments.envs.cabt.cg.sim import (  # noqa: F401
    LATEST_VERSION,
    Battle,
    SerialData,
    StartData,
    get_lib,
    lib,
    load_lib,
)

__all__ = [
    "LATEST_VERSION",
    "Battle",
    "SerialData",
    "StartData",
    "get_lib",
    "lib",
    "load_lib",
]
