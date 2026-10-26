"""Shared visuals for Naruto-themed fighters."""
import math

import pygame
from pygame.math import Vector2

from .. import gfx


def polar(center: Vector2, angle_deg: float, dist: float) -> Vector2:
    """Point around center; 0deg = right, -90deg = straight up (screen coords)."""
    a = math.radians(angle_deg)
    return center + Vector2(math.cos(a), math.sin(a)) * dist


def draw_headband(surface, center: Vector2, radius: float):
    band = pygame.Rect(0, 0, radius * 1.5, radius * 0.32)
    band.center = (center.x, center.y - radius * 0.55)
    plate = pygame.Rect(0, 0, radius * 0.7, radius * 0.38)
    plate.center = band.center
    pygame.draw.rect(surface, (30, 40, 80), band, border_radius=3)
    pygame.draw.rect(surface, (195, 200, 215), plate, border_radius=3)
    pygame.draw.rect(surface, (110, 115, 130), plate, width=1, border_radius=3)
    pygame.draw.circle(surface, (90, 95, 110), plate.center, radius * 0.1, width=2)


def draw_body(surface, center: Vector2, radius: float, color, hair=None, outline=None):
    """Face circle, then hair (a callable(surface, center, radius)), then headband."""
    pygame.draw.circle(surface, color, center, radius)
    pygame.draw.circle(surface, outline or gfx.darken(color, 0.5), center, radius, width=3)
    if hair:
        hair(surface, center, radius)
    draw_headband(surface, center, radius)


def draw_hair(surface, center, radius, color, profile, outline=None, hairline=-0.2):
    """One hair silhouette. profile: (angle_deg, radius_factor) points running
    over the top of the head from left to right; closed along the hairline."""
    top = [polar(center, a, radius * f) for a, f in profile]
    shape = top + [center + Vector2(radius * 0.95, radius * hairline),
                   center + Vector2(-radius * 0.95, radius * hairline)]
    pygame.draw.polygon(surface, color, shape)
    pygame.draw.lines(surface, outline or gfx.darken(color, 0.4), False, top, 2)


def tufted_profile(start, end, tufts, tip, valley=1.0, sweep=5.0):
    """Crown of tufts, tallest in the middle, tips leaning slightly clockwise."""
    points = []
    span = end - start
    for i in range(2 * tufts + 1):
        angle = start + span * i / (2 * tufts)
        if i % 2:
            height = valley + (tip - valley) * (0.55 + 0.45 * math.sin(math.pi * i / (2 * tufts)))
            points.append((angle + sweep, height))
        else:
            points.append((angle, valley))
    return points


def smooth_profile(start, end, shape, steps=24):
    """Rounded hair: shape(t) gives the radius factor for t in 0..1."""
    return [(start + (end - start) * k / steps, shape(k / steps)) for k in range(steps + 1)]


def _tomoe(surface, center, ring_r, size, angle_deg, color):
    """Comma shape: round head on the ring with a tapering tail trailing behind it."""
    head = polar(center, angle_deg, ring_r)
    steps = 8
    outer, inner = [], []
    for k in range(steps + 1):
        f = k / steps
        a = angle_deg - 55 * f
        dist = ring_r + size * 0.5 * f
        w = size * (1 - f) * 0.95
        outer.append(polar(center, a, dist + w))
        inner.append(polar(center, a, dist - w))
    pygame.draw.polygon(surface, color, outer + inner[::-1])
    pygame.draw.circle(surface, color, head, size)


def draw_sharingan(surface, center: Vector2, radius: float, spin_deg: float = 0.0, alpha: int = 255):
    """Red iris, dark ring, pupil and three rotating tomoe."""
    target = surface
    if alpha < 255:
        size = int(radius * 2 + 4)
        target = pygame.Surface((size, size), pygame.SRCALPHA)
        offset, center = center, Vector2(size / 2, size / 2)
    black = (10, 5, 5)
    pygame.draw.circle(target, (205, 15, 25), center, radius)
    pygame.draw.circle(target, (120, 0, 10), center, radius * 0.95, width=max(1, int(radius * 0.08)))
    ring_r = radius * 0.58
    pygame.draw.circle(target, (90, 0, 8), center, ring_r, width=max(1, int(radius * 0.06)))
    for k in range(3):
        _tomoe(target, center, ring_r, radius * 0.16, spin_deg + k * 120, black)
    pygame.draw.circle(target, black, center, radius * 0.22)
    pygame.draw.circle(target, black, center, radius, width=max(1, int(radius * 0.07)))
    if target is not surface:
        target.set_alpha(alpha)
        surface.blit(target, target.get_rect(center=offset))
