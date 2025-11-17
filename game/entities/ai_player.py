from __future__ import annotations
import math
from typing import Optional, Tuple
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

        # Sistema de sprites direccionales
        self.sprite_textures = {}
        self.current_direction = "down"  # down, up, left, right

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

    def _calculate_direction_from_step(self, dx: int, dy: int):
        """Calcula el ángulo y la dirección del sprite basado en el paso"""
        if dx == 0 and dy == 0:
            return

        # Calcular ángulo basado en el movimiento
        target_angle = math.atan2(dy, dx)
        self.angle = target_angle

        # Determinar dirección del sprite (4 direcciones)
        angle_deg = math.degrees(target_angle)

        # Normalizar ángulo a 0-360
        if angle_deg < 0:
            angle_deg += 360

        # Dividir en 4 cuadrantes
        if 45 <= angle_deg < 135:
            self.current_direction = "up"  # Norte
        elif 135 <= angle_deg < 225:
            self.current_direction = "left"  # Oeste
        elif 225 <= angle_deg < 315:
            self.current_direction = "down"  # Sur
        else:
            self.current_direction = "right"  # Este

    def _apply_step(self, dx: int, dy: int, game):
        if dx == 0 and dy == 0:
            self._current_step = (0, 0)
            return
        city = getattr(game, "city", None)
        if not city:
            return

        # Actualizar dirección y ángulo
        self._calculate_direction_from_step(dx, dy)

        # Normalizar el vector de movimiento
        magnitude = math.sqrt(dx * dx + dy * dy)
        if magnitude > 0:
            norm_dx = dx / magnitude
            norm_dy = dy / magnitude
        else:
            norm_dx, norm_dy = 0, 0

        # Obtener delta_time del game (aproximado si no existe)
        delta_time = getattr(game, '_last_delta_time', 1 / 60.0)

        # Usar el método move() heredado que aplica:
        # - Velocidad efectiva con penalizaciones
        # - Consumo de stamina
        # - Detección de colisiones
        # - Estados de fatiga
        # - Efectos del clima
        # - Peso del inventario
        # - Surface weight
        self.move(norm_dx, norm_dy, delta_time, city)

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

        # Aplicar efectos del clima al AI
        if self.world and hasattr(self.world, 'weather_system') and self.world.weather_system:
            weather_info = self.world.weather_system.get_weather_info()
            self.weather_speed_multiplier = weather_info.get('speed_multiplier', 1.0)
            self.weather_stamina_drain = weather_info.get('stamina_drain', 0.0)

    def update_with_strategy(self, game):
        # limpiar seen timestamps de pedidos que ya no existen
        self._prune_seen_orders(game)

        if not self.strategy:
            return

        # Verificar si el AI puede moverse (no está exhausto)
        if not self.can_move():
            # Si está exhausto, no mover pero sí recuperar stamina
            self._current_step = (0, 0)
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
        # Guardar delta_time para uso en _apply_step
        game._last_delta_time = delta_time

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
        # Guardar delta_time para uso en _apply_step
        game._last_delta_time = delta_time

        self.update(delta_time)
        self.update_with_strategy(game)

    def get_sprite_direction(self) -> str:
        """Retorna la dirección actual del sprite"""
        return self.current_direction

    def get_direction_index(self) -> int:
        """Retorna índice de dirección para arrays (0=down, 1=up, 2=left, 3=right)"""
        directions = {"down": 0, "up": 1, "left": 2, "right": 3}
        return directions.get(self.current_direction, 0)