from __future__ import annotations
import random
from typing import Tuple
from game.IA.interfaces import StepPolicy


def _cardinal_neighbors():
    return [(1,0),(-1,0),(0,1),(0,-1)]


def _is_walkable(world, x: float, y: float) -> bool:
    city = world.city
    if x < 0 or y < 0 or x >= city.width or y >= city.height:
        return False
    return not city.is_wall(x, y)


class RandomChoicePolicy(StepPolicy):
    """
    Random choice con sesgo hacia el target y anti-oscilación.
    """
    def __init__(self, world, bias: float = 0.55):
        self.world = world
        self.bias = float(bias)

    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        candidates = []
        for dx, dy in _cardinal_neighbors():
            nx, ny = ai.x + dx, ai.y + dy
            if _is_walkable(self.world, nx, ny):
                candidates.append((dx, dy))
        if not candidates:
            return (0, 0)

        # Sesgo hacia target si existe
        if ai.current_target:
            tx, ty = ai.current_target
            def after_dist(step):
                dx, dy = step
                return abs((ai.x + dx) - tx) + abs((ai.y + dy) - ty)
            if random.random() < self.bias:
                return min(candidates, key=after_dist)

        choice = random.choice(candidates)
        # Anti-oscilación: evita reversa inmediata
        # Usa el último paso aplicado cuando existe
        if getattr(ai, "_current_step", (0,0)) != (0,0) and len(candidates) > 1:
            last = ai._current_step
            if (-choice[0], -choice[1]) == last:
                alt = [c for c in candidates if c != choice]
                if alt:
                    choice = random.choice(alt)
        return choice