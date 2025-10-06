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
        # usar deque para eficiencia en pop/append desde ambos lados
        undo_config = config.get("undo", {})
        self.max_undo_steps = int(undo_config.get("max_steps", 50))
        self.undo_save_interval = float(undo_config.get("save_interval", 0.5))  # cada 0.5s

        self.undo_stack: deque = deque(maxlen=self.max_undo_steps)
        self.last_undo_save_time = 0.0
        self.undo_cooldown = 0.3  # cooldown entre undos para evitar spam
        self.last_undo_time = 0.0

        # guardar estado inicial
        self._save_undo_state()

    def _save_undo_state(self):
        """
        guarda el estado actual del jugador en el stack de undo.
        usa copia profunda para evitar referencias compartidas.
        """
        state = {
            # posición y orientación
            'x': float(self.x),
            'y': float(self.y),
            'angle': float(self.angle),

            # stats
            'stamina': float(self.stamina),
            'reputation': float(self.reputation),
            'earnings': float(self.earnings),
            'total_weight': float(self.total_weight),

            # contadores
            'deliveries_completed': int(self.deliveries_completed),
            'orders_cancelled': int(self.orders_cancelled),
            'consecutive_on_time': int(self.consecutive_on_time),

            # estado
            'state': str(self.state),

            # inventario (solo ids y status para no duplicar objetos pesados)
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
                    'time_limit': order.time_limit
                }
                for order in self.inventory.orders
            ],
            'inventory_current_index': int(self.inventory.current_index),
            'inventory_sort_mode': str(self.inventory.sort_mode),

            # timestamp para debugging
            'timestamp': datetime.now().isoformat()
        }

        self.undo_stack.append(state)

    def should_save_undo_state(self, current_time: float) -> bool:
        """
        determina si debe guardarse un nuevo estado de undo.
        criterios: tiempo transcurrido o cambio significativo.
        """
        return (current_time - self.last_undo_save_time) >= self.undo_save_interval

    def save_undo_state_if_needed(self, current_time: float):
        """
        guarda estado si ha pasado suficiente tiempo desde el último guardado.
        llamar esto desde el update loop del juego.
        """
        if self.should_save_undo_state(current_time):
            self._save_undo_state()
            self.last_undo_save_time = current_time

    def can_undo(self, current_time: float) -> bool:
        """
        verifica si el jugador puede deshacer un paso.
        """
        # debe haber al menos 2 estados (actual + anterior)
        if len(self.undo_stack) < 2:
            return False

        # verificar cooldown para evitar spam
        if (current_time - self.last_undo_time) < self.undo_cooldown:
            return False

        return True

    def undo(self, current_time: float) -> bool:
        """
        deshace el último movimiento y restaura el estado anterior.
        retorna True si tuvo éxito, False si no hay estados que deshacer.
        """
        if not self.can_undo(current_time):
            return False

        try:
            # remover estado actual (el más reciente)
            self.undo_stack.pop()

            # obtener estado anterior (sin removerlo todavía)
            if not self.undo_stack:
                return False

            previous_state = self.undo_stack[-1]

            # restaurar estado del jugador
            self._restore_from_state(previous_state)

            # actualizar timestamp de último undo
            self.last_undo_time = current_time

            return True

        except Exception as e:
            print(f"error al deshacer: {e}")
            return False

    def _restore_from_state(self, state: Dict[str, Any]):
        """
        restaura el jugador a un estado guardado previamente.
        """
        # posición y orientación
        self.x = float(state['x'])
        self.y = float(state['y'])
        self.angle = float(state['angle'])

        # stats
        self.stamina = float(state['stamina'])
        self.reputation = float(state['reputation'])
        self.earnings = float(state['earnings'])
        self.total_weight = float(state['total_weight'])

        # contadores
        self.deliveries_completed = int(state['deliveries_completed'])
        self.orders_cancelled = int(state['orders_cancelled'])
        self.consecutive_on_time = int(state['consecutive_on_time'])

        # estado
        self.state = state['state']

        # restaurar inventario
        self._restore_inventory(state)

    def _restore_inventory(self, state: Dict[str, Any]):
        """
        restaura el inventario desde un snapshot guardado.
        """
        # limpiar inventario actual
        self.inventory.orders.clear()

        # recrear órdenes desde snapshot
        for order_data in state['inventory_snapshot']:
            # crear objeto Order desde datos guardados
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
            self.inventory.orders.append(order)

        # restaurar estado del inventario
        self.inventory.current_index = int(state.get('inventory_current_index', 0))
        self.inventory.sort_mode = state.get('inventory_sort_mode', 'priority')

        # validar índice actual
        if self.inventory.current_index >= len(self.inventory.orders):
            self.inventory.current_index = max(0, len(self.inventory.orders) - 1)

    def get_undo_stats(self) -> Dict[str, Any]:
        """
        obtiene estadísticas del sistema de undo para debugging/ui.
        """
        return {
            'available_undos': len(self.undo_stack) - 1,  # -1 porque uno es el estado actual
            'max_undos': self.max_undo_steps,
            'can_undo': self.can_undo(datetime.now().timestamp()),
            'last_undo_time': self.last_undo_time,
            'oldest_state': self.undo_stack[0]['timestamp'] if self.undo_stack else None,
            'newest_state': self.undo_stack[-1]['timestamp'] if self.undo_stack else None
        }

    # ========== FIN SISTEMA DE UNDO ==========

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
        if hasattr(order, 'deadline') and order.deadline:
            try:
                if isinstance(order.deadline, str):
                    deadline_dt = datetime.fromisoformat(order.deadline.replace('Z', '+00:00'))
                else:
                    deadline_dt = order.deadline

                now = datetime.now(deadline_dt.tzinfo) if deadline_dt.tzinfo else datetime.now()
                time_diff = (deadline_dt - now).total_seconds()
                time_margin = time_diff / order.time_limit if hasattr(order,
                                                                      'time_limit') and order.time_limit > 0 else 0

                if time_margin >= 0.20:
                    rep_change = self.rep_changes.get("delivery_early", 5)
                elif time_diff >= 0:
                    rep_change = self.rep_changes.get("delivery_on_time", 3)
                else:
                    late_seconds = abs(time_diff)
                    if late_seconds <= self.delivery_thresholds.get("late_minor", 30):
                        rep_change = self.rep_changes.get("delivery_late_minor", -2)
                    elif late_seconds <= self.delivery_thresholds.get("late_moderate", 120):
                        rep_change = self.rep_changes.get("delivery_late_moderate", -5)
                    else:
                        rep_change = self.rep_changes.get("delivery_late_severe", -10)

                    if self.reputation >= self.rep_thresholds.get("bonus_first_late", 85):
                        rep_change *= self.payment_mods.get("first_late_penalty", 0.5)
            except Exception:
                rep_change = self.rep_changes.get("delivery_on_time", 3)
        else:
            rep_change = self.rep_changes.get("delivery_on_time", 3)

        self.reputation = clamp(self.reputation + rep_change, 0, 100)
        self.deliveries_completed += 1
        self.consecutive_on_time += 1

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