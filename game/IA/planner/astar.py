# game/IA/planner/astar.py

from __future__ import annotations
import heapq
import math
from typing import List, Tuple, Optional
from game.IA.interfaces import PathPlanner


def _cardinal_neighbors():
    return [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _manhattan(a, b) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class AStarPlanner(PathPlanner):
    """
    A* con detección robusta de esquinas y colisiones.
    VERSIÓN CORREGIDA - Previene que la IA entre en edificios.
    """

    def __init__(self, world, heuristic=_manhattan):
        self.world = world
        self.heuristic = heuristic
        self._goal: Optional[Tuple[int, int]] = None
        self._path: List[Tuple[int, int]] = []
        self._last_start: Optional[Tuple[int, int]] = None
        self.debug = False

    def set_goal(self, goal: Optional[Tuple[int, int]]) -> None:
        self._goal = tuple(goal) if goal else None
        self._path.clear()

    def _is_walkable(self, x: int, y: int) -> bool:
        """
        Versión CORREGIDA: Menos restrictiva pero segura.
        """
        city = self.world.city

        # 1. Límites del mapa
        if x < 0 or y < 0 or x >= city.width or y >= city.height:
            return False

        # 2. La celda NO debe ser edificio
        if city.tiles[y][x] == "B":
            return False

        # 3. SOLO bloquear esquinas que sean REALMENTE imposibles
        # (donde hay edificios en L formando un callejón sin salida)
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            corner_x, corner_y = x + dx, y + dy

            # Verificar límites
            if not (0 <= corner_x < city.width and 0 <= corner_y < city.height):
                continue

            # Si hay edificio en diagonal
            if city.tiles[corner_y][corner_x] == "B":
                # Solo bloquear si AMBOS lados adyacentes son edificios
                side1_x, side1_y = x + dx, y
                side2_x, side2_y = x, y + dy

                side1_wall = False
                side2_wall = False

                if 0 <= side1_x < city.width and 0 <= side1_y < city.height:
                    side1_wall = (city.tiles[side1_y][side1_x] == "B")
                else:
                    side1_wall = True  # Fuera de límites = pared

                if 0 <= side2_x < city.width and 0 <= side2_y < city.height:
                    side2_wall = (city.tiles[side2_y][side2_x] == "B")
                else:
                    side2_wall = True  # Fuera de límites = pared

                # CRÍTICO: Solo bloquear si es esquina CERRADA (ambos lados son paredes)
                if side1_wall and side2_wall:
                    if self.debug:
                        print(f"[A*] Esquina cerrada en ({x},{y})")
                    return False


        return True

    def _step_cost(self, x: int, y: int) -> float:
        """Costo del paso basado en superficie"""
        try:
            w = float(self.world.city.get_surface_weight(x, y))
            return max(0.5, w)
        except:
            return 1.0

    def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
        """
        A* pathfinding con validación exhaustiva de esquinas.
        """
        self._last_start = start
        self._goal = goal

        # Validar que start sea caminable
        if not self._is_walkable(start[0], start[1]):
            if self.debug:
                print(f"[A*] Start {start} no es caminable!")
            # Buscar celda cercana válida
            start = self._find_nearest_walkable(start)
            if not start:
                self._path = []
                return

        # Validar que goal sea caminable
        if not self._is_walkable(goal[0], goal[1]):
            if self.debug:
                print(f"[A*] Goal {goal} no es caminable!")
            # Buscar celda cercana válida
            goal = self._find_nearest_walkable(goal)
            if not goal:
                self._path = []
                return

        # A* estándar
        open_heap = []
        heapq.heappush(open_heap, (0.0, start))
        came_from = {}
        g_score = {start: 0.0}
        closed_set = set()

        iterations = 0
        max_iterations = self.world.city.width * self.world.city.height * 2

        while open_heap and iterations < max_iterations:
            iterations += 1
            _, current = heapq.heappop(open_heap)

            if current in closed_set:
                continue

            closed_set.add(current)

            # Meta alcanzada
            if current == goal:
                break

            # Explorar vecinos cardinales
            for dx, dy in _cardinal_neighbors():
                neighbor = (current[0] + dx, current[1] + dy)

                if neighbor in closed_set:
                    continue

                # Validación robusta de walkability
                if not self._is_walkable(neighbor[0], neighbor[1]):
                    continue

                # Calcular nuevo g_score
                tentative_g = g_score[current] + self._step_cost(neighbor[0], neighbor[1])

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self.heuristic(neighbor, goal)
                    heapq.heappush(open_heap, (f_score, neighbor))
                    came_from[neighbor] = current

        # Reconstruir camino
        if goal not in came_from and start != goal:
            if self.debug:
                print(f"[A*] No se encontró camino de {start} a {goal}")
            self._path = []
            return

        # Reconstruir path desde goal hasta start
        path_reversed: List[Tuple[int, int]] = []
        current = goal
        safety_counter = 0
        max_path_length = self.world.city.width * self.world.city.height

        while current != start and safety_counter < max_path_length:
            path_reversed.append(current)
            current = came_from.get(current)
            if current is None:
                break
            safety_counter += 1

        path_reversed.reverse()
        self._path = path_reversed

        # Validar que el camino completo sea seguro
        if not self._validate_path(self._path):
            if self.debug:
                print(f"[A*] Path inválido detectado, limpiando")
            self._path = []
            return

        if self.debug:
            print(f"[A*] Camino encontrado: {len(self._path)} pasos (iteraciones: {iterations})")

    def _validate_path(self, path: List[Tuple[int, int]]) -> bool:
        """
        Valida que todo el camino sea seguro (sin edificios).
        """
        if not path:
            return True

        for x, y in path:
            if not self._is_walkable(x, y):
                if self.debug:
                    print(f"[A*] Path inválido en ({x},{y})")
                return False

        return True

    def _find_nearest_walkable(self, pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """
        Encuentra la celda caminable más cercana usando BFS.
        """
        x, y = pos

        from collections import deque
        queue = deque([(x, y, 0)])  # (x, y, distancia)
        visited = {(x, y)}

        while queue:
            cx, cy, dist = queue.popleft()

            if self._is_walkable(cx, cy):
                if self.debug:
                    print(f"[A*] Celda caminable encontrada en ({cx},{cy}) a distancia {dist}")
                return (cx, cy)

            # No buscar demasiado lejos
            if dist > 8:
                continue

            for dx, dy in _cardinal_neighbors():
                nx, ny = cx + dx, cy + dy

                if (nx, ny) in visited:
                    continue

                if nx < 0 or ny < 0 or nx >= self.world.city.width or ny >= self.world.city.height:
                    continue

                visited.add((nx, ny))
                queue.append((nx, ny, dist + 1))

        if self.debug:
            print(f"[A*] No se encontró celda caminable cerca de {pos}")
        return None

    def next_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        """
        Retorna el siguiente paso discreto hacia el objetivo.
        VERSIÓN OPTIMIZADA: Reduce recálculos innecesarios.
        """
        if not self._goal:
            return (0, 0)

        # Redondear posición actual al entero más cercano
        start = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Calcular distancia al siguiente nodo del path
        needs_replan = False

        if not self._path:
            needs_replan = True
        elif self._goal != (self._path[-1] if self._path else None):
            needs_replan = True
        elif self._path and len(self._path) > 0:
            next_node = self._path[0]
            distance_to_next = math.sqrt((ai.x - next_node[0]) ** 2 + (ai.y - next_node[1]) ** 2)
            if distance_to_next > 1.5:
                needs_replan = True

        # Replanificar solo si es necesario
        if needs_replan:
            self.replan(start, self._goal)

        if not self._path:
            if self.debug:
                print(f"[A*] Sin camino disponible para AI en {start}")
            return (0, 0)

        next_node = self._path[0]
        current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))

        # Si ya llegamos al nodo actual, avanzar al siguiente
        if current_pos == next_node:
            self._path.pop(0)
            if not self._path:
                return (0, 0)
            next_node = self._path[0]

        # Calcular paso discreto
        dx = 1 if next_node[0] > ai.x else -1 if next_node[0] < ai.x else 0
        dy = 1 if next_node[1] > ai.y else -1 if next_node[1] < ai.y else 0

        return (dx, dy)