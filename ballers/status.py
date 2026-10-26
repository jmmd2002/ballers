"""Status conditions attached to entities (any Entity, so balls and fighters too).

A status can block movement or casting, scale speed, run logic every step
(damage over time, steering), show a HUD label and draw itself over its
entity. Add one with entity.add_status(match, status); it is removed when its
duration runs out or when it calls end()."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .entity import DamageType

if TYPE_CHECKING:
    import pygame
    from pygame.math import Vector2

    from .entity import Entity
    from .match import Match


class Status:
    name = "Status"
    label: str | None = None   # shown on the fighter's HUD status line while active
    immobile = False           # entity stops moving and can't be pushed
    blocks_casting = False     # abilities won't trigger
    speed_mult = 1.0           # scales a ball's constant speed
    sound: str | None = None   # sfx key played when applied

    def __init__(self, duration: float | None = None, source: Entity | None = None):
        self.remaining = duration   # None lasts until end() is called
        self.source = source        # whoever applied it, if anyone
        self.age = 0.0
        self.ended = False

    @property
    def done(self) -> bool:
        return self.ended or (self.remaining is not None and self.remaining <= 0)

    def end(self):
        """Remove this status at the entity's next step."""
        self.ended = True

    def tick(self, entity: Entity, match: Match, dt: float):
        self.age += dt
        if self.remaining is not None:
            self.remaining -= dt
        if not self.done:
            self.on_update(entity, match, dt)

    # --- Override in subclasses ---------------------------------------------

    def on_apply(self, entity: Entity, match: Match):
        pass

    def on_update(self, entity: Entity, match: Match, dt: float):
        pass

    def on_expire(self, entity: Entity, match: Match):
        """Called whenever the status is removed (timed out, ended, or removed)."""

    def draw(self, surface: pygame.Surface, entity: Entity, origin: Vector2):
        """Drawn right after the entity itself."""


class Channeling(Status):
    """Standing still while performing a technique."""
    name = "Channeling"
    immobile = True
    blocks_casting = True


class Stunned(Status):
    name = "Stunned"
    label = "Stunned"
    immobile = True
    blocks_casting = True


class DamageOverTime(Status):
    """Deals `dps` damage per second, spread over every step. With an `interval`,
    the damage builds up instead and lands as one hit every `interval` seconds;
    whatever hasn't landed yet is lost if the status ends early. Ends early if
    its source is gone."""
    name = "Damage over time"
    dps = 10.0
    damage_type = DamageType.PHYSICAL
    interval: float | None = None

    def __init__(self, duration=None, source=None, dps: float | None = None,
                 damage_type: DamageType | None = None, interval: float | None = None):
        super().__init__(duration, source)
        if dps is not None:
            self.dps = dps
        if damage_type is not None:
            self.damage_type = damage_type
        if interval is not None:
            self.interval = interval
        self.last_proc = 0.0   # age of the last hit

    def _source_gone(self) -> bool:
        return self.source is not None and not self.source.alive

    def _proc(self, entity, match):
        """Land every full interval of built-up damage."""
        procs = int((self.age - self.last_proc) / self.interval + 1e-6)
        if procs:
            self.last_proc += procs * self.interval
            match.deal_damage(self.source, entity, self.dps * self.interval * procs, self.damage_type)

    def on_update(self, entity, match, dt):
        if self._source_gone():
            self.end()
            return
        if self.interval is None:
            match.deal_damage(self.source, entity, self.dps * dt, self.damage_type, continuous=True)
        else:
            self._proc(entity, match)

    def on_expire(self, entity, match):
        # A duration that's a whole number of intervals still lands its last hit.
        if self.interval is not None and not self.ended and not self._source_gone():
            self._proc(entity, match)


class Grasped(DamageOverTime):
    """Held in something's grip: can't move or cast and is slowly crushed."""
    name = "Grasped"
    label = "Grabbed!"
    sound = "grab"
    immobile = True
    blocks_casting = True


class Slowed(Status):
    name = "Slowed"
    label = "Slowed"
    speed_mult = 0.6
