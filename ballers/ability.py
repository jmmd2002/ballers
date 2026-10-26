"""Abilities trigger automatically when off cooldown and their condition holds."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fighter import Fighter
    from .match import Match


class Ability:
    name = "Ability"
    cooldown = 10.0
    initial_cooldown: float | None = None   # delay before first use; defaults to cooldown
    sfx: str | None = None                  # extra sound effect key on use

    def __init__(self, owner: Fighter):
        self.owner = owner
        self.timer = self.cooldown if self.initial_cooldown is None else self.initial_cooldown
        self._wait = self.timer   # length of the current wait, for the HUD bar

    @property
    def ready(self) -> bool:
        return self.timer <= 0

    @property
    def charge(self) -> float:
        """0..1 progress toward being ready, for HUD cooldown bars."""
        return 1.0 - min(self.timer / self._wait, 1.0) if self._wait > 0 else 1.0

    @property
    def voice(self) -> str:
        """Voice line file stem, looked up per fighter: sounds/voices/<fighter>/<voice>.*"""
        return self.name.lower().replace(" ", "_")

    def hud_label(self, match: Match) -> str | None:
        """Override to replace the HUD's READY/seconds label (e.g. "ACTIVE")."""
        return None

    def update(self, match: Match, dt: float):
        self.timer = max(0.0, self.timer - dt)
        if self.ready and self.owner.can_cast and self.can_activate(match):
            self.activate(match)
            self.timer = self._wait = self.cooldown

    def activate(self, match: Match, callout: str | None = None):
        match.announce(self.owner, callout or self.name, self)
        self.cast(match)

    # --- Override in subclasses ---------------------------------------------

    def can_activate(self, match: Match) -> bool:
        return True

    def cast(self, match: Match):
        raise NotImplementedError
