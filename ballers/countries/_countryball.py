"""Shared pieces for countryball fighters: the country's flag (from _flags.py)
clipped to the ball, an outline and the classic white countryball eyes (no pupils)."""
import pygame
from pygame.math import Vector2

from ..fighter import Fighter
from ._flags import OWN_FACE, paint

OUTLINE = (20, 20, 26)
_balls: dict[tuple[str, int], pygame.Surface] = {}


def flag_ball(key: str, size: int) -> pygame.Surface:
    """Circular cutout of a country's flag painted over the full square."""
    cache_key = (key, size)
    if cache_key not in _balls:
        flag = pygame.Surface((size, size), pygame.SRCALPHA)
        paint(key, flag)
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (size / 2, size / 2), size / 2)
        flag.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        _balls[cache_key] = flag
    return _balls[cache_key]


def draw_eyes(surface, center: Vector2, radius: float, look: Vector2):
    """White oval eyes, shifted a little toward where the ball is heading."""
    shift = look * radius * 0.12
    w, h = radius * 0.3, radius * 0.42
    for side in (-1, 1):
        eye = pygame.Rect(0, 0, w, h)
        eye.center = center + Vector2(side * radius * 0.33, -radius * 0.08) + shift
        pygame.draw.ellipse(surface, (255, 255, 255), eye)
        pygame.draw.ellipse(surface, OUTLINE, eye, width=2)


def draw_countryball(surface, center: Vector2, radius: float, key: str, look: Vector2):
    img = flag_ball(key, int(radius * 2))
    surface.blit(img, img.get_rect(center=center))
    pygame.draw.circle(surface, OUTLINE, center, radius, width=3)
    if key not in OWN_FACE:
        draw_eyes(surface, center, radius, look)


class Countryball(Fighter):
    """A country fighter; `key` must match its entry in _roster.py / _flags.py."""
    category = "countries"
    damage = 5

    def draw(self, surface, origin):
        draw_countryball(surface, self.screen_pos(origin), self.radius, self.key, self.direction)
