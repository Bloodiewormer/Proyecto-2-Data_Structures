# file: game/player.py
import math
from typing import Dict, Any, Tuple, Optional
from .utils import clamp, normalize_angle
from .inventory import Inventory
from game.orders import Order 
from datetime import datetime

class PlayerState:
    NORMAL = "normal"      # >30 stamina
    TIRED = "tired"        # 10-30 stamina
    EXHAUSTED = "exhausted"  # 0-10 stamina

class Player:
    def __init__(self, start_x: float, start_y: float, config: Dict[str, Any]):
        self.x = start_x
        self.y = start_y
        self.angle = 0.0

        self.base_speed = config.get("base_speed", 3.0)
        self.turn_speed = config.get("turn_speed", 1.5)
        self.move_speed = config.get("move_speed", 3.0)

        # Atributos dinámicos se deben cambiar en config.json
        game_config = config.get("game", {}) if "game" in config else {}
        self.stamina = float(game_config.get("initial_stamina", 100.0))
        self.reputation = float(game_config.get("initial_reputation", 70.0))
        self.earnings = 0.0
        self.total_weight = 0.0

        self.rep_changes = game_config.get("reputation_changes", {
            "delivery_on_time": 3,
            "delivery_early": 5,
            "delivery_late_minor": -2,
            "delivery_late_moderate": -5,
            "delivery_late_severe": -10,
            "cancel_order": -4,
            "expire_order": -6,
            "streak_bonus": 2,
            "streak_threshold": 3
        })

        self.rep_thresholds = game_config.get("reputation_thresholds", {
            "critical": 20,
            "excellent": 90,
            "bonus_first_late": 85
        })

        self.payment_mods = game_config.get("payment_modifiers", {
            "excellent_bonus": 1.05,
            "first_late_penalty": 0.5
        })

        self.delivery_thresholds = game_config.get("delivery_time_thresholds", {
            "late_minor": 30,
            "late_moderate": 120
        })

        #inventario 
        max_inventory_weight = config.get("max_inventory_weight", 10.0)
        self.inventory = Inventory(max_inventory_weight)

        self.state = PlayerState.NORMAL
        self.is_moving = False
        self.recovery_timer = 0.0

        # Multiplicadores de clima
        self.weather_speed_multiplier = 1.0
        self.weather_stamina_drain = 0.0

        self.deliveries_completed = 0
        self.orders_cancelled = 0
        self.consecutive_on_time = 0


    def add_order_to_inventory(self, order: Order) -> bool:
        """agregar un pedido al inventario del player y actualiza el peso total"""
        success = self.inventory.add_order(order)
        if success:
            self.set_inventory_weight(self.inventory.current_weight)
        return success

    def remove_order_from_inventory(self, order_id: str) -> Optional[Order]:
        """quita un pedido del inventario y actualiza el peso total"""
        removed_order = self.inventory.remove_order(order_id)
        if removed_order:
            self.set_inventory_weight(self.inventory.current_weight)
        return removed_order

    def get_current_order(self) -> Optional[Order]:
        """obtiene el pedido que se agarro actualmente"""
        return self.inventory.get_current_order()

    def update(self, delta_time: float):
        self._update_state()

        if not self.is_moving:
            self._recover_stamina(delta_time)

        if self.weather_stamina_drain > 0:
            self.stamina = clamp(self.stamina - self.weather_stamina_drain * delta_time, 0, 100)

        self.is_moving = False

    def move(self, dx: float, dy: float, delta_time: float, city_map):
        # Evaluar estado antes de mover
        self._update_state()
        if self.state == PlayerState.EXHAUSTED:
            return

        # v = v0 * Mclima * Mpeso * Mrep * Mresistencia * surface_weight(tile)
        effective_speed = self._calculate_effective_speed() * self._get_surface_weight(city_map)

        move_distance = effective_speed * delta_time
        new_x = self.x + dx * move_distance
        new_y = self.y + dy * move_distance

        if not city_map.is_wall(new_x, self.y):
            self.x = new_x
        if not city_map.is_wall(self.x, new_y):
            self.y = new_y

        self._consume_stamina_for_movement(delta_time)
        self.is_moving = True

    def turn_left(self, delta_time: float):
        self.angle = normalize_angle(self.angle - self.turn_speed * delta_time)

    def turn_right(self, delta_time: float):
        self.angle = normalize_angle(self.angle + self.turn_speed * delta_time)

    def apply_weather_effects(self, speed_multiplier: float, stamina_drain: float):
        self.weather_speed_multiplier = speed_multiplier
        self.weather_stamina_drain = stamina_drain

    def add_earnings(self, amount: float):
        if self.reputation >= self.rep_thresholds.get("excellent", 90):
            amount *= self.payment_mods.get("excellent_bonus", 1.05)
        self.earnings += amount

    def update_reputation_for_delivery(self, order):

        # Calcular si fue a tiempo, temprano o tarde
        if hasattr(order, 'deadline') and order.deadline:
            try:
                if isinstance(order.deadline, str):
                    deadline_dt = datetime.fromisoformat(order.deadline.replace('Z', '+00:00'))
                else:
                    deadline_dt = order.deadline

                now = datetime.now(deadline_dt.tzinfo) if deadline_dt.tzinfo else datetime.now()
                time_diff = (deadline_dt - now).total_seconds()

                # Calcular porcentaje de tiempo restante
                time_margin = time_diff / order.time_limit if hasattr(order, 'time_limit') and order.time_limit > 0 else 0

                # Entrega temprana (≥20% del tiempo antes)
                if time_margin >= 0.20:
                    rep_change = self.rep_changes.get("delivery_early", 5)
                # A tiempo
                elif time_diff >= 0:
                    rep_change = self.rep_changes.get("delivery_on_time", 3)
                # Tarde
                else:
                    late_seconds = abs(time_diff)
                    if late_seconds <= self.delivery_thresholds.get("late_minor", 30):
                        rep_change = self.rep_changes.get("delivery_late_minor", -2)
                    elif late_seconds <= self.delivery_thresholds.get("late_moderate", 120):
                        rep_change = self.rep_changes.get("delivery_late_moderate", -5)
                    else:
                        rep_change = self.rep_changes.get("delivery_late_severe", -10)

                    # Primera tardanza del día con reputación alta
                    if self.reputation >= self.rep_thresholds.get("bonus_first_late", 85):
                        rep_change *= self.payment_mods.get("first_late_penalty", 0.5)
            except Exception:
                # Fallback: asumir entrega a tiempo
                rep_change = self.rep_changes.get("delivery_on_time", 3)
        else:
            # Sin deadline: asumir entrega a tiempo
            rep_change = self.rep_changes.get("delivery_on_time", 3)

        self.reputation = clamp(self.reputation + rep_change, 0, 100)
        self.deliveries_completed += 1
        self.consecutive_on_time += 1

        # Bonus por racha
        streak_threshold = self.rep_changes.get("streak_threshold", 3)
        if self.consecutive_on_time >= streak_threshold:
            streak_bonus = self.rep_changes.get("streak_bonus", 2)
            self.reputation = clamp(self.reputation + streak_bonus, 0, 100)
            self.consecutive_on_time = 0

    def cancel_order(self):
        penalty = self.rep_changes.get("cancel_order", -4)
        self.reputation = clamp(self.reputation + penalty, 0, 100)
        self.orders_cancelled += 1
        self.consecutive_on_time = 0

    def set_inventory_weight(self, weight: float):
        self.total_weight = weight

    def get_position(self) -> Tuple[float, float]:
        return self.x, self.y

    def get_forward_vector(self) -> Tuple[float, float]:
        return math.cos(self.angle), math.sin(self.angle)

    def calculate_effective_speed(self, city_map=None) -> float:
        # Pública: para HUD u otros, opcionalmente con `surface_weight`
        speed = self._calculate_effective_speed()
        if city_map is not None:
            speed *= self._get_surface_weight(city_map)
        return speed

    def _calculate_effective_speed(self) -> float:
        speed = self.base_speed

        # Mclima
        speed *= self.weather_speed_multiplier

        # Mpeso
        if self.total_weight > 3:
            weight_penalty = max(0.8, 1 - 0.03 * self.total_weight)
            speed *= weight_penalty

        # Mrep
        if self.reputation >= self.rep_thresholds.get("excellent", 90):
            speed *= self.payment_mods.get("excellent_bonus", 1.03)

        # Mresistencia
        if self.state == PlayerState.TIRED:
            speed *= 0.8
        elif self.state == PlayerState.EXHAUSTED:
            speed = 0.0

        return speed

    def _get_surface_weight(self, city_map) -> float:
        # Lee el `surface_weight` desde la leyenda si existe; fallback: C=1.0, P=0.95
        try:
            tile = city_map.get_tile_at(int(self.x), int(self.y))
        except Exception:
            tile = None

        w = 1.0
        if tile:
            legend = getattr(city_map, "legend", None)
            if isinstance(legend, dict):
                entry = legend.get(tile, {})
                w = float(entry.get("surface_weight", 1.0))
            else:
                if tile == "P":
                    w = 0.95
                elif tile == "C":
                    w = 1.0
        return w

    def _consume_stamina_for_movement(self, delta_time: float):
        base_drain = 5 * delta_time
        if self.total_weight > 3:
            weight_drain = 0.2 * (self.total_weight - 3) * delta_time
            base_drain += weight_drain
        self.stamina = clamp(self.stamina - base_drain, 0, 100)

    def _recover_stamina(self, delta_time: float):
        if self.state == PlayerState.EXHAUSTED:
            recovery_rate = 3.0
        else:
            recovery_rate = 5.0
        self.stamina = clamp(self.stamina + recovery_rate * delta_time, 0, 100)

    def _update_state(self):
        # Mantener EXHAUSTED hasta 30% de stamina
        if self.stamina <= 0:
            self.state = PlayerState.EXHAUSTED
        elif self.state == PlayerState.EXHAUSTED and self.stamina < 30.0:
            self.state = PlayerState.EXHAUSTED
        elif self.stamina <= 30:
            self.state = PlayerState.TIRED
        else:
            self.state = PlayerState.NORMAL

    def can_move(self) -> bool:
        return self.state != PlayerState.EXHAUSTED

    def get_stamina_percentage(self) -> float:
        return self.stamina / 100.0

    def get_reputation_percentage(self) -> float:
        return self.reputation / 100.0

    def is_reputation_critical(self) -> bool:
        return self.reputation < self.rep_thresholds.get("critical", 20)

    def get_stats_summary(self) -> Dict[str, Any]:
        return {
            "position": (self.x, self.y),
            "angle": self.angle,
            "stamina": self.stamina,
            "reputation": self.reputation,
            "earnings": self.earnings,
            "state": self.state,
            "deliveries_completed": self.deliveries_completed,
            "orders_cancelled": self.orders_cancelled,
            "total_weight": self.total_weight
        }