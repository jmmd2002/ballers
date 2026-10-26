"""Entity: anything that exists in the arena (fighters, clones, projectiles,
hitboxes). Ball: a solid, bouncing, circular entity."""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pygame
from pygame.math import Vector2

from . import gfx
from .events import StatusApplied

if TYPE_CHECKING:
    from .match import Match
    from .status import Status


class DamageType(Enum):
    PHYSICAL = "physical"
    FIRE = "fire"
    CHAKRA = "chakra"
    SLASHING = "slashing"


class Entity:
    name = "Entity"
    color = (200, 200, 200)
    max_hp = 1
    damage = 0                        # dealt to enemies on contact
    damage_type = DamageType.PHYSICAL
    resistances: frozenset[DamageType] = frozenset()   # half damage
    weaknesses: frozenset[DamageType] = frozenset()    # double damage
    immunities: frozenset[DamageType] = frozenset()    # no damage
    tags: frozenset[str] = frozenset()  # free-form labels abilities can query ("clone", ...)

    shape = "circle"                  # "circle" or "cone"
    radius = 10
    solid = False                     # solid entities bounce; others only overlap
    is_fighter = False
    dies_on_hit = False               # destroyed after it hits an enemy
    hit_cooldown = 0.3                # min seconds between hits on the same target
    lifetime: float | None = None     # seconds until it disappears on its own
    layer = 0                         # draw order, higher on top
    death_effect: str | None = None   # visual effect name played on removal
    death_shake = 0.0                 # screen shake when removed (visual only)
    spawn_sound: str | None = None    # sound keys, see ballers/audio.py
    death_sound: str | None = None
    hit_sound: str | None = None      # played when this entity damages something

    def __init__(self, pos: Vector2, team: int, owner: Entity | None = None):
        self.pos = Vector2(pos)
        self.vel = Vector2()
        self.hp = float(self.max_hp)
        self.team = team
        self.owner = owner
        self.age = 0.0
        self.statuses: list[Status] = []
        self.removed = False

    @property
    def alive(self) -> bool:
        return not self.removed and self.hp > 0

    @property
    def is_immobile(self) -> bool:
        return any(s.immobile for s in self.statuses)

    @property
    def can_cast(self) -> bool:
        return not any(s.blocks_casting for s in self.statuses)

    @property
    def speed_mult(self) -> float:
        mult = 1.0
        for s in self.statuses:
            mult *= s.speed_mult
        return mult

    def destroy(self):
        self.removed = True

    # --- Status conditions (ballers/status.py) --------------------------------

    def add_status(self, match: Match, status: Status) -> Status:
        self.statuses.append(status)
        status.on_apply(self, match)
        match.bus.emit(StatusApplied(self, status))
        return status

    def remove_status(self, match: Match, status: Status):
        if status in self.statuses:
            self.statuses.remove(status)
            status.on_expire(self, match)

    def get_status(self, cls: type[Status]) -> Status | None:
        return next((s for s in self.statuses if isinstance(s, cls) and not s.done), None)

    def has_status(self, cls: type[Status]) -> bool:
        return self.get_status(cls) is not None

    def damage_multiplier(self, damage_type: DamageType) -> float:
        if damage_type in self.immunities:
            return 0.0
        mult = 1.0
        if damage_type in self.resistances:
            mult *= 0.5
        if damage_type in self.weaknesses:
            mult *= 2.0
        return mult

    def tick(self, match: Match, dt: float):
        """Called by the match every step; subclasses override on_update instead."""
        self.age += dt
        for status in list(self.statuses):
            status.tick(self, match, dt)
            if status.done:
                self.remove_status(match, status)
        if self.lifetime is not None and self.age >= self.lifetime:
            self.destroy()
            return
        self.on_update(match, dt)

    # --- Hooks: override in subclasses --------------------------------------

    def on_spawn(self, match: Match):
        pass

    def on_update(self, match: Match, dt: float):
        pass

    def on_wall_hit(self, match: Match, normal: Vector2):
        pass

    def on_contact(self, match: Match, other: Entity):
        """Any new contact, including allies."""

    def can_damage(self, match: Match, target: Entity) -> bool:
        """Veto contact damage against a specific target (checked before hit_cooldown)."""
        return True

    def on_hit(self, match: Match, target: Entity, dealt: float):
        """After this entity's contact damage was applied to an enemy."""

    def on_take_damage(self, match: Match, amount: float, damage_type: DamageType,
                       source: Entity | None):
        pass

    def on_death(self, match: Match):
        pass

    # --- Visuals -------------------------------------------------------------

    def screen_pos(self, origin: Vector2) -> Vector2:
        return origin + self.pos

    def draw(self, surface: pygame.Surface, origin: Vector2):
        pygame.draw.circle(surface, self.color, self.screen_pos(origin), self.radius)

    def __repr__(self):
        return f"<{type(self).__name__} team={self.team} hp={self.hp:.0f}>"


class Ball(Entity):
    """Solid circle moving at constant speed and bouncing off walls and other balls."""
    radius = 30
    speed = 320
    mass = 1.0
    solid = True

    def __init__(self, pos, team, direction: Vector2 | None = None, owner=None):
        super().__init__(pos, team, owner)
        self.vel = Vector2(direction or (1, 0))
        self.vel.scale_to_length(self.speed)

    @property
    def inv_mass(self) -> float:
        return 0.0 if self.is_immobile else 1.0 / self.mass

    @property
    def direction(self) -> Vector2:
        return self.vel.normalize() if self.vel.length_squared() > 1e-9 else Vector2(1, 0)

    @property
    def current_speed(self) -> float:
        return self.speed * self.speed_mult

    def keep_speed(self):
        if not self.is_immobile and self.vel.length_squared() > 1e-9:
            self.vel.scale_to_length(self.current_speed)

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        pygame.draw.circle(surface, self.color, center, self.radius)
        pygame.draw.circle(surface, gfx.darken(self.color, 0.45), center, self.radius, width=3)
