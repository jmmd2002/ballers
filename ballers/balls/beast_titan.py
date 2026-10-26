import math
import random

import pygame
from pygame.math import Vector2

from .. import gfx
from ..ability import Ability
from ..entity import Ball, Entity
from ..fighter import Fighter
from ..registry import register
from ..status import Channeling, Grasped

FUR = (176, 132, 84)        # golden-brown pelt
FUR_DARK = (118, 82, 50)
FACE = (214, 182, 156)      # pale titan skin
SOCKET = (92, 58, 44)
ROCK = (168, 154, 136)


def _rock_outline(seed: float, points: int = 9) -> list[float]:
    """Lumpy radius factors so each rock looks a bit different (visual only)."""
    rng = random.Random(seed)
    return [rng.uniform(0.75, 1.1) for _ in range(points)]


def _shaggy(center: Vector2, radius: float, tufts: int, depth: float, phase: float) -> list[Vector2]:
    """Ring of pointed fur tufts."""
    pts = []
    for i in range(tufts * 2):
        f = 1.0 if i % 2 == 0 else 1.0 - depth * (0.8 + 0.4 * math.sin(i * 1.7 + phase))
        pts.append(center + Vector2(radius * f, 0).rotate(i * 180 / tufts + phase))
    return pts


def draw_beast_titan(surface, c: Vector2, r: float):
    """Zeke's Beast Titan: shaggy ape mane, widow's peak over a heavy brow,
    deep-set eyes, broad flat nose, muzzle and a furry beard."""
    pygame.draw.polygon(surface, FUR_DARK, _shaggy(c, r * 1.04, 20, 0.16, 0))
    pygame.draw.polygon(surface, FUR, _shaggy(c, r * 0.94, 18, 0.14, 7))
    for i in range(24):   # fur strands
        d = Vector2(1, 0).rotate(i * 15 + 4)
        pygame.draw.line(surface, FUR_DARK, c + d * r * 0.66, c + d.rotate(6) * r * 0.86, max(1, int(r * 0.035)))
    # Face: pale skin, narrower at the top where the fur comes down.
    face = pygame.Rect(0, 0, r * 1.12, r * 1.12)
    face.center = (c.x, c.y + r * 0.12)
    pygame.draw.ellipse(surface, FACE, face)
    peak = [c + Vector2(-r * 0.62, -r * 0.55), c + Vector2(r * 0.62, -r * 0.55),
            c + Vector2(r * 0.3, -r * 0.3), c + Vector2(0, -r * 0.1), c + Vector2(-r * 0.3, -r * 0.3)]
    pygame.draw.polygon(surface, FUR, peak)
    # Beard framing the jaw.
    beard = [c + Vector2(-r * 0.6, r * 0.2), c + Vector2(-r * 0.42, r * 0.62), c + Vector2(-r * 0.18, r * 0.78),
             c + Vector2(0, r * 0.9), c + Vector2(r * 0.18, r * 0.78), c + Vector2(r * 0.42, r * 0.62),
             c + Vector2(r * 0.6, r * 0.2), c + Vector2(r * 0.45, r * 0.5), c + Vector2(0, r * 0.66),
             c + Vector2(-r * 0.45, r * 0.5)]
    pygame.draw.polygon(surface, FUR, beard)
    pygame.draw.polygon(surface, FUR_DARK, beard, 2)
    # Muzzle.
    muzzle = pygame.Rect(0, 0, r * 0.74, r * 0.46)
    muzzle.center = (c.x, c.y + r * 0.38)
    pygame.draw.ellipse(surface, gfx.lighten(FACE, 0.18), muzzle)
    # Deep, shadowed eye sockets under a heavy brow.
    for s in (-1, 1):
        sock = pygame.Rect(0, 0, r * 0.36, r * 0.22)
        sock.center = (c.x + s * r * 0.24, c.y + r * 0.02)
        pygame.draw.ellipse(surface, SOCKET, sock)
        eye = c + Vector2(s * r * 0.23, r * 0.04)
        pygame.draw.circle(surface, (196, 180, 150), eye, r * 0.048)
        pygame.draw.circle(surface, (25, 18, 14), eye + Vector2(-s * r * 0.008, r * 0.005), r * 0.03)
    brow = [c + Vector2(-r * 0.5, -r * 0.02), c + Vector2(-r * 0.22, -r * 0.08), c + Vector2(0, -r * 0.02),
            c + Vector2(r * 0.22, -r * 0.08), c + Vector2(r * 0.5, -r * 0.02)]
    pygame.draw.lines(surface, FUR_DARK, False, brow, max(3, int(r * 0.11)))
    # Broad, flat nose.
    nose = [c + Vector2(-r * 0.04, r * 0.08), c + Vector2(r * 0.04, r * 0.08),
            c + Vector2(r * 0.15, r * 0.27), c + Vector2(-r * 0.15, r * 0.27)]
    pygame.draw.polygon(surface, gfx.darken(FACE, 0.12), nose)
    for s in (-1, 1):
        pygame.draw.circle(surface, SOCKET, c + Vector2(s * r * 0.07, r * 0.25), r * 0.035)
    # Wide grim mouth with a row of teeth.
    mouth = pygame.Rect(0, 0, r * 0.5, r * 0.13)
    mouth.center = (c.x, c.y + r * 0.45)
    pygame.draw.ellipse(surface, (70, 30, 24), mouth)
    teeth = mouth.inflate(-r * 0.12, -r * 0.06)
    pygame.draw.rect(surface, (238, 230, 214), (teeth.x, mouth.y + 1, teeth.width, teeth.height), border_radius=2)
    pygame.draw.polygon(surface, gfx.darken(FUR_DARK, 0.3), _shaggy(c, r * 1.04, 20, 0.16, 0), 2)


class RockShard(Ball):
    """Small fragment that ricochets off walls until it hits something or crumbles."""
    name = "Rock Shard"
    color = gfx.darken(ROCK, 0.15)
    solid = False
    radius = 8
    speed = 430
    max_hp = 1
    damage = 10
    dies_on_hit = True
    lifetime = 1.4
    layer = 1
    death_effect = "crumble"

    def __init__(self, pos, team, direction, owner=None, ricocheted_off: Entity | None = None):
        super().__init__(pos, team, direction, owner)
        self.ricocheted_off = ricocheted_off   # what the boulder broke on; shards fly off it
        self.outline = _rock_outline(pos.x * 31.7 + pos.y * 7.3 + direction.x, 6)

    def can_damage(self, match, target):
        return target is not self.ricocheted_off or self.age > 0.3

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        spin = self.age * 600
        pts = [center + Vector2(self.radius * f, 0).rotate(spin + i * 360 / len(self.outline))
               for i, f in enumerate(self.outline)]
        pygame.draw.polygon(surface, self.color, pts)
        pygame.draw.polygon(surface, gfx.darken(self.color, 0.45), pts, 1)


class BoulderRock(Ball):
    """Thrown boulder. Shatters into ricocheting shards when it hits a wall or
    any enemy entity."""
    name = "Rock"
    color = ROCK
    solid = False
    radius = 24
    speed = 380
    max_hp = 1
    damage = 20
    lifetime = 5
    layer = 1
    death_effect = "crumble"
    death_sound = "rock_break"
    death_shake = 9
    shard_count = 5
    shard_spread = 65     # degrees around the bounce direction

    def __init__(self, pos, team, direction, owner=None):
        super().__init__(pos, team, direction, owner)
        self.outline = _rock_outline(pos.x * 13.1 + pos.y * 3.7 + direction.y)

    def on_wall_hit(self, match, normal):
        self.shatter(match, self.direction, self.pos)   # velocity is already reflected

    def on_contact(self, match, other):
        if other.team == self.team or self.removed:
            return
        away = self.pos - other.pos
        if other.shape == "circle" and away.length_squared() > 1e-9:
            away.normalize_ip()
            bounce = self.direction.reflect(away) if self.direction.dot(away) < 0 else self.direction
            self.shatter(match, bounce, other.pos + away * (other.radius + RockShard.radius + 1), other)
        else:
            self.shatter(match, -self.direction, self.pos, other)

    def shatter(self, match, heading: Vector2, at: Vector2, hit: Entity | None = None):
        self.destroy()
        at = match.clamp_to_arena(at, RockShard.radius)
        for _ in range(self.shard_count):
            d = heading.rotate(match.rng.uniform(-self.shard_spread, self.shard_spread))
            match.spawn(RockShard(at, self.team, d, owner=self.owner, ricocheted_off=hit))

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        spin = self.age * 240
        pts = [center + Vector2(self.radius * f, 0).rotate(spin + i * 360 / len(self.outline))
               for i, f in enumerate(self.outline)]
        back = -self.direction   # dust trail
        trail = pygame.Surface((self.radius * 6, self.radius * 6), pygame.SRCALPHA)
        mid = Vector2(trail.get_size()) / 2
        for k in range(1, 4):
            pygame.draw.circle(trail, (205, 195, 180, 90 - k * 25), mid + back * self.radius * 0.9 * k,
                               self.radius * (0.75 - k * 0.12))
        surface.blit(trail, trail.get_rect(center=center))
        pygame.draw.polygon(surface, self.color, pts)
        pygame.draw.polygon(surface, gfx.darken(self.color, 0.55), pts, 3)
        crack = gfx.darken(self.color, 0.45)
        for a in (20, 150, 260):   # cracks spinning with the rock
            d = Vector2(1, 0).rotate(spin + a)
            pygame.draw.lines(surface, crack, False, [center + d * self.radius * 0.15,
                              center + d.rotate(18) * self.radius * 0.5, center + d * self.radius * 0.8], 2)
        pygame.draw.circle(surface, gfx.lighten(self.color, 0.3), center + Vector2(-7, -7), 4)


class BeastArm(Entity):
    """Long arm stretched from the titan. The hand reaches for a target, grips
    the first enemy body it touches, then pulls back. Cutting the hand frees the
    victim."""
    name = "Titan Arm"
    color = FUR
    radius = 20           # the hand
    max_hp = 30
    layer = 2
    death_effect = "burst"
    reach_speed = 900
    retract_speed = 1100
    max_reach = 290       # from the titan's center
    grip_time = 2
    grip_dps = 10
    grip_interval = 2     # the squeeze lands every 2 s; cutting the hand first wastes it

    def __init__(self, owner: Ball, target: Entity, channel: Channeling):
        direction = (target.pos - owner.pos).normalize()
        super().__init__(owner.pos + direction * owner.radius, owner.team, owner)
        self.target = target
        self.channel = channel       # keeps the titan in place while the arm is out
        self.phase = "reach"
        self.grip: Grasped | None = None
        self.held = None

    def on_contact(self, match, other):
        if self.phase == "reach" and other.team != self.team and other.solid and other.alive:
            self.held = other
            self.grip = other.add_status(match, Grasped(self.grip_time, source=self, dps=self.grip_dps,
                                                         interval=self.grip_interval))
            self.phase = "hold"

    def _retract(self):
        if self.grip:
            self.grip.end()
        self.phase = "retract"

    def on_update(self, match, dt):
        owner = self.owner
        if self.phase == "reach":
            if not self.target.alive or self.pos.distance_to(owner.pos) > self.max_reach:
                self._retract()
                return
            to = self.target.pos - self.pos
            step = self.reach_speed * dt
            self.pos += to if to.length() <= step else to.normalize() * step
        elif self.phase == "hold":
            if self.grip.done or not self.held.alive:
                self._retract()
                return
            toward_owner = owner.pos - self.held.pos
            if toward_owner.length_squared() > 1e-9:
                self.pos = self.held.pos + toward_owner.normalize() * self.held.radius * 0.55
        else:
            to = owner.pos - self.pos
            step = self.retract_speed * dt
            if to.length() <= owner.radius + step:
                self.destroy()
            else:
                self.pos += to.normalize() * step

    def on_death(self, match):
        if self.grip:
            self.grip.end()
        self.owner.remove_status(match, self.channel)

    def draw(self, surface, origin):
        hand = self.screen_pos(origin)
        shoulder = self.owner.screen_pos(origin)
        to = hand - shoulder
        if to.length_squared() < 1e-9:
            return
        d = to.normalize()
        side = Vector2(-d.y, d.x)
        base = shoulder + d * self.owner.radius * 0.7
        arm = [base + side * 13, hand + side * 9, hand - side * 9, base - side * 13]
        pygame.draw.polygon(surface, FUR, arm)
        pygame.draw.polygon(surface, gfx.darken(FUR, 0.45), arm, 2)
        held = self.held if self.phase == "hold" else None
        # Fingers: spread open while reaching, wrapped around the victim while holding.
        for k in (-1.5, -0.5, 0.5, 1.5):
            if held:
                center = held.screen_pos(origin)
                finger = center + (-d).rotate(k * 38) * held.radius * 0.95
                pygame.draw.line(surface, FACE, hand, finger, 9)
                pygame.draw.circle(surface, FACE, finger, 6)
            else:
                finger = hand + d.rotate(k * 28) * self.radius * 1.1
                pygame.draw.line(surface, FACE, hand, finger, 7)
        pygame.draw.circle(surface, FACE, hand, self.radius * 0.8)
        pygame.draw.circle(surface, gfx.darken(FACE, 0.4), hand, self.radius * 0.8, 2)


class RockThrow(Ability):
    name = "Rock Throw"
    cooldown = 12
    initial_cooldown = 2
    sfx = "rock_throw"
    spread = 32           # degrees between rocks
    windup = 0.4          # stands still for the follow-through

    def can_activate(self, match):
        return match.nearest_enemy(self.owner) is not None

    def cast(self, match):
        owner = self.owner
        aim = match.nearest_enemy(owner).pos - owner.pos
        aim = aim.normalize() if aim.length_squared() > 1e-9 else owner.direction
        owner.add_status(match, Channeling(self.windup))
        for k in (-1, 0, 1):
            d = aim.rotate(k * self.spread)
            pos = match.clamp_to_arena(owner.pos + d * (owner.radius + BoulderRock.radius + 2),
                                       BoulderRock.radius)
            match.spawn(BoulderRock(pos, owner.team, d, owner=owner))


class TitanGrab(Ability):
    name = "Grab"
    cooldown = 14
    initial_cooldown = 5
    sfx = "rock_throw"    # heavy whoosh as the arm shoots out

    def _target(self, match):
        return match.nearest_enemy(self.owner, reach=BeastArm.max_reach - 10)

    def update(self, match, dt):
        if match.owned_by(self.owner, BeastArm):
            self.timer = self.cooldown
        super().update(match, dt)

    def can_activate(self, match):
        return self._target(match) is not None and not match.owned_by(self.owner, BeastArm)

    def hud_label(self, match):
        return "ACTIVE" if match.owned_by(self.owner, BeastArm) else None

    def cast(self, match):
        channel = self.owner.add_status(match, Channeling())
        match.spawn(BeastArm(self.owner, self._target(match), channel))


@register
class BeastTitan(Fighter):
    key = "beast_titan"
    name = "Beast Titan"
    description = "Huge and slow. Hurls boulders that shatter into shards and grabs foes with a long arm."
    color = FUR
    max_hp = 500
    radius = 44
    speed = 250
    mass = 3.0
    damage = 5
    ability_types = (RockThrow, TitanGrab)

    def draw(self, surface, origin):
        draw_beast_titan(surface, self.screen_pos(origin), self.radius)
