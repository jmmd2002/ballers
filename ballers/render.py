"""Draws a Match onto the 9:16 canvas. Visual effects (popups, flashes, shake,
callouts) are driven by match events, so the simulation stays render-agnostic."""
from __future__ import annotations

import random

import pygame
from pygame.math import Vector2

from . import gfx
from .config import CANVAS_WIDTH
from .entity import DamageType
from .events import AbilityUsed, Damage, EntityRemoved, WallHit
from .match import Match

BG = (16, 16, 22)
ARENA_BG = (26, 26, 36)
ARENA_BORDER = (220, 220, 235)
TEXT = (235, 235, 245)
MUTED = (140, 140, 160)

ARENA_TOP = 230
POPUP_LIFE = 0.9
FLASH_LIFE = 0.12
RING_LIFE = 0.25
CALLOUT_LIFE = 1.4
EFFECT_LIFE = {"smoke": 0.6, "burst": 0.35, "slash": 0.25, "crumble": 0.45}
DOT_POPUP_EVERY = 0.4   # seconds between summed popups for damage over time


class Renderer:
    def __init__(self, match: Match):
        self.match = match
        cfg = match.config
        self.arena_rect = pygame.Rect(0, 0, int(cfg.arena_width), int(cfg.arena_height))
        self.arena_rect.midtop = (CANVAS_WIDTH // 2, ARENA_TOP)
        self.popups: list[dict] = []
        self.rings: list[dict] = []
        self.effects: list[dict] = []
        self.callouts: list[dict] = []
        self.flash: dict[int, float] = {}
        self.dot: dict[int, dict] = {}   # damage over time collected per target
        self.shake = 0.0
        self.end_time = 0.0
        self._rng = random.Random()

        match.bus.subscribe(Damage, self._on_damage)
        match.bus.subscribe(WallHit, self._on_wall_hit)
        match.bus.subscribe(EntityRemoved, self._on_removed)
        match.bus.subscribe(AbilityUsed, self._on_ability)

    # --- Event handlers -----------------------------------------------------

    def _on_damage(self, e: Damage):
        color = e.source.color if e.source else TEXT
        if e.damage_type is DamageType.SLASHING and e.amount >= 1:   # every cut, flurry procs too
            self.effects.append({"kind": "slash", "pos": Vector2(e.target.pos), "age": 0.0,
                                 "radius": e.target.radius, "color": color,
                                 "angle": self._rng.uniform(0, 360)})
        if e.continuous:
            # Damage over time: sum it up and pop the total periodically.
            dot = self.dot.setdefault(id(e.target), {"target": e.target, "amount": 0.0,
                                                     "timer": 0.0, "color": color})
            dot["amount"] += e.amount
            dot["color"] = color
            if e.amount >= 1:
                self.flash[id(e.target)] = FLASH_LIFE * 0.6
            return
        self._hit(e.target, e.amount, color, Vector2(e.point))

    def _hit(self, target, amount, color, point):
        self.flash[id(target)] = FLASH_LIFE
        if not target.is_fighter:
            return
        self.popups.append({"text": f"-{amount:g}", "pos": point, "age": 0.0,
                            "size": int(30 + min(amount, 60) * 0.8), "color": color})
        self.shake = max(self.shake, min(4 + amount * 0.3, 18))

    def _update_dot(self, dt):
        for key, dot in list(self.dot.items()):
            dot["timer"] += dt
            target = dot["target"]
            if dot["timer"] >= DOT_POPUP_EVERY or not target.alive:
                if round(dot["amount"]) >= 1:
                    self._hit(target, round(dot["amount"]), dot["color"], Vector2(target.pos))
                    self.shake = min(self.shake, 3)
                del self.dot[key]

    def _on_wall_hit(self, e: WallHit):
        self.rings.append({"pos": Vector2(e.point), "age": 0.0, "color": e.entity.color})

    def _on_removed(self, e: EntityRemoved):
        kind = e.entity.death_effect
        self.shake = max(self.shake, e.entity.death_shake)
        if kind in EFFECT_LIFE:
            self.effects.append({"kind": kind, "pos": Vector2(e.entity.pos), "age": 0.0,
                                 "radius": e.entity.radius, "color": e.entity.color})

    def _on_ability(self, e: AbilityUsed):
        text = e.text.upper() + "!"
        for c in self.callouts:
            if c["caster"] is e.caster and c["text"] == text:   # chained recasts refresh one callout
                c["age"] = 0.0
                return
        stacked = sum(1 for c in self.callouts if c["caster"] is e.caster)
        self.callouts.append({"caster": e.caster, "text": text, "age": 0.0,
                              "pos": Vector2(e.caster.pos), "slot": stacked})

    # --- Per-frame ----------------------------------------------------------

    def update(self, dt: float):
        self._update_dot(dt)
        for group in (self.popups, self.rings, self.effects, self.callouts):
            for item in group:
                item["age"] += dt
        for p in self.popups:
            p["pos"].y -= 60 * dt
        for c in self.callouts:
            if c["caster"].alive:
                c["pos"] = Vector2(c["caster"].pos)
        self.popups = [p for p in self.popups if p["age"] < POPUP_LIFE]
        self.rings = [r for r in self.rings if r["age"] < RING_LIFE]
        self.effects = [f for f in self.effects if f["age"] < EFFECT_LIFE[f["kind"]]]
        self.callouts = [c for c in self.callouts if c["age"] < CALLOUT_LIFE]
        self.flash = {k: v - dt for k, v in self.flash.items() if v - dt > 0}
        self.shake = max(0.0, self.shake - 60 * dt)
        if self.match.over:
            self.end_time += dt

    def draw(self, surface: pygame.Surface, paused: bool = False):
        surface.fill(BG)
        self._draw_header(surface)

        shake = Vector2(self._rng.uniform(-1, 1), self._rng.uniform(-1, 1)) * self.shake
        arena = self.arena_rect.move(shake)
        origin = Vector2(arena.topleft)
        pygame.draw.rect(surface, ARENA_BG, arena)

        prev_clip = surface.get_clip()
        surface.set_clip(arena)
        for r in self.rings:
            t = r["age"] / RING_LIFE
            pygame.draw.circle(surface, gfx.lighten(r["color"], t * 0.6), origin + r["pos"],
                               4 + 18 * t, width=max(1, int(4 * (1 - t))))
        for entity in sorted(self.match.entities, key=lambda e: e.layer):
            entity.draw(surface, origin)
            for status in entity.statuses:
                status.draw(surface, entity, origin)
            if id(entity) in self.flash and entity.shape == "circle":
                self._draw_flash(surface, origin + entity.pos, entity.radius,
                                 self.flash[id(entity)] / FLASH_LIFE)
        for fx in self.effects:
            self._draw_effect(surface, origin, fx)
        surface.set_clip(prev_clip)

        pygame.draw.rect(surface, ARENA_BORDER, arena, width=4)

        for p in self.popups:
            t = p["age"] / POPUP_LIFE
            gfx.draw_text(surface, p["text"], p["size"], gfx.lighten(p["color"], 0.3), bold=True,
                          outline=3, alpha=int(255 * (1 - t * t)), center=origin + p["pos"])
        for c in self.callouts:
            self._draw_callout(surface, origin, c)

        self._draw_abilities(surface)
        if paused:
            gfx.draw_text(surface, "PAUSED", 40, (255, 210, 90), bold=True, outline=3,
                          center=self.arena_rect.center)
        if self.match.over:
            self._draw_result(surface)

    # --- Effects ------------------------------------------------------------

    @staticmethod
    def _draw_flash(surface, center, radius, strength):
        overlay = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (255, 255, 255, int(220 * strength)), (radius, radius), radius)
        surface.blit(overlay, overlay.get_rect(center=center))

    def _draw_effect(self, surface, origin, fx):
        t = fx["age"] / EFFECT_LIFE[fx["kind"]]
        center = origin + fx["pos"]
        r = fx["radius"]
        size = int(r * 5)
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        mid = Vector2(size / 2, size / 2)
        alpha = int(230 * (1 - t))
        if fx["kind"] == "smoke":
            for i in range(7):
                offset = Vector2(1, 0).rotate(i * 360 / 7 + 20) * r * (0.3 + 0.9 * t)
                pygame.draw.circle(overlay, (225, 225, 230, alpha), mid + offset, r * (0.5 + 0.5 * t))
            pygame.draw.circle(overlay, (245, 245, 250, alpha), mid, r * (0.7 + 0.4 * t))
        elif fx["kind"] == "burst":
            pygame.draw.circle(overlay, (*gfx.lighten(fx["color"], 0.4), alpha), mid,
                               r * (1 + 2 * t), width=max(1, int(6 * (1 - t))))
            pygame.draw.circle(overlay, (255, 255, 255, alpha), mid, r * (1 - t))
        elif fx["kind"] == "slash":
            # A bright cut sweeping across the target.
            d = Vector2(1, 0).rotate(fx["angle"])
            n = Vector2(-d.y, d.x)
            head, tail = min(t * 2.5, 1.0), max(0.0, t * 2.5 - 0.6)
            start = mid + d * r * (-1.3 + 2.6 * tail)
            end = mid + d * r * (-1.3 + 2.6 * head)
            bow = n * r * 0.25
            for width, color in ((7, (*gfx.lighten(fx["color"], 0.2), alpha)), (3, (255, 255, 255, alpha))):
                pygame.draw.lines(overlay, color, False, [start, (start + end) / 2 + bow, end], width)
        elif fx["kind"] == "crumble":
            # Dust cloud plus chunks of debris flung outwards.
            pygame.draw.circle(overlay, (200, 190, 175, alpha // 2), mid, r * (0.7 + 1.1 * t))
            for i in range(8):
                d = Vector2(1, 0).rotate(i * 45 + fx["radius"] * 7)
                chunk = mid + d * r * (0.3 + 1.7 * t)
                size = max(1.0, r * (0.28 + 0.1 * (i % 3)) * (1 - t))
                pts = [chunk + d.rotate(a + i * 40 + t * 300) * size for a in (0, 130, 230)]
                pygame.draw.polygon(overlay, (*fx["color"], alpha), pts)
        surface.blit(overlay, overlay.get_rect(center=center))

    def _draw_callout(self, surface, origin, c):
        t = c["age"] / CALLOUT_LIFE
        pop = min(c["age"] / 0.12, 1.0)
        caster = c["caster"]
        pos = origin + c["pos"] - Vector2(0, caster.radius + 22 + c["slot"] * 30 + 20 * t)
        img = gfx.render_text(c["text"], int(22 + 10 * pop), gfx.lighten(caster.color, 0.35),
                              bold=True, outline=3)
        img.set_alpha(int(255 * min(1.0, (1 - t) * 3)))
        rect = img.get_rect(center=pos)
        rect.clamp_ip(surface.get_rect().inflate(-16, 0))
        surface.blit(img, rect)

    # --- HUD ----------------------------------------------------------------

    def _draw_header(self, surface):
        fighters = self.match.fighters
        title = "  VS  ".join(f.name.upper() for f in fighters)
        size = 44
        while size > 24 and gfx.font(size, True).size(title)[0] > CANVAS_WIDTH - 30:
            size -= 2   # long names (e.g. "Flávio Bolsonaro") shrink the title to fit
        gfx.draw_text(surface, title, size, TEXT, bold=True, center=(CANVAS_WIDTH // 2, 45))

        margin, gap = 20, 20
        bar_w = (CANVAS_WIDTH - 2 * margin - gap * (len(fighters) - 1)) // len(fighters)
        for i, fighter in enumerate(fighters):
            x = margin + i * (bar_w + gap)
            gfx.draw_text(surface, fighter.name, 30, gfx.lighten(fighter.color, 0.25), bold=True,
                          topleft=(x, 85))
            bar = pygame.Rect(x, 112, bar_w, 34)
            pygame.draw.rect(surface, (45, 45, 58), bar, border_radius=6)
            frac = fighter.hp / fighter.max_hp
            if frac > 0:
                fill = bar.copy()
                fill.width = max(1, int(bar_w * frac))
                pygame.draw.rect(surface, fighter.color, fill, border_radius=6)
            pygame.draw.rect(surface, gfx.darken(fighter.color, 0.5), bar, width=2, border_radius=6)
            gfx.draw_text(surface, f"{fighter.hp:.0f} / {fighter.max_hp}", 26, (255, 255, 255),
                          bold=True, outline=2, center=bar.center)
            gfx.draw_text(surface, fighter.status_line(self.match), 26, MUTED, topleft=(x, 156))

    def _draw_abilities(self, surface):
        """Cooldown bars for each fighter's abilities, under the arena."""
        fighters = self.match.fighters
        margin, gap = 20, 20
        col_w = (CANVAS_WIDTH - 2 * margin - gap * (len(fighters) - 1)) // len(fighters)
        for i, fighter in enumerate(fighters):
            x = margin + i * (col_w + gap)
            y = self.arena_rect.bottom + 28
            for ability in fighter.abilities:
                label = ability.hud_label(self.match) or ("READY" if ability.ready else "")
                done = bool(label)
                name_color = gfx.lighten(fighter.color, 0.35) if done else TEXT
                size = 24
                room = col_w - (gfx.font(22).size(label)[0] + 8 if label else 0)
                while size > 16 and gfx.font(size, True).size(ability.name)[0] > room:
                    size -= 1   # long names make room for the READY label
                gfx.draw_text(surface, ability.name, size, name_color, bold=True, topleft=(x, y))
                if label:
                    gfx.draw_text(surface, label, 22, name_color, topright=(x + col_w, y + 2))
                bar = pygame.Rect(x, y + 24, col_w, 12)
                pygame.draw.rect(surface, (45, 45, 58), bar, border_radius=6)
                fill = bar.copy()
                fill.width = col_w if done else max(0, int(col_w * ability.charge))
                if fill.width:
                    color = gfx.lighten(fighter.color, 0.3) if done else gfx.darken(fighter.color, 0.15)
                    pygame.draw.rect(surface, color, fill, border_radius=6)
                y += 58

    def _draw_result(self, surface):
        t = min(self.end_time / 0.4, 1.0)
        veil = pygame.Surface(self.arena_rect.size, pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(150 * t)))
        surface.blit(veil, self.arena_rect)
        winner = self.match.winner
        if winner:
            text, color = f"{winner.name.upper()} WINS!", winner.color
        else:
            text, color = "DRAW!", TEXT
        img = gfx.render_text(text, int(40 + 30 * t), gfx.lighten(color, 0.45), bold=True, outline=4)
        max_w = self.arena_rect.width - 30   # long names shrink to stay inside the arena
        if img.get_width() > max_w:
            img = pygame.transform.smoothscale(img, (max_w, int(img.get_height() * max_w / img.get_width())))
        surface.blit(img, img.get_rect(center=self.arena_rect.center))
