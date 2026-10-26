"""Fighter: a selectable ball with an HP bar and abilities. Register subclasses
with @register (see ballers/balls/)."""
from __future__ import annotations

from .ability import Ability
from .entity import Ball


class Fighter(Ball):
    key = "fighter"         # unique id used by the registry and CLI
    category = "anime"      # roster the fighter belongs to (menu tab), see registry.PACKAGES
    description = ""
    announcer_name: str | None = None   # TTS-friendly spelling, if `name` is mispronounced
    max_hp = 100
    is_fighter = True
    ability_types: tuple[type[Ability], ...] = ()

    def __init__(self, pos, team, direction=None, owner=None):
        super().__init__(pos, team, direction, owner)
        self.abilities = [cls(self) for cls in self.ability_types]

    def tick(self, match, dt):
        super().tick(match, dt)
        if self.alive:
            for ability in self.abilities:
                ability.update(match, dt)

    def status(self, match) -> str:
        """Fighter-specific text for the HUD line under the HP bar."""
        return ""

    def status_line(self, match) -> str:
        """status() plus the labels of active status conditions."""
        parts = [self.status(match)] + [s.label for s in self.statuses if s.label and not s.done]
        return "  ·  ".join(p for p in parts if p)
