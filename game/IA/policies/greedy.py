from __future__ import annotations
from typing import Tuple, Optional
from game.IA.interfaces import StepPolicy


def _cardinal_neighbors():
    return [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _is_walkable(world, x: float, y: float) -> bool:
    """
    Verifica si una posición es caminable.
    Usa int() para convertir, que trunca hacia cero.
    """
    city = world.city

    ix = int(x)
    iy = int(y)

    if ix < 0 or iy < 0 or ix >= city.width or iy >= city.height:
        return False

    # Verificar la celda principal
    if city.tiles[iy][ix] == "B":
        return False

    return True


def _manhattan(a, b) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class GreedyPolicy(StepPolicy):
    """
    Greedy simple y robusto que SIEMPRE encuentra un movimiento válido.
    """

    def __init__(self, world, climate_weight: float = 0.5, lookahead_depth: int = 1):
        self.world = world
        self.climate_weight = float(climate_weight)
        self.depth = int(lookahead_depth)
        self.debug = False  # Activar para debugging

    def _climate_risk(self) -> float:
        return 0.3 if getattr(self.world, "weather_system", None) else 0.0

    def _h(self, pos: Tuple[float, float], target: Tuple[int, int]) -> float:
        """Heurística: distancia Manhattan + riesgo climático"""
        if not target:
            return 0.0
        return _manhattan(pos, target) + self.climate_weight * self._climate_risk()

    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        """
        Decide el siguiente paso usando greedy con heurística.
        GARANTIZA retornar un movimiento válido.
        """
        # Sin objetivo, quedarse quieto
        if not ai.current_target:
            if self.debug:
                print(f"[Greedy] AI {id(ai)} sin target")
            return (0, 0)

        target = ai.current_target
        last_dx, last_dy = getattr(ai, "_current_step", (0, 0))
        inverse_last = (-last_dx, -last_dy)

        # Evaluar todas las direcciones cardinales
        candidates = []

        for dx, dy in _cardinal_neighbors():
            nx = ai.x + dx
            ny = ai.y + dy

            # Verificar si es caminable
            if not _is_walkable(self.world, nx, ny):
                continue

            # Calcular score (menor es mejor - más cerca del objetivo)
            score = self._h((nx, ny), target)

            # Penalizar retrocesos
            if (dx, dy) == inverse_last:
                score += 1.0  # Penalización más fuerte

            # Bonus por mantener dirección
            if (dx, dy) == (last_dx, last_dy):
                score -= 0.1

            candidates.append((score, dx, dy))

            if self.debug:
                print(f"[Greedy] Candidato ({dx},{dy}): pos=({nx:.1f},{ny:.1f}) score={score:.2f}")

        # Si no hay candidatos válidos, quedarse quieto
        if not candidates:
            if self.debug:
                print(f"[Greedy] AI en ({ai.x:.1f},{ai.y:.1f}) sin movimientos válidos!")
            return (0, 0)

        # Ordenar por score y tomar el mejor
        candidates.sort(key=lambda x: x[0])
        best_score, best_dx, best_dy = candidates[0]

        if self.debug:
            print(
                f"[Greedy] AI en ({ai.x:.1f},{ai.y:.1f}) -> target={target} elegido=({best_dx},{best_dy}) score={best_score:.2f}")

        return (best_dx, best_dy)