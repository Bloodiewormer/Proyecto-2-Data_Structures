from __future__ import annotations
import heapq
from typing import List, Tuple, Optional
from game.IA.interfaces import PathPlanner


def _cardinal_neighbors():
    return [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _manhattan(a, b) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class AStarPlanner(PathPlanner):
    """
    A* con detección robusta de esquinas y colisiones.
    """

    def __init__(self, world, heuristic=_manhattan):
        self.world = world
        self.heuristic = heuristic
        self._goal: Optional[Tuple[int, int]] = None
        self._path: List[Tuple[int, int]] = []
        self._last_start: Optional[Tuple[int, int]] = None
        self.debug = False  # Activar para debugging

    def set_goal(self, goal: Optional[Tuple[int, int]]) -> None:
        self._goal = tuple(goal) if goal else None
        self._path.clear()

    def _is_walkable(self, x: int, y: int) -> bool:
        """
        Verifica si una celda es caminable Y no es esquina peligrosa.
        """
        city = self.world.city

        # Fuera de límites = no caminable
        if x < 0 or y < 0 or x >= city.width or y >= city.height:
            return False

        # Celda es pared = no caminable
        if city.tiles[y][x] == "B":
            return False

        # CRUCIAL: Evitar esquinas diagonales de edificios
        # Verificar las 4 diagonales
        dangerous_corner = False

        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            corner_x = x + dx
            corner_y = y + dy

            # Si está fuera de límites, ignorar
            if corner_x < 0 or corner_y < 0 or corner_x >= city.width or corner_y >= city.height:
                continue

            # Si hay pared en la diagonal
            if city.tiles[corner_y][corner_x] == "B":
                # Verificar los dos lados adyacentes
                side1_x, side1_y = x + dx, y
                side2_x, side2_y = x, y + dy

                side1_wall = False
                side2_wall = False

                if 0 <= side1_x < city.width and 0 <= side1_y < city.height:
                    side1_wall = (city.tiles[side1_y][side1_x] == "B")

                if 0 <= side2_x < city.width and 0 <= side2_y < city.height:
                    side2_wall = (city.tiles[side2_y][side2_x] == "B")

                # Si AMBOS lados son paredes, es esquina cerrada - MUY PELIGROSO
                if side1_wall and side2_wall:
                    dangerous_corner = True
                    break

        return not dangerous_corner

    def _step_cost(self, x: int, y: int) -> float:
        """Costo del paso basado en superficie"""
        try:
            w = float(self.world.city.get_surface_weight(x, y))
            return max(0.5, w)
        except:
            return 1.0

    def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
        """
        A* pathfinding con validación de esquinas.
        """
        self._last_start = start
        self._goal = goal

        # Validar que start y goal sean caminables
        if not self._is_walkable(start[0], start[1]):
            if self.debug:
                print(f"[A*] Start {start} no es caminable!")
            # Buscar celda cercana válida
            start = self._find_nearest_walkable(start)
            if not start:
                self._path = []
                return

        if not self._is_walkable(goal[0], goal[1]):
            if self.debug:
                print(f"[A*] Goal {goal} no es caminable!")
            # Buscar celda cercana válida
            goal = self._find_nearest_walkable(goal)
            if not goal:
                self._path = []
                return

        open_heap = []
        heapq.heappush(open_heap, (0.0, start))
        came = {}
        g = {start: 0.0}
        closed = set()

        iterations = 0
        max_iterations = self.world.city.width * self.world.city.height

        while open_heap and iterations < max_iterations:
            iterations += 1
            _, cur = heapq.heappop(open_heap)

            if cur in closed:
                continue

            closed.add(cur)

            if cur == goal:
                break

            for dx, dy in _cardinal_neighbors():
                nx, ny = cur[0] + dx, cur[1] + dy

                if (nx, ny) in closed:
                    continue

                if not self._is_walkable(nx, ny):
                    continue

                ng = g[cur] + self._step_cost(nx, ny)

                if (nx, ny) not in g or ng < g[(nx, ny)]:
                    g[(nx, ny)] = ng
                    f = ng + self.heuristic((nx, ny), goal)
                    heapq.heappush(open_heap, (f, (nx, ny)))
                    came[(nx, ny)] = cur

        # Reconstruir camino
        if goal not in came and start != goal:
            if self.debug:
                print(f"[A*] No se encontró camino de {start} a {goal}")
            self._path = []
            return

        path_rev: List[Tuple[int, int]] = []
        cur = goal
        safety = 0
        max_path_length = self.world.city.width * self.world.city.height

        while cur != start and safety < max_path_length:
            path_rev.append(cur)
            cur = came.get(cur)
            if cur is None:
                break
            safety += 1

        path_rev.reverse()
        self._path = path_rev

        if self.debug:
            print(f"[A*] Camino encontrado: {len(self._path)} pasos")

    def _find_nearest_walkable(self, pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """
        Encuentra la celda caminable más cercana usando BFS.
        """
        x, y = pos

        # BFS para encontrar la celda más cercana
        from collections import deque
        queue = deque([(x, y, 0)])  # (x, y, distancia)
        visited = {(x, y)}

        while queue:
            cx, cy, dist = queue.popleft()

            if self._is_walkable(cx, cy):
                return (cx, cy)

            # No buscar muy lejos
            if dist > 5:
                continue

            for dx, dy in _cardinal_neighbors():
                nx, ny = cx + dx, cy + dy

                if (nx, ny) in visited:
                    continue

                if nx < 0 or ny < 0 or nx >= self.world.city.width or ny >= self.world.city.height:
                    continue

                visited.add((nx, ny))
                queue.append((nx, ny, dist + 1))

        return None

    def next_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        """
        Retorna el siguiente paso discreto hacia el objetivo.
        """
        if not self._goal:
            return (0, 0)

        # Redondear posición actual al entero más cercano
        start = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Replanificar si es necesario
        if (not self._path or
                self._goal != (self._path[-1] if self._path else None) or
                start != self._last_start):
            self.replan(start, self._goal)

        if not self._path:
            if self.debug:
                print(f"[A*] Sin camino disponible")
            return (0, 0)

        nx, ny = self._path[0]
        current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Si ya llegamos al nodo actual, avanzar al siguiente
        if current_pos == (nx, ny):
            self._path.pop(0)
            if not self._path:
                return (0, 0)
            nx, ny = self._path[0]

        # Calcular paso discreto
        dx = 1 if nx > ai.x else -1 if nx < ai.x else 0
        dy = 1 if ny > ai.y else -1 if ny < ai.y else 0

        return (dx, dy)