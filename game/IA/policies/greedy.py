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
    Greedy con pathfinding básico BFS para evitar quedar atrapado.
    Usa BFS (más simple que A*) para encontrar caminos cuando greedy falla.
    """

    def __init__(self, world, climate_weight: float = 0.5, lookahead_depth: int = 1):
        self.world = world
        self.climate_weight = float(climate_weight)
        self.depth = int(lookahead_depth)
        self.debug = getattr(world, 'debug', False)

        # Sistema de pathfinding básico
        self._bfs_path = []
        self._bfs_target = None
        self._stuck_counter = 0
        self._last_position = None

    def _climate_risk(self) -> float:
        return 0.3 if getattr(self.world, "weather_system", None) else 0.0

    def _h(self, pos: Tuple[float, float], target: Tuple[int, int]) -> float:
        """Heurística: distancia Manhattan + riesgo climático"""
        if not target:
            return 0.0
        return _manhattan(pos, target) + self.climate_weight * self._climate_risk()

    def _find_bfs_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> list:
        """
        BFS simple para encontrar camino cuando greedy falla.
        Menos eficiente que A* pero funciona para IA media.
        """
        from collections import deque

        queue = deque([(start, [start])])
        visited = {start}
        max_iterations = 500
        iterations = 0

        while queue and iterations < max_iterations:
            iterations += 1
            current, path = queue.popleft()

            if current == goal:
                return path[1:] if len(path) > 1 else []

            for dx, dy in _cardinal_neighbors():
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if neighbor in visited:
                    continue

                if not _is_walkable(self.world, nx, ny):
                    continue

                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

        return []

    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        """
        Decide el siguiente paso usando greedy + BFS de respaldo.
        """
        # Sin objetivo, quedarse quieto
        if not ai.current_target:
            self._bfs_path = []
            self._stuck_counter = 0
            if self.debug:
                print(f"[Greedy-MEDIUM] AI en ({ai.x:.1f},{ai.y:.1f}) sin target")
            return (0, 0)

        target = ai.current_target
        current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Detectar si está atascado (posición no cambia)
        if self._last_position == current_pos:
            self._stuck_counter += 1
        else:
            # CRÍTICO: Solo resetear si NO está siguiendo un path BFS activo
            if not self._bfs_path:
                self._stuck_counter = 0
            else:
                # Está avanzando en el path, resetear contador
                self._stuck_counter = 0

        self._last_position = current_pos

        # Si está atascado O el target cambió, recalcular path con BFS
        should_replan = False

        if self._stuck_counter >= 3:
            should_replan = True
            reason = "stuck"
        elif self._bfs_target != target:
            should_replan = True
            reason = "target_change"
        elif not self._bfs_path:
            should_replan = True
            reason = "no_path"

        if should_replan:
            if self.debug:
                print(f"[Greedy-MEDIUM] 🔄 BFS desde {current_pos} a {target} (razón: {reason})")

            self._bfs_path = self._find_bfs_path(current_pos, target)
            self._bfs_target = target
            self._stuck_counter = 0

            if not self._bfs_path:
                if self.debug:
                    print(f"[Greedy-MEDIUM] ❌ Sin camino a {target}")
                return (0, 0)
            elif self.debug:
                print(f"[Greedy-MEDIUM] ✅ Path: {len(self._bfs_path)} nodos")

        # Si hay path BFS activo, seguirlo
        if self._bfs_path:
            next_node = self._bfs_path[0]

            # Si llegamos al nodo actual, avanzar al siguiente
            if current_pos == next_node:
                self._bfs_path.pop(0)
                if not self._bfs_path:
                    if self.debug:
                        print(f"[Greedy-MEDIUM] ✓ Llegó al objetivo")
                    return (0, 0)
                next_node = self._bfs_path[0]

            # Calcular paso hacia el siguiente nodo
            dx = 1 if next_node[0] > ai.x else -1 if next_node[0] < ai.x else 0
            dy = 1 if next_node[1] > ai.y else -1 if next_node[1] < ai.y else 0

            return (dx, dy)

        # Greedy normal (solo si no hay path BFS)
        last_dx, last_dy = getattr(ai, "_current_step", (0, 0))
        inverse_last = (-last_dx, -last_dy)

        candidates = []

        for dx, dy in _cardinal_neighbors():
            nx = ai.x + dx
            ny = ai.y + dy

            if not _is_walkable(self.world, nx, ny):
                continue

            score = self._h((nx, ny), target)

            if (dx, dy) == inverse_last:
                score += 1.0

            if (dx, dy) == (last_dx, last_dy):
                score -= 0.1

            candidates.append((score, dx, dy))

        if not candidates:
            if self.debug:
                print(f"[Greedy-MEDIUM] ⚠️  Sin movimientos, activando BFS")
            self._stuck_counter = 3
            return (0, 0)

        candidates.sort(key=lambda x: x[0])
        best_score, best_dx, best_dy = candidates[0]

        return (best_dx, best_dy)