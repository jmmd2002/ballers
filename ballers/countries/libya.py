import math
import random

import pygame
from pygame.math import Vector2

from .. import gfx
from ..ability import Ability
from ..entity import Ball, Entity
from ..fighter import Fighter
from ..registry import register
from ..status import Slowed
from ._countryball import Countryball

GREEN = (35, 158, 70)
SAND = (214, 170, 100)
STONE = (222, 205, 170)

# Sand grains swirling in the storm: (angle, distance factor, spin speed, size).
_grains_rng = random.Random(7)
GRAINS = [(_grains_rng.uniform(0, 360), _grains_rng.uniform(0.15, 1.0),
           _grains_rng.uniform(90, 220), _grains_rng.uniform(1.2, 2.6)) for _ in range(46)]


class Sandstorm(Entity):
    """Ghibli wind swirling around Libya. Slows and grinds down enemy balls inside.
    Its shape is not a collision shape, so it never touches anything (no contact
    rule); it applies its effects itself."""
    name = "Ghibli Sandstorm"
    shape = "area"
    color = SAND
    radius = 110
    max_hp = 1
    lifetime = 4.0
    layer = -1
    spawn_sound = "sandstorm"
    tags = frozenset({"storm"})
    dps = 28.0
    slow_linger = 0.25   # the slow wears off this long after leaving the storm
    fade_time = 0.4

    def __init__(self, owner: Ball):
        super().__init__(owner.pos, owner.team, owner)
        self.dispelled = False

    def disperse(self):
        """Blown away (Duduk Song): stop working and fade out quickly."""
        if not self.dispelled:
            self.dispelled = True
            self.lifetime = min(self.lifetime, self.age + self.fade_time)

    def on_update(self, match, dt):
        self.pos = Vector2(self.owner.pos)
        if self.dispelled:
            return
        for e in match.enemies_of(self, Ball):
            if "projectile" in e.tags or e.pos.distance_to(self.pos) >= self.radius:
                continue
            slow = e.get_status(Slowed)
            if slow and slow.source is self:
                slow.remaining = self.slow_linger
            else:
                e.add_status(match, Slowed(self.slow_linger, source=self))
            match.deal_damage(self, e, self.dps * dt, continuous=True)

    def draw(self, surface, origin):
        fade = min(self.age / self.fade_time, (self.lifetime - self.age) / self.fade_time, 1.0)
        if fade <= 0:
            return
        r = self.radius
        size = int(r * 2 + 8)
        mid = Vector2(size / 2, size / 2)
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (*SAND, int(60 * fade)), mid, r)
        rect = pygame.Rect(0, 0, 0, 0)
        for k, (ring, width) in enumerate(((0.95, 3), (0.7, 3), (0.45, 2))):
            rect.size = (r * 2 * ring, r * 2 * ring)
            rect.center = mid
            start = -self.age * (5 - k) + k * 2.1
            for half in (0, math.pi):
                pygame.draw.arc(overlay, (*gfx.lighten(SAND, 0.3), int(150 * fade)), rect,
                                start + half, start + half + 1.3, width)
        for angle, dist, spin, grain in GRAINS:
            a = math.radians(angle + self.age * spin)
            p = mid + Vector2(math.cos(a), math.sin(a)) * r * dist
            pygame.draw.circle(overlay, (*gfx.darken(SAND, 0.25), int(220 * fade)), p, grain)
        surface.blit(overlay, overlay.get_rect(center=self.screen_pos(origin)))


class Pillar(Ball):
    """Roman column of Leptis Magna: an immovable stone post that blocks balls
    and projectiles until it is knocked down."""
    name = "Pillar"
    color = STONE
    radius = 17
    speed = 0
    max_hp = 20
    lifetime = 8
    layer = 1
    death_effect = "crumble"
    spawn_sound = "pillar_rise"
    death_sound = "rock_break"

    @property
    def inv_mass(self):
        return 0.0

    def draw(self, surface, origin):
        c = self.screen_pos(origin)
        r = self.radius
        pygame.draw.circle(surface, gfx.darken(STONE, 0.35), c + Vector2(2, 3), r)   # shadow
        pygame.draw.circle(surface, STONE, c, r)
        for i in range(10):   # fluting seen from above
            d = Vector2(1, 0).rotate(i * 36)
            pygame.draw.line(surface, gfx.darken(STONE, 0.2), c + d * r * 0.55, c + d * r * 0.95, 2)
        pygame.draw.circle(surface, gfx.lighten(STONE, 0.4), c, r * 0.5)
        pygame.draw.circle(surface, gfx.darken(STONE, 0.4), c, r, width=2)
        damage = 1 - self.hp / self.max_hp
        if damage > 0.2:
            for k in range(1 + int(damage * 3)):
                d = Vector2(1, 0).rotate(40 + k * 110)
                pts = [c + d * r * 0.15, c + d.rotate(25) * r * 0.55, c + d * r * 0.95]
                pygame.draw.lines(surface, (70, 60, 50), False, pts, 2)


class GhibliSandstorm(Ability):
    name = "Ghibli Sandstorm"
    cooldown = 6
    initial_cooldown = 5
    trigger_range = 180

    def can_activate(self, match):
        return match.nearest_enemy(self.owner, Fighter, reach=self.trigger_range) is not None

    def cast(self, match):
        match.spawn(Sandstorm(self.owner))


class PillarsOfLeptisMagna(Ability):
    name = "Pillars of Leptis Magna"
    cooldown = 9
    initial_cooldown = 3
    distance = 80     # from Libya toward the enemy
    spread = 42       # sideways from that point
    min_range = 120   # only worth it when the enemy is not already on top of Libya

    def _target(self, match):
        enemy = match.nearest_enemy(self.owner, Fighter)
        if enemy and enemy.pos.distance_to(self.owner.pos) >= self.min_range:
            return enemy
        return None

    def can_activate(self, match):
        return self._target(match) is not None

    def cast(self, match):
        owner = self.owner
        aim = (self._target(match).pos - owner.pos).normalize()
        base = owner.pos + aim * self.distance
        side = Vector2(-aim.y, aim.x) * self.spread
        for offset in (side, -side):
            pos = match.clamp_to_arena(base + offset, Pillar.radius)
            match.spawn(Pillar(pos, owner.team, owner=owner))


@register
class Libya(Countryball):
    key = "libya"
    name = "Libya"
    description = "Ghibli Sandstorm slows and grinds nearby enemies. Raises Roman pillars as cover."
    color = GREEN
    ability_types = (GhibliSandstorm, PillarsOfLeptisMagna)

    def status(self, match):
        storms = [s for s in match.owned_by(self, Sandstorm) if not s.dispelled]
        return "Sandstorm" if storms else ""
