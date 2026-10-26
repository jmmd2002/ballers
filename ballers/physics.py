"""Stateless physics and overlap helpers."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pygame.math import Vector2

if TYPE_CHECKING:
    from .entity import Ball, Entity


def move(ball: Ball, dt: float):
    ball.pos += ball.vel * dt


def collide_walls(ball: Ball, width: float, height: float) -> list[Vector2]:
    """Keep the ball inside the arena. Returns the inward normal of every wall
    the ball bounced off this step (only counted when moving into the wall)."""
    hits = []
    r = ball.radius
    if ball.pos.x - r < 0:
        ball.pos.x = r
        if ball.vel.x < 0:
            ball.vel.x = -ball.vel.x
            hits.append(Vector2(1, 0))
    elif ball.pos.x + r > width:
        ball.pos.x = width - r
        if ball.vel.x > 0:
            ball.vel.x = -ball.vel.x
            hits.append(Vector2(-1, 0))
    if ball.pos.y - r < 0:
        ball.pos.y = r
        if ball.vel.y < 0:
            ball.vel.y = -ball.vel.y
            hits.append(Vector2(0, 1))
    elif ball.pos.y + r > height:
        ball.pos.y = height - r
        if ball.vel.y > 0:
            ball.vel.y = -ball.vel.y
            hits.append(Vector2(0, -1))
    return hits


def collide_balls(a: Ball, b: Ball) -> Vector2 | None:
    """Resolve overlap and bounce two balls elastically. Immobile balls act as
    immovable walls. Returns the contact point if they hit while approaching."""
    delta = b.pos - a.pos
    dist = delta.length()
    min_dist = a.radius + b.radius
    if dist >= min_dist:
        return None

    normal = delta / dist if dist > 1e-9 else Vector2(1, 0)
    ia, ib = a.inv_mass, b.inv_mass
    total = ia + ib
    overlap = min_dist - dist
    if total == 0:
        a.pos -= normal * overlap / 2
        b.pos += normal * overlap / 2
        return None
    a.pos -= normal * (overlap * ia / total)
    b.pos += normal * (overlap * ib / total)

    approach = (b.vel - a.vel).dot(normal)
    if approach >= 0:
        return None  # already separating; don't count as a new hit

    impulse = -2 * approach / total
    a.vel -= normal * (impulse * ia)
    b.vel += normal * (impulse * ib)
    return a.pos + normal * a.radius


def circle_in_cone(center: Vector2, radius: float, apex: Vector2, direction: Vector2,
                   length: float, half_angle: float) -> bool:
    """Approximate circle vs. circular-sector overlap (angles in degrees)."""
    d = center - apex
    dist = d.length()
    if dist > length + radius:
        return False
    if dist <= radius:
        return True
    angle = abs((direction.angle_to(d) + 180) % 360 - 180)
    margin = math.degrees(math.asin(min(1.0, radius / dist)))
    return angle <= half_angle + margin


def circle_overlaps(center: Vector2, radius: float, e: Entity) -> bool:
    """Does a circular area overlap an entity of any shape?"""
    if e.shape == "circle":
        return center.distance_squared_to(e.pos) < (radius + e.radius) ** 2
    if e.shape == "cone":
        return circle_in_cone(center, radius, e.pos, e.direction, e.length, e.half_angle)
    return False


def overlaps(a: Entity, b: Entity) -> bool:
    if a.shape != "circle":
        a, b = b, a
    return a.shape == "circle" and circle_overlaps(a.pos, a.radius, b)
