import math

import pygame
from pygame.math import Vector2

from ..ability import Ability
from ..entity import Ball, DamageType, Entity
from ..fighter import Fighter
from ..registry import register
from ..status import Channeling
from ._shinobi import draw_body, draw_hair, draw_sharingan, smooth_profile

NAVY = (55, 65, 150)
SKIN = (240, 222, 205)
HAIR = (34, 36, 62)
HAIR_SHINE = (95, 110, 190)
# Smooth hair with extra volume swept toward the back-right.
SASUKE_HAIR = smooth_profile(170, 370, lambda t: 1.04 + 0.16 * math.sin(math.pi * t) ** 2 * (0.6 + 0.4 * t))


def sasuke_hair(surface, center, radius):
    draw_hair(surface, center, radius, HAIR, SASUKE_HAIR, outline=HAIR_SHINE)
    for side in (-1, 1):   # long bangs framing the face
        bang = [center + Vector2(side * radius * 0.98, -radius * 0.3),
                center + Vector2(side * radius * 0.5, -radius * 0.4),
                center + Vector2(side * radius * 0.74, radius * 0.45)]
        pygame.draw.polygon(surface, HAIR, bang)


class FireballCone(Entity):
    """Cone of fire spat from the caster's front. Grows quickly, then fades."""
    name = "Fireball"
    shape = "cone"
    color = (255, 120, 30)
    max_hp = 40
    damage = 20
    damage_type = DamageType.FIRE
    immunities = frozenset({DamageType.PHYSICAL})
    hit_cooldown = 999        # each target is burned once per fireball
    lifetime = 1.2
    layer = 2
    spawn_sound = "fireball"
    hit_sound = "burn"
    full_length = 220
    half_angle = 28           # degrees
    grow_time = 0.25
    fade_time = 0.25

    def __init__(self, owner: Ball, direction: Vector2):
        self.direction = Vector2(direction).normalize()
        super().__init__(owner.pos + self.direction * owner.radius * 0.8, owner.team, owner)

    @property
    def length(self) -> float:
        grow = min(self.age / self.grow_time, 1.0)
        fade = min((self.lifetime - self.age) / self.fade_time, 1.0)
        return self.full_length * max(0.0, min(grow, fade))

    def _sector(self, origin, length, half_angle, wobble):
        apex = self.screen_pos(origin)
        points = [apex]
        steps = 10
        for i in range(steps + 1):
            a = -half_angle + 2 * half_angle * i / steps
            jitter = 1 + wobble * math.sin(self.age * 45 + i * 1.7)
            points.append(apex + self.direction.rotate(a) * length * jitter)
        return points

    def draw(self, surface, origin):
        if self.length < 2:
            return
        layers = ((1.0, 1.0, (200, 40, 20)), (0.8, 0.8, (255, 120, 30)),
                  (0.55, 0.55, (255, 200, 60)), (0.3, 0.35, (255, 245, 180)))
        for len_f, ang_f, color in layers:
            pygame.draw.polygon(surface, color,
                                self._sector(origin, self.length * len_f, self.half_angle * ang_f, 0.06))


class FireballJutsu(Ability):
    name = "Fireball Jutsu"
    cooldown = 5
    initial_cooldown = 4
    channel_time = 1.4
    range_factor = 1.1   # fire when a target is within this much of the cone length

    def _target_in_range(self, match):
        """Closest enemy ball within fireball range, or None. Clones count, so they work as decoys."""
        return match.nearest_enemy(self.owner, reach=FireballCone.full_length * self.range_factor)

    def can_activate(self, match):
        return self._target_in_range(match) is not None

    def cast(self, match):
        owner = self.owner
        target = self._target_in_range(match)
        aim = target.pos - owner.pos
        direction = aim.normalize() if aim.length_squared() > 1e-9 else owner.direction
        owner.vel = direction * owner.speed
        owner.add_status(match, Channeling(self.channel_time))
        match.spawn(FireballCone(owner, direction))


class Sharingan(Ability):
    """Dispels enemy clones and copies any copyable technique the enemy has ready."""
    name = "Sharingan"
    cooldown = 10
    sfx = "sharingan"
    initial_cooldown = 5
    eye_time = 1.5

    def _clones(self, match):
        return [e for e in match.enemies_of(self.owner) if "clone" in e.tags]

    def _copyable(self, match):
        return [e for e in match.enemies_of(self.owner) if "copyable" in e.tags]

    def can_activate(self, match):
        return bool(self._clones(match) or self._copyable(match))

    def cast(self, match):
        self.owner.eye_timer = self.eye_time
        for clone in self._clones(match):
            clone.destroy()
        copied = set()
        for technique in self._copyable(match):
            ability_cls = type(technique.source_ability)
            if ability_cls in copied:
                continue
            copy = ability_cls(self.owner)
            if copy.can_activate(match):
                copy.activate(match, callout=f"Copied: {copy.name}")
                copied.add(ability_cls)


@register
class Sasuke(Fighter):
    key = "sasuke"
    name = "Sasuke"
    announcer_name = "Sasukay"
    description = "Sharingan dispels clones and copies jutsu. Stops to breathe a huge Fireball."
    color = NAVY
    damage = 5
    ability_types = (Sharingan, FireballJutsu)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eye_timer = 0.0

    def on_update(self, match, dt):
        self.eye_timer = max(0.0, self.eye_timer - dt)

    def status(self, match):
        return "Sharingan!" if self.eye_timer > 0 else ""

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        r = self.radius
        draw_body(surface, center, r, SKIN, sasuke_hair, outline=NAVY)
        spin = self.age * 240
        for side in (-1, 1):
            eye = center + Vector2(side * r * 0.3, r * 0.08)
            if self.eye_timer > 0:
                draw_sharingan(surface, eye, r * 0.21, spin)
            else:
                pygame.draw.circle(surface, (15, 15, 20), eye, r * 0.09)
        if self.eye_timer > 0:
            # Close-up flash: a big Sharingan swells over Sasuke and fades out.
            phase = 1 - self.eye_timer / Sharingan.eye_time
            if phase < 0.6:
                fade = 1 - phase / 0.6
                draw_sharingan(surface, center, r * (1.6 + 2.4 * phase), spin, alpha=int(230 * fade))
