from dataclasses import dataclass


@dataclass(frozen=True)
class MatchConfig:
    arena_width: float = 500
    arena_height: float = 500
    physics_dt: float = 1 / 120   # fixed timestep keeps matches deterministic per seed
    time_limit: float = 90.0      # seconds; 0 disables the timeout


# Logical canvas size (9:16, matches Shorts/Reels). The window scales this to fit.
CANVAS_WIDTH = 540
CANVAS_HEIGHT = 960
FPS = 60
