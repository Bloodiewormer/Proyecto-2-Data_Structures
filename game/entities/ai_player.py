from __future__ import annotations
import math
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

        self._decision_interval = 0.3  # Más rápido para respuestas más naturales
        self._decision_cooldown = 0.0

        self.strategy: BaseStrategy = strategy or self._build_default_strategy(self.difficulty)

        # Sistema de sprites direccionales con 8 direcciones
        self.sprite_textures = {}
        self.current_direction = "down"

        # Interpolación suave de movimiento y rotación
        self.target_angle = 0.0
        self.angle_smoothing = 5.0  # Velocidad de rotación (rad/s)

        # Velocidad de movimiento suavizada
        self.current_velocity = [0.0, 0.0]
        self.velocity_smoothing = 8.0  # Aceleración/desaceleración

        # Anti-atascamiento
        self.stuck_counter = 0
        self.last_valid_position = (start_x, start_y)
        self.position_history = []  # Últimas 10 posiciones
        self.max_position_history = 10

        # Distancia mínima a paredes
        self.wall_avoidance_distance = 0.3
        self.wall_slowdown_distance = 0.6

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

    def _smooth_angle_to_target(self, delta_time: float):
        """Interpola suavemente el ángulo hacia el objetivo"""
        diff = self.target_angle - self.angle

        # Normalizar diferencia a -π a π (camino más corto)
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi

        # Interpolar
        max_rotation = self.angle_smoothing * delta_time

        if abs(diff) < 0.01:
            self.angle = self.target_angle
        elif abs(diff) <= max_rotation:
            self.angle = self.target_angle
        else:
            self.angle += math.copysign(max_rotation, diff)

        # Normalizar ángulo
        while self.angle > math.pi:
            self.angle -= 2 * math.pi
        while self.angle < -math.pi:
            self.angle += 2 * math.pi

    def _update_sprite_direction(self):
        """Actualiza la dirección del sprite basado en el ángulo actual"""
        angle_deg = math.degrees(self.angle)

        # Normalizar a 0-360
        while angle_deg < 0:
            angle_deg += 360
        while angle_deg >= 360:
            angle_deg -= 360

        # 8 direcciones (45° cada sector)
        if 337.5 <= angle_deg or angle_deg < 22.5:
            self.current_direction = "right"
        elif 22.5 <= angle_deg < 67.5:
            self.current_direction = "up_right"
        elif 67.5 <= angle_deg < 112.5:
            self.current_direction = "up"
        elif 112.5 <= angle_deg < 157.5:
            self.current_direction = "up_left"
        elif 157.5 <= angle_deg < 202.5:
            self.current_direction = "left"
        elif 202.5 <= angle_deg < 247.5:
            self.current_direction = "down_left"
        elif 247.5 <= angle_deg < 292.5:
            self.current_direction = "down"
        else:
            self.current_direction = "down_right"

    def _check_wall_ahead(self, city, dx: float, dy: float, distance: float = 0.5) -> bool:
        """Verifica si hay una pared en la dirección de movimiento"""
        test_x = self.x + dx * distance
        test_y = self.y + dy * distance
        return city.is_wall(test_x, test_y)

    def _calculate_wall_avoidance_vector(self, city, target_dx: float, target_dy: float) -> Tuple[float, float]:
        """
        Calcula un vector de movimiento que evita paredes suavemente.
        Usa campos de fuerza repulsivos alrededor de las paredes.
        """
        # Normalizar dirección objetivo
        mag = math.sqrt(target_dx ** 2 + target_dy ** 2)
        if mag < 0.001:
            return (0.0, 0.0)

        norm_dx = target_dx / mag
        norm_dy = target_dy / mag

        # Detectar paredes cercanas en múltiples direcciones
        check_angles = [-45, -30, -15, 0, 15, 30, 45]  # Ángulos relativos
        base_angle = math.atan2(norm_dy, norm_dx)

        # Vector de repulsión acumulado
        repulsion_x = 0.0
        repulsion_y = 0.0

        for angle_offset in check_angles:
            check_angle = base_angle + math.radians(angle_offset)
            check_dx = math.cos(check_angle)
            check_dy = math.sin(check_angle)

            # Verificar múltiples distancias
            for dist in [0.3, 0.5, 0.7]:
                test_x = self.x + check_dx * dist
                test_y = self.y + check_dy * dist

                if city.is_wall(test_x, test_y):
                    # Calcular fuerza de repulsión (más fuerte si está más cerca)
                    strength = (1.0 - dist / 0.7) * 2.0
                    # Repeler en dirección opuesta
                    repulsion_x -= check_dx * strength
                    repulsion_y -= check_dy * strength
                    break

        # Combinar dirección objetivo con repulsión
        final_dx = norm_dx + repulsion_x
        final_dy = norm_dy + repulsion_y

        # Normalizar resultado
        final_mag = math.sqrt(final_dx ** 2 + final_dy ** 2)
        if final_mag > 0.001:
            final_dx /= final_mag
            final_dy /= final_mag

        return (final_dx, final_dy)

    def _calculate_speed_multiplier(self, city) -> float:
        """
        Calcula multiplicador de velocidad basado en proximidad a paredes.
        Velocidad completa lejos de paredes, reducida cerca.
        """
        # Verificar 8 direcciones principales
        directions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (0.707, 0.707), (-0.707, 0.707), (0.707, -0.707), (-0.707, -0.707)
        ]

        min_distance = float('inf')

        for dx, dy in directions:
            # Buscar la pared más cercana en esta dirección
            for dist in [0.2, 0.4, 0.6, 0.8]:
                test_x = self.x + dx * dist
                test_y = self.y + dy * dist

                if city.is_wall(test_x, test_y):
                    min_distance = min(min_distance, dist)
                    break

        # Sin paredes cerca = velocidad completa
        if min_distance >= self.wall_slowdown_distance:
            return 1.0

        # Cerca de paredes = reducir velocidad gradualmente
        if min_distance <= self.wall_avoidance_distance:
            return 0.3  # Muy lento cerca de paredes

        # Interpolación lineal entre wall_avoidance y wall_slowdown
        t = (min_distance - self.wall_avoidance_distance) / \
            (self.wall_slowdown_distance - self.wall_avoidance_distance)
        return 0.3 + (0.7 * t)

    def _detect_stuck(self) -> bool:
        """Detecta si el AI está atascado comparando historial de posiciones"""
        if len(self.position_history) < self.max_position_history:
            return False

        # Calcular distancia total recorrida en las últimas posiciones
        total_distance = 0.0
        for i in range(1, len(self.position_history)):
            prev = self.position_history[i - 1]
            curr = self.position_history[i]
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            total_distance += math.sqrt(dx ** 2 + dy ** 2)

        # Si se movió muy poco en las últimas N posiciones, está atascado
        return total_distance < 0.5

    def _unstuck_maneuver(self, city) -> Tuple[float, float]:
        """Realiza maniobra para desatascarse"""
        # Intentar moverse hacia atrás primero
        back_angle = self.angle + math.pi
        for dist in [0.5, 1.0, 1.5]:
            test_x = self.x + math.cos(back_angle) * dist
            test_y = self.y + math.sin(back_angle) * dist

            if not city.is_wall(test_x, test_y):
                return (math.cos(back_angle), math.sin(back_angle))

        # Si no funciona, probar ángulos aleatorios
        import random
        for _ in range(8):
            random_angle = random.uniform(0, 2 * math.pi)
            test_x = self.x + math.cos(random_angle) * 0.8
            test_y = self.y + math.sin(random_angle) * 0.8

            if not city.is_wall(test_x, test_y):
                return (math.cos(random_angle), math.sin(random_angle))

        # Último recurso: teleportarse a última posición válida
        if self.last_valid_position:
            self.x, self.y = self.last_valid_position
            self.position_history.clear()

        return (0.0, 0.0)

    def _apply_step(self, dx: int, dy: int, game):
        """Aplica movimiento con suavizado y evitación de paredes"""
        city = getattr(game, "city", None)
        if not city:
            return

        delta_time = getattr(game, '_last_delta_time', 1 / 60.0)

        # Agregar posición actual al historial
        self.position_history.append((self.x, self.y))
        if len(self.position_history) > self.max_position_history:
            self.position_history.pop(0)

        # Detectar atascamiento
        if self._detect_stuck():
            self.stuck_counter += 1
            if self.stuck_counter > 3:
                dx, dy = self._unstuck_maneuver(city)
                self.stuck_counter = 0
        else:
            self.stuck_counter = 0
            self.last_valid_position = (self.x, self.y)

        if dx == 0 and dy == 0:
            # Detenerse suavemente
            self.current_velocity[0] *= (1.0 - delta_time * self.velocity_smoothing)
            self.current_velocity[1] *= (1.0 - delta_time * self.velocity_smoothing)

            if abs(self.current_velocity[0]) < 0.01:
                self.current_velocity[0] = 0
            if abs(self.current_velocity[1]) < 0.01:
                self.current_velocity[1] = 0

            self._current_step = (0, 0)
            return

        # Normalizar dirección objetivo
        magnitude = math.sqrt(dx ** 2 + dy ** 2)
        if magnitude > 0:
            target_dx = dx / magnitude
            target_dy = dy / magnitude
        else:
            target_dx, target_dy = 0.0, 0.0

        # Aplicar evitación de paredes
        adjusted_dx, adjusted_dy = self._calculate_wall_avoidance_vector(
            city, target_dx, target_dy
        )

        # Calcular ángulo objetivo
        self.target_angle = math.atan2(adjusted_dy, adjusted_dx)

        # Suavizar rotación
        self._smooth_angle_to_target(delta_time)

        # Actualizar dirección del sprite
        self._update_sprite_direction()

        # Calcular multiplicador de velocidad por proximidad a paredes
        speed_mult = self._calculate_speed_multiplier(city)

        # Suavizar velocidad (aceleración/desaceleración)
        target_vel_x = adjusted_dx * speed_mult
        target_vel_y = adjusted_dy * speed_mult

        smoothing_factor = min(1.0, delta_time * self.velocity_smoothing)
        self.current_velocity[0] += (target_vel_x - self.current_velocity[0]) * smoothing_factor
        self.current_velocity[1] += (target_vel_y - self.current_velocity[1]) * smoothing_factor

        # Aplicar movimiento usando la velocidad suavizada
        self.move(self.current_velocity[0], self.current_velocity[1], delta_time, city)

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
        """Override con timestamp para renderer"""
        super().update(delta_time)

        import time
        self._last_update_time = time.time()

        if self.world and hasattr(self.world, 'weather_system') and self.world.weather_system:
            weather_info = self.world.weather_system.get_weather_info()
            self.weather_speed_multiplier = weather_info.get('speed_multiplier', 1.0)
            self.weather_stamina_drain = weather_info.get('stamina_drain', 0.0)

    def update_with_strategy(self, game):
        if not self.strategy:
            return

        if not self.can_move():
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
        """Actualización optimizada con cooldown"""
        game._last_delta_time = delta_time

        self.update(delta_time)
        self._decision_cooldown -= delta_time
        if self._decision_cooldown <= 0:
            self._decision_cooldown = self._decision_interval
            self.update_with_strategy(game)

    def update_tick(self, delta_time: float, game):
        """Actualización cada frame"""
        game._last_delta_time = delta_time

        self.update(delta_time)
        self.update_with_strategy(game)

    def get_sprite_direction(self) -> str:
        """Dirección actual (8 direcciones)"""
        return self.current_direction