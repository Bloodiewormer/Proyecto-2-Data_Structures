from __future__ import annotations
import heapq
from typing import List, Tuple, Optional
from game.IA.interfaces import PathPlanner


def _cardinal_neighbors():
    return [(1,0),(-1,0),(0,1),(0,-1)]


def _manhattan(a, b) -> float:           # distancia manhattan forma de medir distancia entre dos puntos en un grid
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


class AStarPlanner(PathPlanner):
    """
    A* sobre la grilla de CityMap usando surface_weight como costo.
    Entrega el siguiente paso discreto; mantiene path interno si se requiere.
    """
    def __init__(self, world, heuristic=_manhattan):
        self.world = world
        self.heuristic = heuristic
        self._goal: Optional[Tuple[int, int]] = None
        self._path: List[Tuple[int, int]] = []
        self._last_start: Optional[Tuple[int, int]] = None

    def set_goal(self, goal: Optional[Tuple[int, int]]) -> None:
        self._goal = tuple(goal) if goal else None
        self._path.clear()

    def _is_walkable(self, x: int, y: int) -> bool:
        city = self.world.city
        if x < 0 or y < 0 or x >= city.width or y >= city.height:
            return False
        return not city.is_wall(x, y)

    def _step_cost(self, x: int, y: int) -> float:
        # Puedes incorporar clima multiplicando este costo
        w = float(self.world.city.get_surface_weight(x, y))
        return max(0.5, w)

    def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
        self._last_start = start
        self._goal = goal

        open_heap = []
        heapq.heappush(open_heap, (0.0, start))
        came = {}
        g = {start: 0.0}

        while open_heap:
            _, cur = heapq.heappop(open_heap)
            if cur == goal:
                break
            for dx, dy in _cardinal_neighbors():
                nx, ny = cur[0] + dx, cur[1] + dy
                if not self._is_walkable(nx, ny):
                    continue
                ng = g[cur] + self._step_cost(nx, ny)
                if (nx, ny) not in g or ng < g[(nx, ny)]:
                    g[(nx, ny)] = ng
                    f = ng + self.heuristic((nx, ny), goal)
                    heapq.heappush(open_heap, (f, (nx, ny)))
                    came[(nx, ny)] = cur

        if goal not in came and start != goal:
            self._path = []
            return

        path_rev: List[Tuple[int, int]] = []
        cur = goal
        while cur != start:
            path_rev.append(cur)
            cur = came.get(cur, start)
            if cur == start:
                break
        path_rev.reverse()
        self._path = path_rev

    def next_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        if not self._goal:
            return (0, 0)

        start = (int(ai.x), int(ai.y))
        if not self._path or self._goal != (self._path[-1] if self._path else None) or start != self._last_start:
            self.replan(start, self._goal)

        if not self._path:
            return (0, 0)

        nx, ny = self._path[0]
        if (int(ai.x), int(ai.y)) == (nx, ny):
            # Ya estamos en el nodo; consumirlo
            self._path.pop(0)
            return (0, 0)

        dx = 1 if nx > ai.x else -1 if nx < ai.x else 0
        dy = 1 if ny > ai.y else -1 if ny < ai.y else 0
        return (dx, dy)