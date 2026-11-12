"""Python API for the cabt engine (``cg.api``).

The ``kaggle-environments`` wheel only ships ``cg/sim.py`` and ``cg/game.py``;
the official SDK also has ``cg/api.py`` with enums, observation data classes,
card metadata and the forward-search entry points.  This module restores that
API on top of the *same* compiled library (``libcg.so`` / ``libcg.dylib`` /
``cg.dll``) shipped in the wheel.

Recovered native prototypes (x86-64 build shipped with
``kaggle-environments==1.33.3``)::

    void *AgentStart(void);
    char *SearchBegin(void *agent, const char *search_begin_input, int input_len,
                      const int *your_deck, const int *your_prize,
                      const int *opponent_deck, const int *opponent_prize,
                      const int *opponent_hand, const int *opponent_active,
                      int manual_coin);
    char *SearchStep(void *agent, int search_id, const int *picks, int pick_count);
    void  SearchEnd(void *agent);
    void  SearchRelease(void *agent, int search_id);

Both search entry points return a JSON ``ApiResult`` document::

    {"state": {"observation": {...}, "searchId": 0}, "error": 0}

The first call must be preceded by ``AgentStart()`` (it allocates the
search-mode engine object and switches the internal mode from battle to
search).  See ``docs/SEARCH_API.md`` for the full reverse-engineering notes.
"""
from __future__ import annotations

import ctypes
import json
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enums (values copied from https://matsuoinstitute.github.io/cabt/api.html)
# ---------------------------------------------------------------------------


class AreaType(IntEnum):
    """Areas where a card can be located."""

    DECK = 1
    HAND = 2
    DISCARD = 3
    ACTIVE = 4
    BENCH = 5
    PRIZE = 6
    STADIUM = 7
    ENERGY = 8
    TOOL = 9
    PRE_EVOLUTION = 10
    PLAYER = 11
    LOOKING = 12


class EnergyType(IntEnum):
    """Energy types."""

    COLORLESS = 0
    GRASS = 1
    FIRE = 2
    WATER = 3
    LIGHTNING = 4
    PSYCHIC = 5
    FIGHTING = 6
    DARKNESS = 7
    METAL = 8
    DRAGON = 9
    RAINBOW = 10
    TEAM_ROCKET = 11


class CardType(IntEnum):
    """Card types."""

    POKEMON = 0
    ITEM = 1
    TOOL = 2
    SUPPORTER = 3
    STADIUM = 4
    BASIC_ENERGY = 5
    SPECIAL_ENERGY = 6


class SpecialConditionType(IntEnum):
    """Special condition types."""

    POISON = 0
    BURN = 1
    SLEEP = 2
    PARALYZE = 3
    CONFUSE = 4


class SelectType(IntEnum):
    """Selection type (``Observation.select.type``)."""

    MAIN = 0
    CARD = 1
    ATTACHED_CARD = 2
    CARD_OR_ATTACHED_CARD = 3
    ENERGY = 4
    SKILL = 5
    ATTACK = 6
    EVOLVE = 7
    COUNT = 8
    YES_NO = 9
    SPECIAL_CONDITION = 10


class SelectContext(IntEnum):
    """Detailed purpose of a selection (``Observation.select.context``)."""

    MAIN = 0
    SETUP_ACTIVE_POKEMON = 1
    SETUP_BENCH_POKEMON = 2
    SWITCH = 3
    TO_ACTIVE = 4
    TO_BENCH = 5
    TO_FIELD = 6
    TO_HAND = 7
    DISCARD = 8
    TO_DECK = 9
    TO_DECK_BOTTOM = 10
    TO_PRIZE = 11
    NOT_MOVE = 12
    DAMAGE_COUNTER = 13
    DAMAGE_COUNTER_ANY = 14
    DAMAGE = 15
    REMOVE_DAMAGE_COUNTER = 16
    HEAL = 17
    EVOLVES_FROM = 18
    EVOLVES_TO = 19
    DEVOLVE = 20
    ATTACH_FROM = 21
    ATTACH_TO = 22
    DETACH_FROM = 23
    LOOK = 24
    EFFECT_TARGET = 25
    DISCARD_ENERGY_CARD = 26
    DISCARD_TOOL_CARD = 27
    SWITCH_ENERGY_CARD = 28
    DISCARD_CARD_OR_ATTACHED_CARD = 29
    DISCARD_ENERGY = 30
    TO_HAND_ENERGY = 31
    TO_DECK_ENERGY = 32
    SWITCH_ENERGY = 33
    SKILL_ORDER = 34
    ATTACK = 35
    DISABLE_ATTACK = 36
    EVOLVE = 37
    DRAW_COUNT = 38
    DAMAGE_COUNTER_COUNT = 39
    REMOVE_DAMAGE_COUNTER_COUNT = 40
    IS_FIRST = 41
    MULLIGAN = 42
    ACTIVATE = 43
    FIRST_EFFECT = 44
    MORE_DEVOLVE = 45
    COIN_HEAD = 46
    AFFECT_SPECIAL_CONDITION = 47
    RECOVER_SPECIAL_CONDITION = 48


class OptionType(IntEnum):
    """Kinds of options that can be selected."""

    NUMBER = 0
    YES = 1
    NO = 2
    CARD = 3
    TOOL_CARD = 4
    ENERGY_CARD = 5
    ENERGY = 6
    PLAY = 7
    ATTACH = 8
    EVOLVE = 9
    ABILITY = 10
    DISCARD = 11
    RETREAT = 12
    ATTACK = 13
    END = 14
    SKILL = 15
    SPECIAL_CONDITION = 16


class LogType(IntEnum):
    """Game log event types."""

    SHUFFLE = 0
    HAS_BASIC_POKEMON = 1
    TURN_START = 2
    TURN_END = 3
    DRAW = 4
    DRAW_REVERSE = 5
    MOVE_CARD = 6
    MOVE_CARD_REVERSE = 7
    SWITCH = 8
    CHANGE = 9
    PLAY = 10
    ATTACH = 11
    EVOLVE = 12
    DEVOLVE = 13
    MOVE_ATTACHED = 14
    ATTACK = 15
    HP_CHANGE = 16
    POISONED = 17
    BURNED = 18
    ASLEEP = 19
    PARALYZED = 20
    CONFUSED = 21
    COIN = 22
    RESULT = 23


# ---------------------------------------------------------------------------
# Data classes
#
# Field order mirrors the official documentation.  Every field has a default
# so that older/newer engine payloads (which occasionally omit optional keys)
# can still be converted without raising.  Dataclasses are intentionally not
# slotted: unknown engine keys are attached as extra attributes by the
# converter below, which keeps agents forward-compatible.
# ---------------------------------------------------------------------------


@dataclass
class Card:
    """A card instance: card id, unique serial and owning player."""

    id: int = 0
    serial: int = 0
    playerIndex: int = 0


@dataclass
class Pokemon:
    """In-play Pokémon state."""

    id: int = 0
    serial: int = 0
    hp: int = 0
    maxHp: int = 0
    appearThisTurn: bool = False
    energies: list[Any] = field(default_factory=list)
    energyCards: list[Card] = field(default_factory=list)
    tools: list[Card] = field(default_factory=list)
    preEvolution: list[Card] = field(default_factory=list)


@dataclass
class PlayerState:
    """One player's visible board / hidden-zone counts."""

    active: list[Any] = field(default_factory=list)
    bench: list[Pokemon] = field(default_factory=list)
    benchMax: int = 0
    deckCount: int = 0
    discard: list[Card] = field(default_factory=list)
    prize: list[Any] = field(default_factory=list)
    handCount: int = 0
    hand: list[Any] | None = None
    poisoned: bool = False
    burned: bool = False
    asleep: bool = False
    paralyzed: bool = False
    confused: bool = False


@dataclass
class State:
    """Full game state."""

    turn: int = 0
    turnActionCount: int = 0
    yourIndex: int = 0
    firstPlayer: int = -1
    supporterPlayed: bool = False
    stadiumPlayed: bool = False
    energyAttached: bool = False
    retreated: bool = False
    result: int = -1
    stadium: list[Card] = field(default_factory=list)
    looking: list[Any] | None = None
    players: list[PlayerState] = field(default_factory=list)


@dataclass
class Option:
    """One selectable option."""

    type: Any = OptionType.END
    number: int | None = None
    area: Any = None
    index: int | None = None
    playerIndex: int | None = None
    toolIndex: int | None = None
    energyIndex: int | None = None
    count: int | None = None
    inPlayArea: Any = None
    inPlayIndex: int | None = None
    attackId: int | None = None
    cardId: int | None = None
    serial: int | None = None
    specialConditionType: Any = None


@dataclass
class SelectData:
    """The pending selection."""

    type: Any = SelectType.MAIN
    context: Any = SelectContext.MAIN
    minCount: int = 0
    maxCount: int = 1
    remainDamageCounter: int = 0
    remainEnergyCost: int = 0
    option: list[Option] = field(default_factory=list)
    deck: list[Card] | None = None
    contextCard: Card | None = None
    effect: Card | None = None


@dataclass
class Log:
    """A game event."""

    type: Any = LogType.TURN_START
    playerIndex: int | None = None
    hasBasicPokemon: bool | None = None
    cardId: int | None = None
    serial: int | None = None
    fromArea: Any = None
    toArea: Any = None
    cardIdActive: int | None = None
    serialActive: int | None = None
    cardIdBench: int | None = None
    serialBench: int | None = None
    cardIdBefore: int | None = None
    serialBefore: int | None = None
    cardIdAfter: int | None = None
    serialAfter: int | None = None
    cardIdTarget: int | None = None
    serialTarget: int | None = None
    attackId: int | None = None
    value: int | None = None
    putDamageCounter: bool | None = None
    isRecover: bool | None = None
    head: bool | None = None
    result: int | None = None
    reason: int | None = None


@dataclass
class Observation:
    """State plus pending choices handed to an agent."""

    select: SelectData | None = None
    logs: list[Log] = field(default_factory=list)
    current: State | None = None
    search_begin_input: str | None = None


@dataclass
class SearchState:
    """A node in the engine's forward-search tree."""

    observation: Observation | None = None
    searchId: int = -1


@dataclass
class ApiResult:
    """Result wrapper used by the native search calls."""

    state: SearchState | None = None
    error: int = 0


@dataclass
class Skill:
    name: str = ""
    text: str = ""


@dataclass
class CardData:
    """Static card metadata (``all_card_data()``)."""

    cardId: int = 0
    name: str = ""
    cardType: Any = None
    retreatCost: int = 0
    hp: int = 0
    weakness: Any = None
    resistance: Any = None
    energyType: Any = None
    basic: bool = False
    stage1: bool = False
    stage2: bool = False
    ex: bool = False
    megaEx: bool = False
    tera: bool = False
    aceSpec: bool = False
    evolvesFrom: str | None = None
    skills: list[Skill] = field(default_factory=list)
    attacks: list[int] = field(default_factory=list)


@dataclass
class Attack:
    """Static attack metadata (``all_attack()``)."""

    attackId: int = 0
    name: str = ""
    text: str = ""
    damage: int = 0
    energies: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# dict -> data class conversion
# ---------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _enum(cls: type[IntEnum], value: Any) -> Any:
    if value is None or isinstance(value, cls):
        return value
    try:
        return cls(value)
    except (TypeError, ValueError):
        return value


def _enum_list(cls: type[IntEnum], values: Any) -> list[Any]:
    if not values:
        return []
    return [_enum(cls, value) for value in values]


def _extras(obj: Any, data: dict, known: set[str]) -> Any:
    """Attach engine keys that are newer than this SDK revision."""
    for key, value in data.items():
        if key not in known:
            setattr(obj, key, value)
    return obj


def _card(data: Any) -> Card | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    return Card(
        id=int(data.get("id", 0) or 0),
        serial=int(data.get("serial", 0) or 0),
        playerIndex=int(data.get("playerIndex", 0) or 0),
    )


def _pokemon(data: Any) -> Pokemon | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    obj = Pokemon(
        id=int(data.get("id", 0) or 0),
        serial=int(data.get("serial", 0) or 0),
        hp=int(data.get("hp", 0) or 0),
        maxHp=int(data.get("maxHp", 0) or 0),
        appearThisTurn=bool(data.get("appearThisTurn", False)),
        energies=_enum_list(EnergyType, data.get("energies")),
        energyCards=[_card(item) for item in data.get("energyCards") or []],
        tools=[_card(item) for item in data.get("tools") or []],
        preEvolution=[_card(item) for item in data.get("preEvolution") or []],
    )
    return _extras(
        obj,
        data,
        {
            "id", "serial", "hp", "maxHp", "appearThisTurn", "energies",
            "energyCards", "tools", "preEvolution",
        },
    )


def _player(data: Any) -> PlayerState | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    hand = data.get("hand")
    obj = PlayerState(
        active=[_pokemon(item) for item in data.get("active") or []],
        bench=[_pokemon(item) for item in data.get("bench") or []],
        benchMax=int(data.get("benchMax", 0) or 0),
        deckCount=int(data.get("deckCount", 0) or 0),
        discard=[_card(item) for item in data.get("discard") or []],
        prize=[_card(item) for item in data.get("prize") or []],
        handCount=int(data.get("handCount", 0) or 0),
        hand=None if hand is None else [_card(item) for item in hand],
        poisoned=bool(data.get("poisoned", False)),
        burned=bool(data.get("burned", False)),
        asleep=bool(data.get("asleep", False)),
        paralyzed=bool(data.get("paralyzed", False)),
        confused=bool(data.get("confused", False)),
    )
    return _extras(
        obj,
        data,
        {
            "active", "bench", "benchMax", "deckCount", "discard", "prize",
            "handCount", "hand", "poisoned", "burned", "asleep", "paralyzed",
            "confused",
        },
    )


def _state(data: Any) -> State | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    looking = data.get("looking")
    obj = State(
        turn=int(data.get("turn", 0) or 0),
        turnActionCount=int(data.get("turnActionCount", 0) or 0),
        yourIndex=int(data.get("yourIndex", 0) or 0),
        firstPlayer=int(data.get("firstPlayer", -1) if data.get("firstPlayer") is not None else -1),
        supporterPlayed=bool(data.get("supporterPlayed", False)),
        stadiumPlayed=bool(data.get("stadiumPlayed", False)),
        energyAttached=bool(data.get("energyAttached", False)),
        retreated=bool(data.get("retreated", False)),
        result=int(data.get("result", -1) if data.get("result") is not None else -1),
        stadium=[_card(item) for item in data.get("stadium") or []],
        looking=None if looking is None else [_card(item) for item in looking],
        players=[_player(item) for item in data.get("players") or []],
    )
    return _extras(
        obj,
        data,
        {
            "turn", "turnActionCount", "yourIndex", "firstPlayer",
            "supporterPlayed", "stadiumPlayed", "energyAttached", "retreated",
            "result", "stadium", "looking", "players",
        },
    )


def _option(data: Any) -> Option | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    obj = Option(
        type=_enum(OptionType, data.get("type")),
        number=data.get("number"),
        area=_enum(AreaType, data.get("area")),
        index=data.get("index"),
        playerIndex=data.get("playerIndex"),
        toolIndex=data.get("toolIndex"),
        energyIndex=data.get("energyIndex"),
        count=data.get("count"),
        inPlayArea=_enum(AreaType, data.get("inPlayArea")),
        inPlayIndex=data.get("inPlayIndex"),
        attackId=data.get("attackId"),
        cardId=data.get("cardId"),
        serial=data.get("serial"),
        specialConditionType=_enum(SpecialConditionType, data.get("specialConditionType")),
    )
    return _extras(
        obj,
        data,
        {
            "type", "number", "area", "index", "playerIndex", "toolIndex",
            "energyIndex", "count", "inPlayArea", "inPlayIndex", "attackId",
            "cardId", "serial", "specialConditionType",
        },
    )


def _select(data: Any) -> SelectData | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    deck = data.get("deck")
    obj = SelectData(
        type=_enum(SelectType, data.get("type")),
        context=_enum(SelectContext, data.get("context")),
        minCount=int(data.get("minCount", 0) or 0),
        maxCount=int(data.get("maxCount", 0) or 0),
        remainDamageCounter=int(data.get("remainDamageCounter", 0) or 0),
        remainEnergyCost=int(data.get("remainEnergyCost", 0) or 0),
        option=[_option(item) for item in data.get("option") or []],
        deck=None if deck is None else [_card(item) for item in deck],
        contextCard=_card(data.get("contextCard")),
        effect=_card(data.get("effect")),
    )
    return _extras(
        obj,
        data,
        {
            "type", "context", "minCount", "maxCount", "remainDamageCounter",
            "remainEnergyCost", "option", "deck", "contextCard", "effect",
        },
    )


def _log(data: Any) -> Log | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    obj = Log(type=_enum(LogType, data.get("type")))
    for key, value in data.items():
        if key == "type":
            continue
        if key in ("fromArea", "toArea"):
            value = _enum(AreaType, value)
        setattr(obj, key, value)
    return obj


def _observation(data: Any) -> Observation | None:
    if data is None:
        return None
    if isinstance(data, Observation):
        return data
    if not isinstance(data, dict):
        return data
    return Observation(
        select=_select(data.get("select")),
        logs=[_log(item) for item in data.get("logs") or []],
        current=_state(data.get("current")),
        search_begin_input=data.get("search_begin_input"),
    )


def to_observation_class(obs: dict[str, Any] | Observation | None) -> Observation | None:
    """Convert a raw observation dict into the attribute-access form.

    Example::

        obs = to_observation_class(raw)
        obs.select.option[0].type
        obs.current.players[0].active[0].hp
        obs.search_begin_input
    """
    return _observation(obs)


def _search_state_from_dict(data: dict[str, Any]) -> SearchState:
    observation = data.get("observation")
    return SearchState(
        observation=_observation(observation),
        searchId=int(data.get("searchId", -1)),
    )


# ---------------------------------------------------------------------------
# Card metadata
# ---------------------------------------------------------------------------

_CARD_CACHE: list[CardData] | None = None
_ATTACK_CACHE: list[Attack] | None = None


def _lib():
    """Return the shared engine CDLL and install the extra symbol prototypes."""
    from .sim import lib

    _install_bindings(lib)
    return lib


def _install_bindings(lib) -> None:
    if getattr(lib, "_cg_api_bound", False):
        return
    lib.AllCard.restype = ctypes.c_char_p
    lib.AllCard.argtypes = []
    lib.AllAttack.restype = ctypes.c_char_p
    lib.AllAttack.argtypes = []

    lib.AgentStart.restype = ctypes.c_void_p
    lib.AgentStart.argtypes = []
    lib.SearchBegin.restype = ctypes.c_char_p
    lib.SearchBegin.argtypes = [
        ctypes.c_void_p,          # agent (from AgentStart)
        ctypes.c_char_p,          # search_begin_input (base64 ASCII)
        ctypes.c_int,             # input length
        ctypes.POINTER(ctypes.c_int),  # your_deck
        ctypes.POINTER(ctypes.c_int),  # your_prize
        ctypes.POINTER(ctypes.c_int),  # opponent_deck
        ctypes.POINTER(ctypes.c_int),  # opponent_prize
        ctypes.POINTER(ctypes.c_int),  # opponent_hand
        ctypes.POINTER(ctypes.c_int),  # opponent_active
        ctypes.c_int,             # manual_coin
    ]
    lib.SearchStep.restype = ctypes.c_char_p
    lib.SearchStep.argtypes = [
        ctypes.c_void_p,          # agent
        ctypes.c_int,             # search id
        ctypes.POINTER(ctypes.c_int),  # picks
        ctypes.c_int,             # number of picks
    ]
    lib.SearchEnd.restype = None
    lib.SearchEnd.argtypes = [ctypes.c_void_p]
    lib.SearchRelease.restype = None
    lib.SearchRelease.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib._cg_api_bound = True


def all_card_data() -> list[CardData]:
    """Return all card metadata from the engine as ``CardData`` objects."""
    global _CARD_CACHE
    if _CARD_CACHE is None:
        raw = _lib().AllCard()
        cards = json.loads(raw.decode("utf-8")) if raw else []
        out: list[CardData] = []
        for data in cards:
            obj = CardData(
                cardId=int(data.get("cardId", 0) or 0),
                name=data.get("name", ""),
                cardType=_enum(CardType, data.get("cardType")),
                retreatCost=int(data.get("retreatCost", 0) or 0),
                hp=int(data.get("hp", 0) or 0),
                weakness=_enum(EnergyType, data.get("weakness")),
                resistance=_enum(EnergyType, data.get("resistance")),
                energyType=_enum(EnergyType, data.get("energyType")),
                basic=bool(data.get("basic", False)),
                stage1=bool(data.get("stage1", False)),
                stage2=bool(data.get("stage2", False)),
                ex=bool(data.get("ex", False)),
                megaEx=bool(data.get("megaEx", False)),
                tera=bool(data.get("tera", False)),
                aceSpec=bool(data.get("aceSpec", False)),
                evolvesFrom=data.get("evolvesFrom"),
                skills=[
                    Skill(name=skill.get("name", ""), text=skill.get("text", ""))
                    for skill in data.get("skills") or []
                ],
                attacks=[int(item) for item in data.get("attacks") or []],
            )
            _extras(
                obj,
                data,
                {
                    "cardId", "name", "cardType", "retreatCost", "hp",
                    "weakness", "resistance", "energyType", "basic", "stage1",
                    "stage2", "ex", "megaEx", "tera", "aceSpec",
                    "evolvesFrom", "skills", "attacks",
                },
            )
            out.append(obj)
        _CARD_CACHE = out
    return list(_CARD_CACHE)


def all_attack() -> list[Attack]:
    """Return all attack metadata from the engine as ``Attack`` objects."""
    global _ATTACK_CACHE
    if _ATTACK_CACHE is None:
        raw = _lib().AllAttack()
        attacks = json.loads(raw.decode("utf-8")) if raw else []
        out: list[Attack] = []
        for data in attacks:
            obj = Attack(
                attackId=int(data.get("attackId", 0) or 0),
                name=data.get("name", ""),
                text=data.get("text", ""),
                damage=int(data.get("damage", 0) or 0),
                energies=_enum_list(EnergyType, data.get("energies")),
            )
            _extras(obj, data, {"attackId", "name", "text", "damage", "energies"})
            out.append(obj)
        _ATTACK_CACHE = out
    return list(_ATTACK_CACHE)


# ---------------------------------------------------------------------------
# Forward search
# ---------------------------------------------------------------------------

# The native engine is process-global; serialize calls so a threaded agent
# cannot interleave two searches on the same object.
_SEARCH_LOCK = threading.RLock()
_AGENT_PTR: int | None = None

# Arrays are padded so that a wrong belief length can never make the engine
# read past the end of a ctypes buffer.  The engine reads exactly the count
# stored in its own state; the padding is never used unless our count
# derivation is wrong.
_ARRAY_PAD = 80

_FALLBACK_CARD_ID: int | None = None
_BASIC_IDS: set[int] | None = None


def _fallback_card_id() -> int:
    global _FALLBACK_CARD_ID
    if _FALLBACK_CARD_ID is None:
        for data in all_card_data():
            if data.basic:
                _FALLBACK_CARD_ID = int(data.cardId)
                break
        else:
            cards = all_card_data()
            _FALLBACK_CARD_ID = int(cards[0].cardId) if cards else 1
    return _FALLBACK_CARD_ID


def _basic_ids() -> set[int]:
    global _BASIC_IDS
    if _BASIC_IDS is None:
        _BASIC_IDS = {int(data.cardId) for data in all_card_data() if data.basic}
    return _BASIC_IDS


def _basic_or_fallback(deck: list[int]) -> int:
    basics = _basic_ids()
    for cid in deck:
        try:
            if int(cid) in basics:
                return int(cid)
        except (TypeError, ValueError):
            continue
    return _fallback_card_id()


def _int_sequence(values: Any) -> list[int]:
    if values is None:
        return []
    if isinstance(values, (int,)):
        return [int(values)]
    try:
        return [int(value) for value in values]
    except TypeError:
        return [int(values)]


def _fit(values: Any, minimum: int, fallback: int) -> list[int]:
    """Return an int list at least ``max(minimum, _ARRAY_PAD)`` long."""
    out = _int_sequence(values)
    target = max(len(out), int(minimum), _ARRAY_PAD)
    if len(out) < target:
        out.extend([int(fallback)] * (target - len(out)))
    return out


def _c_ints(values: list[int]):
    array = (ctypes.c_int * max(1, len(values)))()
    for index, value in enumerate(values):
        array[index] = int(value)
    return array


def _agent() -> int:
    global _AGENT_PTR
    if _AGENT_PTR is None:
        lib = _lib()
        pointer = lib.AgentStart()
        if not pointer:
            raise RuntimeError("cabt: AgentStart() returned NULL")
        _AGENT_PTR = int(pointer)
    return _AGENT_PTR


def _parse_result(raw: bytes | None) -> SearchState:
    if not raw:
        raise RuntimeError("cabt search: engine returned NULL")
    data = json.loads(raw.decode("utf-8"))
    error = int(data.get("error", 0) or 0)
    if error:
        messages = {
            1: "invalid search id",
            2: "invalid selection",
            3: "search state is already finished",
            5: "illegal selection for this search node",
            30: "search API not initialised (AgentStart was not used)",
        }
        raise RuntimeError(
            f"cabt search error {error}: {messages.get(error, 'unknown error')}"
        )
    state = data.get("state")
    if not isinstance(state, dict):
        raise RuntimeError("cabt search: engine returned no state")
    return _search_state_from_dict(state)


def _observation_parts(agent_observation: Any) -> tuple[Any, int, int, int, int, int, int]:
    """Extract the encoded state and hidden-zone counts from an observation."""
    obs = agent_observation
    current = _get(obs, "current")
    if current is None:
        raise ValueError("search_begin: observation has no current state")
    players = _get(current, "players") or []
    if len(players) != 2:
        raise ValueError("search_begin: observation.current.players must have 2 players")
    your_index = int(_get(current, "yourIndex", 0) or 0)
    if your_index not in (0, 1):
        raise ValueError(f"search_begin: invalid yourIndex {your_index}")
    me = players[your_index]
    opponent = players[1 - your_index]

    me_deck_count = int(_get(me, "deckCount", 0) or 0)
    me_prize = _get(me, "prize") or []
    opp_deck_count = int(_get(opponent, "deckCount", 0) or 0)
    opp_prize = _get(opponent, "prize") or []
    opp_hand_count = int(_get(opponent, "handCount", 0) or 0)
    opp_active = _get(opponent, "active") or []
    opp_active_needed = len(opp_active) > 0 and opp_active[0] is None

    # If the engine already knows our deck (a "search your deck" effect, when
    # select.deck is not None), SearchBegin ignores the your_deck argument.
    # We still pass a padded array so the pointer is always valid.

    return (
        _get(obs, "search_begin_input"),
        me_deck_count,
        len(me_prize) if me_prize else 6,
        opp_deck_count,
        len(opp_prize) if opp_prize else 6,
        opp_hand_count,
        1 if opp_active_needed else 0,
    )


def search_begin(
    agent_observation: Observation | dict[str, Any],
    your_deck: list[int],
    your_prize: list[int],
    opponent_deck: list[int],
    opponent_prize: list[int],
    opponent_hand: list[int],
    opponent_active: list[int] | None = None,
    manual_coin: bool = False,
) -> SearchState:
    """Create a determinized forward-search root from an observation.

    The argument order and meaning follow the official documentation.  Hidden
    zones are supplied as beliefs; the engine fills the unknown cards and
    returns a fully observable search state.
    """
    (
        encoded,
        me_deck_count,
        me_prize_count,
        opp_deck_count,
        opp_prize_count,
        opp_hand_count,
        opp_active_needed,
    ) = _observation_parts(agent_observation)

    if isinstance(encoded, bytes):
        payload = encoded
    elif isinstance(encoded, str) and encoded:
        payload = encoded.encode("ascii")
    else:
        raise ValueError(
            "search_begin: observation.search_begin_input is missing; "
            "the observation must come from a live battle or search node"
        )

    deck_fallback = _fallback_card_id()
    your_deck_values = _int_sequence(your_deck)
    your_deck_fallback = your_deck_values[-1] if your_deck_values else deck_fallback
    opp_deck_values = _int_sequence(opponent_deck)
    opp_fallback = opp_deck_values[-1] if opp_deck_values else deck_fallback
    opp_active_fallback = _basic_or_fallback(opp_deck_values)

    arrays = (
        _c_ints(_fit(your_deck_values, me_deck_count, your_deck_fallback)),
        _c_ints(_fit(your_prize, me_prize_count, your_deck_fallback)),
        _c_ints(_fit(opp_deck_values, opp_deck_count, opp_fallback)),
        _c_ints(_fit(opponent_prize, opp_prize_count, opp_fallback)),
        _c_ints(_fit(opponent_hand, opp_hand_count, opp_fallback)),
        _c_ints(_fit(opponent_active, 1 if opp_active_needed else 0, opp_active_fallback)),
    )

    with _SEARCH_LOCK:
        raw = _lib().SearchBegin(
            _agent(),
            payload,
            len(payload),
            arrays[0],
            arrays[1],
            arrays[2],
            arrays[3],
            arrays[4],
            arrays[5],
            1 if manual_coin else 0,
        )
    return _parse_result(raw)


def search_step(
    search_id: int | None = None,
    pick: list[int] | tuple[int, ...] | int | None = None,
    *,
    select: list[int] | tuple[int, ...] | int | None = None,
    searchId: int | None = None,
) -> SearchState:
    """Advance one node of the search tree by choosing option indices.

    Both the task's ``pick`` and the official docs' ``select`` keyword are
    accepted, as is ``searchId`` for callers that mirror the JSON field name.
    """
    if search_id is None:
        search_id = searchId
    if search_id is None:
        raise TypeError("search_step() missing required argument: 'search_id'")
    if pick is None:
        pick = select
    if pick is None:
        raise TypeError("search_step() missing required argument: 'pick'")
    picks = _int_sequence(pick)
    with _SEARCH_LOCK:
        raw = _lib().SearchStep(_agent(), int(search_id), _c_ints(picks), len(picks))
    return _parse_result(raw)


def search_end() -> None:
    """Terminate the current search and recycle its node memory."""
    with _SEARCH_LOCK:
        if _AGENT_PTR is not None:
            _lib().SearchEnd(_AGENT_PTR)


def search_release(search_id: int | None = None, *, searchId: int | None = None) -> None:
    """Release one search node so its memory can be reused."""
    if search_id is None:
        search_id = searchId
    if search_id is None:
        raise TypeError("search_release() missing required argument: 'search_id'")
    with _SEARCH_LOCK:
        if _AGENT_PTR is not None:
            _lib().SearchRelease(_AGENT_PTR, int(search_id))


__all__ = [
    "AreaType",
    "EnergyType",
    "CardType",
    "SpecialConditionType",
    "SelectType",
    "SelectContext",
    "OptionType",
    "LogType",
    "Card",
    "Pokemon",
    "PlayerState",
    "State",
    "Option",
    "SelectData",
    "Log",
    "Observation",
    "SearchState",
    "ApiResult",
    "Skill",
    "CardData",
    "Attack",
    "all_card_data",
    "all_attack",
    "to_observation_class",
    "search_begin",
    "search_step",
    "search_end",
    "search_release",
]
