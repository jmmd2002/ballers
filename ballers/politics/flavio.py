import pygame
from pygame.math import Vector2

from ..ability import Ability
from ..entity import Entity
from ..fighter import Fighter
from ..registry import register
from ..status import Status
from ._common import Politician

GREEN = (0, 156, 59)
YELLOW = (255, 214, 0)


class Bullet(Entity):
    """Small fast shot that flies straight until it hits something or leaves the arena."""
    name = "Arminha"
    color = YELLOW
    radius = 5
    max_hp = 1
    damage = 4
    dies_on_hit = True
    lifetime = 1.2
    layer = 2
    death_effect = "burst"
    spawn_sound = "arminha_shot"
    speed = 650

    def __init__(self, owner: Entity, direction: Vector2):
        direction = Vector2(direction).normalize()
        super().__init__(owner.pos + direction * (owner.radius + 6), owner.team, owner)
        self.vel = direction * self.speed

    def on_update(self, match, dt):
        self.pos += self.vel * dt
        w, h = match.config.arena_width, match.config.arena_height
        if not (0 <= self.pos.x <= w and 0 <= self.pos.y <= h):
            self.destroy()

    def draw(self, surface, origin):
        center = self.screen_pos(origin)
        tail = center - self.vel.normalize() * 16
        pygame.draw.line(surface, (255, 240, 170), tail, center, 3)
        pygame.draw.circle(surface, self.color, center, self.radius)
        pygame.draw.circle(surface, (120, 90, 0), center, self.radius, width=1)


class Burst(Status):
    """Fires `shots` bullets at the nearest enemy, one every `interval` seconds."""
    name = "Arminha"
    shots = 3
    interval = 0.12

    def __init__(self):
        super().__init__(self.shots * self.interval)
        self.fired = 0

    def on_update(self, entity, match, dt):
        if self.age < self.fired * self.interval:
            return
        target = match.nearest_enemy(entity)
        if target is None:
            return
        aim = target.pos - entity.pos
        if aim.length_squared() > 1e-9:
            match.spawn(Bullet(entity, aim))
        self.fired += 1


class Arminha(Ability):
    name = "Arminha"
    cooldown = 5
    initial_cooldown = 2
    reach = 280

    def can_activate(self, match):
        return match.nearest_enemy(self.owner, reach=self.reach) is not None

    def cast(self, match):
        self.owner.add_status(match, Burst())


class Tired(Status):
    name = "Tired"
    label = "Cansado"
    speed_mult = 0.55


class Riding(Status):
    """Fast charge on a motorcycle that homes in on the target and hits hard once."""
    name = "Motociata"
    label = "Motociata!"
    speed_mult = 2.1
    damage = 20
    turn_rate = 140      # degrees per second of homing
    tired_time = 1.4

    def __init__(self, duration, target: Entity):
        super().__init__(duration)
        self.target = target

    def on_apply(self, entity, match):
        self.base_damage = entity.damage
        entity.damage = self.damage

    def on_update(self, entity, match, dt):
        if not self.target.alive:
            return
        turn = entity.vel.angle_to(self.target.pos - entity.pos)
        turn = (turn + 180) % 360 - 180
        step = self.turn_rate * dt
        entity.vel.rotate_ip(max(-step, min(step, turn)))

    def on_expire(self, entity, match):
        entity.damage = self.base_damage
        entity.add_status(match, Tired(self.tired_time))

    def draw(self, surface, entity, origin):
        center = entity.screen_pos(origin)
        back = -entity.direction
        side = back.rotate(90)
        for k, offset in enumerate((-0.6, 0.0, 0.6)):
            start = center + back * entity.radius * 0.9 + side * offset * entity.radius
            length = entity.radius * (1.2 + 0.4 * ((k + int(self.age * 20)) % 2))
            pygame.draw.line(surface, (YELLOW, GREEN, YELLOW)[k], start, start + back * length, 4)


class Motociata(Ability):
    name = "Motociata"
    cooldown = 9
    sfx = "motociata"
    initial_cooldown = 5
    ride_time = 2.0
    min_distance = 140   # needs some runway to build up speed

    def _target(self, match):
        enemies = match.enemies_of(self.owner, Fighter)
        return min(enemies, key=lambda e: e.pos.distance_squared_to(self.owner.pos), default=None)

    def can_activate(self, match):
        target = self._target(match)
        return target is not None and target.pos.distance_to(self.owner.pos) >= self.min_distance

    def cast(self, match):
        target = self._target(match)
        owner = self.owner
        owner.vel = (target.pos - owner.pos).normalize() * owner.speed
        owner.add_status(match, Riding(self.ride_time, target))


@register
class Flavio(Politician):
    key = "flavio"
    name = "Flávio Bolsonaro"
    announcer_name = "Flavio Bolsonaro"
    description = "Charges in a Motociata that hits hard once, and pokes with Arminha bursts."
    color = GREEN
    max_hp = 100
    damage = 5
    speed = 330
    face_key = "flavio"
    face_crop = (518, 345, 285)
    ability_types = (Motociata, Arminha)

    def on_hit(self, match, target, dealt):
        ride = self.get_status(Riding)
        if ride and target.is_fighter:
            ride.end()   # the charge is spent on the first fighter it hits
