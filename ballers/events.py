"""Events emitted by a match. Renderers, sound, and stats subscribe to these
instead of the simulation knowing about them."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from pygame.math import Vector2

if TYPE_CHECKING:
    from .ability import Ability
    from .entity import DamageType, Entity
    from .fighter import Fighter
    from .status import Status


class Event:
    pass


@dataclass
class EntitySpawned(Event):
    entity: Entity


@dataclass
class EntityRemoved(Event):
    entity: Entity


@dataclass
class WallHit(Event):
    entity: Entity
    point: Vector2
    normal: Vector2


@dataclass
class Contact(Event):
    a: Entity
    b: Entity


@dataclass
class Damage(Event):
    source: Entity | None
    target: Entity
    amount: float
    damage_type: DamageType
    point: Vector2
    continuous: bool = False   # one step of damage over time


@dataclass
class StatusApplied(Event):
    entity: Entity
    status: Status


@dataclass
class AbilityUsed(Event):
    caster: Entity
    text: str
    ability: Ability | None = None


@dataclass
class FighterDefeated(Event):
    fighter: Fighter


@dataclass
class MatchOver(Event):
    winner: Fighter | None   # None means draw
    reason: str              # "knockout" or "timeout"


class EventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: Callable[[Event], None]):
        self._handlers[event_type].append(handler)

    def emit(self, event: Event):
        for event_type, handlers in self._handlers.items():
            if isinstance(event, event_type):
                for handler in handlers:
                    handler(event)
