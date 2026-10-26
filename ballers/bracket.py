"""Draws the Countryball Cup bracket and plays the post-match sequence of a
tournament video: zoomed in on the match, the winner moves forward, then
the camera zooms out to the whole bracket.

The bracket lives in "world" units (WORLD_W x WORLD_H, two halves converging
on the final in the middle). It is rendered once per state at 2x and 1x, and
the camera crops and scales those images for each video frame."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

from . import gfx
from .countries._flags import flag_image
from .countries._roster import CODES, COUNTRIES, NAMES
from .export import VIDEO_FPS, VIDEO_SIZE
from .tournament import ROUND_NAMES, ROUNDS, SLOTS, TITLE, Match, Tournament

WORLD_W, WORLD_H = 1920, 3072
TOP, BOTTOM = 330, 3040
PITCH = (BOTTOM - TOP) / (SLOTS // 2)  # vertical spacing of first-round slots
LEAF_W, LEAF_H = 190, 18
BOX_W, BOX_H = 76, 24
COL_GAP = 34
CENTER_X = WORLD_W / 2

BG = (16, 16, 22)
BOX = (38, 38, 52)
BOX_EDGE = (70, 70, 90)
LINE = (70, 70, 92)
LINE_WON = (235, 235, 245)
TEXT = (235, 235, 245)
MUTED = (120, 120, 140)
GOLD = (255, 210, 90)

# Timing of the post-match sequence (seconds).
WINNER_HOLD = 1.6      # winner screen of the match before cutting to the bracket
CROSSFADE = 0.35
ZOOM_HOLD = 0.5
ADVANCE = 1.1
LANDED_HOLD = 0.9
ZOOM_OUT = 1.6
FULL_HOLD = 1.4
CARD_TIME = 3.0
ZOOM_WIDTH = 450       # world units visible when zoomed in on a match


# --- Layout -----------------------------------------------------------------

def _col_x(r: int) -> float:
    """Left edge of round r's column on the left half."""
    if r == 0:
        return 16
    return 16 + LEAF_W + COL_GAP * r + BOX_W * (r - 1)


def slot_rect(r: int, p: int) -> pygame.FRect:
    """World rect of the entrant box in slot p of round r (r = ROUNDS: champion)."""
    if r == ROUNDS:
        return pygame.FRect(CENTER_X - 95, (TOP + BOTTOM) / 2 - 250, 190, 64)
    count = SLOTS >> r
    half = count // 2
    side, local = divmod(p, half)
    span = (SLOTS // 2) / half                       # first-round slots under this box
    y = TOP + (local * span + span / 2) * PITCH
    w, h = (LEAF_W, LEAF_H) if r == 0 else (BOX_W, BOX_H)
    if r == ROUNDS - 1:
        x = CENTER_X - 12 - w if side == 0 else CENTER_X + 12
    else:
        x = _col_x(r) if side == 0 else WORLD_W - _col_x(r) - w
    return pygame.FRect(x, y - h / 2, w, h)


def _flag_rect(box: pygame.FRect) -> pygame.FRect:
    fh = box.h - 6
    return pygame.FRect(box.x + 3, box.y + 3, fh * 1.5, fh)


def match_center(m: Match) -> Vector2:
    r, i = m
    rects = [slot_rect(r, 2 * i), slot_rect(r, 2 * i + 1), slot_rect(r + 1, i)]
    union = rects[0].unionall(rects[1:])
    return Vector2(union.center)


def full_camera() -> pygame.FRect:
    w = WORLD_W
    h = w * VIDEO_SIZE[1] / VIDEO_SIZE[0]
    return pygame.FRect(0, (WORLD_H - h) / 2, w, h)


def match_camera(m: Match) -> pygame.FRect:
    w = ZOOM_WIDTH
    h = w * VIDEO_SIZE[1] / VIDEO_SIZE[0]
    c = match_center(m)
    x = min(max(c.x - w / 2, 0), WORLD_W - w)
    y = c.y - h / 2   # may show empty space past the ends, keeping the match centered
    return pygame.FRect(x, y, w, h)


def lerp_camera(a: pygame.FRect, b: pygame.FRect, t: float) -> pygame.FRect:
    """Zoom between two cameras: width changes geometrically so the zoom speed feels even."""
    w = math.exp(math.log(a.w) + (math.log(b.w) - math.log(a.w)) * t)
    h = w * a.h / a.w
    ca, cb = Vector2(a.center), Vector2(b.center)
    c = ca + (cb - ca) * t
    return pygame.FRect(c.x - w / 2, c.y - h / 2, w, h)


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# --- Drawing ----------------------------------------------------------------

def _scaled(rect: pygame.FRect, s: float) -> pygame.Rect:
    return pygame.Rect(round(rect.x * s), round(rect.y * s), round(rect.w * s), round(rect.h * s))


def _line(surf, s, color, points, width=2):
    pygame.draw.lines(surf, color, False, [(x * s, y * s) for x, y in points], max(1, round(width * s)))


def _connector(tour: Tournament, m: Match) -> list[tuple[list, bool]]:
    """Polylines from a match's entrants to its winner's slot, each flagged
    True when it is the winner's path (drawn bright)."""
    r, i = m
    parent = slot_rect(r + 1, i)
    win = tour.winner(m)
    paths = []
    if r == ROUNDS - 1:   # final: up from both finalists into the champion box
        join_y = parent.bottom + 40
        for p in (0, 1):
            box = slot_rect(r, p)
            pts = [(box.centerx, box.top), (box.centerx, join_y), (parent.centerx, join_y), parent.midbottom]
            paths.append((pts, win is not None and win == tour.entrant(r, p)))
        return paths
    left = parent.centerx < CENTER_X
    px = parent.left if left else parent.right
    for p in (2 * i, 2 * i + 1):
        if r == 0 and tour.slots[p] is None:
            continue   # bye: no line from the empty slot
        box = slot_rect(r, p)
        cx = box.right if left else box.left
        mx = (cx + px) / 2
        pts = [(cx, box.centery), (mx, box.centery), (mx, parent.centery), (px, parent.centery)]
        paths.append((pts, win is not None and win == tour.entrant(r, p)))
    return paths


def _draw_entry(surf, s, box: pygame.FRect, key: str | None, leaf: bool, out: bool, champion=False):
    rect = _scaled(box, s)
    pygame.draw.rect(surf, BOX, rect, border_radius=round(4 * s))
    pygame.draw.rect(surf, GOLD if champion else BOX_EDGE, rect, width=max(1, round((2 if champion else 1) * s)),
                     border_radius=round(4 * s))
    if key is None:
        return
    fr = _scaled(_flag_rect(box), s)
    surf.blit(flag_image(key, fr.w, fr.h), fr)
    pygame.draw.rect(surf, (10, 10, 14), fr, width=max(1, round(s)))
    text = NAMES[key] if (leaf or champion) else CODES[key]
    size = round((box.h * (0.5 if champion else 0.78)) * s)
    img = gfx.render_text(text, size, GOLD if champion else TEXT, bold=True)
    room = rect.right - fr.right - round(6 * s)
    if img.get_width() > room:
        img = pygame.transform.smoothscale(img, (room, img.get_height()))
    surf.blit(img, img.get_rect(midleft=(fr.right + round(4 * s), rect.centery)))
    if out:
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        veil.fill((12, 12, 18, 170))
        surf.blit(veil, rect)


def _draw_trophy(surf, s, center: Vector2, size: float):
    c = center * s
    k = size * s
    cup = [c + Vector2(-0.5, -0.6) * k, c + Vector2(0.5, -0.6) * k, c + Vector2(0.4, -0.1) * k,
           c + Vector2(0.12, 0.15) * k, c + Vector2(-0.12, 0.15) * k, c + Vector2(-0.4, -0.1) * k]
    for side in (-1, 1):
        pygame.draw.circle(surf, GOLD, c + Vector2(side * 0.5, -0.35) * k, 0.22 * k, width=max(1, round(0.08 * k)))
    pygame.draw.polygon(surf, GOLD, cup)
    pygame.draw.rect(surf, GOLD, pygame.Rect(c.x - 0.07 * k, c.y + 0.1 * k, 0.14 * k, 0.3 * k))
    pygame.draw.rect(surf, GOLD, pygame.Rect(c.x - 0.3 * k, c.y + 0.38 * k, 0.6 * k, 0.14 * k), border_radius=round(0.04 * k))
    pygame.draw.polygon(surf, gfx.lighten(GOLD, 0.5), [cup[0], cup[0] + Vector2(0.18, 0) * k, cup[5] + Vector2(0.18, 0) * k, cup[5]])


def draw_title(surf, s: float, origin=(0, 0), alpha=255):
    """Title over the bracket's header area; drawn separately so zoomed-in
    shots don't show it cut off. origin = world (0, 0) on surf, s = scale."""
    if alpha <= 0:
        return
    ox, oy = origin
    gfx.draw_text(surf, TITLE, round(120 * s), GOLD, bold=True, outline=max(1, round(4 * s)), alpha=alpha,
                  center=(ox + CENTER_X * s, oy + 130 * s))
    gfx.draw_text(surf, f"{len(COUNTRIES)} COUNTRIES · ONE CHAMPION", round(48 * s), MUTED, bold=True, alpha=alpha,
                  center=(ox + CENTER_X * s, oy + 225 * s))


def render(tour: Tournament, s: float, highlight: Match | None = None) -> pygame.Surface:
    surf = pygame.Surface((round(WORLD_W * s), round(WORLD_H * s)))
    surf.fill(BG)

    matches = [(r, i) for r in range(ROUNDS) for i in range(SLOTS >> (r + 1))]
    for m in matches:   # dim lines first, the winners' paths on top
        for pts, won in _connector(tour, m):
            if not won:
                _line(surf, s, LINE, pts)
    for m in matches:
        for pts, won in _connector(tour, m):
            if won:
                _line(surf, s, LINE_WON, pts, 3)

    out = tour.eliminated()
    for r in range(ROUNDS):
        for p in range(SLOTS >> r):
            key = tour.entrant(r, p)
            if r == 0 and key is None:
                continue   # empty side of a bye
            _draw_entry(surf, s, slot_rect(r, p), key, leaf=r == 0, out=key in out)

    champ_box = slot_rect(ROUNDS, 0)
    _draw_entry(surf, s, champ_box, tour.entrant(ROUNDS, 0), leaf=False, out=False, champion=True)
    _draw_trophy(surf, s, Vector2(champ_box.centerx, champ_box.top - 120), 150)
    gfx.draw_text(surf, "FINAL", round(30 * s), MUTED, bold=True,
                  center=(CENTER_X * s, (slot_rect(ROUNDS - 1, 0).bottom + 28) * s))

    if highlight is not None:
        r, i = highlight
        for p in (2 * i, 2 * i + 1):
            rect = _scaled(slot_rect(r, p).inflate(6, 6), s)
            pygame.draw.rect(surf, GOLD, rect, width=max(2, round(2.5 * s)), border_radius=round(6 * s))
    return surf


class View:
    """A bracket state rendered at 2x and 1x; frame() films it through a camera."""

    def __init__(self, tour: Tournament, highlight: Match | None = None):
        self.hi = render(tour, 2, highlight)
        self.lo = pygame.transform.smoothscale(self.hi, (WORLD_W, WORLD_H))

    def frame(self, cam: pygame.FRect, out: pygame.Surface):
        k = out.get_width() / cam.w             # screen pixels per world unit
        src, s = (self.hi, 2) if k > 1 else (self.lo, 1)
        out.fill(BG)
        inter = cam.clip(pygame.FRect(0, 0, WORLD_W, WORLD_H))
        if inter.w <= 0 or inter.h <= 0:
            return
        src_rect = _scaled(inter, s).clip(src.get_rect())
        dst = pygame.Rect(round((inter.x - cam.x) * k), round((inter.y - cam.y) * k),
                          round(inter.w * k), round(inter.h * k))
        out.blit(pygame.transform.smoothscale(src.subsurface(src_rect), dst.size), dst)


def title(cam: pygame.FRect, out: pygame.Surface):
    """Title overlay that fades in as the camera zooms out to the whole bracket."""
    k = out.get_width() / cam.w
    alpha = int(255 * ease((cam.w - 1600) / (WORLD_W - 1600)))
    draw_title(out, k, to_screen(cam, out, (0, 0)), alpha)


def to_screen(cam: pygame.FRect, out: pygame.Surface, p) -> Vector2:
    k = out.get_width() / cam.w
    return (Vector2(p) - Vector2(cam.topleft)) * k


def _pill(out, text, y, color=TEXT, size=46, alpha=255):
    img = gfx.render_text(text, size, color, bold=True)
    rect = img.get_rect(center=(out.get_width() // 2, y)).inflate(44, 22)
    pill = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(pill, (10, 10, 16, 225), pill.get_rect(), border_radius=rect.h // 2)
    pygame.draw.rect(pill, (*color, 255), pill.get_rect(), width=3, border_radius=rect.h // 2)
    pill.blit(img, img.get_rect(center=(rect.w // 2, rect.h // 2)))
    pill.set_alpha(alpha)
    out.blit(pill, rect)


def _card(out, t: float):
    """End card over the full bracket."""
    veil = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    veil.fill((8, 8, 14, int(190 * min(t / 0.3, 1))))
    out.blit(veil, (0, 0))
    p = min(t / 0.45, 1)
    alpha = int(255 * min(p * 3, 1))
    scale = 0.6 + 0.4 * (1 - (1 - p) ** 3)
    cx, cy = out.get_width() // 2, out.get_height() // 2
    for text, size, color, dy in (("WHO WINS NEXT?", 104, GOLD, -70), ("Subscribe to follow the", 56, TEXT, 60),
                                  (f"{TITLE.title()}!", 56, TEXT, 125)):
        img = gfx.render_text(text, max(1, int(size * scale)), color, bold=True, outline=5)
        img.set_alpha(alpha)
        out.blit(img, img.get_rect(center=(cx, cy + dy * scale)))


def epilogue(tour: Tournament, m: Match):
    """Generator factory for export(epilogue=...): bracket zoomed on the match,
    winner moves to the next slot, zoom out to the full bracket, end card."""
    def run(match, last_frame: pygame.Surface, cue):
        winner = match.winner.key
        after_tour = tour.with_result(m, winner)
        before, after = View(tour, highlight=m), View(after_tour, highlight=m)
        near, far = match_camera(m), full_camera()
        out = pygame.Surface(VIDEO_SIZE)
        frames = lambda sec: range(max(1, int(sec * VIDEO_FPS)))
        label = tour.label(m).upper()
        r, i = m
        a, b = tour.players(m)
        start = slot_rect(r, 2 * i if winner == a else 2 * i + 1)
        dest = slot_rect(r + 1, i)
        path = [Vector2(p) for p in _connector(tour.with_result(m, winner), m)[0 if winner == a else 1][0]]
        if r == ROUNDS - 1:
            path = path[:-1] + [Vector2(dest.center)]

        for f in frames(CROSSFADE):
            before.frame(near, out)
            last_frame.set_alpha(int(255 * (1 - f / (CROSSFADE * VIDEO_FPS))))
            out.blit(last_frame, (0, 0))
            yield out
        for _ in frames(ZOOM_HOLD):
            before.frame(near, out)
            _pill(out, label, 120)
            yield out

        cue("sfx/swoosh")
        lengths = [(path[k + 1] - path[k]).length() for k in range(len(path) - 1)]
        total = sum(lengths)
        fr_start, fr_end = _flag_rect(start), _flag_rect(dest)
        n = len(frames(ADVANCE))
        for f in range(n):
            t = ease(f / (n - 1))
            before.frame(near, out)
            # Trail along the connector, then the flag riding on its tip.
            dist, pts = t * total, [path[0]]
            for k, seg in enumerate(lengths):
                if dist >= seg:
                    pts.append(path[k + 1])
                    dist -= seg
                else:
                    pts.append(path[k] + (path[k + 1] - path[k]) * (dist / seg if seg else 0))
                    break
            screen_pts = [to_screen(near, out, p) for p in pts]
            if len(screen_pts) > 1:
                pygame.draw.lines(out, GOLD, False, screen_pts, 8)
            k = out.get_width() / near.w
            pop = 1 + 0.5 * math.sin(math.pi * t)
            fw = (fr_start.w + (fr_end.w - fr_start.w) * t) * k * pop
            img = pygame.transform.smoothscale(flag_image(winner, 96, 64), (int(fw), int(fw / 1.5)))
            rect = img.get_rect(center=screen_pts[-1])
            pygame.draw.rect(out, GOLD, rect.inflate(10, 10), border_radius=6)
            out.blit(img, rect)
            _pill(out, label, 120)
            yield out

        cue("sfx/advance")
        for f in frames(LANDED_HOLD):
            after.frame(near, out)
            glow = to_screen(near, out, dest.center)
            radius = (dest.w * 0.75 + 30 * f / VIDEO_FPS) * out.get_width() / near.w
            pygame.draw.circle(out, GOLD, glow, radius, width=max(1, int(8 * (1 - f / (LANDED_HOLD * VIDEO_FPS)))))
            _pill(out, label, 120)
            _pill(out, f"{NAMES[winner].upper()} ADVANCES!" if r < ROUNDS - 1 else f"{NAMES[winner].upper()} IS THE CHAMPION!",
                  out.get_height() - 170, GOLD, 58)
            yield out

        cue("sfx/swoosh")
        n = len(frames(ZOOM_OUT))
        for f in range(n):
            cam = lerp_camera(near, far, ease(f / (n - 1)))
            after.frame(cam, out)
            title(cam, out)
            yield out
        for _ in frames(FULL_HOLD):
            after.frame(far, out)
            title(far, out)
            yield out
        for f in frames(CARD_TIME):
            after.frame(far, out)
            title(far, out)
            _card(out, f / VIDEO_FPS)
            yield out
    return run


def save_image(tour: Tournament, path, scale: float = 1):
    pygame.init()
    surf = render(tour, scale)
    draw_title(surf, scale)
    pygame.image.save(surf, str(path))
