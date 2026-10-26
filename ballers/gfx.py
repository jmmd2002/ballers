"""Small drawing helpers shared by the renderer, scenes, and ball visuals."""
import pygame

_fonts: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[key] = f
    return _fonts[key]


def render_text(text, size, color, bold=False, outline=0, outline_color=(0, 0, 0)) -> pygame.Surface:
    f = font(size, bold)
    inner = f.render(text, True, color)
    if not outline:
        return inner
    w, h = inner.get_size()
    surf = pygame.Surface((w + outline * 2, h + outline * 2), pygame.SRCALPHA)
    edge = f.render(text, True, outline_color)
    for dx in (-outline, 0, outline):
        for dy in (-outline, 0, outline):
            if dx or dy:
                surf.blit(edge, (outline + dx, outline + dy))
    surf.blit(inner, (outline, outline))
    return surf


def draw_text(surface, text, size, color, bold=False, outline=0, alpha=255, **anchor):
    """Draw text positioned by a pygame.Rect anchor kwarg, e.g. center=(x, y)."""
    img = render_text(text, size, color, bold, outline)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**anchor)
    surface.blit(img, rect)
    return rect


def wrap(text, size, width, bold=False) -> list[str]:
    f = font(size, bold)
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if f.size(candidate)[0] <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def darken(color, amount):
    return tuple(max(0, int(c * (1 - amount))) for c in color[:3])


def lighten(color, amount):
    return tuple(min(255, int(c + (255 - c) * amount)) for c in color[:3])
