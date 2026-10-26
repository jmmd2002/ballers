import math

import pygame
from pygame.math import Vector2

from .. import gfx
from ..ability import Ability
from ..entity import Ball, Entity
from ..registry import register
from ..status import Channeling, Status, Stunned
from ._common import Politician, draw_bubble

RED = (210, 25, 35)
GOLD = (255, 205, 60)


class Asleep(Stunned):
    """Stunned by a speech that went on a bit too long."""
    name = "Asleep"
    label = "Dormiu"
    sound = "snore"

    def draw(self, surface, entity, origin):
        center = entity.screen_pos(origin)
        for k in range(3):
            phase = (self.age * 1.5 + k / 3) % 1
            pos = center + Vector2(entity.radius * (0.5 + 0.4 * phase), -entity.radius * (0.7 + 1.1 * phase))
            gfx.draw_text(surface, "z", int(18 + 14 * phase), (200, 220, 255), bold=True, outline=2,
                          alpha=int(255 * (1 - phase)), center=pos)


class Shockwave(Entity):
    """Visual ring of the speech's blast. Shape "fx" never overlaps anything."""
    name = "Discurso"
    shape = "fx"
    color = RED
    lifetime = 0.45
    layer = 3

    def __init__(self, owner: Entity, radius: float):
        super().__init__(owner.pos, owner.team, owner)
        self.max_radius = radius

    def draw(self, surface, origin):
        t = self.age / self.lifetime
        r = self.max_radius * (0.3 + 0.7 * t)
        overlay = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        mid = (r + 4, r + 4)
        alpha = int(220 * (1 - t))
        pygame.draw.circle(overlay, (*RED, alpha // 4), mid, r)
        pygame.draw.circle(overlay, (255, 230, 230, alpha), mid, r, width=max(2, int(8 * (1 - t))))
        surface.blit(overlay, overlay.get_rect(center=self.screen_pos(origin)))


class Speaking(Channeling):
    """Lula stands still and talks; when he finishes, everyone nearby has fallen asleep."""
    name = "Discurso"
    label = "Discursando..."
    words = ("Companheiros...", "Companheiros e companheiras...", "Nunca antes na história...")

    def __init__(self, duration, radius, damage, sleep_time):
        super().__init__(duration)
        self.radius, self.damage, self.sleep_time = radius, damage, sleep_time
        self.line = ""

    def on_apply(self, entity, match):
        self.line = match.rng.choice(self.words)

    def on_expire(self, entity, match):
        if self.ended or not entity.alive:
            return   # interrupted
        match.spawn(Shockwave(entity, self.radius))
        for enemy in match.enemies_of(entity, Ball):
            away = enemy.pos - entity.pos
            if away.length() - enemy.radius > self.radius:
                continue
            for status in list(enemy.statuses):
                if status.speed_mult > 1:
                    enemy.remove_status(match, status)   # knocks Flávio off his motorcycle
            match.deal_damage(entity, enemy, self.damage)
            if away.length_squared() > 1e-9:
                enemy.vel = away.normalize() * enemy.speed
            enemy.add_status(match, Asleep(self.sleep_time, source=entity))

    def draw(self, surface, entity, origin):
        center = entity.screen_pos(origin)
        shown = self.line[:max(1, int(len(self.line) * min(self.age / (self.remaining + self.age) * 1.6, 1)))]
        draw_bubble(surface, center + Vector2(0, entity.radius), shown)


class Discurso(Ability):
    name = "Discurso"
    cooldown = 7
    initial_cooldown = 6
    trigger_reach = 150
    channel_time = 1.4
    blast_radius = 165
    damage = 20
    sleep_time = 1.6

    def can_activate(self, match):
        return match.nearest_enemy(self.owner, reach=self.trigger_reach) is not None

    def cast(self, match):
        self.owner.add_status(match, Speaking(self.channel_time, self.blast_radius, self.damage,
                                              self.sleep_time))


class Barbecue(Channeling):
    """Stops to eat and drink, healing over time. A hard hit ruins the barbecue."""
    name = "Picanha e Cervejinha"
    label = "Churrasco"

    def __init__(self, duration, hps):
        super().__init__(duration)
        self.hps = hps

    def on_update(self, entity, match, dt):
        entity.hp = min(entity.max_hp, entity.hp + self.hps * dt)

    def draw(self, surface, entity, origin):
        center = entity.screen_pos(origin)
        r = entity.radius
        bob = math.sin(self.age * 8) * 2
        # Skewer of picanha on the left.
        x = center.x - r * 1.25
        pygame.draw.line(surface, (190, 190, 200), (x, center.y - r * 0.9 + bob), (x, center.y + r * 0.8 + bob), 3)
        for k in range(3):
            chunk = pygame.Rect(0, 0, 16, 11)
            chunk.center = (x, center.y - r * 0.55 + k * 13 + bob)
            pygame.draw.rect(surface, (150, 50, 40), chunk, border_radius=4)
            pygame.draw.rect(surface, (245, 225, 200), chunk.inflate(-2, -7).move(0, -3), border_radius=2)
        # Beer mug on the right.
        mug = pygame.Rect(0, 0, 18, 24)
        mug.center = (center.x + r * 1.25, center.y - bob)
        pygame.draw.rect(surface, (240, 170, 20), mug, border_radius=3)
        pygame.draw.rect(surface, (255, 255, 245), (mug.x, mug.y - 5, mug.w, 8), border_radius=4)
        pygame.draw.circle(surface, (230, 230, 230), (mug.right + 3, mug.centery), 6, width=2)


class PicanhaECervejinha(Ability):
    name = "Picanha e Cervejinha"
    cooldown = 12
    sfx = "beer_open"
    initial_cooldown = 8
    duration = 2.0
    heal_per_second = 10
    hp_below = 0.75       # only bothers when hurt
    break_damage = 8      # a hit at least this strong interrupts the meal

    def can_activate(self, match):
        comeback = next(a for a in self.owner.abilities if isinstance(a, VoltaPorCima))
        if comeback.used and match.time - comeback.used_at < comeback.line_time:
            return False   # let "Faz o L!" finish before the picanha line
        return self.owner.hp <= self.owner.max_hp * self.hp_below

    def cast(self, match):
        self.owner.add_status(match, Barbecue(self.duration, self.heal_per_second))


class Comeback(Status):
    name = "Volta por Cima"
    label = "Imune"

    def draw(self, surface, entity, origin):
        center = entity.screen_pos(origin)
        pulse = 0.5 + 0.5 * math.sin(self.age * 14)
        pygame.draw.circle(surface, GOLD, center, entity.radius + 4 + 3 * pulse, width=4)


class BigL(Entity):
    """Red "L" that zooms out of Lula and fades as it grows, timed to the "L" in
    the "Faz o L!" voice line. Shape "fx" never overlaps anything."""
    name = "Faz o L"
    shape = "fx"
    color = RED
    delay = 1.25        # seconds into the voice line where "L" is said
    grow_time = 1.0
    lifetime = delay + grow_time
    layer = 4
    _img: pygame.Surface | None = None

    def __init__(self, owner: Entity):
        super().__init__(owner.pos, owner.team, owner)

    def on_update(self, match, dt):
        self.pos = Vector2(self.owner.pos)

    @classmethod
    def image(cls) -> pygame.Surface:
        if cls._img is None:   # rendered once, large, then scaled down per frame
            cls._img = gfx.render_text("L", 240, RED, bold=True, outline=8, outline_color=(255, 255, 255))
        return cls._img

    def draw(self, surface, origin):
        t = (self.age - self.delay) / self.grow_time
        if t < 0:
            return
        ease = 1 - (1 - t) ** 3
        img = self.image()
        scale = (0.25 + 1.6 * ease)
        size = (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))
        frame = pygame.transform.smoothscale(img, size)
        frame.set_alpha(int(255 * (1 - t) ** 1.5))
        surface.blit(frame, frame.get_rect(center=self.screen_pos(origin)))


class VoltaPorCima(Ability):
    """Passive, once per match: the first time HP drops low (even to zero), Lula
    comes back with some HP and a moment of immunity."""
    name = "Volta por Cima"
    sfx = "cheer"
    threshold = 0.2
    heal = 22
    immune_time = 1.5
    line_time = 3.8       # length of the "Faz o L!" voice line

    def __init__(self, owner):
        super().__init__(owner)
        self.used = False
        self.used_at = 0.0

    @property
    def charge(self):
        return 0.0 if self.used else 1.0

    def hud_label(self, match):
        return None if self.used else "PASSIVE"

    def update(self, match, dt):
        pass

    def check(self, match):
        owner = self.owner
        if self.used or owner.hp >= owner.max_hp * self.threshold:
            return
        self.used = True
        self.used_at = match.time
        owner.hp = min(owner.max_hp, owner.hp + self.heal)
        for status in list(owner.statuses):
            if isinstance(status, Channeling):
                status.end()   # interrupted, so a speech in progress doesn't go off
                owner.remove_status(match, status)
        owner.add_status(match, Comeback(self.immune_time))
        match.spawn(BigL(owner))
        match.announce(owner, self.name, self)


@register
class Lula(Politician):
    key = "lula"
    name = "Lula"
    description = ("Long Discurso puts nearby enemies to sleep, stops for Picanha e Cervejinha "
                   "to heal, and makes a comeback once when nearly beaten.")
    color = RED
    max_hp = 100
    damage = 5
    speed = 300
    face_key = "lula"
    face_crop = (465, 370, 300)
    ability_types = (Discurso, PicanhaECervejinha, VoltaPorCima)

    def damage_multiplier(self, damage_type):
        return 0.0 if self.has_status(Comeback) else super().damage_multiplier(damage_type)

    def on_take_damage(self, match, amount, damage_type, source):
        meal = self.get_status(Barbecue)
        if meal and amount >= PicanhaECervejinha.break_damage:
            meal.end()
        next(a for a in self.abilities if isinstance(a, VoltaPorCima)).check(match)
