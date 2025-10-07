import math
import copy
from typing import Dict, Any, Tuple, Optional, List
from collections import deque
from .utils import clamp, normalize_angle
from .inventory import Inventory
from game.orders import Order
from datetime import datetime


class PlayerState:
    NORMAL = "normal"
    TIRED = "tired"
    EXHAUSTED = "exhausted"


class Player:
    def __init__(self, start_x: float, start_y: float, config: Dict[str, Any]):
        self.x = start_x
        self.y = start_y
        self.angle = 0.0

        self.base_speed = config.get("base_speed", 3.0)
        self.turn_speed = config.get("turn_speed", 1.5)
        self.move_speed = config.get("move_speed", 3.0)

        game_config = config.get("game", {}) if "game" in config else {}
        self.stamina = float(game_config.get("initial_stamina", 100.0))
        self.reputation = float(game_config.get("initial_reputation", 70.0))
        self.earnings = 0.0
        self.total_weight = 0.0

        # Debug mode
        self.debug = bool(config.get("debug", False))

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

        max_inventory_weight = config.get("max_inventory_weight", 10.0)
        self.inventory = Inventory(max_inventory_weight)

        self.state = PlayerState.NORMAL
        self.is_moving = False
        self.recovery_timer = 0.0

        self.weather_speed_multiplier = 1.0
        self.weather_stamina_drain = 0.0

        self.deliveries_completed = 0
        self.orders_cancelled = 0
        self.consecutive_on_time = 0

        # ========== SISTEMA DE UNDO ==========
        undo_config = config.get("undo", {})
        self.max_undo_steps = int(undo_config.get("max_steps", 50))
        self.undo_save_interval = float(undo_config.get("save_interval", 0.5))

        self.undo_stack: deque = deque(maxlen=self.max_undo_steps)
        self.last_undo_save_time = 0.0
        self.undo_cooldown = 0.3
        self.last_undo_time = 0.0

        self._save_undo_state()

    def _save_undo_state(self):
        state = {
            'x': float(self.x),
            'y': float(self.y),
            'angle': float(self.angle),
            'stamina': float(self.stamina),
            'reputation': float(self.reputation),
            'earnings': float(self.earnings),
            'total_weight': float(self.total_weight),
            'deliveries_completed': int(self.deliveries_completed),
            'orders_cancelled': int(self.orders_cancelled),
            'consecutive_on_time': int(self.consecutive_on_time),
            'state': str(self.state),
            'inventory_snapshot': [
                {
                    'id': order.id,
                    'status': order.status,
                    'weight': order.weight,
                    'pickup_pos': order.pickup_pos,
                    'dropoff_pos': order.dropoff_pos,
                    'payment': order.payment,
                    'priority': order.priority,
                    'deadline': order.deadline,
                    'time_limit': order.time_limit,
                    'picked_up_at': order.picked_up_at.isoformat() if order.picked_up_at else None
                }
                for order in self.inventory.orders
            ],
            'inventory_current_index': int(self.inventory.current_index),
            'inventory_sort_mode': str(self.inventory.sort_mode),
            'timestamp': datetime.now().isoformat()
        }

        self.undo_stack.append(state)

    def should_save_undo_state(self, current_time: float) -> bool:
        return (current_time - self.last_undo_save_time) >= self.undo_save_interval

    def save_undo_state_if_needed(self, current_time: float):
        if self.should_save_undo_state(current_time):
            self._save_undo_state()
            self.last_undo_save_time = current_time

    def can_undo(self, current_time: float) -> bool:
        if len(self.undo_stack) < 2:
            return False

        if (current_time - self.last_undo_time) < self.undo_cooldown:
            return False

        return True

    def undo(self, current_time: float) -> bool:
        if not self.can_undo(current_time):
            return False

        try:
            self.undo_stack.pop()

            if not self.undo_stack:
                return False

            previous_state = self.undo_stack[-1]

            self._restore_from_state(previous_state)

            self.last_undo_time = current_time

            return True

        except Exception as e:
            print(f"error al deshacer: {e}")
            return False

    def _restore_from_state(self, state: Dict[str, Any]):
        self.x = float(state['x'])
        self.y = float(state['y'])
        self.angle = float(state['angle'])
        self.stamina = float(state['stamina'])
        self.reputation = float(state['reputation'])
        self.earnings = float(state['earnings'])
        self.total_weight = float(state['total_weight'])
        self.deliveries_completed = int(state['deliveries_completed'])
        self.orders_cancelled = int(state['orders_cancelled'])
        self.consecutive_on_time = int(state['consecutive_on_time'])
        self.state = state['state']

        self._restore_inventory(state)

    def _restore_inventory(self, state: Dict[str, Any]):
        self.inventory.orders.clear()

        for order_data in state['inventory_snapshot']:
            order = Order(
                order_id=order_data['id'],
                pickup_pos=tuple(order_data['pickup_pos']),
                dropoff_pos=tuple(order_data['dropoff_pos']),
                payment=float(order_data['payment']),
                time_limit=float(order_data.get('time_limit', 600.0)),
                weight=float(order_data.get('weight', 1.0)),
                priority=int(order_data.get('priority', 0)),
                deadline=order_data.get('deadline', ''),
                release_time=0
            )
            order.status = order_data['status']

            if order_data.get('picked_up_at'):
                order.picked_up_at = datetime.fromisoformat(order_data['picked_up_at'])

            self.inventory.orders.append(order)

        self.inventory.current_index = int(state.get('inventory_current_index', 0))
        self.inventory.sort_mode = state.get('inventory_sort_mode', 'priority')

        if self.inventory.current_index >= len(self.inventory.orders):
            self.inventory.current_index = max(0, len(self.inventory.orders) - 1)

    def get_undo_stats(self) -> Dict[str, Any]:
        return {
            'available_undos': len(self.undo_stack) - 1,
            'max_undos': self.max_undo_steps,
            'can_undo': self.can_undo(datetime.now().timestamp()),
            'last_undo_time': self.last_undo_time,
            'oldest_state': self.undo_stack[0]['timestamp'] if self.undo_stack else None,
            'newest_state': self.undo_stack[-1]['timestamp'] if self.undo_stack else None
        }

    def add_order_to_inventory(self, order: Order) -> bool:
        success = self.inventory.add_order(order)
        if success:
            self.set_inventory_weight(self.inventory.current_weight)
        return success

    def remove_order_from_inventory(self, order_id: str) -> Optional[Order]:
        removed_order = self.inventory.remove_order(order_id)
        if removed_order:
            self.set_inventory_weight(self.inventory.current_weight)
        return removed_order

    def get_current_order(self) -> Optional[Order]:
        return self.inventory.get_current_order()

    def update(self, delta_time: float):
        self._update_state()

        if not self.is_moving:
            self._recover_stamina(delta_time)

        if self.weather_stamina_drain > 0:
            self.stamina = clamp(self.stamina - self.weather_stamina_drain * delta_time, 0, 100)

        self.is_moving = False

    def move(self, dx: float, dy: float, delta_time: float, city_map):
        self._update_state()
        if self.state == PlayerState.EXHAUSTED:
            return

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
        if not hasattr(order, 'picked_up_at') or order.picked_up_at is None:
            rep_change = self.rep_changes.get("delivery_on_time", 3)
            if self.debug:
                print(f"Pedido {order.id} sin timestamp de recogida, usando rep neutral: +{rep_change}")
        else:
            now = datetime.now(order.picked_up_at.tzinfo) if order.picked_up_at.tzinfo else datetime.now()
            time_elapsed = (now - order.picked_up_at).total_seconds()

            time_limit = float(getattr(order, 'time_limit', 600.0))

            time_remaining = time_limit - time_elapsed
            time_margin = time_remaining / time_limit if time_limit > 0 else 0

            if time_margin >= 0.20:
                rep_change = self.rep_changes.get("delivery_early", 5)
                status = "TEMPRANO"
            elif time_remaining >= 0:
                rep_change = self.rep_changes.get("delivery_on_time", 3)
                status = "A TIEMPO"
            else:
                late_seconds = abs(time_remaining)
                if late_seconds <= self.delivery_thresholds.get("late_minor", 30):
                    rep_change = self.rep_changes.get("delivery_late_minor", -2)
                    status = "TARDE (menor)"
                elif late_seconds <= self.delivery_thresholds.get("late_moderate", 120):
                    rep_change = self.rep_changes.get("delivery_late_moderate", -5)
                    status = "TARDE (moderado)"
                else:
                    rep_change = self.rep_changes.get("delivery_late_severe", -10)
                    status = "TARDE (severo)"

                if self.reputation >= self.rep_thresholds.get("bonus_first_late", 85):
                    original_change = rep_change
                    rep_change *= self.payment_mods.get("first_late_penalty", 0.5)
                    if self.debug:
                        print(f"  Penalizacion reducida por alta reputacion: {original_change} -> {rep_change:.1f}")

            if self.debug:
                print(f"Entrega {order.id}:")
                print(f"  Tiempo transcurrido: {time_elapsed:.1f}s / {time_limit:.1f}s")
                print(f"  Margen: {time_margin * 100:.1f}% ({time_remaining:.1f}s)")
                print(f"  Estado: {status}")
                print(f"  Cambio de reputacion: {rep_change:+.1f}")

        old_rep = self.reputation
        self.reputation = clamp(self.reputation + rep_change, 0, 100)
        if self.debug:
            print(f"  Reputacion: {old_rep:.1f} -> {self.reputation:.1f}")

        self.deliveries_completed += 1

        if rep_change > 0:
            self.consecutive_on_time += 1

            streak_threshold = self.rep_changes.get("streak_threshold", 3)
            if self.consecutive_on_time >= streak_threshold:
                streak_bonus = self.rep_changes.get("streak_bonus", 2)
                self.reputation = clamp(self.reputation + streak_bonus, 0, 100)
                if self.debug:
                    print(f"  Bonus por racha! ({self.consecutive_on_time} entregas) +{streak_bonus}")
                self.consecutive_on_time = 0
        else:
            if self.debug and self.consecutive_on_time > 0:
                print(f"  Racha rota ({self.consecutive_on_time} entregas)")
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
        speed = self._calculate_effective_speed()
        if city_map is not None:
            speed *= self._get_surface_weight(city_map)
        return speed

    def _calculate_effective_speed(self) -> float:
        speed = self.base_speed
        speed *= self.weather_speed_multiplier

        if self.total_weight > 3:
            weight_penalty = max(0.8, 1 - 0.03 * self.total_weight)
            speed *= weight_penalty

        if self.reputation >= self.rep_thresholds.get("excellent", 90):
            speed *= self.payment_mods.get("excellent_bonus", 1.03)

        if self.state == PlayerState.TIRED:
            speed *= 0.8
        elif self.state == PlayerState.EXHAUSTED:
            speed = 0.0

        return speed

    def _get_surface_weight(self, city_map) -> float:
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