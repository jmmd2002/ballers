"""Shared pieces for politician fighters: photo faces (assets/faces/<key>.jpg)."""
from pathlib import Path

import pygame
from pygame.math import Vector2

from .. import gfx
from ..fighter import Fighter

FACES_DIR = Path(__file__).resolve().parents[2] / "assets" / "faces"
_faces: dict[tuple[str, int], pygame.Surface] = {}


def face(key: str, crop: tuple[int, int, int], size: int) -> pygame.Surface:
    """Circular cutout of a photo. crop = (center x, center y, radius) in source pixels."""
    cache_key = (key, size)
    if cache_key not in _faces:
        photo = pygame.image.load(str(FACES_DIR / f"{key}.jpg"))
        cx, cy, r = crop
        square = photo.subsurface(pygame.Rect(cx - r, cy - r, 2 * r, 2 * r))
        img = pygame.Surface((size, size), pygame.SRCALPHA)
        img.blit(pygame.transform.smoothscale(square, (size, size)), (0, 0))
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (size / 2, size / 2), size / 2)
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        _faces[cache_key] = img
    return _faces[cache_key]


def draw_face(surface, center: Vector2, radius: float, key: str, crop, ring_color):
    img = face(key, crop, int(radius * 2))
    surface.blit(img, img.get_rect(center=center))
    pygame.draw.circle(surface, ring_color, center, radius, width=3)


def draw_bubble(surface, anchor: Vector2, text: str, color=(255, 255, 255), size=22):
    """Speech bubble below anchor, its tail pointing up at it (callouts go above balls)."""
    img = gfx.render_text(text, size, (20, 20, 25), bold=True)
    rect = img.get_rect(midtop=(anchor.x, anchor.y + 10)).inflate(14, 8)
    rect.clamp_ip(surface.get_clip())
    pygame.draw.polygon(surface, color, [(anchor.x - 6, rect.top + 1), (anchor.x + 6, rect.top + 1),
                                         (anchor.x, anchor.y)])
    pygame.draw.rect(surface, color, rect, border_radius=8)
    surface.blit(img, img.get_rect(center=rect.center))


class Politician(Fighter):
    category = "politics"
    face_key = ""
    face_crop = (0, 0, 1)

    def draw(self, surface, origin):
        draw_face(surface, self.screen_pos(origin), self.radius, self.face_key, self.face_crop,
                  self.color)
