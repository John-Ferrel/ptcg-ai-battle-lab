import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptcg_ai import deck  # noqa: E402
from ptcg_ai.harness import play_game  # noqa: E402


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.parent.name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_random_vs_first_completes():
    a = _load(ROOT / "agents" / "random_legal" / "main.py")
    b = _load(ROOT / "agents" / "first_legal" / "main.py")
    d = deck.load_deck(ROOT / "decks" / "default.csv")
    r = play_game(a.agent, b.agent, d, d)
    assert r.winner in (0, 1, 2)
    assert not r.illegal
    assert r.decisions > 10


def test_agent_deck_contract():
    a = _load(ROOT / "agents" / "random_legal" / "main.py")
    assert len(a.agent({"select": None, "current": None})) == 60
