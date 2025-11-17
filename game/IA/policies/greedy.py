from __future__ import annotations
from typing import Tuple, Optional
from game.IA.interfaces import StepPolicy


def _cardinal_neighbors():
    return [(1,0),(-1,0),(0,1),(0,-1)]


def _is_walkable(world, x: float, y: float) -> bool:
    city = world.city
    if x < 0 or y < 0 or x >= city.width or y >= city.height:
        return False
    return not city.is_wall(x, y)


def _manhattan(a, b) -> float:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


class GreedyPolicy(StepPolicy):
    """
    Greedy con heurística y pequeña penalización para evitar retrocesos inmediatos.
    """
    def __init__(self, world, climate_weight: float = 0.5, lookahead_depth: int = 2):
        self.world = world
        self.climate_weight = float(climate_weight)
        self.depth = int(lookahead_depth)

    def _climate_risk(self) -> float:
        return 0.3 if getattr(self.world, "weather_system", None) else 0.0

    def _h(self, pos, target: Optional[Tuple[int,int]]) -> float:
        if not target:
            return 0.0
        return _manhattan(pos, target) + self.climate_weight * self._climate_risk()

    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        # Si no hay objetivo, no oscilar sin sentido
        if not ai.current_target:
            return (0, 0)

        last_dx, last_dy = getattr(ai, "_current_step", (0, 0))
        inverse_last = (-last_dx, -last_dy)

        best = (0, 0)
        best_score = float("inf")

        for dx, dy in _cardinal_neighbors():
            nx, ny = ai.x + dx, ai.y + dy
            if not _is_walkable(self.world, nx, ny):
                continue

            score = self._h((nx, ny), ai.current_target)

            # Lookahead opcional
            if self.depth > 1:
                local_best = score
                for sdx, sdy in _cardinal_neighbors():
                    nnx, nny = nx + sdx, ny + sdy
                    if _is_walkable(self.world, nnx, nny):
                        local_best = min(local_best, self._h((nnx, nny), ai.current_target))
                score = local_best

            # Penalizar revertir inmediatamente el movimiento anterior
            if (dx, dy) == inverse_last:
                score += 0.25  # pequeño castigo

            # Favorecer continuar en misma dirección si similar (tie-break)
            if (dx, dy) == (last_dx, last_dy):
                score -= 0.05

            if score < best_score:
                best_score = score
                best = (dx, dy)

        return best