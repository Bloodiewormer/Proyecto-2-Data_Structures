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


def _nearest_walkable(world, goal: Tuple[int, int], max_search: int = 8) -> Optional[Tuple[int, int]]:
    """
    Encuentra la celda caminable más cercana al objetivo.
    Usado cuando el objetivo está dentro de un edificio.
    """
    from collections import deque

    gx, gy = goal

    # Si el objetivo ya es caminable, retornarlo
    if _is_walkable(world, gx, gy):
        return goal

    # BFS para encontrar la celda caminable más cercana
    queue = deque([(gx, gy, 0)])
    visited = {(gx, gy)}

    while queue:
        cx, cy, dist = queue.popleft()

        # No buscar demasiado lejos
        if dist > max_search:
            continue

        # Verificar vecinos
        for dx, dy in _cardinal_neighbors():
            nx, ny = cx + dx, cy + dy

            if (nx, ny) in visited:
                continue

            visited.add((nx, ny))

            # ¿Es caminable?
            if _is_walkable(world, nx, ny):
                return (nx, ny)

            # Agregar a la cola para seguir buscando
            queue.append((nx, ny, dist + 1))

    # No se encontró nada caminable cerca
    return None


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

        # Control de debug
        self._last_debug_time = 0.0
        self._debug_interval = 5.0  # Debug cada 5 segundos

    def _climate_risk(self) -> float:
        return 0.3 if getattr(self.world, "weather_system", None) else 0.0

    def _h(self, pos: Tuple[float, float], target: Tuple[int, int]) -> float:
        """Heurística: distancia Manhattan + riesgo climático"""
        if not target:
            return 0.0
        return _manhattan(pos, target) + self.climate_weight * self._climate_risk()

    def _should_show_debug(self, current_time: float) -> bool:
        """Determina si debe mostrar debug (cada 5 segundos)"""
        if not self.debug:
            return False

        if current_time - self._last_debug_time >= self._debug_interval:
            self._last_debug_time = current_time
            return True
        return False

    def _find_bfs_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> list:
        """
        BFS simple para encontrar camino cuando greedy falla.
        Menos eficiente que A* pero funciona para IA media.
        """
        from collections import deque

        # CRÍTICO: Verificar que el objetivo sea caminable
        original_goal = goal
        if not _is_walkable(self.world, goal[0], goal[1]):
            # Buscar la celda caminable más cercana
            adjusted_goal = _nearest_walkable(self.world, goal, max_search=10)
            if adjusted_goal:
                goal = adjusted_goal
            else:
                return []

        # Verificar que el inicio sea caminable
        if not _is_walkable(self.world, start[0], start[1]):
            return []

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
        import time
        current_time = time.time()
        show_debug = self._should_show_debug(current_time)

        # Sin objetivo, quedarse quieto
        if not ai.current_target:
            self._bfs_path = []
            self._stuck_counter = 0
            return (0, 0)

        target = ai.current_target
        current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Detectar si está atascado (posición no cambia)
        if self._last_position == current_pos:
            self._stuck_counter += 1
        else:
            # Solo resetear si NO está siguiendo un path BFS activo
            if not self._bfs_path:
                self._stuck_counter = 0
            else:
                self._stuck_counter = 0

        self._last_position = current_pos

        # Si está atascado O el target cambió, recalcular path con BFS
        should_replan = False

        if self._stuck_counter >= 3:
            should_replan = True
            reason = "atascado"
        elif self._bfs_target != target:
            should_replan = True
            reason = "cambio_objetivo"
        elif not self._bfs_path:
            should_replan = True
            reason = "sin_path"

        if should_replan:
            if show_debug:
                print(f"[Greedy-MEDIUM] 🔄 Recalculando path ({reason})")

            self._bfs_path = self._find_bfs_path(current_pos, target)
            self._bfs_target = target
            self._stuck_counter = 0

            if not self._bfs_path and show_debug:
                print(f"[Greedy-MEDIUM] ⚠️  No se encontró path a {target}")
            elif self._bfs_path and show_debug:
                print(f"[Greedy-MEDIUM] ✅ Path encontrado: {len(self._bfs_path)} nodos")

        # Si hay path BFS activo, seguirlo
        if self._bfs_path:
            next_node = self._bfs_path[0]

            # Si llegamos al nodo actual, avanzar al siguiente
            if current_pos == next_node:
                self._bfs_path.pop(0)
                if not self._bfs_path:
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
            self._stuck_counter = 3
            return (0, 0)

        candidates.sort(key=lambda x: x[0])
        best_score, best_dx, best_dy = candidates[0]

        return (best_dx, best_dy)