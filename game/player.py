import math
from typing import Dict, Any, Tuple, Optional
from .utils import clamp, normalize_angle

class PlayerState:
    NORMAL = "normal"      # >30 stamina
    TIRED = "tired"        # 10-30 stamina
    EXHAUSTED = "exhausted"  # 0-10 stamina

class Player:
    def __init__(self, start_x: float, start_y: float, config: Dict[str, Any]):
        # Posición y orientación
        self.x = start_x
        self.y = start_y
        self.angle = 0.0  # En radianes

        # Configuración
        self.base_speed = config.get("base_speed", 3.0)
        self.turn_speed = config.get("turn_speed", 1.5)
        self.move_speed = config.get("move_speed", 3.0)

        # Estadísticas del jugador
        self.stamina = 100.0  # 0-100
        self.reputation = 70.0  # 0-100, empieza en 70
        self.earnings = 0.0
        self.total_weight = 0.0

        # Estado del jugador
        self.state = PlayerState.NORMAL
        self.is_moving = False
        self.recovery_timer = 0.0

        # Efectos temporales
        self.weather_speed_multiplier = 1.0
        self.weather_stamina_drain = 0.0

        # Estadísticas de sesión
        self.deliveries_completed = 0
        self.orders_cancelled = 0
        self.consecutive_on_time = 0

    def update(self, delta_time: float):
        # Actualizar estado basado en resistencia
        self._update_state()

        # Recuperación de resistencia si no se está moviendo
        if not self.is_moving:
            self._recover_stamina(delta_time)

        # Aplicar drenaje de resistencia por clima
        if self.weather_stamina_drain > 0:
            self.stamina = clamp(self.stamina - self.weather_stamina_drain * delta_time, 0, 100)

        # Resetear flag de movimiento para el próximo frame
        self.is_moving = False

    def move(self, dx: float, dy: float, delta_time: float, city_map):
        # No permitir movimiento si está exhausto
        if self.state == PlayerState.EXHAUSTED:
            return

        # Calcular velocidad efectiva
        effective_speed = self._calculate_effective_speed()

        # Calcular nueva posición
        move_distance = effective_speed * delta_time
        new_x = self.x + dx * move_distance
        new_y = self.y + dy * move_distance

        # Verificar colisiones con paredes
        if not city_map.is_wall(new_x, self.y):
            self.x = new_x
        if not city_map.is_wall(self.x, new_y):
            self.y = new_y

        # Consumir resistencia por movimiento
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
        # Aplicar bonus por reputación alta
        if self.reputation >= 90:
            amount *= 1.05

        self.earnings += amount

    def update_reputation_for_delivery(self, order):
        # Calcular si llegó a tiempo, temprano o tarde
        # Por ahora implementación simplificada

        # TODO: Implementar cálculo real de tiempo basado en deadline

        # Entrega a tiempo (simplificado)
        self.reputation = clamp(self.reputation + 3, 0, 100)
        self.deliveries_completed += 1
        self.consecutive_on_time += 1

        # Bonus por racha de entregas puntuales
        if self.consecutive_on_time >= 3:
            self.reputation = clamp(self.reputation + 2, 0, 100)
            self.consecutive_on_time = 0  # Reset racha

    def cancel_order(self):
        self.reputation = clamp(self.reputation - 4, 0, 100)
        self.orders_cancelled += 1
        self.consecutive_on_time = 0

    def set_inventory_weight(self, weight: float):
        self.total_weight = weight

    def get_position(self) -> Tuple[float, float]:
        return self.x, self.y

    def get_forward_vector(self) -> Tuple[float, float]:
        return math.cos(self.angle), math.sin(self.angle)

    def _calculate_effective_speed(self) -> float:
        speed = self.base_speed

        # Modificador por clima
        speed *= self.weather_speed_multiplier

        # Modificador por peso
        if self.total_weight > 3:
            weight_penalty = max(0.8, 1 - 0.03 * self.total_weight)
            speed *= weight_penalty

        # Modificador por reputación alta
        if self.reputation >= 90:
            speed *= 1.03

        # Modificador por estado de resistencia
        if self.state == PlayerState.TIRED:
            speed *= 0.8
        elif self.state == PlayerState.EXHAUSTED:
            speed = 0

        return speed

    def _consume_stamina_for_movement(self, delta_time: float):
        base_drain = 0.5 * delta_time  # -0.5 por segundo base

        # Drenaje extra por peso
        if self.total_weight > 3:
            weight_drain = 0.2 * (self.total_weight - 3) * delta_time
            base_drain += weight_drain

        # Drenaje por clima ya se aplica en update()

        self.stamina = clamp(self.stamina - base_drain, 0, 100)

    def _recover_stamina(self, delta_time: float):
        if self.state == PlayerState.EXHAUSTED:
            # Recuperación lenta cuando está exhausto
            recovery_rate = 3.0  # +3 por segundo
        else:
            # Recuperación normal
            recovery_rate = 5.0  # +5 por segundo

        self.stamina = clamp(self.stamina + recovery_rate * delta_time, 0, 100)

    def _update_state(self):
        if self.stamina <= 0:
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
        return self.reputation < 20

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


