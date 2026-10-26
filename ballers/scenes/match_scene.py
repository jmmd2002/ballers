import pygame

from ..app import Scene
from ..audio import VOICE_VOLUME, SoundCues, ensure_matchup_line, last_word_onset
from ..match import Match
from ..render import Renderer

MAX_STEPS_PER_FRAME = 20


class MatchScene(Scene):
    def __init__(self, app, ball_types, seed=None):
        super().__init__(app)
        self.ball_types = ball_types
        self.match = Match(ball_types, seed=seed)
        self.renderer = Renderer(self.match)
        SoundCues(self.match, app.sound)
        intro = ensure_matchup_line(ball_types)
        app.sound(intro, VOICE_VOLUME)
        self.intro_left = last_word_onset(intro)   # match starts on the announcer's "fight!"
        self.accumulator = 0.0
        self.paused = False

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE:
            self.paused = not self.paused
        elif event.key == pygame.K_r:
            self.app.switch(MatchScene(self.app, self.ball_types))
        elif event.key in (pygame.K_ESCAPE, pygame.K_m):
            from .menu import MenuScene
            self.app.switch(MenuScene(self.app))

    def update(self, dt):
        if self.paused:
            return
        if self.intro_left > 0:
            self.intro_left -= dt
            return
        step = self.match.config.physics_dt
        self.accumulator += dt
        steps = 0
        while self.accumulator >= step and steps < MAX_STEPS_PER_FRAME:
            self.match.step(step)
            self.accumulator -= step
            steps += 1
        if steps == MAX_STEPS_PER_FRAME:
            self.accumulator = 0.0
        self.renderer.update(dt)

    def draw(self, canvas):
        self.renderer.draw(canvas, paused=self.paused)
