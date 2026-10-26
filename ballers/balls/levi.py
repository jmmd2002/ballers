import math

import pygame
from pygame.math import Vector2

from .. import gfx, physics
from ..ability import Ability
from ..entity import DamageType
from ..fighter import Fighter
from ..registry import register
from ..status import Status
from ._shinobi import draw_hair, smooth_profile

CLOAK = (50, 115, 70)
SKIN = (245, 226, 208)
HAIR = (22, 22, 28)
STEEL = (215, 222, 232)
CABLE = (170, 175, 185)
LEVI_HAIR = smooth_profile(175, 365, lambda t: 1.02 + 0.06 * math.sin(math.pi * t))


def draw_blades(surface, center: Vector2, radius: float, facing: Vector2):
    """Two swords held at the sides, pointing the way Levi is moving."""
    side = Vector2(-facing.y, facing.x)
    for s in (-1, 1):
        hilt = center + side * s * radius * 0.92 + facing * radius * 0.1
        tip = hilt + facing.rotate(s * 12) * radius * 1.05
        pygame.draw.line(surface, gfx.darken(STEEL, 0.55), hilt, tip, 6)
        pygame.draw.line(surface, STEEL, hilt, tip, 3)
        pygame.draw.circle(surface, (60, 60, 70), hilt, 4)


def draw_levi(surface, center: Vector2, radius: float):
    pygame.draw.circle(surface, CLOAK, center, radius)    # hood/cloak ring
    pygame.draw.circle(surface, SKIN, center, radius * 0.84)
    pygame.draw.circle(surface, gfx.darken(CLOAK, 0.5), center, radius, width=3)
    draw_hair(surface, center, radius * 0.86, HAIR, LEVI_HAIR, outline=(70, 70, 85), hairline=-0.25)
    for s in (-1, 1):   # curtain bangs parted in the middle
        bang = [center + Vector2(s * radius * 0.04, -radius * 0.62),
                center + Vector2(s * radius * 0.78, -radius * 0.3),
                center + Vector2(s * radius * 0.6, radius * 0.05),
                center + Vector2(s * radius * 0.2, -radius * 0.3)]
        pygame.draw.polygon(surface, HAIR, bang)
        eye = center + Vector2(s * radius * 0.3, radius * 0.12)   # narrow, unimpressed eyes
        pygame.draw.line(surface, (40, 40, 50), eye - Vector2(radius * 0.13, 0), eye + Vector2(radius * 0.13, 0), 3)
        pygame.draw.circle(surface, (90, 100, 115), eye + Vector2(0, radius * 0.03), radius * 0.05)
    mouth = center + Vector2(0, radius * 0.42)
    pygame.draw.line(surface, (150, 95, 85), mouth - Vector2(radius * 0.12, 0), mouth + Vector2(radius * 0.12, 0), 2)
    cravat = [center + Vector2(-radius * 0.2, radius * 0.72), center + Vector2(radius * 0.2, radius * 0.72),
              center + Vector2(0, radius * 0.98)]
    pygame.draw.polygon(surface, (250, 250, 250), cravat)


class ODMGrapple(Status):
    """Shoots a cable at the target, reels in fast, slashes it, then springs back."""
    name = "ODM Gear"
    damage = 20
    cable_speed = 2400    # px/s the hook flies
    reel_speed = 3.0      # speed multipliers
    recoil_speed = 2.2
    recoil_time = 0.25
    slash_gap = 10        # edge-to-edge distance at which the slash lands
    give_up = 2.0         # seconds of reeling before letting go

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.anchor = Vector2(target.pos)
        self.phase = "shoot"
        self.cable = 0.0      # drawn cable length
        self.recoil = 0.0

    def on_update(self, entity, match, dt):
        if entity.is_immobile:   # grabbed or stunned mid-flight
            self.end()
            return
        target = self.target
        if self.phase == "recoil":
            self.recoil -= dt
            self.cable = max(0.0, self.cable - self.cable_speed * dt)
            if self.recoil <= 0:
                self.end()
            return
        if not target.alive or self.age > self.give_up:
            self.end()
            return
        self.anchor = Vector2(target.pos)
        to_target = target.pos - entity.pos
        dist = to_target.length()
        direction = to_target / dist if dist > 1e-9 else entity.direction
        if self.phase == "shoot":
            self.cable += self.cable_speed * dt
            if self.cable >= dist - target.radius:
                self.phase = "reel"
                self.speed_mult = self.reel_speed
        else:
            self.cable = dist - target.radius
            if dist - entity.radius - target.radius <= self.slash_gap:
                match.deal_damage(entity, target, self.damage, DamageType.SLASHING)
                self.phase = "recoil"
                self.speed_mult = self.recoil_speed
                self.recoil = self.recoil_time
                entity.vel = -direction * entity.current_speed
                return
        entity.vel = direction * entity.current_speed

    def draw(self, surface, entity, origin):
        if self.cable <= 1:
            return
        start = entity.screen_pos(origin)
        to_anchor = self.anchor - entity.pos
        if to_anchor.length_squared() < 1e-9:
            return
        end = start + to_anchor.normalize() * min(self.cable, to_anchor.length())
        pygame.draw.line(surface, CABLE, start, end, 2)
        pygame.draw.circle(surface, (90, 90, 100), end, 4)
        if self.phase == "reel":   # gas burst trailing behind
            back = -entity.direction
            puff = pygame.Surface((60, 60), pygame.SRCALPHA)
            for k in range(3):
                pygame.draw.circle(puff, (235, 235, 240, 110 - k * 35), Vector2(30, 30) + back * (k * 9),
                                   4 + k * 3)
            surface.blit(puff, puff.get_rect(center=start + back * (entity.radius + 2)))


class SlashFlurry(Status):
    """Spinning blades that cut every enemy entity nearby. Keeps going while
    anything is in reach; stops after `linger` seconds with nothing around.
    Damage builds up per target every step and lands as a cut each time it
    reaches `proc`, so it reads as a rapid series of slashes."""
    name = "Flurry of Slashes"
    label = "Flurry!"
    dps = 20
    reach = 80            # from Levi's center
    linger = 1.0
    proc = 1.0            # damage per cut

    def __init__(self):
        super().__init__()
        self.idle = 0.0
        self.pending: dict[int, float] = {}   # id(target) -> damage built up

    @classmethod
    def targets(cls, entity, match):
        return [e for e in match.enemies_of(entity) if physics.circle_overlaps(entity.pos, cls.reach, e)]

    def on_update(self, entity, match, dt):
        targets = self.targets(entity, match)
        if not targets:
            self.idle += dt
            if self.idle >= self.linger:
                self.end()
            return
        self.idle = 0.0
        pending = {}
        for target in targets:
            # Anything newly in reach gets cut right away; after that, one cut per `proc` damage.
            built = self.pending.get(id(target), self.proc - self.dps * dt) + self.dps * dt
            if built >= self.proc:
                cuts = built // self.proc
                match.deal_damage(entity, target, cuts * self.proc, DamageType.SLASHING, continuous=True)
                built -= cuts * self.proc
            pending[id(target)] = built
        self.pending = pending   # forget targets that left reach

    def draw(self, surface, entity, origin):
        size = int(self.reach * 2 + 8)
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        mid = Vector2(size / 2, size / 2)
        strength = 1.0 if self.idle == 0 else max(0.25, 1 - self.idle / self.linger)
        rect = pygame.Rect(0, 0, self.reach * 2, self.reach * 2)
        rect.center = mid
        spin = self.age * 16
        for i in range(4):
            a = spin + i * math.pi / 2
            pygame.draw.arc(overlay, (255, 255, 255, int(220 * strength)), rect, a, a + 0.9, 3)
            inner = rect.inflate(-18, -18)
            pygame.draw.arc(overlay, (*STEEL, int(150 * strength)), inner, -a, -a + 0.6, 2)
        surface.blit(overlay, overlay.get_rect(center=entity.screen_pos(origin)))


class ODMGear(Ability):
    name = "ODM Gear"
    cooldown = 2
    initial_cooldown = 2
    sfx = "zipline"
    min_distance = 90     # edge-to-edge; closer than this he just uses his blades

    def _target(self, match):
        target = match.nearest_enemy(self.owner)
        if target is None:
            return None
        gap = self.owner.pos.distance_to(target.pos) - self.owner.radius - target.radius
        return target if gap >= self.min_distance else None

    def update(self, match, dt):
        if self.owner.has_status(ODMGrapple):
            self.timer = self.cooldown
        super().update(match, dt)

    def can_activate(self, match):
        return self._target(match) is not None

    def hud_label(self, match):
        return "ACTIVE" if self.owner.has_status(ODMGrapple) else None

    def cast(self, match):
        self.owner.add_status(match, ODMGrapple(self._target(match)))


class FlurryOfSlashes(Ability):
    name = "Flurry of Slashes"
    cooldown = 2
    initial_cooldown = 3
    sfx = "slash"

    def update(self, match, dt):
        # Cooldown only starts once the flurry has died down.
        if self.owner.has_status(SlashFlurry):
            self.timer = self.cooldown
        super().update(match, dt)

    def can_activate(self, match):
        return not self.owner.has_status(SlashFlurry) and bool(SlashFlurry.targets(self.owner, match))

    def hud_label(self, match):
        return "ACTIVE" if self.owner.has_status(SlashFlurry) else None

    def cast(self, match):
        self.owner.add_status(match, SlashFlurry())


@register
class Levi(Fighter):
    key = "levi"
    name = "Levi"
    description = "Fast and fragile. Zips in with ODM gear to slash and spins into a flurry of blades."
    color = CLOAK
    max_hp = 100
    damage = 10               # his blades, instead of a plain bump
    damage_type = DamageType.SLASHING
    hit_sound = "slash"
    ability_types = (ODMGear, FlurryOfSlashes)

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        draw_blades(surface, center, self.radius, self.direction)
        draw_levi(surface, center, self.radius)
