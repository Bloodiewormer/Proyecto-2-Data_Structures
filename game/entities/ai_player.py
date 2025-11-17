from __future__ import annotations
from typing import Optional, Tuple, Dict
import time

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

        # --- Accept-delay por dificultad / configurable ---
        # valores por defecto (puedes cambiarlos)
        default_delays = {
            "easy": 5,
            "medium": 2.5,
            "hard": 1.0
        }
        # intentamos leer configuration en app_config: app_config["ai"]["accept_delays"]
        configured_delays = {}
        try:
            cfg = getattr(self.world, "app_config", {}) or {}
            configured_delays = (cfg.get("ai", {}) or {}).get("accept_delays", {})
            # espera un mapping, ej: {"easy": 2.0, "medium": 1.0, "hard": 0.1}
        except Exception:
            configured_delays = {}

        self.order_accept_delay = float(
            configured_delays.get(self.difficulty, default_delays.get(self.difficulty, 0.0)))

        # timestamp en que se 'vio' cada pedido (order.id -> timestamp)
        self._order_seen_times: Dict[str, float] = {}



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
        # si aceptó, actualizar peso
        try:
            self.set_inventory_weight(self.inventory.current_weight)
        except Exception:
            pass
        return True

    def try_accept_order_with_delay(self, order, current_time: Optional[float] = None) -> bool:
        """
        Intentar aceptar 'order' respetando el delay de aceptación configurado.
        current_time preferiblemente game.total_play_time; si es None usa time.time()
        Retorna True si el pedido fue aceptado (y ya se debe eliminar de pending_orders).
        """
        now = current_time if current_time is not None else time.time()
        oid = getattr(order, "id", None)
        if oid is None:
            # si no tiene id, intentar aceptar de forma inmediata
            return self.add_order_to_inventory(order)

        # si el pedido ya no está en la cola (otro jugador lo tomó), limpiar y devolver False
        try:
            pending = getattr(self.world, "pending_orders", None)
            if pending is not None and all(getattr(o, "id", None) != oid for o in pending):
                self._order_seen_times.pop(str(oid), None)
                return False
        except Exception:
            pass

        seen_ts = self._order_seen_times.get(str(oid))
        if seen_ts is None:
            # registrar el primer "visto"
            self._order_seen_times[str(oid)] = now
            return False

        # comprobar si ya pasó el delay requerido
        if (now - seen_ts) >= float(self.order_accept_delay):
            accepted = False
            try:
                accepted = self.add_order_to_inventory(order)
            except Exception:
                accepted = False
            if accepted:
                self._order_seen_times.pop(str(oid), None)
            return accepted

        return False

    def _prune_seen_orders(self, game):
        """
        Quitar timestamps de pedidos que ya no están en pending_orders para no acumular memoria.
        """
        try:
            pending_ids = {str(getattr(o, "id", None)) for o in (getattr(game, "pending_orders", []) or [])}
            for oid in list(self._order_seen_times.keys()):
                if oid not in pending_ids:
                    self._order_seen_times.pop(oid, None)
        except Exception:
            pass

    def update(self, delta_time: float):
        super().update(delta_time)

    def update_with_strategy(self, game):
        # limpiar seen timestamps de pedidos que ya no existen
        self._prune_seen_orders(game)

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
