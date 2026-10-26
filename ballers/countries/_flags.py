"""Every country's flag, drawn in code with a tiny drawing vocabulary.

A flag is a list of ops; each op paints onto a surface of any size using
coordinates relative to it (x, y in 0..1 of width/height, radii and
thicknesses as a fraction of the height). So the same flag works as a 3:2
rectangle on the bracket and as a square clipped into a countryball.
Complex coats of arms are simplified to a recognisable shape."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

# --- Palette ----------------------------------------------------------------

W = (255, 255, 255)
K = (20, 20, 20)
R = (206, 17, 38)
DR = (160, 20, 40)        # dark red / maroon
G = (0, 122, 61)
DG = (0, 98, 51)
Y = (252, 209, 22)
GOLD = (230, 180, 30)
O = (255, 130, 0)
B = (0, 56, 168)
NAVY = (1, 33, 105)
LB = (90, 170, 230)
SKY = (117, 170, 219)
BROWN = (130, 80, 40)


# --- Ops --------------------------------------------------------------------

def _p(s, x, y) -> Vector2:
    w, h = s.get_size()
    return Vector2(x * w, y * h)


def fill(c):
    return lambda s: s.fill(c)


def H(*colors, w=None):
    """Horizontal stripes, top to bottom, with optional relative heights."""
    def op(s):
        sw, sh = s.get_size()
        weights = w or [1] * len(colors)
        total, y = sum(weights), 0.0
        for color, weight in zip(colors, weights):
            band = sh * weight / total
            pygame.draw.rect(s, color, pygame.Rect(0, round(y), sw, math.ceil(band) + 1))
            y += band
    return op


def V(*colors, w=None):
    """Vertical stripes, hoist to fly."""
    def op(s):
        sw, sh = s.get_size()
        weights = w or [1] * len(colors)
        total, x = sum(weights), 0.0
        for color, weight in zip(colors, weights):
            band = sw * weight / total
            pygame.draw.rect(s, color, pygame.Rect(round(x), 0, math.ceil(band) + 1, sh))
            x += band
    return op


def rect(x0, y0, x1, y1, c):
    def op(s):
        a, b = _p(s, x0, y0), _p(s, x1, y1)
        pygame.draw.rect(s, c, pygame.Rect(round(a.x), round(a.y), math.ceil(b.x - a.x), math.ceil(b.y - a.y)))
    return op


def poly(points, c):
    return lambda s: pygame.draw.polygon(s, c, [_p(s, x, y) for x, y in points])


def disc(x, y, r, c):
    return lambda s: pygame.draw.circle(s, c, _p(s, x, y), r * s.get_height())


def ring(x, y, r, c, t=0.03):
    return lambda s: pygame.draw.circle(s, c, _p(s, x, y), r * s.get_height(),
                                        width=max(1, round(t * s.get_height())))


def star_points(center: Vector2, outer: float, n=5, inner=0.38, rot=-90.0) -> list[Vector2]:
    pts = []
    for i in range(2 * n):
        r = outer if i % 2 == 0 else outer * inner
        a = math.radians(rot + i * 180 / n)
        pts.append(center + Vector2(math.cos(a), math.sin(a)) * r)
    return pts


def star(x, y, r, c, n=5, inner=0.38, rot=-90.0):
    return lambda s: pygame.draw.polygon(s, c, star_points(_p(s, x, y), r * s.get_height(), n, inner, rot))


def stars(points, r, c, **kw):
    ops = [star(x, y, r, c, **kw) for x, y in points]
    return lambda s: [op(s) for op in ops]


def line(x0, y0, x1, y1, c, t):
    """Thick straight band between two points (t = thickness, fraction of height)."""
    def op(s):
        a, b = _p(s, x0, y0), _p(s, x1, y1)
        d = b - a
        if d.length_squared() == 0:
            return
        n = Vector2(-d.y, d.x).normalize() * t * s.get_height() / 2
        pygame.draw.polygon(s, c, [a + n, b + n, b - n, a - n])
    return op


def cross(c, t=0.2, x=0.5, y=0.5):
    """Upright cross; x moves the vertical bar (Nordic crosses sit toward the hoist)."""
    def op(s):
        sw, sh = s.get_size()
        th = t * sh
        pygame.draw.rect(s, c, pygame.Rect(round(x * sw - th / 2), 0, math.ceil(th), sh))
        pygame.draw.rect(s, c, pygame.Rect(0, round(y * sh - th / 2), sw, math.ceil(th)))
    return op


def nordic(c, t=0.2, inner=None, ti=0.1):
    """Nordic cross, optionally with an inner cross of another color."""
    ops = [cross(c, t, x=0.36)] + ([cross(inner, ti, x=0.36)] if inner else [])
    return lambda s: [op(s) for op in ops]


def saltire(c, t=0.2):
    a, b = line(0, 0, 1, 1, c, t), line(0, 1, 1, 0, c, t)
    return lambda s: (a(s), b(s))


def crescent(x, y, r, c, off=0.3, cut=0.82, angle=0.0):
    """Disc minus an offset disc; `angle` is where the opening faces (0 = fly side)."""
    def op(s):
        layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        center, rad = _p(s, x, y), r * s.get_height()
        pygame.draw.circle(layer, c, center, rad)
        shift = Vector2(math.cos(math.radians(angle)), math.sin(math.radians(angle))) * rad * off
        pygame.draw.circle(layer, (0, 0, 0, 0), center + shift, rad * cut)
        s.blit(layer, (0, 0))
    return op


def clip(points, *ops):
    """Paint ops only inside a polygon."""
    def op(s):
        layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        for o in ops:
            o(layer)
        mask = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), [_p(s, x, y) for x, y in points])
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(layer, (0, 0))
    return op


def sub(x0, y0, x1, y1, *ops):
    """Paint ops into a sub-rectangle as if it were its own flag (cantons)."""
    def op(s):
        a, b = _p(s, x0, y0), _p(s, x1, y1)
        area = s.subsurface(pygame.Rect(round(a.x), round(a.y), max(1, round(b.x - a.x)), max(1, round(b.y - a.y))))
        for o in ops:
            o(area)
    return op


def sun(x, y, r, c, rays=12, ray_len=0.6, core=None):
    """Disc with triangular rays."""
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        for i in range(rays):
            a = math.radians(i * 360 / rays)
            tip = center + Vector2(math.cos(a), math.sin(a)) * rad * (1 + ray_len)
            side = Vector2(-math.sin(a), math.cos(a)) * rad * math.sin(math.pi / rays) * 1.1
            base = center + Vector2(math.cos(a), math.sin(a)) * rad * 0.8
            pygame.draw.polygon(s, c, [base + side, tip, base - side])
        pygame.draw.circle(s, core or c, center, rad)
    return op


def emblem(x, y, r, c, inner=None):
    """Stand-in for a detailed coat of arms: a small shield shape."""
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        shield = [center + Vector2(-rad * 0.8, -rad), center + Vector2(rad * 0.8, -rad),
                  center + Vector2(rad * 0.8, rad * 0.2), center + Vector2(0, rad),
                  center + Vector2(-rad * 0.8, rad * 0.2)]
        pygame.draw.polygon(s, c, shield)
        if inner:
            pygame.draw.polygon(s, inner, [center + (p - center) * 0.6 for p in shield])
    return op


def stripes_n(n, a, b):
    """n alternating stripes starting with a."""
    return H(*[a if i % 2 == 0 else b for i in range(n)])


def union_jack():
    return [fill(NAVY), saltire(W, 0.2), saltire(R, 0.07), cross(W, 0.33), cross(R, 0.2)]


UJ = union_jack()


def us_canton():
    pts = [(0.08 + 0.168 * (i % 6) + (0.084 if (i // 6) % 2 else 0), 0.1 + 0.2 * (i // 6))
           for i in range(30) if not ((i // 6) % 2 and i % 6 == 5)]
    return [fill(NAVY), stars(pts, 0.055, W)]


def eagle(x, y, r, c):
    """Simplified spread eagle silhouette."""
    pts = [(-1, -0.6), (-0.4, -0.2), (-0.2, -0.8), (0, -0.4), (0.2, -0.8), (0.4, -0.2), (1, -0.6),
           (0.7, 0.2), (0.25, 0.25), (0.35, 0.9), (0, 0.6), (-0.35, 0.9), (-0.25, 0.25), (-0.7, 0.2)]
    def op(s):
        sw, sh = s.get_size()
        center, rad = _p(s, x, y), r * sh
        pygame.draw.polygon(s, c, [center + Vector2(px, py) * rad for px, py in pts])
    return op


def maple(x, y, r, c):
    pts = [(0, -1), (0.18, -0.62), (0.4, -0.72), (0.32, -0.2), (0.75, -0.55), (0.68, -0.3), (1, -0.32),
           (0.85, 0.05), (0.95, 0.15), (0.45, 0.45), (0.5, 0.6), (0.05, 0.52), (0.05, 1), (-0.05, 1),
           (-0.05, 0.52), (-0.5, 0.6), (-0.45, 0.45), (-0.95, 0.15), (-0.85, 0.05), (-1, -0.32),
           (-0.68, -0.3), (-0.75, -0.55), (-0.32, -0.2), (-0.4, -0.72), (-0.18, -0.62)]
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        pygame.draw.polygon(s, c, [center + Vector2(px, py) * rad for px, py in pts])
    return op


def serrated(x, c, points, depth=0.08):
    """Hoist band of color c ending at x with a zigzag edge (Bahrain, Qatar)."""
    pts = [(0, 0), (x, 0)]
    for i in range(points):
        pts += [(x + depth, (i + 0.5) / points), (x, (i + 1) / points)]
    return poly(pts + [(0, 1)], c)


def taegeuk(x, y, r):
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        pygame.draw.circle(s, (0, 71, 160), center, rad)
        top = pygame.Rect(0, 0, rad * 2, rad * 2)
        top.center = center
        layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(layer, R, center, rad, draw_top_left=True, draw_top_right=True)
        pygame.draw.circle(layer, R, center + Vector2(rad / 2, 0), rad / 2)
        pygame.draw.circle(layer, (0, 0, 0, 0), center - Vector2(rad / 2, 0), rad / 2)
        s.blit(layer, (0, 0))
        pygame.draw.circle(s, (0, 71, 160), center - Vector2(rad / 2, 0), rad / 2)
    return op


def trigram(x, y, r, angle, pattern):
    """Three bars (pattern: 1 = solid, 0 = broken), rotated around the flag center."""
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        d = Vector2(1, 0).rotate(angle)
        n = Vector2(-d.y, d.x)
        for i, solid in enumerate(pattern):
            mid = center + d * (i - 1) * rad * 0.42
            segs = [(-1, 1)] if solid else [(-1, -0.12), (0.12, 1)]
            for a, b in segs:
                p0, p1 = mid + n * a * rad * 0.8, mid + n * b * rad * 0.8
                th = d * rad * 0.15
                pygame.draw.polygon(s, K, [p0 - th, p1 - th, p1 + th, p0 + th])
    return op


def shahada(x0, x1, y, c, t=0.06):
    """Calligraphy stand-in: a wavy line of strokes."""
    def op(s):
        sw, sh = s.get_size()
        n = 14
        pts = [Vector2((x0 + (x1 - x0) * i / n) * sw, y * sh + math.sin(i * 1.7) * t * sh) for i in range(n + 1)]
        pygame.draw.lines(s, c, False, pts, max(1, round(t * sh * 0.6)))
        for i in range(0, n, 3):
            p = pts[i]
            pygame.draw.line(s, c, p, p - Vector2(0, t * sh * 1.6), max(1, round(t * sh * 0.4)))
    return op


def glyph(text, x, y, size, c):
    """A character of text; size is its height as a fraction of the flag height."""
    def op(s):
        from .. import gfx
        img = gfx.render_text(text, max(1, round(size * s.get_height())), c, bold=True)
        s.blit(img, img.get_rect(center=_p(s, x, y)))
    return op


def oval(x, y, rx, ry, c, width=0):
    """Ellipse; radii as fractions of the height."""
    def op(s):
        h = s.get_height()
        r = pygame.Rect(0, 0, 2 * rx * h, 2 * ry * h)
        r.center = _p(s, x, y)
        pygame.draw.ellipse(s, c, r, width=round(width * h))
    return op


def arc(x, y, r, start, end, c, t):
    """Circular arc, angles in degrees counter-clockwise from the fly side (pygame convention)."""
    def op(s):
        h = s.get_height()
        rect = pygame.Rect(0, 0, 2 * r * h, 2 * r * h)
        rect.center = _p(s, x, y)
        pygame.draw.arc(s, c, rect, math.radians(start), math.radians(end), max(1, round(t * h)))
    return op


def star_of_david(x, y, r, c, t=0.025):
    def op(s):
        center, rad = _p(s, x, y), r * s.get_height()
        for rot in (-90, 90):
            pts = [center + Vector2(math.cos(math.radians(rot + k * 120)), math.sin(math.radians(rot + k * 120))) * rad
                   for k in range(3)]
            pygame.draw.polygon(s, c, pts, width=max(1, round(t * s.get_height())))
    return op


# --- Flags ------------------------------------------------------------------

FLAGS_SINGAPORE = [H((239, 51, 64), W), crescent(0.17, 0.25, 0.17, W, off=0.3, cut=0.82),
                  stars([(0.27, 0.13), (0.21, 0.24), (0.33, 0.24), (0.23, 0.36), (0.31, 0.36)], 0.035, W)]

FLAGS: dict[str, list] = {
    "afghanistan": [V(K, (190, 0, 0), (0, 122, 54)), ring(0.5, 0.5, 0.2, W, 0.035), rect(0.46, 0.42, 0.54, 0.58, W)],
    "albania": [fill((228, 30, 32)), eagle(0.5, 0.5, 0.33, K)],
    "algeria": [V((0, 98, 51), W), crescent(0.5, 0.5, 0.25, (210, 16, 52), off=0.3, cut=0.8),
                star(0.56, 0.5, 0.12, (210, 16, 52), rot=180)],
    "andorra": [V((16, 6, 159), (254, 223, 0), (213, 0, 50), w=(8, 9, 8)), emblem(0.5, 0.5, 0.17, (200, 150, 30), (213, 0, 50))],
    "angola": [H((204, 9, 47), K), sun(0.5, 0.5, 0.12, (255, 203, 0), rays=5, ray_len=0.5, core=(255, 203, 0)),
               disc(0.5, 0.5, 0.08, (204, 9, 47))],
    "antigua_and_barbuda": [fill((206, 17, 38)), clip([(0, 0), (1, 0), (0.5, 1)], fill(K),
                            sun(0.5, 0.36, 0.12, (252, 209, 22), rays=16, ray_len=0.5), rect(0, 0.4, 1, 0.62, (0, 114, 198)),
                            rect(0, 0.62, 1, 1, W))],
    "argentina": [H((116, 172, 223), W, (116, 172, 223)), sun(0.5, 0.5, 0.08, (246, 180, 14), rays=16, ray_len=0.5)],
    "armenia": [H((217, 0, 18), (0, 51, 160), (242, 168, 0))],
    "australia": [fill(NAVY), sub(0, 0, 0.5, 0.5, *UJ), star(0.25, 0.75, 0.15, W, n=7, inner=0.45),
                  stars([(0.75, 0.2), (0.62, 0.45), (0.75, 0.85), (0.87, 0.4)], 0.07, W, n=7, inner=0.45),
                  star(0.81, 0.55, 0.04, W)],
    "austria": [H((200, 16, 46), W, (200, 16, 46))],
    "azerbaijan": [H((0, 181, 226), (239, 51, 64), (80, 158, 47)), crescent(0.48, 0.5, 0.13, W, off=0.25, cut=0.82),
                   star(0.57, 0.5, 0.07, W, n=8, inner=0.5)],
    "bahamas": [H((0, 171, 201), (250, 224, 66), (0, 171, 201)), poly([(0, 0), (0.43, 0.5), (0, 1)], K)],
    "bahrain": [fill((206, 17, 38)), serrated(0.25, W, 5)],
    "bangladesh": [fill((0, 106, 78)), disc(0.45, 0.5, 0.3, (244, 42, 65))],
    "barbados": [V((0, 38, 127), (255, 199, 38), (0, 38, 127)),
                 poly([(0.47, 0.75), (0.47, 0.5), (0.4, 0.45), (0.4, 0.25), (0.44, 0.35), (0.48, 0.42), (0.48, 0.2),
                       (0.5, 0.15), (0.52, 0.2), (0.52, 0.42), (0.56, 0.35), (0.6, 0.25), (0.6, 0.45), (0.53, 0.5),
                       (0.53, 0.75)], K)],
    "belarus": [H((200, 49, 62), (77, 153, 69), w=(2, 1)), rect(0, 0, 0.11, 1, W),
                *[poly([(0.055, 0.04 + i * 0.16), (0.1, 0.12 + i * 0.16), (0.055, 0.2 + i * 0.16), (0.01, 0.12 + i * 0.16)],
                       (200, 49, 62)) for i in range(6)]],
    "belgium": [V(K, (253, 218, 36), (239, 51, 64))],
    "belize": [H((206, 17, 38), (0, 56, 147), (206, 17, 38), w=(1, 8, 1)), disc(0.5, 0.5, 0.3, W),
               ring(0.5, 0.5, 0.28, (40, 130, 60), 0.05), emblem(0.5, 0.5, 0.12, (100, 140, 200))],
    "benin": [H((252, 209, 22), (232, 17, 45)), rect(0, 0, 0.4, 1, (0, 135, 81))],
    "bhutan": [fill((255, 78, 18)), poly([(0, 0), (1, 0), (0, 1)], (255, 213, 32)),
               line(0.25, 0.7, 0.75, 0.3, W, 0.16), disc(0.28, 0.68, 0.09, W), disc(0.72, 0.32, 0.07, W)],
    "bolivia": [H((213, 43, 30), (249, 228, 0), (0, 122, 51))],
    "bosnia_and_herzegovina": [fill((0, 35, 149)), poly([(0.27, 0), (0.77, 0), (0.77, 1)], (254, 203, 0)),
                               stars([(0.2 + 0.1 * i, -0.05 + 0.15 * i) for i in range(9)], 0.06, W)],
    "botswana": [H((117, 170, 219), W, K, W, (117, 170, 219), w=(9, 1, 4, 1, 9))],
    "brazil": [fill((0, 156, 59)), poly([(0.08, 0.5), (0.5, 0.1), (0.92, 0.5), (0.5, 0.9)], (255, 223, 0)),
               disc(0.5, 0.5, 0.25, (0, 39, 118)), line(0.3, 0.42, 0.7, 0.55, W, 0.05)],
    "brunei": [fill((247, 224, 23)), poly([(0, 0.08), (0, 0.35), (1, 0.85), (1, 0.6)], W),
               poly([(0, 0.35), (0, 0.55), (1, 1.0), (1, 0.85)], K), crescent(0.5, 0.52, 0.2, (206, 17, 38), angle=-90, off=0.35),
               rect(0.48, 0.3, 0.52, 0.6, (206, 17, 38))],
    "bulgaria": [H(W, (0, 150, 110), (214, 38, 18))],
    "burkina_faso": [H((239, 43, 45), (0, 158, 73)), star(0.5, 0.5, 0.17, (252, 209, 22))],
    "burundi": [fill((206, 17, 38)), poly([(0, 0), (0.5, 0.5), (0, 1)], (30, 181, 58)),
                poly([(1, 0), (0.5, 0.5), (1, 1)], (30, 181, 58)), saltire(W, 0.15), disc(0.5, 0.5, 0.27, W),
                stars([(0.5, 0.37), (0.43, 0.58), (0.57, 0.58)], 0.07, (206, 17, 38), n=6, inner=0.5)],
    "cabo_verde": [H((0, 56, 147), W, (207, 32, 39), W, (0, 56, 147), w=(6, 1, 1, 1, 3)),
                   stars([(0.375 + 0.25 * math.cos(math.radians(a)), 0.625 + 0.25 * math.sin(math.radians(a)))
                          for a in range(0, 360, 36)], 0.045, (247, 214, 23))],
    "cambodia": [H((3, 46, 161), (224, 0, 37), (3, 46, 161), w=(1, 2, 1)),
                 poly([(0.3, 0.68), (0.33, 0.5), (0.38, 0.5), (0.42, 0.38), (0.46, 0.38), (0.5, 0.28), (0.54, 0.38),
                       (0.58, 0.38), (0.62, 0.5), (0.67, 0.5), (0.7, 0.68)], W)],
    "cameroon": [V((0, 122, 94), (206, 17, 38), (252, 209, 22)), star(0.5, 0.5, 0.13, (252, 209, 22))],
    "canada": [V((216, 6, 33), W, (216, 6, 33), w=(1, 2, 1)), maple(0.5, 0.5, 0.3, (216, 6, 33))],
    "central_african_republic": [H((0, 48, 130), W, (40, 155, 65), (255, 206, 0)), rect(0.43, 0, 0.57, 1, (210, 16, 52)),
                                 star(0.15, 0.125, 0.09, (255, 206, 0))],
    "chad": [V((0, 38, 100), (254, 203, 0), (198, 12, 48))],
    "chile": [H(W, (213, 43, 30)), rect(0, 0, 0.33, 0.5, (0, 57, 166)), star(0.165, 0.25, 0.12, W)],
    "china": [fill((238, 28, 37)), star(0.17, 0.25, 0.15, (255, 255, 0)),
              stars([(0.33, 0.1), (0.4, 0.2), (0.4, 0.35), (0.33, 0.45)], 0.05, (255, 255, 0))],
    "colombia": [H((252, 209, 22), (0, 56, 147), (206, 17, 38), w=(2, 1, 1))],
    "comoros": [H((255, 196, 0), W, (206, 17, 38), (58, 117, 196)), poly([(0, 0), (0.5, 0.5), (0, 1)], (61, 142, 51)),
                crescent(0.17, 0.5, 0.2, W, off=0.35, cut=0.8),
                stars([(0.22, 0.32 + 0.12 * i) for i in range(4)], 0.035, W)],
    "congo": [fill((220, 36, 31)), poly([(0, 0), (0.75, 0), (0, 1)], (0, 149, 67)),
              poly([(0.75, 0), (1, 0), (0.25, 1), (0, 1)], (251, 222, 74))],
    "dr_congo": [fill((0, 127, 255)), line(-0.1, 1.05, 1.1, -0.05, (247, 216, 23), 0.36),
                 line(-0.1, 1.05, 1.1, -0.05, (206, 16, 33), 0.24), star(0.15, 0.2, 0.12, (247, 216, 23))],
    "costa_rica": [H((0, 43, 127), W, (206, 17, 38), W, (0, 43, 127), w=(1, 1, 2, 1, 1))],
    "cote_divoire": [V((247, 127, 0), W, (0, 158, 96))],
    "croatia": [H((255, 0, 0), W, (23, 23, 150)),
                *[rect(0.42 + 0.04 * (i % 4), 0.3 + 0.06 * (i // 4), 0.46 + 0.04 * (i % 4), 0.36 + 0.06 * (i // 4),
                       (255, 0, 0) if (i + i // 4) % 2 == 0 else W) for i in range(24)]],
    "cuba": [stripes_n(5, (0, 42, 143), W), poly([(0, 0), (0.45, 0.5), (0, 1)], (207, 20, 43)), star(0.16, 0.5, 0.13, W)],
    "cyprus": [fill(W), poly([(0.25, 0.45), (0.4, 0.3), (0.55, 0.35), (0.75, 0.2), (0.68, 0.32), (0.72, 0.42),
                              (0.55, 0.5), (0.35, 0.55)], (215, 120, 40)),
               line(0.35, 0.72, 0.48, 0.65, (70, 120, 50), 0.04), line(0.65, 0.72, 0.52, 0.65, (70, 120, 50), 0.04)],
    "czechia": [H(W, (215, 20, 26)), poly([(0, 0), (0.5, 0.5), (0, 1)], (17, 69, 126))],
    "denmark": [fill((200, 16, 46)), nordic(W, 0.14)],
    "djibouti": [H((106, 178, 231), (18, 173, 43)), poly([(0, 0), (0.5, 0.5), (0, 1)], W), star(0.17, 0.5, 0.1, (215, 20, 26))],
    "dominica": [fill((0, 98, 51)), cross((252, 209, 22), 0.2), cross(K, 0.13), cross(W, 0.06),
                 disc(0.5, 0.5, 0.22, (210, 16, 52)),
                 stars([(0.5 + 0.17 * math.cos(math.radians(a)), 0.5 + 0.17 * math.sin(math.radians(a)))
                        for a in range(-90, 270, 36)], 0.035, (0, 160, 80)), disc(0.5, 0.5, 0.08, (110, 40, 120))],
    "dominican_republic": [fill(W), sub(0, 0, 0.45, 0.43, fill((0, 45, 98))), sub(0.55, 0, 1, 0.43, fill((206, 17, 38))),
                           sub(0, 0.57, 0.45, 1, fill((206, 17, 38))), sub(0.55, 0.57, 1, 1, fill((0, 45, 98))),
                           emblem(0.5, 0.5, 0.09, (0, 100, 50), (206, 17, 38))],
    "ecuador": [H((255, 221, 0), (3, 78, 162), (237, 28, 36), w=(2, 1, 1)), emblem(0.5, 0.5, 0.17, (100, 70, 30), (90, 160, 220))],
    "egypt": [H((206, 17, 38), W, K), eagle(0.5, 0.5, 0.12, (192, 147, 0))],
    "el_salvador": [H((0, 71, 171), W, (0, 71, 171)), ring(0.5, 0.5, 0.11, (200, 170, 40), 0.03), poly([(0.45, 0.55), (0.5, 0.45), (0.55, 0.55)], (0, 120, 60))],
    "equatorial_guinea": [H((62, 153, 66), W, (227, 32, 23)), poly([(0, 0), (0.2, 0.5), (0, 1)], (0, 115, 206)),
                          emblem(0.5, 0.5, 0.1, (180, 180, 180), (60, 120, 60))],
    "eritrea": [H((18, 173, 43), (65, 137, 221)), poly([(0, 0), (1, 0.5), (0, 1)], (234, 0, 0)),
                ring(0.24, 0.5, 0.2, (255, 199, 38), 0.04), rect(0.23, 0.33, 0.25, 0.65, (255, 199, 38))],
    "estonia": [H((0, 114, 206), K, W)],
    "eswatini": [H((62, 94, 198), (255, 213, 32), (177, 0, 0), (255, 213, 32), (62, 94, 198), w=(3, 1, 8, 1, 3)),
                 disc(0.5, 0.5, 0.18, W), clip([(0.5, 0.2), (1, 0.2), (1, 0.8), (0.5, 0.8)], disc(0.5, 0.5, 0.18, K)),
                 line(0.2, 0.5, 0.8, 0.5, (130, 90, 40), 0.03)],
    "ethiopia": [H((7, 137, 48), (252, 221, 9), (218, 18, 26)), disc(0.5, 0.5, 0.22, (15, 71, 175)),
                 star(0.5, 0.5, 0.17, (252, 221, 9), inner=0.42)],
    "fiji": [fill((104, 191, 229)), sub(0, 0, 0.5, 0.5, *UJ), emblem(0.75, 0.5, 0.2, W, (206, 17, 38))],
    "finland": [fill(W), nordic((0, 47, 108), 0.27)],
    "france": [V((0, 35, 149), W, (237, 41, 57))],
    "gabon": [H((0, 158, 96), (252, 209, 22), (58, 117, 196))],
    "gambia": [H((206, 17, 38), W, (12, 28, 140), W, (58, 119, 40), w=(6, 1, 4, 1, 6))],
    "georgia": [fill(W), cross((255, 0, 0), 0.2),
                *[cross_small for cx, cy in ((0.21, 0.2), (0.79, 0.2), (0.21, 0.8), (0.79, 0.8))
                  for cross_small in (rect(cx - 0.05, cy - 0.025, cx + 0.05, cy + 0.025, (255, 0, 0)),
                                      rect(cx - 0.017, cy - 0.08, cx + 0.017, cy + 0.08, (255, 0, 0)))]],
    "germany": [H(K, (221, 0, 0), (255, 206, 0))],
    "ghana": [H((206, 17, 38), (252, 209, 22), (0, 107, 63)), star(0.5, 0.5, 0.15, K)],
    "greece": [stripes_n(9, (13, 94, 175), W), rect(0, 0, 0.37, 5 / 9, (13, 94, 175)),
               sub(0, 0, 0.37, 5 / 9, cross(W, 0.2))],
    "grenada": [fill((206, 17, 38)), sub(0.08, 0.12, 0.92, 0.88, fill((0, 122, 94)),
                poly([(0, 0), (1, 0), (0.5, 0.5)], (252, 209, 22)), poly([(0, 1), (1, 1), (0.5, 0.5)], (252, 209, 22)),
                disc(0.5, 0.5, 0.15, (206, 17, 38)), star(0.5, 0.5, 0.12, (252, 209, 22))),
                stars([(0.3, 0.06), (0.5, 0.06), (0.7, 0.06), (0.3, 0.94), (0.5, 0.94), (0.7, 0.94)], 0.04, (252, 209, 22))],
    "guatemala": [V((73, 151, 208), W, (73, 151, 208)), ring(0.5, 0.5, 0.13, (60, 140, 60), 0.035), disc(0.5, 0.48, 0.05, (60, 160, 90))],
    "guinea": [V((206, 17, 38), (252, 209, 22), (0, 148, 96))],
    "guinea_bissau": [H((252, 209, 22), (0, 148, 96)), rect(0, 0, 0.33, 1, (206, 17, 38)), star(0.165, 0.5, 0.13, K)],
    "guyana": [fill((0, 158, 73)), poly([(0, 0), (1, 0.5), (0, 1)], W), poly([(0, 0.03), (0.94, 0.5), (0, 0.97)], (252, 209, 22)),
               poly([(0, 0), (0.5, 0.5), (0, 1)], K), poly([(0, 0.05), (0.45, 0.5), (0, 0.95)], (206, 17, 38))],
    "haiti": [H((0, 32, 159), (210, 16, 52)), rect(0.38, 0.35, 0.62, 0.65, W), poly([(0.45, 0.6), (0.5, 0.4), (0.55, 0.6)], (0, 120, 60))],
    "honduras": [H((0, 115, 207), W, (0, 115, 207)),
                 stars([(0.5, 0.5), (0.38, 0.43), (0.38, 0.57), (0.62, 0.43), (0.62, 0.57)], 0.04, (0, 115, 207))],
    "hungary": [H((206, 41, 57), W, (71, 112, 80))],
    "iceland": [fill((2, 82, 156)), nordic(W, 0.22, inner=(220, 30, 53), ti=0.12)],
    "india": [H((255, 153, 51), W, (19, 136, 8)), ring(0.5, 0.5, 0.13, (0, 0, 128), 0.025),
              *[line(0.5, 0.5, 0.5 + 0.087 * math.cos(math.radians(a)), 0.5 + 0.13 * math.sin(math.radians(a)), (0, 0, 128), 0.01)
                for a in range(0, 360, 15)]],
    "indonesia": [H((255, 0, 0), W)],
    "iran": [H((35, 159, 64), W, (218, 0, 0)), crescent(0.5, 0.5, 0.1, (218, 0, 0), angle=-90, off=0.3), rect(0.49, 0.4, 0.51, 0.6, (218, 0, 0))],
    "iraq": [H((206, 17, 38), W, K), shahada(0.3, 0.7, 0.52, (0, 122, 61), 0.05)],
    "ireland": [V((22, 155, 98), W, (255, 136, 62))],
    "israel": [H(W, (0, 56, 184), W, (0, 56, 184), W, w=(2, 1.5, 6, 1.5, 2)), star_of_david(0.5, 0.5, 0.17, (0, 56, 184))],
    "italy": [V((0, 146, 70), W, (206, 43, 55))],
    "jamaica": [fill((0, 155, 58)), poly([(0, 0), (0.5, 0.5), (0, 1)], K), poly([(1, 0), (0.5, 0.5), (1, 1)], K),
                saltire((254, 209, 0), 0.17)],
    "japan": [fill(W), disc(0.5, 0.5, 0.3, (188, 0, 45))],
    "jordan": [H(K, W, (0, 122, 61)), poly([(0, 0), (0.5, 0.5), (0, 1)], (206, 17, 38)), star(0.17, 0.5, 0.08, W, n=7, inner=0.5)],
    "kazakhstan": [fill((0, 175, 202)), sun(0.5, 0.42, 0.13, (254, 197, 0), rays=24, ray_len=0.45),
                   poly([(0.3, 0.68), (0.5, 0.6), (0.7, 0.68), (0.5, 0.74)], (254, 197, 0)),
                   *[rect(0.03, 0.05 + i * 0.1, 0.08, 0.1 + i * 0.1, (254, 197, 0)) for i in range(0, 9, 2)]],
    "kenya": [H(K, W, (187, 0, 0), W, (0, 102, 0), w=(6, 1, 6, 1, 6)),
              poly([(0.5, 0.15), (0.58, 0.3), (0.6, 0.5), (0.58, 0.7), (0.5, 0.85), (0.42, 0.7), (0.4, 0.5), (0.42, 0.3)], (187, 0, 0)),
              poly([(0.5, 0.25), (0.54, 0.5), (0.5, 0.75), (0.46, 0.5)], K), line(0.38, 0.15, 0.62, 0.85, W, 0.025),
              line(0.62, 0.15, 0.38, 0.85, W, 0.025)],
    "kiribati": [H((206, 17, 38), (0, 50, 160), W, (0, 50, 160), W, (0, 50, 160), w=(10, 2, 1, 1, 1, 1)),
                 clip([(0, 0), (1, 0), (1, 0.62), (0, 0.62)], sun(0.5, 0.62, 0.15, (252, 209, 22), rays=17, ray_len=0.8)),
                 poly([(0.35, 0.25), (0.5, 0.2), (0.65, 0.18), (0.5, 0.28), (0.4, 0.3)], (252, 209, 22))],
    "kuwait": [H((0, 122, 61), W, (206, 17, 38)), poly([(0, 0), (0.25, 0.33), (0.25, 0.67), (0, 1)], K)],
    "kyrgyzstan": [fill((232, 17, 45)), sun(0.5, 0.5, 0.17, (255, 239, 0), rays=40, ray_len=0.55),
                   ring(0.5, 0.5, 0.11, (232, 17, 45), 0.025), line(0.42, 0.42, 0.58, 0.58, (232, 17, 45), 0.02),
                   line(0.42, 0.58, 0.58, 0.42, (232, 17, 45), 0.02)],
    "laos": [H((206, 17, 38), (0, 40, 104), (206, 17, 38), w=(1, 2, 1)), disc(0.5, 0.5, 0.2, W)],
    "latvia": [H((158, 48, 57), W, (158, 48, 57), w=(2, 1, 2))],
    "lebanon": [H((237, 28, 36), W, (237, 28, 36), w=(1, 2, 1)),
                poly([(0.5, 0.27), (0.62, 0.45), (0.56, 0.45), (0.66, 0.6), (0.58, 0.6), (0.68, 0.72), (0.32, 0.72),
                      (0.42, 0.6), (0.34, 0.6), (0.44, 0.45), (0.38, 0.45)], (0, 166, 81))],
    "lesotho": [H((0, 32, 159), W, (0, 149, 67), w=(3, 4, 3)),
                poly([(0.5, 0.3), (0.56, 0.45), (0.62, 0.62), (0.38, 0.62), (0.44, 0.45)], K)],
    "liberia": [stripes_n(11, (191, 10, 48), W), rect(0, 0, 0.42, 5 / 11, (0, 40, 104)), star(0.21, 0.23, 0.12, W)],
    "libya": [H((231, 0, 19), (10, 10, 10), (35, 158, 70), w=(1, 2, 1)), crescent(0.46, 0.5, 0.2, W, off=0.25, cut=0.83),
              star(0.63, 0.5, 0.085, W, rot=180)],
    "liechtenstein": [H((0, 43, 127), (206, 17, 38)),
                      poly([(0.12, 0.38), (0.12, 0.2), (0.18, 0.28), (0.22, 0.12), (0.26, 0.28), (0.32, 0.2), (0.32, 0.38)], (255, 214, 0))],
    "lithuania": [H((253, 185, 19), (0, 106, 68), (193, 39, 45))],
    "luxembourg": [H((237, 41, 57), W, (0, 161, 222))],
    "madagascar": [H((252, 61, 50), (0, 126, 58)), rect(0, 0, 0.33, 1, W)],
    "malawi": [H(K, (206, 17, 38), (0, 155, 72)),
               clip([(0, 0), (1, 0), (1, 0.33), (0, 0.33)], sun(0.5, 0.36, 0.12, (206, 17, 38), rays=31, ray_len=0.9))],
    "malaysia": [stripes_n(14, (204, 0, 1), W), rect(0, 0, 0.5, 8 / 14, (1, 0, 102)),
                 crescent(0.2, 0.29, 0.2, (255, 204, 0), off=0.25, cut=0.82), star(0.33, 0.29, 0.13, (255, 204, 0), n=14, inner=0.45)],
    "maldives": [fill((210, 41, 57)), rect(0.25, 0.25, 0.75, 0.75, (0, 126, 58)), crescent(0.52, 0.5, 0.17, W, off=0.3, cut=0.82)],
    "mali": [V((20, 181, 58), (252, 209, 22), (206, 17, 38))],
    "malta": [V(W, (207, 20, 43)), rect(0.105, 0.05, 0.155, 0.3, (165, 165, 170)),
              rect(0.05, 0.14, 0.21, 0.21, (165, 165, 170))],
    "marshall_islands": [fill((0, 56, 147)), line(0, 1, 1, 0.05, (221, 117, 0), 0.1), line(0, 1, 1, 0.18, W, 0.1),
                         star(0.23, 0.3, 0.17, W, n=24, inner=0.5)],
    "mauritania": [H((210, 16, 52), (0, 98, 51), (210, 16, 52), w=(1, 4, 1)),
                   crescent(0.5, 0.42, 0.25, (255, 214, 0), angle=-90, off=0.35, cut=0.85), star(0.5, 0.4, 0.09, (255, 214, 0))],
    "mauritius": [H((234, 40, 57), (26, 32, 108), (255, 213, 0), (0, 165, 81))],
    "mexico": [V((0, 104, 71), W, (206, 17, 38)), ring(0.5, 0.52, 0.13, (0, 104, 71), 0.03), eagle(0.5, 0.47, 0.09, (140, 90, 40))],
    "micronesia": [fill((106, 168, 223)), stars([(0.5, 0.25), (0.33, 0.5), (0.67, 0.5), (0.5, 0.75)], 0.08, W)],
    "moldova": [V((0, 70, 174), (255, 210, 0), (204, 9, 47)), eagle(0.5, 0.45, 0.13, (150, 100, 40)), emblem(0.5, 0.55, 0.08, (204, 9, 47), (0, 70, 174))],
    "monaco": [H((206, 17, 38), W)],
    "mongolia": [V((218, 32, 50), (0, 102, 178), (218, 32, 50)), disc(0.165, 0.32, 0.06, (255, 211, 0)),
                 rect(0.12, 0.42, 0.21, 0.46, (255, 211, 0)), disc(0.165, 0.55, 0.06, (255, 211, 0)),
                 rect(0.12, 0.64, 0.21, 0.68, (255, 211, 0)), rect(0.08, 0.3, 0.1, 0.75, (255, 211, 0)),
                 rect(0.23, 0.3, 0.25, 0.75, (255, 211, 0))],
    "montenegro": [fill((198, 54, 60)), ring(0.5, 0.5, 0.95, (212, 175, 55), 0.1), rect(0, 0, 1, 0.04, (212, 175, 55)),
                   rect(0, 0.96, 1, 1, (212, 175, 55)), rect(0, 0, 0.03, 1, (212, 175, 55)), rect(0.97, 0, 1, 1, (212, 175, 55)),
                   eagle(0.5, 0.5, 0.25, (212, 175, 55))],
    "morocco": [fill((193, 39, 45)),
                lambda s: pygame.draw.polygon(s, (0, 98, 51), star_points(Vector2(s.get_width() / 2, s.get_height() / 2),
                                                                           0.25 * s.get_height(), inner=0.38),
                                              width=max(1, round(0.04 * s.get_height())))],
    "mozambique": [H((0, 150, 57), W, K, W, (252, 225, 0), w=(6, 1, 6, 1, 6)), poly([(0, 0), (0.45, 0.5), (0, 1)], (210, 16, 52)),
                   star(0.15, 0.5, 0.15, (252, 225, 0)), line(0.08, 0.6, 0.22, 0.4, K, 0.03)],
    "myanmar": [H((254, 203, 0), (52, 178, 51), (234, 40, 57)), star(0.5, 0.54, 0.36, W)],
    "namibia": [fill((0, 53, 128)), poly([(0, 1), (1, 1), (1, 0)], (0, 149, 67)), line(-0.05, 1.05, 1.05, -0.05, W, 0.5),
                line(-0.05, 1.05, 1.05, -0.05, (210, 16, 52), 0.36), sun(0.2, 0.27, 0.07, (255, 206, 0), rays=12, ray_len=0.8)],
    "nauru": [fill((0, 43, 127)), rect(0, 0.46, 1, 0.54, (255, 199, 0)), star(0.25, 0.73, 0.12, W, n=12, inner=0.5)],
    "nepal": [fill(W), poly([(0.05, 0.02), (0.75, 0.48), (0.3, 0.48), (0.75, 0.98), (0.05, 0.98)], (0, 56, 147)),
              poly([(0.09, 0.08), (0.62, 0.44), (0.2, 0.44), (0.62, 0.94), (0.09, 0.94)], (220, 20, 60)),
              crescent(0.25, 0.3, 0.1, W, angle=-90, off=0.5, cut=0.85), sun(0.25, 0.72, 0.07, W, rays=12, ray_len=0.6)],
    "netherlands": [H((174, 28, 40), W, (33, 70, 139))],
    "new_zealand": [fill(NAVY), sub(0, 0, 0.5, 0.5, *UJ),
                    stars([(0.75, 0.2), (0.65, 0.45), (0.87, 0.4), (0.75, 0.82)], 0.08, W),
                    stars([(0.75, 0.2), (0.65, 0.45), (0.87, 0.4), (0.75, 0.82)], 0.055, (204, 20, 43))],
    "nicaragua": [H((0, 103, 198), W, (0, 103, 198)), poly([(0.44, 0.58), (0.5, 0.42), (0.56, 0.58)], (0, 120, 160)),
                  ring(0.5, 0.52, 0.1, (200, 160, 40), 0.02)],
    "niger": [H((224, 82, 6), W, (13, 176, 43)), disc(0.5, 0.5, 0.12, (224, 82, 6))],
    "nigeria": [V((0, 135, 81), W, (0, 135, 81))],
    "north_korea": [H((2, 79, 162), W, (237, 28, 39), W, (2, 79, 162), w=(6, 1, 15, 1, 6)), disc(0.33, 0.5, 0.2, W),
                    star(0.33, 0.5, 0.19, (237, 28, 39))],
    "north_macedonia": [fill((210, 0, 0)),
                        *[line(0.5, 0.5, 0.5 + 0.9 * math.cos(math.radians(a)), 0.5 + 0.9 * math.sin(math.radians(a)), (255, 230, 0), 0.12)
                          for a in (0, 45, 90, 135, 180, 225, 270, 315)],
                        disc(0.5, 0.5, 0.2, (210, 0, 0)), disc(0.5, 0.5, 0.15, (255, 230, 0))],
    "norway": [fill((186, 12, 47)), nordic(W, 0.25, inner=(0, 32, 91), ti=0.12)],
    "oman": [H(W, (219, 22, 28), (0, 128, 0)), rect(0, 0, 0.3, 1, (219, 22, 28)), line(0.08, 0.08, 0.22, 0.28, W, 0.03),
             line(0.22, 0.08, 0.08, 0.28, W, 0.03), rect(0.14, 0.06, 0.16, 0.3, W)],
    "pakistan": [fill((1, 65, 28)), rect(0, 0, 0.25, 1, W), crescent(0.63, 0.5, 0.3, W, angle=-45, off=0.3, cut=0.85),
                 star(0.71, 0.4, 0.09, W, rot=-60)],
    "palau": [fill((0, 153, 255)), disc(0.45, 0.5, 0.3, (255, 222, 0))],
    "panama": [sub(0, 0, 0.5, 0.5, fill(W), star(0.5, 0.5, 0.25, (0, 82, 147))), sub(0.5, 0, 1, 0.5, fill((210, 16, 52))),
               sub(0, 0.5, 0.5, 1, fill((0, 82, 147))), sub(0.5, 0.5, 1, 1, fill(W), star(0.5, 0.5, 0.25, (210, 16, 52)))],
    "papua_new_guinea": [fill(K), poly([(0, 0), (1, 0), (1, 1)], (206, 17, 38)),
                         stars([(0.25, 0.5), (0.18, 0.66), (0.32, 0.64), (0.25, 0.85)], 0.06, W),
                         poly([(0.55, 0.3), (0.75, 0.15), (0.85, 0.2), (0.7, 0.3), (0.82, 0.42), (0.62, 0.38)], (252, 209, 22))],
    "paraguay": [H((213, 43, 30), W, (0, 56, 168)), ring(0.5, 0.5, 0.1, (0, 100, 50), 0.03), star(0.5, 0.5, 0.05, (252, 209, 22))],
    "peru": [V((217, 16, 35), W, (217, 16, 35))],
    "philippines": [H((0, 56, 168), (206, 17, 38)), poly([(0, 0), (0.43, 0.5), (0, 1)], W),
                    sun(0.15, 0.5, 0.07, (252, 209, 22), rays=8, ray_len=0.9),
                    stars([(0.05, 0.1), (0.05, 0.9), (0.36, 0.5)], 0.045, (252, 209, 22))],
    "poland": [H(W, (220, 20, 60))],
    "portugal": [V((4, 106, 56), (218, 41, 28), w=(2, 3)), ring(0.4, 0.5, 0.2, (255, 225, 0), 0.04),
                 emblem(0.4, 0.5, 0.12, W, (218, 41, 28))],
    "qatar": [fill((138, 21, 56)), serrated(0.28, W, 9, depth=0.06)],
    "romania": [V((0, 43, 127), (252, 209, 22), (206, 17, 38))],
    "russia": [H(W, (0, 57, 166), (213, 43, 30))],
    "rwanda": [H((0, 161, 222), (250, 210, 1), (32, 96, 61), w=(2, 1, 1)), sun(0.8, 0.27, 0.07, (229, 190, 1), rays=24, ray_len=0.7)],
    "saint_kitts_and_nevis": [fill((206, 17, 38)), poly([(0, 0), (1, 0), (0, 1)], (0, 158, 73)),
                              line(-0.05, 1.05, 1.05, -0.05, (252, 209, 22), 0.4), line(-0.05, 1.05, 1.05, -0.05, K, 0.3),
                              stars([(0.33, 0.62), (0.67, 0.38)], 0.09, W)],
    "saint_lucia": [fill((102, 204, 255)), poly([(0.5, 0.1), (0.75, 0.9), (0.25, 0.9)], W),
                    poly([(0.5, 0.18), (0.71, 0.9), (0.29, 0.9)], K), poly([(0.5, 0.5), (0.75, 0.9), (0.25, 0.9)], (252, 209, 22))],
    "saint_vincent_and_the_grenadines": [V((0, 114, 198), (252, 209, 22), (0, 158, 96), w=(1, 2, 1)),
                                         *[poly([(cx, cy - 0.1), (cx + 0.05, cy), (cx, cy + 0.1), (cx - 0.05, cy)], (0, 158, 96))
                                           for cx, cy in ((0.42, 0.38), (0.58, 0.38), (0.5, 0.62))]],
    "samoa": [fill((206, 17, 38)), rect(0, 0, 0.5, 0.5, (0, 43, 127)),
              stars([(0.25, 0.1), (0.15, 0.25), (0.35, 0.22), (0.25, 0.4), (0.3, 0.3)], 0.045, W)],
    "san_marino": [H(W, (94, 182, 228)), emblem(0.5, 0.5, 0.15, (94, 182, 228), W)],
    "sao_tome_and_principe": [H((18, 173, 43), (255, 206, 0), (18, 173, 43), w=(2, 3, 2)),
                              poly([(0, 0), (0.25, 0.5), (0, 1)], (210, 16, 52)), stars([(0.5, 0.5), (0.75, 0.5)], 0.11, K)],
    "saudi_arabia": [fill((0, 108, 53)), shahada(0.22, 0.78, 0.38, W, 0.07), line(0.25, 0.68, 0.75, 0.68, W, 0.04),
                     rect(0.7, 0.64, 0.73, 0.72, W)],
    "senegal": [V((0, 133, 63), (253, 239, 66), (227, 27, 35)), star(0.5, 0.5, 0.13, (0, 133, 63))],
    "serbia": [H((198, 54, 60), (12, 64, 118), W), eagle(0.33, 0.45, 0.14, W), emblem(0.33, 0.48, 0.08, (198, 54, 60), W)],
    "seychelles": [fill((0, 122, 61)), poly([(0, 1), (0, 0), (0.33, 0)], (0, 63, 135)), poly([(0, 1), (0.33, 0), (0.67, 0)], (252, 216, 86)),
                   poly([(0, 1), (0.67, 0), (1, 0), (1, 0.33)], (214, 40, 40)), poly([(0, 1), (1, 0.33), (1, 0.67)], W)],
    "sierra_leone": [H((30, 181, 58), W, (0, 114, 198))],
    "singapore": FLAGS_SINGAPORE,
    "slovakia": [H(W, (11, 78, 162), (238, 28, 37)), emblem(0.33, 0.5, 0.25, W, (238, 28, 37)),
                 cross(W, 0.03, x=0.33, y=0.42), rect(0.3, 0.5, 0.36, 0.53, W)],
    "slovenia": [H(W, (0, 93, 164), (237, 28, 36)), emblem(0.3, 0.37, 0.15, (237, 28, 36), (0, 93, 164)),
                 poly([(0.24, 0.42), (0.3, 0.3), (0.36, 0.42)], W)],
    "solomon_islands": [fill((0, 81, 186)), poly([(0, 1), (1, 1), (1, 0)], (33, 94, 33)),
                        line(-0.05, 1.05, 1.05, -0.05, (252, 209, 22), 0.1),
                        stars([(0.08, 0.12), (0.32, 0.12), (0.2, 0.25), (0.08, 0.38), (0.32, 0.38)], 0.06, W)],
    "somalia": [fill((65, 137, 221)), star(0.5, 0.5, 0.25, W)],
    "south_africa": [H((224, 60, 49), (0, 20, 137)), poly([(0, 0), (0.15, 0), (0.5, 0.38), (1, 0.38), (1, 0.62), (0.5, 0.62), (0.15, 1), (0, 1)], W),
                     poly([(0, 0.08), (0.42, 0.45), (1, 0.45), (1, 0.55), (0.42, 0.55), (0, 0.92)], (0, 119, 73)),
                     poly([(0, 0.15), (0.35, 0.5), (0, 0.85)], (255, 184, 28)), poly([(0, 0.22), (0.3, 0.5), (0, 0.78)], K)],
    "south_korea": [fill(W), taegeuk(0.5, 0.5, 0.25), trigram(0.22, 0.25, 0.12, 34, (1, 1, 1)),
                    trigram(0.78, 0.75, 0.12, 34, (0, 0, 0)), trigram(0.78, 0.25, 0.12, -34, (1, 0, 1)),
                    trigram(0.22, 0.75, 0.12, -34, (0, 1, 0))],
    "south_sudan": [H(K, W, (218, 18, 26), W, (7, 137, 48), w=(6, 1, 6, 1, 6)), poly([(0, 0), (0.4, 0.5), (0, 1)], (15, 71, 175)),
                    star(0.13, 0.5, 0.12, (252, 221, 9))],
    "spain": [H((170, 21, 27), (241, 191, 0), (170, 21, 27), w=(1, 2, 1)), emblem(0.33, 0.5, 0.15, (170, 21, 27), (241, 191, 0))],
    "sri_lanka": [fill((255, 190, 41)), rect(0.04, 0.06, 0.15, 0.94, (0, 83, 78)), rect(0.15, 0.06, 0.26, 0.94, (255, 91, 0)),
                  rect(0.3, 0.06, 0.96, 0.94, (141, 20, 54)), poly([(0.5, 0.75), (0.5, 0.35), (0.6, 0.3), (0.7, 0.4), (0.75, 0.75)], (255, 190, 41))],
    "sudan": [H((210, 16, 52), W, K), poly([(0, 0), (0.33, 0.5), (0, 1)], (0, 114, 41))],
    "suriname": [H((55, 126, 63), W, (180, 10, 45), W, (55, 126, 63), w=(2, 1, 4, 1, 2)), star(0.5, 0.5, 0.16, (236, 200, 50))],
    "sweden": [fill((0, 106, 167)), nordic((254, 204, 0), 0.2)],
    "switzerland": [fill((218, 41, 28)), rect(0.43, 0.2, 0.57, 0.8, W), rect(0.3, 0.4, 0.7, 0.6, W)],
    "syria": [H((0, 122, 61), W, K), stars([(0.3, 0.5), (0.5, 0.5), (0.7, 0.5)], 0.09, (206, 17, 38))],
    "tajikistan": [H((204, 0, 0), W, (0, 102, 0), w=(2, 3, 2)),
                   poly([(0.44, 0.55), (0.44, 0.47), (0.47, 0.5), (0.5, 0.44), (0.53, 0.5), (0.56, 0.47), (0.56, 0.55)], (248, 195, 0)),
                   stars([(0.5 + 0.12 * math.cos(math.radians(a)), 0.53 + 0.14 * math.sin(math.radians(a))) for a in range(-160, -10, 25)],
                         0.025, (248, 195, 0))],
    "tanzania": [fill((30, 181, 58)), poly([(1, 0), (1, 1), (0, 1)], (0, 163, 221)),
                 line(-0.05, 1.05, 1.05, -0.05, (252, 209, 22), 0.42), line(-0.05, 1.05, 1.05, -0.05, K, 0.3)],
    "thailand": [H((165, 25, 49), W, (45, 42, 74), W, (165, 25, 49), w=(1, 1, 2, 1, 1))],
    "timor_leste": [fill((220, 36, 31)), poly([(0, 0), (0.5, 0.5), (0, 1)], (255, 199, 38)), poly([(0, 0), (0.33, 0.5), (0, 1)], K),
                    star(0.12, 0.5, 0.11, W, rot=-60)],
    "togo": [stripes_n(5, (0, 106, 78), (255, 206, 0)), rect(0, 0, 0.4, 0.6, (210, 16, 52)), star(0.2, 0.3, 0.17, W)],
    "tonga": [fill((193, 0, 0)), rect(0, 0, 0.42, 0.5, W), rect(0.17, 0.08, 0.25, 0.42, (193, 0, 0)),
              rect(0.09, 0.21, 0.33, 0.29, (193, 0, 0))],
    "trinidad_and_tobago": [fill((218, 26, 53)), line(0, -0.05, 1, 1.05, W, 0.4), line(0, -0.05, 1, 1.05, K, 0.28)],
    "tunisia": [fill((231, 0, 19)), disc(0.5, 0.5, 0.25, W), crescent(0.5, 0.5, 0.19, (231, 0, 19), off=0.25, cut=0.8),
                star(0.54, 0.5, 0.09, (231, 0, 19), rot=180)],
    "turkey": [fill((227, 10, 23)), crescent(0.4, 0.5, 0.25, W, off=0.25, cut=0.8), star(0.55, 0.5, 0.11, W, rot=180)],
    "turkmenistan": [fill((0, 132, 66)), rect(0.13, 0, 0.29, 1, (180, 40, 40)),
                     *[disc(0.21, 0.1 + i * 0.16, 0.05, (230, 140, 60)) for i in range(6)],
                     crescent(0.4, 0.22, 0.12, W, off=0.3, cut=0.8), stars([(0.47, 0.13), (0.5, 0.22), (0.47, 0.31), (0.43, 0.17), (0.43, 0.27)], 0.025, W)],
    "tuvalu": [fill((0, 155, 222)), sub(0, 0, 0.5, 0.5, *UJ),
               stars([(0.6, 0.85), (0.7, 0.6), (0.62, 0.4), (0.78, 0.82), (0.85, 0.45), (0.9, 0.2), (0.8, 0.12), (0.93, 0.65), (0.72, 0.25)],
                     0.05, (255, 206, 0))],
    "uganda": [H(K, (252, 220, 4), (217, 0, 0), K, (252, 220, 4), (217, 0, 0)), disc(0.5, 0.5, 0.18, W),
               poly([(0.48, 0.35), (0.52, 0.38), (0.5, 0.6), (0.56, 0.65), (0.46, 0.65)], (100, 100, 100))],
    "ukraine": [H((0, 87, 183), (255, 215, 0))],
    "united_arab_emirates": [H((0, 115, 47), W, K), rect(0, 0, 0.25, 1, (255, 0, 0))],
    "united_kingdom": list(UJ),
    "united_states": [stripes_n(13, (178, 34, 52), W), sub(0, 0, 0.4, 7 / 13, *us_canton())],
    "uruguay": [stripes_n(9, W, (0, 56, 168)), rect(0, 0, 0.36, 5 / 9, W),
                sun(0.18, 0.28, 0.08, (252, 209, 22), rays=16, ray_len=0.8)],
    "uzbekistan": [H((0, 153, 181), (206, 17, 38), W, (206, 17, 38), (30, 181, 58), w=(31, 1, 30, 1, 31)),
                   crescent(0.15, 0.17, 0.1, W, off=0.3, cut=0.8),
                   stars([(0.27 + 0.07 * (i % 5), 0.08 + 0.09 * (i // 5)) for i in range(12) if i not in (0, 5)], 0.02, W)],
    "vanuatu": [H((210, 16, 52), (0, 154, 68)), poly([(0, 0), (0.58, 0.5), (0, 1)], (253, 206, 18)),
                rect(0.3, 0.45, 1, 0.55, (253, 206, 18)), poly([(0, 0.08), (0.5, 0.5), (0, 0.92)], K)],
    "venezuela": [H((255, 204, 0), (0, 36, 125), (207, 20, 43)),
                  stars([(0.5 + 0.17 * math.cos(math.radians(a)), 0.6 + 0.2 * math.sin(math.radians(a))) for a in range(-160, -10, 21)],
                        0.035, W)],
    "vietnam": [fill((218, 37, 29)), star(0.5, 0.5, 0.3, (255, 255, 0))],
    "yemen": [H((206, 17, 38), W, K)],
    "zambia": [fill((25, 138, 0)), rect(0.68, 0.37, 0.78, 1, (222, 32, 16)), rect(0.78, 0.37, 0.89, 1, K),
               rect(0.89, 0.37, 1, 1, (239, 125, 0)), eagle(0.84, 0.2, 0.1, (239, 125, 0))],
    "zimbabwe": [H((49, 149, 64), (255, 210, 0), (210, 16, 52), K, (210, 16, 52), (255, 210, 0), (49, 149, 64)),
                 poly([(0, 0), (0.45, 0.5), (0, 1)], W), poly([(0, 0), (0.42, 0.5), (0, 1)], K),
                 poly([(0, 0.03), (0.4, 0.5), (0, 0.97)], W), star(0.14, 0.5, 0.15, (210, 16, 52)), disc(0.14, 0.5, 0.05, (255, 210, 0))],
    "vatican_city": [V((255, 225, 0), W), line(0.65, 0.35, 0.85, 0.7, (200, 160, 40), 0.05), line(0.85, 0.35, 0.65, 0.7, (180, 180, 180), 0.05),
                     poly([(0.7, 0.3), (0.75, 0.15), (0.8, 0.3)], (200, 160, 40))],
    "palestine": [H(K, W, (0, 150, 57)), poly([(0, 0), (0.33, 0.5), (0, 1)], (206, 17, 38))],
    "taiwan": [fill((254, 0, 0)), rect(0, 0, 0.5, 0.5, (0, 0, 149)),
               sun(0.25, 0.25, 0.09, W, rays=12, ray_len=0.85), disc(0.25, 0.25, 0.075, (0, 0, 149)), disc(0.25, 0.25, 0.06, W)],
    "kosovo": [fill((36, 74, 165)), poly([(0.38, 0.35), (0.48, 0.28), (0.6, 0.32), (0.64, 0.45), (0.6, 0.62), (0.5, 0.68),
                                          (0.42, 0.6), (0.36, 0.48)], (208, 167, 46)),
               stars([(0.5 + 0.22 * math.cos(math.radians(a)), 0.3 + 0.12 * math.sin(math.radians(a))) for a in range(-150, -20, 26)],
                     0.04, W)],
    "western_sahara": [H(K, W, (0, 122, 61)), poly([(0, 0), (0.33, 0.5), (0, 1)], (198, 12, 48)),
                       crescent(0.48, 0.5, 0.12, (198, 12, 48), off=0.3, cut=0.82), star(0.53, 0.5, 0.06, (198, 12, 48), rot=180)],
    "northern_cyprus": [fill(W), rect(0, 0.08, 1, 0.16, (227, 10, 23)), rect(0, 0.84, 1, 0.92, (227, 10, 23)),
                        crescent(0.43, 0.5, 0.17, (227, 10, 23), off=0.25, cut=0.8), star(0.53, 0.5, 0.08, (227, 10, 23), rot=180)],
    "somaliland": [H((0, 150, 57), W, (210, 16, 52)), star(0.5, 0.5, 0.11, K), shahada(0.3, 0.7, 0.18, W, 0.05)],
    "abkhazia": [stripes_n(7, (0, 140, 70), W), rect(0, 0, 0.42, 3 / 7, (206, 17, 38)),
                 poly([(0.17, 0.33), (0.17, 0.18), (0.19, 0.12), (0.21, 0.18), (0.22, 0.11), (0.24, 0.18), (0.26, 0.13), (0.27, 0.2),
                       (0.28, 0.26), (0.25, 0.33)], W),
                 stars([(0.21 + 0.13 * math.cos(math.radians(a)), 0.21 + 0.15 * math.sin(math.radians(a))) for a in range(-180, 1, 30)],
                       0.022, W)],
    "south_ossetia": [H(W, (206, 17, 38), (255, 209, 0))],
    "transnistria": [H((210, 16, 52), (0, 122, 61), (210, 16, 52), w=(2, 1, 2)),
                     poly([(0.08, 0.2), (0.13, 0.08), (0.2, 0.2), (0.14, 0.3)], (255, 206, 0))],
    # --- Meme entries (designed here where the meme has no official flag) ---
    "glaggle_land": [fill((250, 214, 40)), disc(0.5, 0.5, 0.5, (255, 232, 110)), disc(0.5, 0.58, 0.42, (250, 214, 40)),
                     oval(0.4, 0.36, 0.07, 0.14, K), oval(0.6, 0.36, 0.07, 0.14, K),
                     arc(0.5, 0.45, 0.32, 200, 340, K, 0.05)],
    "ohio": [fill((30, 30, 40)), H((187, 19, 62), W, (187, 19, 62), W, (187, 19, 62)),
             poly([(1, 0), (0.72, 0.5), (1, 1)], (30, 30, 40)), poly([(0, 0), (0.48, 0.5), (0, 1)], (0, 33, 71)),
             ring(0.18, 0.5, 0.14, W, 0.07), disc(0.18, 0.5, 0.07, (187, 19, 62)),
             stars([(0.06, 0.25), (0.06, 0.75), (0.3, 0.33), (0.3, 0.67), (0.12, 0.12), (0.12, 0.88),
                    (0.38, 0.42), (0.38, 0.58)], 0.04, W)],
    "sealand": [fill(K), poly([(0, 0), (1, 0), (0, 1)], (227, 6, 19)), line(-0.05, 1.05, 1.05, -0.05, W, 0.3)],
    "bir_tawil": [fill((222, 190, 130)), glyph("?", 0.5, 0.52, 0.85, K)],   # the land nobody claims
    "flat_earth": [fill((10, 20, 50)), disc(0.5, 0.5, 0.46, W), disc(0.5, 0.5, 0.42, (40, 110, 200)),
                   poly([(0.45, 0.3), (0.55, 0.28), (0.6, 0.4), (0.52, 0.47), (0.42, 0.42)], (70, 160, 70)),
                   poly([(0.62, 0.48), (0.75, 0.45), (0.78, 0.6), (0.66, 0.7), (0.6, 0.6)], (70, 160, 70)),
                   poly([(0.3, 0.5), (0.4, 0.55), (0.42, 0.7), (0.32, 0.75), (0.25, 0.62)], (70, 160, 70)),
                   disc(0.5, 0.5, 0.04, W)],
    "area_51": [fill((12, 16, 32)), stars([(0.12, 0.15), (0.85, 0.2), (0.2, 0.8), (0.9, 0.75), (0.75, 0.1)], 0.025, W),
                oval(0.5, 0.48, 0.26, 0.34, (120, 220, 100)),
                poly([(0.36, 0.42), (0.47, 0.5), (0.45, 0.6), (0.35, 0.52)], K),
                poly([(0.64, 0.42), (0.53, 0.5), (0.55, 0.6), (0.65, 0.52)], K)],
    "bermuda_triangle": [fill((0, 80, 140)), *[ring(0.5, 0.58, rr, (0, 50, 100), 0.03) for rr in (0.08, 0.16, 0.24)],
                         lambda s: pygame.draw.polygon(s, W, [_p(s, 0.5, 0.12), _p(s, 0.82, 0.85), _p(s, 0.18, 0.85)],
                                                       width=max(1, round(0.05 * s.get_height())))],
    "roman_empire": [fill((140, 10, 20)), eagle(0.5, 0.3, 0.17, (230, 180, 40)), glyph("SPQR", 0.5, 0.68, 0.3, (230, 180, 40)),
                     rect(0.06, 0.06, 0.94, 0.09, (230, 180, 40)), rect(0.06, 0.91, 0.94, 0.94, (230, 180, 40))],
    "tralalero_land": [H((130, 200, 240), (20, 110, 190)),
                       poly([(0.15, 0.45), (0.35, 0.32), (0.6, 0.3), (0.85, 0.38), (0.95, 0.25), (0.92, 0.48),
                             (0.6, 0.55), (0.35, 0.55)], (110, 130, 160)),
                       poly([(0.48, 0.3), (0.56, 0.12), (0.62, 0.3)], (110, 130, 160)),
                       poly([(0.15, 0.45), (0.35, 0.55), (0.28, 0.49)], W),
                       disc(0.25, 0.42, 0.025, K),
                       *[line(x + 0.065, 0.52, x + 0.065, 0.63, (110, 130, 160), 0.05) for x in (0.3, 0.5, 0.7)],
                       *[rect(x, 0.6, x + 0.13, 0.7, (40, 90, 230)) for x in (0.3, 0.5, 0.7)],
                       *[rect(x, 0.68, x + 0.15, 0.73, W) for x in (0.3, 0.5, 0.7)]],
    "tringapore": [fill((30, 30, 40)), clip([(0.5, 0.05), (0.95, 0.95), (0.05, 0.95)], H((239, 51, 64), W)),
                   crescent(0.44, 0.35, 0.12, W, off=0.3, cut=0.82),
                   stars([(0.52, 0.25), (0.48, 0.33), (0.56, 0.33), (0.5, 0.42), (0.55, 0.42)], 0.025, W)],
    "liberland": [H((255, 205, 0), K, (255, 205, 0), w=(2, 1, 2)), emblem(0.5, 0.5, 0.2, K, (255, 205, 0))],
    "null_island": [fill((120, 200, 230)), disc(0.5, 0.5, 0.2, (240, 220, 160)), disc(0.5, 0.5, 0.11, (60, 170, 90)),
                    line(0, 0.5, 1, 0.5, K, 0.025), line(0.5, 0, 0.5, 1, K, 0.025), ring(0.5, 0.5, 0.3, K, 0.025)],
}

OWN_FACE = {"glaggle_land", "area_51"}   # flags that already are a face: no countryball eyes on top

_cache: dict[tuple[str, int, int], pygame.Surface] = {}


def paint(key: str, surface: pygame.Surface):
    for op in FLAGS[key]:
        op(surface)


def painter(key: str):
    return lambda surface: paint(key, surface)


def flag_image(key: str, w: int, h: int) -> pygame.Surface:
    """Cached w x h rendering of a country's flag."""
    cache_key = (key, w, h)
    if cache_key not in _cache:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        paint(key, surf)
        _cache[cache_key] = surf
    return _cache[cache_key]
