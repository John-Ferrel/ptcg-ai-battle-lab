"""Wrapper that runs a downloaded public agent against this repo's ``cg`` SDK.

The public agent lives outside the repo (``/tmp/search_agent/main.py`` by
default).  It does ``from cg.api import ...``, so ``vendor/`` must be on
``sys.path`` *before* the module is imported.  This wrapper does that and then
loads the file by absolute path (the public agent finds its own ``deck.csv``
via ``__file__``).

Usage::

    PYTHONPATH=vendor .venv/bin/python scripts/arena.py \
        --agent-a scripts/search_smoke_public.py \
        --deck-a /tmp/search_agent/deck.csv \
        --agent-b agents/greedy --deck-b decks/default.csv --games 20
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))

PUBLIC_AGENT = Path(
    os.environ.get("SEARCH_SMOKE_AGENT", "/tmp/search_agent/main.py")
)

_spec = importlib.util.spec_from_file_location("_public_search_agent", PUBLIC_AGENT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load public agent from {PUBLIC_AGENT}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

agent = _module.agent
