import math

import pygame
from pygame.math import Vector2

from ..ability import Ability
from ..entity import Ball, DamageType, Entity
from ..fighter import Fighter
from ..registry import register
from ._shinobi import draw_body, draw_hair, tufted_profile

ORANGE = (255, 140, 30)
BLOND = (255, 214, 60)
NARUTO_HAIR = tufted_profile(168, 372, tufts=7, tip=1.32, valley=1.04, sweep=0)


def naruto_hair(surface, center, radius):
    draw_hair(surface, center, radius, BLOND, NARUTO_HAIR, outline=(200, 140, 20))


def draw_naruto(surface, center, radius):
    draw_body(surface, center, radius, ORANGE, naruto_hair)
    for side in (-1, 1):
        pygame.draw.circle(surface, (40, 90, 200), center + Vector2(side * radius * 0.28, radius * 0.02),
                           radius * 0.1)
        for dy in (-0.1, 0.1, 0.3):     # whiskers
            start = center + Vector2(side * radius * 0.45, radius * (0.25 + dy * 0.5))
            end = center + Vector2(side * radius * 0.85, radius * (0.25 + dy))
            pygame.draw.line(surface, (90, 45, 10), start, end, 2)


class ShadowClone(Ball):
    name = "Shadow Clone"
    color = ORANGE
    max_hp = 1
    damage = 5
    dies_on_hit = True
    lifetime = 15
    death_effect = "smoke"
    death_sound = "puff"
    tags = frozenset({"clone"})

    def draw(self, surface, origin):
        draw_naruto(surface, self.screen_pos(origin), self.radius)


class RasenganOrb(Entity):
    """Spinning chakra sphere held on the side of the owner facing the closest enemy fighter."""
    name = "Rasengan"
    color = (110, 190, 255)
    radius = 15
    max_hp = 1
    damage = 30
    damage_type = DamageType.CHAKRA
    dies_on_hit = True
    lifetime = 6              # fizzles out if it doesn't connect in time
    layer = 1
    death_effect = "burst"
    spawn_sound = "rasengan_form"
    hit_sound = "rasengan_hit"
    tags = frozenset({"copyable"})
    turn_speed = 540          # degrees per second the orb swings around its owner

    def __init__(self, owner: Ball, source_ability: Ability):
        super().__init__(owner.pos, owner.team, owner)
        self.source_ability = source_ability   # lets Sharingan copy the technique
        self.aim = Vector2(owner.direction)

    def _target_dir(self, match) -> Vector2:
        enemies = match.enemies_of(self.owner, Fighter)
        if not enemies:
            return self.aim
        target = min(enemies, key=lambda e: e.pos.distance_squared_to(self.owner.pos))
        to_target = target.pos - self.owner.pos
        return to_target.normalize() if to_target.length_squared() > 1e-9 else self.aim

    def _place(self):
        self.pos = self.owner.pos + self.aim * (self.owner.radius + self.radius * 0.5)

    def on_spawn(self, match):
        self.aim = self._target_dir(match)
        self._place()

    def on_update(self, match, dt):
        turn = self.aim.angle_to(self._target_dir(match))
        turn = (turn + 180) % 360 - 180
        max_step = self.turn_speed * dt
        self.aim.rotate_ip(max(-max_step, min(max_step, turn)))
        self._place()

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        r = self.radius * (1 + 0.08 * math.sin(self.age * 25))
        pygame.draw.circle(surface, (40, 110, 230), center, r + 3)
        pygame.draw.circle(surface, self.color, center, r)
        pygame.draw.circle(surface, (230, 245, 255), center, r * 0.45)
        rect = pygame.Rect(0, 0, r * 2, r * 2)
        rect.center = center
        spin = self.age * 18
        for i in range(3):
            start = spin + i * 2 * math.pi / 3
            pygame.draw.arc(surface, (255, 255, 255), rect, start, start + 1.4, 2)


class ShadowCloneJutsu(Ability):
    name = "Shadow Clone Jutsu"
    cooldown = 14
    initial_cooldown = 3
    clone_count = 4

    def cast(self, match):
        owner = self.owner
        base = match.rng.uniform(0, 360)
        for i in range(self.clone_count):
            d = Vector2(1, 0).rotate(base + i * 360 / self.clone_count)
            pos = match.clamp_to_arena(owner.pos + d * owner.radius * 2.2, ShadowClone.radius)
            match.spawn(ShadowClone(pos, owner.team, direction=d, owner=owner))


class RasenganJutsu(Ability):
    name = "Rasengan"
    cooldown = 9
    initial_cooldown = 6

    def update(self, match, dt):
        # Cooldown only starts once the held orb has been used up.
        if match.owned_by(self.owner, RasenganOrb):
            self.timer = self.cooldown
        super().update(match, dt)

    def can_activate(self, match):
        return not match.owned_by(self.owner, RasenganOrb)

    def hud_label(self, match):
        return "ACTIVE" if match.owned_by(self.owner, RasenganOrb) else None

    def cast(self, match):
        match.spawn(RasenganOrb(self.owner, self))


@register
class Naruto(Fighter):
    key = "naruto"
    name = "Naruto"
    announcer_name = "Narutoe"
    description = "Summons Shadow Clones as decoys and charges a Rasengan that hits hard."
    color = ORANGE
    damage = 5
    ability_types = (ShadowCloneJutsu, RasenganJutsu)

    def status(self, match):
        parts = []
        clones = len(match.owned_by(self, ShadowClone))
        if clones:
            parts.append(f"Clones: {clones}")
        if match.owned_by(self, RasenganOrb):
            parts.append("Rasengan")
        return "  ·  ".join(parts)

    def draw(self, surface, origin):
        draw_naruto(surface, self.screen_pos(origin), self.radius)
