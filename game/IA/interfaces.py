from __future__ import annotations
from typing import Protocol, Tuple, Optional


class StepPolicy(Protocol):
    """
    Calcula un paso discreto (dx, dy) en {-1,0,1} dado el estado del AI.
    No mueve directamente al AI (solo retorna la intención).
    """
    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]: ...


class PathPlanner(Protocol):
    """
    Planifica un camino en la grilla y entrega el siguiente paso hacia la meta.
    """
    def set_goal(self, goal: Optional[Tuple[int, int]]) -> None: ...
    def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None: ...
    def next_step(self, ai: "AIPlayer") -> Tuple[int, int]: ...