"""A single match: pure simulation, no rendering. Can run headless (for
tournaments, balance testing, video export) or driven by a scene."""
from __future__ import annotations

import random
from itertools import combinations

from pygame.math import Vector2

from . import physics
from .config import MatchConfig
from .entity import Ball, DamageType, Entity
from .events import (AbilityUsed, Contact, Damage, EntityRemoved, EntitySpawned, EventBus,
                     FighterDefeated, MatchOver, WallHit)
from .fighter import Fighter


class Match:
    def __init__(self, fighter_types: list[type[Fighter]], seed: int | None = None,
                 config: MatchConfig | None = None):
        self.config = config or MatchConfig()
        self.seed = seed if seed is not None else random.randrange(2**31)
        self.rng = random.Random(self.seed)
        self.bus = EventBus()
        self.time = 0.0
        self.over = False
        self.winner: Fighter | None = None
        self.entities: list[Entity] = []
        self._pending: list[Entity] = []
        self._overlaps: set[tuple[int, int]] = set()        # non-solid overlaps last step
        self._last_hit: dict[tuple[int, int], float] = {}   # (source, target) -> time
        self.fighters = self._spawn_fighters(fighter_types)
        self._flush_spawns()

    def _spawn_fighters(self, fighter_types):
        w, h = self.config.arena_width, self.config.arena_height
        fighters = []
        for team, cls in enumerate(fighter_types):
            pos = Vector2(w * (team + 1) / (len(fighter_types) + 1),
                          h / 2 + self.rng.uniform(-0.2, 0.2) * h)
            # Diagonal-ish start so balls don't get stuck bouncing on one axis.
            angle = self.rng.choice((45, 135, 225, 315)) + self.rng.uniform(-25, 25)
            fighters.append(self.spawn(cls(pos, team, Vector2(1, 0).rotate(angle))))
        return fighters

    # --- API for entities and abilities -------------------------------------

    def spawn(self, entity: Entity) -> Entity:
        """Add an entity; it joins the arena at the end of the current step."""
        self._pending.append(entity)
        return entity

    def announce(self, caster: Entity, text: str, ability=None):
        self.bus.emit(AbilityUsed(caster, text, ability))

    def enemies_of(self, entity: Entity, cls: type[Entity] = Entity) -> list[Entity]:
        return [e for e in self.entities
                if e.alive and e.team != entity.team and isinstance(e, cls)]

    def nearest_enemy(self, entity: Entity, cls: type[Entity] = Ball,
                      reach: float | None = None) -> Entity | None:
        """Closest enemy body (a solid entity: fighters, clones), optionally only
        those whose edge is within `reach` of the entity's center."""
        candidates = [e for e in self.enemies_of(entity, cls) if e.solid
                      and (reach is None or entity.pos.distance_to(e.pos) - e.radius <= reach)]
        return min(candidates, key=lambda e: e.pos.distance_squared_to(entity.pos), default=None)

    def owned_by(self, owner: Entity, cls: type[Entity] = Entity) -> list[Entity]:
        return [e for e in self.entities if e.alive and e.owner is owner and isinstance(e, cls)]

    def clamp_to_arena(self, pos: Vector2, radius: float) -> Vector2:
        w, h = self.config.arena_width, self.config.arena_height
        return Vector2(min(max(pos.x, radius), w - radius), min(max(pos.y, radius), h - radius))

    def deal_damage(self, source: Entity | None, target: Entity, amount: float,
                    damage_type: DamageType | None = None, continuous: bool = False) -> float:
        """continuous: a small slice of damage over time, dealt every step."""
        if amount <= 0 or target.removed or target.hp <= 0:
            return 0.0
        damage_type = damage_type or (source.damage_type if source else DamageType.PHYSICAL)
        dealt = amount * target.damage_multiplier(damage_type)
        if dealt <= 0:
            return 0.0
        target.hp = max(0.0, target.hp - dealt)
        self.bus.emit(Damage(source, target, dealt, damage_type, Vector2(target.pos), continuous))
        target.on_take_damage(self, dealt, damage_type, source)
        return dealt

    # --- Simulation -----------------------------------------------------------

    def step(self, dt: float | None = None):
        if self.over:
            return
        dt = dt or self.config.physics_dt
        self.time += dt
        w, h = self.config.arena_width, self.config.arena_height

        for e in list(self.entities):
            if e.alive:
                e.tick(self, dt)

        balls = [e for e in self.entities if e.alive and isinstance(e, Ball)]
        for ball in balls:
            if not ball.is_immobile:
                physics.move(ball, dt)
        for ball in balls:
            for normal in physics.collide_walls(ball, w, h):
                self.bus.emit(WallHit(ball, ball.pos - normal * ball.radius, normal))
                ball.on_wall_hit(self, normal)

        overlaps = set()
        for a, b in combinations([e for e in self.entities if e.alive], 2):
            if not (a.alive and b.alive):
                continue
            if a.solid and b.solid:
                started = physics.collide_balls(a, b) is not None
            elif physics.overlaps(a, b):
                key = (id(a), id(b))
                overlaps.add(key)
                started = key not in self._overlaps
            else:
                continue
            if started:
                self._contact(a, b)
        self._overlaps = overlaps

        for ball in balls:
            ball.keep_speed()

        self._remove_dead()
        self._flush_spawns()
        self._check_end()

    def _contact(self, a: Entity, b: Entity):
        self.bus.emit(Contact(a, b))
        a.on_contact(self, b)
        b.on_contact(self, a)
        if a.team == b.team:
            return
        # Both sides hit simultaneously, so mutual knockouts are draws.
        spent = []
        for src, tgt in ((a, b), (b, a)):
            if src.damage <= 0 or not self._can_hit(src, tgt):
                continue
            self._last_hit[(id(src), id(tgt))] = self.time
            dealt = self.deal_damage(src, tgt, src.damage, src.damage_type)
            src.on_hit(self, tgt, dealt)
            if src.dies_on_hit:
                spent.append(src)
        for src in spent:
            src.destroy()

    def _can_hit(self, src: Entity, tgt: Entity) -> bool:
        if not src.can_damage(self, tgt):
            return False
        last = self._last_hit.get((id(src), id(tgt)))
        return last is None or self.time - last >= src.hit_cooldown

    def _remove_dead(self):
        while dead := [e for e in self.entities if not e.alive]:
            self.entities = [e for e in self.entities if e.alive]
            for e in dead:
                e.on_death(self)
                self.bus.emit(EntityRemoved(e))
                if e.is_fighter:
                    self.bus.emit(FighterDefeated(e))
                    for minion in self.owned_by(e):
                        minion.destroy()

    def _flush_spawns(self):
        while self._pending:
            entity = self._pending.pop(0)
            self.entities.append(entity)
            entity.on_spawn(self)
            self.bus.emit(EntitySpawned(entity))

    def _check_end(self):
        alive = [f for f in self.fighters if f.alive]
        if len({f.team for f in alive}) <= 1:
            self._finish(alive[0] if alive else None, "knockout")
        elif self.config.time_limit and self.time >= self.config.time_limit:
            ranked = sorted(alive, key=lambda f: f.hp / f.max_hp, reverse=True)
            tied = ranked[1].hp / ranked[1].max_hp == ranked[0].hp / ranked[0].max_hp
            self._finish(None if tied else ranked[0], "timeout")

    def _finish(self, winner, reason):
        self.over = True
        self.winner = winner
        self.bus.emit(MatchOver(winner, reason))

    def run_to_end(self, max_time: float = 600.0) -> Fighter | None:
        """Simulate headlessly until the match ends."""
        while not self.over and self.time < max_time:
            self.step()
        return self.winner
