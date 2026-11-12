"""Compatibility shim for the official ``cg`` Python SDK.

Put ``vendor/`` on ``sys.path`` and ``import cg`` resolves to this package::

    PYTHONPATH=vendor python my_agent.py

``cg.sim`` and ``cg.game`` simply re-export the engine bindings that ship in
the ``kaggle-environments`` wheel.  ``cg.api`` restores the parts of the
official SDK that the wheel does *not* ship (enums, observation data classes,
card metadata and the forward-search API).
"""

__all__ = ["api", "game", "sim"]
