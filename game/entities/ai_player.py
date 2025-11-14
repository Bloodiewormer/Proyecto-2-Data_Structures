from __future__ import annotations
from typing import Optional, Tuple

from game.entities.player import Player
from game.core.orders import Order

try:
    from game.IA.strategies import EasyStrategy, MediumStrategy, HardStrategy, BaseStrategy
except Exception:
    from game.IA.strategies.strategies import EasyStrategy, MediumStrategy, HardStrategy  # type: ignore
    class BaseStrategy:  # type: ignore
        def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
            return (0, 0)


class AIPlayer(Player):
    def __init__(self,
                 start_x: float = 0.0,
                 start_y: float = 0.0,
                 config: Optional[dict] = None,
                 difficulty: str = "easy",
                 world=None,
                 strategy: Optional[BaseStrategy] = None,
                 **kwargs):
        if 'x' in kwargs:
            start_x = kwargs.pop('x')
        if 'y' in kwargs:
            start_y = kwargs.pop('y')

        if config is None and world and hasattr(world, "app_config"):
            try:
                config = world.app_config.get("player", {})
            except Exception:
                config = {}

        config = config or {}
        super().__init__(start_x, start_y, config)

        self.is_ai = True
        self.world = world
        self.difficulty = str(difficulty or "easy").lower().strip()
        self.current_target: Optional[Tuple[int, int]] = None
        self._current_step: Tuple[int, int] = (0, 0)

        self._decision_interval = 0.5
        self._decision_cooldown = 0.0

        self.strategy: BaseStrategy = strategy or self._build_default_strategy(self.difficulty)

    def _build_default_strategy(self, difficulty: str) -> BaseStrategy:
        host = self.world or self
        if difficulty == "easy":
            return EasyStrategy(host)
        if difficulty == "medium":
            return MediumStrategy(host)
        if difficulty == "hard":
            return HardStrategy(host)
        return EasyStrategy(host)

    def set_strategy(self, strategy: BaseStrategy):
        self.strategy = strategy

    def _apply_step(self, dx: int, dy: int, game):
        if dx == 0 and dy == 0:
            self._current_step = (0, 0)
            return
        city = getattr(game, "city", None)
        if not city:
            return
        nx = self.x + dx
        ny = self.y + dy
        if not city.is_wall(nx, self.y):
            self.x = nx
        if not city.is_wall(self.x, ny):
            self.y = ny
        self._current_step = (dx, dy)

    def _handle_order_state_transitions(self, game):
        if not self.inventory.orders:
            return
        order: Order = self.inventory.orders[0]
        cx, cy = int(self.x), int(self.y)
        if getattr(order, "status", "") in ("in_progress", "assigned") and (cx, cy) == tuple(order.pickup_pos):
            try:
                order.pickup()
            except Exception:
                pass

    def add_order_to_inventory(self, order) -> bool:
        try:
            if hasattr(self.inventory, "has_space_for") and not self.inventory.has_space_for(order):
                return False
        except Exception:
            pass
        try:
            self.inventory.add_order(order)
        except Exception:
            self.inventory.orders.append(order)
        try:
            if getattr(order, "status", "") not in ("picked_up", "delivered"):
                order.status = "in_progress"
        except Exception:
            pass
        return True

    def update(self, delta_time: float):
        super().update(delta_time)

    def update_with_strategy(self, game):
        if not self.strategy:
            return
        try:
            if hasattr(self.strategy, "world"):
                self.strategy.world.city = getattr(game, "city", None)
                self.strategy.world.weather_system = getattr(game, "weather_system", None)
        except Exception:
            pass
        try:
            step = self.strategy.decide(self, game)
        except Exception:
            step = (0, 0)
        if not step:
            step = (0, 0)
        dx, dy = step
        self._apply_step(dx, dy, game)
        self._handle_order_state_transitions(game)

    def update_ai(self, delta_time: float, game):
        """
        Modo con cooldown (cada ~0.5s); reduce costo si HardStrategy hace A* frecuente.
        """
        self.update(delta_time)
        self._decision_cooldown -= delta_time
        if self._decision_cooldown <= 0:
            self._decision_cooldown = self._decision_interval
            self.update_with_strategy(game)

    def update_tick(self, delta_time: float, game):
        """
        Decisiones cada frame (más reactivo, más costoso).
        Usa update_ai si prefieres throttling.
        """
        self.update(delta_time)
        self.update_with_strategy(game)
