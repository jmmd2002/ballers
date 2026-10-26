"""Pick one ball per side, then start a match.
Fighters are split into rosters (anime, politics), one tab each.
Mouse: click a roster tab, a ball in either column, then FIGHT.
Keyboard: TAB switch roster, LEFT/RIGHT choose column, UP/DOWN choose ball,
ENTER fight, ESC quit."""
import pygame

from .. import gfx, registry
from ..app import Scene
from ..config import CANVAS_HEIGHT, CANVAS_WIDTH
from ..render import BG, MUTED, TEXT
from .match_scene import MatchScene

MARGIN, GAP = 20, 20
COL_W = (CANVAS_WIDTH - 2 * MARGIN - GAP) // 2
TAB_Y, TAB_H = 150, 40
LIST_TOP, ROW_H, ROW_GAP = 240, 56, 10
HIGHLIGHT = (255, 210, 90)


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.categories = registry.categories()
        self.category = getattr(app, "category", self.categories[0])
        self._load_roster()
        self.selection = [min(i, len(self.balls) - 1) for i in app.selection]
        self.active_col = 0
        self.fight_button = pygame.Rect(0, 0, 260, 70)
        self.fight_button.center = (CANVAS_WIDTH // 2, CANVAS_HEIGHT - 130)

    def _load_roster(self):
        self.balls = [cls for cls in registry.all_fighters() if cls.category == self.category]
        self.selection = [0, min(1, len(self.balls) - 1)]

    def _switch_category(self, category):
        if category != self.category:
            self.category = category
            self._load_roster()

    def _tab_rect(self, i):
        w = (CANVAS_WIDTH - 2 * MARGIN) // len(self.categories)
        return pygame.Rect(MARGIN + i * w, TAB_Y, w - 6, TAB_H)

    def _row_rect(self, col, row):
        x = MARGIN + col * (COL_W + GAP)
        return pygame.Rect(x, LIST_TOP + row * (ROW_H + ROW_GAP), COL_W, ROW_H)

    def _start(self):
        self.app.selection = list(self.selection)
        self.app.category = self.category
        self.app.switch(MatchScene(self.app, [self.balls[i] for i in self.selection]))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.quit()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start()
            elif event.key == pygame.K_TAB:
                i = self.categories.index(self.category)
                self._switch_category(self.categories[(i + 1) % len(self.categories)])
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.active_col = 1 - self.active_col
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                step = -1 if event.key == pygame.K_UP else 1
                col = self.active_col
                self.selection[col] = (self.selection[col] + step) % len(self.balls)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.app.to_canvas(event.pos)
            if self.fight_button.collidepoint(pos):
                self._start()
                return
            for i, category in enumerate(self.categories):
                if self._tab_rect(i).collidepoint(pos):
                    self._switch_category(category)
                    return
            for col in (0, 1):
                for row in range(len(self.balls)):
                    if self._row_rect(col, row).collidepoint(pos):
                        self.selection[col] = row
                        self.active_col = col

    def draw(self, canvas):
        canvas.fill(BG)
        gfx.draw_text(canvas, "BALLERS", 72, TEXT, bold=True, center=(CANVAS_WIDTH // 2, 70))
        gfx.draw_text(canvas, "Choose the fighters", 30, MUTED, center=(CANVAS_WIDTH // 2, 120))
        for i, category in enumerate(self.categories):
            rect = self._tab_rect(i)
            active = category == self.category
            pygame.draw.rect(canvas, HIGHLIGHT if active else (40, 40, 54), rect, border_radius=10)
            gfx.draw_text(canvas, category.upper(), 28, BG if active else TEXT, bold=True,
                          center=rect.center)

        for col in (0, 1):
            x = MARGIN + col * (COL_W + GAP)
            header_color = HIGHLIGHT if col == self.active_col else TEXT
            gfx.draw_text(canvas, f"BALL {col + 1}", 32, header_color, bold=True,
                          midtop=(x + COL_W // 2, LIST_TOP - 30))
            for row, cls in enumerate(self.balls):
                rect = self._row_rect(col, row)
                selected = self.selection[col] == row
                pygame.draw.rect(canvas, (40, 40, 54) if selected else (28, 28, 38), rect,
                                 border_radius=10)
                if selected:
                    pygame.draw.rect(canvas, cls.color, rect, width=3, border_radius=10)
                pygame.draw.circle(canvas, cls.color, (rect.x + 30, rect.centery), 16)
                size = 30
                while size > 18 and gfx.font(size, selected).size(cls.name)[0] > rect.w - 66:
                    size -= 2
                gfx.draw_text(canvas, cls.name, size, TEXT, bold=selected,
                              midleft=(rect.x + 58, rect.centery))

            chosen = self.balls[self.selection[col]]
            y = self._row_rect(col, len(self.balls)).y + 20
            gfx.draw_text(canvas, chosen.name, 30, chosen.color, bold=True, topleft=(x, y))
            y += 32
            for line in gfx.wrap(chosen.description, 24, COL_W):
                gfx.draw_text(canvas, line, 24, MUTED, topleft=(x, y))
                y += 22
            y += 8
            gfx.draw_text(canvas, f"HP {chosen.max_hp}  ·  Speed {chosen.speed}", 24, MUTED,
                          topleft=(x, y))

        names = [self.balls[i].name for i in self.selection]
        gfx.draw_text(canvas, f"{names[0]}  vs  {names[1]}", 34, TEXT, bold=True,
                      center=(CANVAS_WIDTH // 2, self.fight_button.top - 40))
        pygame.draw.rect(canvas, HIGHLIGHT, self.fight_button, border_radius=14)
        gfx.draw_text(canvas, "FIGHT!", 48, BG, bold=True, center=self.fight_button.center)
        gfx.draw_text(canvas, "TAB roster  ·  ARROWS select  ·  ENTER fight  ·  ESC quit", 22, MUTED,
                      midbottom=(CANVAS_WIDTH // 2, CANVAS_HEIGHT - 12))
