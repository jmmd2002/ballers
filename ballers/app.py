"""Window + main loop. Everything draws to a fixed 540x960 canvas that is
scaled (letterboxed) to the window, so layout code never deals with window size."""
from __future__ import annotations

import pygame

from .config import CANVAS_HEIGHT, CANVAS_WIDTH, FPS


class Scene:
    def __init__(self, app: App):
        self.app = app

    def handle_event(self, event: pygame.event.Event):
        pass

    def update(self, dt: float):
        pass

    def draw(self, canvas: pygame.Surface):
        pass


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ballers")
        desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
        scale = min(1.0, (desktop_h - 100) / CANVAS_HEIGHT, (desktop_w - 100) / CANVAS_WIDTH)
        self.window = pygame.display.set_mode(
            (int(CANVAS_WIDTH * scale), int(CANVAS_HEIGHT * scale)), pygame.RESIZABLE)
        self.canvas = pygame.Surface((CANVAS_WIDTH, CANVAS_HEIGHT))
        self.clock = pygame.time.Clock()
        self.scene: Scene | None = None
        self.running = True
        self.selection: list[int] = [0, 1]   # menu picks, remembered between matches
        from .audio import LivePlayer
        self.sound = LivePlayer()

    def switch(self, scene: Scene):
        self.scene = scene

    def quit(self):
        self.running = False

    def _view_rect(self) -> pygame.Rect:
        ww, wh = self.window.get_size()
        scale = min(ww / CANVAS_WIDTH, wh / CANVAS_HEIGHT)
        rect = pygame.Rect(0, 0, int(CANVAS_WIDTH * scale), int(CANVAS_HEIGHT * scale))
        rect.center = (ww // 2, wh // 2)
        return rect

    def to_canvas(self, pos) -> tuple[float, float]:
        """Convert window (mouse) coordinates to canvas coordinates."""
        view = self._view_rect()
        return ((pos[0] - view.x) * CANVAS_WIDTH / view.w,
                (pos[1] - view.y) * CANVAS_HEIGHT / view.h)

    def run(self, scene: Scene):
        self.scene = scene
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.scene.handle_event(event)
            self.scene.update(dt)
            self.scene.draw(self.canvas)

            view = self._view_rect()
            self.window.fill((0, 0, 0))
            self.window.blit(pygame.transform.smoothscale(self.canvas, view.size), view)
            pygame.display.flip()
        pygame.quit()
