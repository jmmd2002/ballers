import math

import pygame
from pygame.math import Vector2

from .. import gfx, physics
from ..ability import Ability
from ..entity import Ball, DamageType, Entity
from ..fighter import Fighter
from ..registry import register
from ..status import Channeling, Stunned
from ._countryball import Countryball

ORANGE = (242, 168, 0)
POMEGRANATE = (180, 20, 45)
SEED = (230, 40, 70)
APRICOT = (255, 196, 110)


class Seed(Ball):
    name = "Pomegranate Seed"
    color = SEED
    radius = 5
    speed = 300
    mass = 0.1
    damage = 3
    dies_on_hit = True
    lifetime = 0.9
    layer = 1
    tags = frozenset({"projectile"})

    def draw(self, surface, origin):
        c = self.screen_pos(origin)
        pygame.draw.circle(surface, gfx.darken(SEED, 0.4), c, self.radius + 1)
        pygame.draw.circle(surface, SEED, c, self.radius)
        pygame.draw.circle(surface, gfx.lighten(SEED, 0.6), c + Vector2(-1.5, -1.5), 1.6)


class Pomegranate(Ball):
    """Thrown at the enemy; bursts into a fan of seeds on impact or when its fuse runs out."""
    name = "Pomegranate"
    color = POMEGRANATE
    radius = 13
    speed = 380
    mass = 0.5
    damage = 8
    dies_on_hit = True
    lifetime = 1.0
    layer = 1
    death_effect = "burst"
    death_sound = "splat"
    tags = frozenset({"projectile"})
    seed_count = 6

    def on_death(self, match):
        if not self.owner or not self.owner.alive:
            return
        base = match.rng.uniform(0, 360)
        for i in range(self.seed_count):
            d = Vector2(1, 0).rotate(base + i * 360 / self.seed_count)
            pos = match.clamp_to_arena(self.pos + d * 14, Seed.radius)
            match.spawn(Seed(pos, self.team, direction=d, owner=self.owner))

    def draw(self, surface, origin):
        c = self.screen_pos(origin)
        r = self.radius
        up = Vector2(0, -1).rotate(self.age * 400)   # tumbles while flying
        crown = [c + up * r * 0.8 + up.rotate(a) * r * f
                 for a, f in ((-60, 0.2), (-35, 0.55), (0, 0.3), (35, 0.55), (60, 0.2))]
        pygame.draw.circle(surface, gfx.darken(POMEGRANATE, 0.4), c, r + 1)
        pygame.draw.circle(surface, POMEGRANATE, c, r)
        pygame.draw.polygon(surface, gfx.darken(POMEGRANATE, 0.3), crown)
        pygame.draw.circle(surface, gfx.lighten(POMEGRANATE, 0.5), c + Vector2(-r * 0.35, -r * 0.35),
                           r * 0.22)


class DudukWave(Entity):
    """Sound of the duduk spreading in a cone: stuns the balls it reaches and
    blows enemy sandstorms away."""
    name = "Duduk Song"
    shape = "cone"
    color = APRICOT
    max_hp = 1
    damage = 6
    immunities = frozenset(DamageType)   # sound can't be hit back
    hit_cooldown = 999        # each target is hit once per song
    lifetime = 0.8
    layer = 2
    spawn_sound = "duduk"
    full_length = 210
    half_angle = 32           # degrees
    grow_time = 0.35
    stun_time = 1.0

    def __init__(self, owner: Ball, direction: Vector2):
        self.direction = Vector2(direction).normalize()
        super().__init__(owner.pos + self.direction * owner.radius * 0.8, owner.team, owner)

    @property
    def length(self) -> float:
        return self.full_length * min(self.age / self.grow_time, 1.0)

    def on_update(self, match, dt):
        for e in match.enemies_of(self):
            if "storm" in e.tags and physics.circle_in_cone(
                    e.pos, e.radius * 0.5, self.pos, self.direction, self.length, self.half_angle):
                e.disperse()

    def on_hit(self, match, target, dealt):
        if isinstance(target, Ball) and not target.has_status(Stunned):
            target.add_status(match, Stunned(self.stun_time, source=self))

    def draw(self, surface, origin):
        apex = self.screen_pos(origin)
        size = int(self.full_length * 2 + 8)
        mid = Vector2(size / 2, size / 2)
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        fade = min(1.0, (self.lifetime - self.age) / 0.25)
        spacing = 42
        for k in range(6):
            dist = (self.age * 300 + k * spacing) % (self.full_length + spacing)
            if dist < 8 or dist > self.length:
                continue
            alpha = int(230 * fade * (1 - 0.6 * dist / self.full_length))
            arc = [mid + self.direction.rotate(a) * dist
                   for a in range(-self.half_angle, self.half_angle + 1, 4)]
            pygame.draw.lines(overlay, (*APRICOT, alpha), False, arc, 5)
            pygame.draw.lines(overlay, (255, 245, 220, alpha), False, arc, 2)
        for k in range(3):   # notes drifting out with the sound
            dist = (self.age * 220 + k * 70) % self.full_length
            if dist > self.length:
                continue
            p = mid + self.direction.rotate(-18 + k * 18 + 6 * math.sin(self.age * 9 + k)) * dist
            color = (*APRICOT, int(255 * fade))
            pygame.draw.circle(overlay, color, p, 4)
            pygame.draw.line(overlay, color, p + Vector2(3, 0), p + Vector2(3, -12), 2)
            pygame.draw.line(overlay, color, p + Vector2(3, -12), p + Vector2(8, -8), 2)
        surface.blit(overlay, overlay.get_rect(center=apex))


class PomegranateBurst(Ability):
    name = "Pomegranate Burst"
    cooldown = 6
    initial_cooldown = 2.5
    sfx = "toss"

    def can_activate(self, match):
        return match.nearest_enemy(self.owner, Fighter) is not None

    def cast(self, match):
        owner = self.owner
        aim = match.nearest_enemy(owner, Fighter).pos - owner.pos
        direction = aim.normalize() if aim.length_squared() > 1e-9 else owner.direction
        pos = owner.pos + direction * (owner.radius + Pomegranate.radius + 2)
        match.spawn(Pomegranate(pos, owner.team, direction=direction, owner=owner))


class DudukSong(Ability):
    name = "Duduk Song"
    cooldown = 11
    initial_cooldown = 6
    channel_time = 0.7

    def _target(self, match):
        return match.nearest_enemy(self.owner, Fighter, reach=DudukWave.full_length)

    def can_activate(self, match):
        return self._target(match) is not None

    def cast(self, match):
        owner = self.owner
        aim = self._target(match).pos - owner.pos
        direction = aim.normalize() if aim.length_squared() > 1e-9 else owner.direction
        owner.vel = direction * owner.speed
        owner.add_status(match, Channeling(self.channel_time))
        match.spawn(DudukWave(owner, direction))


@register
class Armenia(Countryball):
    key = "armenia"
    name = "Armenia"
    description = "Throws pomegranates that burst into seeds. Duduk Song stuns and blows storms away."
    color = ORANGE
    ability_types = (PomegranateBurst, DudukSong)
