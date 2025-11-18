from __future__ import annotations
import math
import time
from typing import Optional, Tuple

from game.entities.player import Player
from game.core.orders import Order

from game.IA.strategies.strategies import EasyStrategy, MediumStrategy, HardStrategy, BaseStrategy


class AIPlayer(Player):
    """
    Jugador controlado por IA con tres niveles de dificultad.
    VERSIÓN CORREGIDA: Completa rutas sin atascarse.
    """

    def __init__(self,
                 start_x: float = 0.0,
                 start_y: float = 0.0,
                 config: Optional[dict] = None,
                 difficulty: str = "easy",
                 world=None,
                 strategy: Optional[BaseStrategy] = None,
                 **kwargs):

        # Manejar parámetros legacy
        if 'x' in kwargs:
            start_x = kwargs.pop('x')
        if 'y' in kwargs:
            start_y = kwargs.pop('y')

        # Configuración
        if config is None and world and hasattr(world, "app_config"):
            try:
                config = world.app_config.get("player", {})
            except Exception:
                config = {}

        config = config or {}

        # Inicializar clase base (Player)
        super().__init__(start_x, start_y, config)

        # Identificación
        self.is_ai = True
        self.world = world
        self.difficulty = str(difficulty or "easy").lower().strip()

        # Target y movimiento
        self.current_target: Optional[Tuple[int, int]] = None
        self._current_step: Tuple[int, int] = (0, 0)

        # Sistema de decisiones
        self._decision_interval = 0.1  # Decidir cada 0.1 segundos (más frecuente)
        self._decision_cooldown = 0.0

        # Estrategia
        self.strategy: BaseStrategy = strategy or self._build_default_strategy(self.difficulty)

        # Sistema de sprites direccionales (8 direcciones)
        self.sprite_textures = {}
        self.current_direction = "down"

        # Interpolación suave de movimiento y rotación
        self.target_angle = 0.0
        self.angle_smoothing = 8.0  # Girar más rápido (antes 5.0)

        # Velocidad de movimiento suavizada
        self.current_velocity = [0.0, 0.0]
        self.velocity_smoothing = 12.0  # Acelerar más rápido (antes 8.0)

        # Sistema anti-atascamiento
        self.stuck_counter = 0
        self.last_valid_position = (start_x, start_y)
        self.position_history = []
        self.max_position_history = 10

        # Configuración de evitación de paredes (AJUSTADO)
        self.wall_avoidance_distance = 0.25  # Menos conservador (antes 0.3)
        self.wall_slowdown_distance = 0.5  # Menos conservador (antes 0.6)

        # Referencia al juego (para notificaciones)
        self._last_game_ref = None

        # Timestamp para renderer
        self._last_update_time = time.time()

        if not hasattr(self, 'max_stamina'):
            self.max_stamina = 100.0

        # Cooldown para recuperación de stamina
        self.stamina_recovery_cooldown = 1.5
        self.time_since_stopped = 0.0
        self._last_order_accept_time = -999.0

    def _build_default_strategy(self, difficulty: str) -> BaseStrategy:
        """Construye la estrategia según dificultad"""
        host = self.world or self
        difficulty = difficulty.lower().strip()

        if difficulty == "easy":
            return EasyStrategy(host)
        elif difficulty == "medium":
            return MediumStrategy(host)
        elif difficulty == "hard":
            return HardStrategy(host)
        else:
            return EasyStrategy(host)

    def set_strategy(self, strategy: BaseStrategy):
        """Cambiar estrategia en runtime"""
        self.strategy = strategy

    # ==================== MOVIMIENTO Y ROTACIÓN ====================

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

        # DEBUG TEMPORAL: Ver qué ángulos llegan
        if self.debug and hasattr(self, '_last_sprite_debug'):
            if abs(angle_deg - self._last_sprite_debug) > 10:
                print(f"[AI-{self.difficulty}] Angulo: {angle_deg:.1f} grados")
                self._last_sprite_debug = angle_deg
        elif not hasattr(self, '_last_sprite_debug'):
            self._last_sprite_debug = angle_deg

        # Sistema de coordenadas: Y crece hacia abajo
        # atan2(dy, dx): 0 = derecha, 90 = abajo, -90 = arriba, 180 = izquierda
        if 337.5 <= angle_deg or angle_deg < 22.5:
            self.current_direction = "right"
        elif 22.5 <= angle_deg < 67.5:
            self.current_direction = "down_right"
        elif 67.5 <= angle_deg < 112.5:
            self.current_direction = "down"
        elif 112.5 <= angle_deg < 157.5:
            self.current_direction = "down_left"
        elif 157.5 <= angle_deg < 202.5:
            self.current_direction = "left"
        elif 202.5 <= angle_deg < 247.5:
            self.current_direction = "up_left"
        elif 247.5 <= angle_deg < 292.5:
            self.current_direction = "up"
        else:
            self.current_direction = "up_right"

    # ==================== EVITACIÓN DE PAREDES ====================

    def _check_wall_ahead(self, city, dx: float, dy: float, distance: float = 0.5) -> bool:
        """Verifica si hay una pared en la dirección de movimiento"""
        test_x = self.x + dx * distance
        test_y = self.y + dy * distance
        return city.is_wall(test_x, test_y)

    def _calculate_wall_avoidance_vector(self, city, target_dx: float, target_dy: float) -> Tuple[float, float]:
        """
        VERSIÓN OPTIMIZADA: Evitación más sutil para IA difícil.
        IA difícil usa evitación MÍNIMA, solo para no chocar.
        """
        mag = math.sqrt(target_dx ** 2 + target_dy ** 2)
        if mag < 0.001:
            return (0.0, 0.0)

        norm_dx = target_dx / mag
        norm_dy = target_dy / mag

        # IA DIFÍCIL: Evitación más agresiva solo si está siguiendo path A*
        if self.difficulty == "hard":
            # Verificar solo si hay pared DIRECTAMENTE adelante
            if self._check_wall_ahead(city, norm_dx, norm_dy, 0.4):
                # Buscar ruta lateral mínima
                base_angle = math.atan2(norm_dy, norm_dx)

                # Probar solo 2 direcciones perpendiculares
                for angle_offset in [math.pi / 4, -math.pi / 4]:  # 45° a cada lado
                    test_angle = base_angle + angle_offset
                    test_dx = math.cos(test_angle)
                    test_dy = math.sin(test_angle)

                    if not self._check_wall_ahead(city, test_dx, test_dy, 0.3):
                        # Mezclar solo 30% de corrección
                        final_dx = norm_dx * 0.7 + test_dx * 0.3
                        final_dy = norm_dy * 0.7 + test_dy * 0.3

                        final_mag = math.sqrt(final_dx ** 2 + final_dy ** 2)
                        if final_mag > 0.001:
                            return (final_dx / final_mag, final_dy / final_mag)

            # No hay pared cerca, seguir directo
            return (norm_dx, norm_dy)

        # OTRAS IAS: Evitación más conservadora (código original simplificado)
        check_angles = [-20, -10, 0, 10, 20]
        base_angle = math.atan2(norm_dy, norm_dx)

        repulsion_x = 0.0
        repulsion_y = 0.0

        for angle_offset in check_angles:
            check_angle = base_angle + math.radians(angle_offset)
            check_dx = math.cos(check_angle)
            check_dy = math.sin(check_angle)

            for dist in [0.4, 0.7]:
                test_x = self.x + check_dx * dist
                test_y = self.y + check_dy * dist

                if city.is_wall(test_x, test_y):
                    strength = (1.0 - dist / 0.7) * 1.0
                    repulsion_x -= check_dx * strength
                    repulsion_y -= check_dy * strength
                    break

        # Combinar con menos peso en la repulsión
        final_dx = norm_dx + repulsion_x * 0.5
        final_dy = norm_dy + repulsion_y * 0.5

        # Normalizar resultado
        final_mag = math.sqrt(final_dx ** 2 + final_dy ** 2)
        if final_mag > 0.001:
            final_dx /= final_mag
            final_dy /= final_mag

        return (final_dx, final_dy)

    def _calculate_speed_multiplier(self, city) -> float:
        """
        Calcula multiplicador de velocidad basado en proximidad a paredes.
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
            return 0.5  # CAMBIO: Antes 0.3 (permitir más velocidad cerca de paredes)

        # Interpolación lineal
        t = (min_distance - self.wall_avoidance_distance) / \
            (self.wall_slowdown_distance - self.wall_avoidance_distance)
        return 0.5 + (0.5 * t)  # CAMBIO: Antes 0.3 + (0.7 * t)

    # ==================== DETECCIÓN DE ATASCAMIENTO ====================

    def _detect_stuck(self) -> bool:
        """
        VERSIÓN CORREGIDA: Menos sensible, solo detecta atascamiento real.
        """
        if len(self.position_history) < self.max_position_history:
            return False

        # Calcular distancia total recorrida
        total_distance = 0.0
        for i in range(1, len(self.position_history)):
            prev = self.position_history[i - 1]
            curr = self.position_history[i]
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            total_distance += math.sqrt(dx ** 2 + dy ** 2)

        # CAMBIO: Umbral más bajo (antes 0.5, ahora 0.2)
        is_stuck = total_distance < 0.2

        if is_stuck and self.debug:
            print(f"[AI-{self.difficulty}] ⚠️  Atascamiento detectado (distancia: {total_distance:.2f})")

        return is_stuck

    def _unstuck_maneuver(self, city) -> Tuple[float, float]:
        """
        VERSIÓN CORREGIDA: Maniobra más inteligente para escapar.
        """
        import random

        if self.debug:
            print(f"[AI-{self.difficulty}] 🔄 Maniobra de escape desde ({self.x:.1f},{self.y:.1f})")

        # 1. Intentar moverse hacia atrás
        back_angle = self.angle + math.pi
        for dist_multiplier in [1.5, 1.0, 0.5]:
            test_x = self.x + math.cos(back_angle) * dist_multiplier
            test_y = self.y + math.sin(back_angle) * dist_multiplier

            if (0 <= test_x < city.width and 0 <= test_y < city.height and
                    not city.is_wall(test_x, test_y)):
                return (math.cos(back_angle), math.sin(back_angle))

        # 2. Intentar moverse perpendicular (90° a cada lado)
        for perpendicular_angle in [self.angle + math.pi / 2, self.angle - math.pi / 2]:
            for dist_multiplier in [1.0, 0.5]:
                test_x = self.x + math.cos(perpendicular_angle) * dist_multiplier
                test_y = self.y + math.sin(perpendicular_angle) * dist_multiplier

                if (0 <= test_x < city.width and 0 <= test_y < city.height and
                        not city.is_wall(test_x, test_y)):
                    return (math.cos(perpendicular_angle), math.sin(perpendicular_angle))

        # 3. Probar 8 direcciones aleatorias
        for _ in range(8):
            random_angle = random.uniform(0, 2 * math.pi)
            test_x = self.x + math.cos(random_angle) * 1.0
            test_y = self.y + math.sin(random_angle) * 1.0

            if (0 <= test_x < city.width and 0 <= test_y < city.height and
                    not city.is_wall(test_x, test_y)):
                return (math.cos(random_angle), math.sin(random_angle))

        # 4. Último recurso: teleportarse a última posición válida
        if self.last_valid_position:
            dx = self.last_valid_position[0] - self.x
            dy = self.last_valid_position[1] - self.y
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist > 0.1:
                if self.debug:
                    print(f"[AI-{self.difficulty}] 🚨 Teleport a {self.last_valid_position}")
                self.x, self.y = self.last_valid_position
                self.position_history.clear()

        return (0.0, 0.0)

    # ==================== APLICAR MOVIMIENTO ====================

    def _apply_step(self, dx: int, dy: int, game):
        """
        Aplica movimiento con evitación; si se descansa, no se mueve ni consume stamina por distancia.
        """
        city = getattr(game, "city", None)
        if not city:
            return

        delta_time = getattr(game, '_last_delta_time', 1 / 60.0)

        # Si estrategia indica descanso, no mover ni anti-atasco
        if getattr(self.strategy, "is_resting", False):
            # NO resetear cooldown cada frame
            self.current_velocity = [0.0, 0.0]
            self.is_moving = False
            self._current_step = (0, 0)
            return

        # Historial de posición
        self.position_history.append((self.x, self.y))
        if len(self.position_history) > self.max_position_history:
            self.position_history.pop(0)

        # Anti-atasco
        if self._detect_stuck():
            self.stuck_counter += 1
            if self.stuck_counter > 3:
                dx, dy = self._unstuck_maneuver(city)
                self.stuck_counter = 0
        else:
            self.stuck_counter = 0
            self.last_valid_position = (self.x, self.y)

        # Sin paso, amortiguar a cero y salir
        if dx == 0 and dy == 0:
            self.current_velocity[0] *= (1.0 - delta_time * self.velocity_smoothing)
            self.current_velocity[1] *= (1.0 - delta_time * self.velocity_smoothing)
            if abs(self.current_velocity[0]) < 0.01:
                self.current_velocity[0] = 0.0
            if abs(self.current_velocity[1]) < 0.01:
                self.current_velocity[1] = 0.0
            self._current_step = (0, 0)
            self.is_moving = False
            return

        # Guardar posición previa
        prev_x, prev_y = self.x, self.y

        # Normalizar dirección
        magnitude = math.sqrt(dx ** 2 + dy ** 2)
        if magnitude > 0:
            target_dx = dx / magnitude
            target_dy = dy / magnitude
        else:
            target_dx, target_dy = 0.0, 0.0

        # Evitación de paredes
        adjusted_dx, adjusted_dy = self._calculate_wall_avoidance_vector(city, target_dx, target_dy)

        # Ángulo objetivo
        if self.difficulty == "hard" and hasattr(self, 'strategy') and hasattr(self.strategy, 'planner'):
            planner = self.strategy.planner
            if planner._path and len(planner._path) > 0:
                next_node = planner._path[0]
                target_angle_dx = next_node[0] - self.x
                target_angle_dy = next_node[1] - self.y
                angle_magnitude = math.sqrt(target_angle_dx ** 2 + target_angle_dy ** 2)
                if angle_magnitude > 0.01:
                    self.target_angle = math.atan2(target_angle_dy, target_angle_dx)
                else:
                    self.target_angle = math.atan2(adjusted_dy, adjusted_dx)
            else:
                self.target_angle = math.atan2(adjusted_dy, adjusted_dx)
        else:
            self.target_angle = math.atan2(adjusted_dy, adjusted_dx)

        # Rotación suave y sprite
        self._smooth_angle_to_target(delta_time)
        self._update_sprite_direction()

        # Velocidad efectiva y proximidad a paredes
        base_effective_speed = self.calculate_effective_speed(city)
        speed_mult = self._calculate_speed_multiplier(city)

        # Suavizado de velocidad
        target_vel_x = adjusted_dx * speed_mult * base_effective_speed
        target_vel_y = adjusted_dy * speed_mult * base_effective_speed
        smoothing_factor = min(1.0, delta_time * self.velocity_smoothing)
        self.current_velocity[0] += (target_vel_x - self.current_velocity[0]) * smoothing_factor
        self.current_velocity[1] += (target_vel_y - self.current_velocity[1]) * smoothing_factor

        # Aplicar movimiento
        vel_mag = math.sqrt(self.current_velocity[0] ** 2 + self.current_velocity[1] ** 2)
        if vel_mag > 0.01:
            norm_vel_x = self.current_velocity[0] / vel_mag
            norm_vel_y = self.current_velocity[1] / vel_mag
            self.move(norm_vel_x, norm_vel_y, delta_time, city)
            self.is_moving = True
        else:
            self.is_moving = False

        # Distancia real movida y consumo stamina
        distance_moved = math.sqrt((self.x - prev_x) ** 2 + (self.y - prev_y) ** 2)
        self.consume_stamina_for_movement(delta_time, distance_moved)

        self._current_step = (dx, dy)

    # ==================== SISTEMA DE STAMINA ====================

    def consume_stamina_for_movement(self, delta_time: float, distance_moved: float):
        """
        CRÍTICO: Consume stamina basado en movimiento real (idéntico a Player).
        """
        if distance_moved < 0.01:
            return

        # Base drain (por celda movida)
        base_drain = 0.5 * distance_moved

        # Penalty por peso
        if self.total_weight > 3:
            weight_penalty = 0.2 * (self.total_weight - 3) * distance_moved
            base_drain += weight_penalty

        # Penalty por clima
        if hasattr(self, 'weather_stamina_drain') and self.weather_stamina_drain > 0:
            base_drain += self.weather_stamina_drain * delta_time

        # Aplicar consumo
        old_stamina = self.stamina
        self.stamina = max(0.0, self.stamina - base_drain)

        # Debug SOLO cuando stamina baja significativamente
        if self.debug and old_stamina >= 20 and self.stamina < 20:
            print(f"[AI-{self.difficulty}] ⚠️  Stamina crítica: {self.stamina:.1f}")

    # ==================== GESTIÓN DE PEDIDOS ====================

    def _handle_order_state_transitions(self, game):
        """
        VERSIÓN CORREGIDA: Usa distancia euclidiana con tolerancia.
        """
        if not self.inventory.orders:
            return

        # Guardar referencia al game
        self._last_game_ref = game

        order = self.inventory.orders[0]

        # CAMBIO: Usar distancia euclidiana con margen
        distance_threshold = 0.7  # Más permisivo

        # PICKUP
        if order.status == "in_progress":
            pickup_x, pickup_y = order.pickup_pos
            distance = math.sqrt((self.x - pickup_x) ** 2 + (self.y - pickup_y) ** 2)

            if distance <= distance_threshold:
                order.pickup()
                self.set_inventory_weight(self.inventory.current_weight)

                if self.debug:
                    print(f"[AI-{self.difficulty}] 📦 PICKUP {order.id[:8]} en ({self.x:.1f},{self.y:.1f})")

                self.current_target = order.dropoff_pos
                return

        # DELIVERY
        elif order.status == "picked_up":
            dropoff_x, dropoff_y = order.dropoff_pos
            distance = math.sqrt((self.x - dropoff_x) ** 2 + (self.y - dropoff_y) ** 2)

            if distance <= distance_threshold:
                payout = float(getattr(order, 'payout', getattr(order, 'payment', 0.0)))

                if self.reputation >= 90:
                    payout *= 1.05

                order.deliver()
                self.add_earnings(payout)
                self.update_reputation_for_delivery(order)
                self.deliveries_completed += 1

                self.remove_order_from_inventory(order.id)
                self.set_inventory_weight(self.inventory.current_weight)

                if self.debug:
                    print(
                        f"[AI-{self.difficulty}] ✅ DELIVERY {order.id[:8]} en ({self.x:.1f},{self.y:.1f}) (+${payout:.0f})")

                self.current_target = None

    def add_order_to_inventory(self, order) -> bool:
        """Agregar pedido al inventario con validaciones"""
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

    def update_order_timers(self, current_play_time: float):
        """
        CRÍTICO: Actualiza timers de todos los pedidos.
        Debe llamarse cada frame desde game.py.
        """
        if not self.inventory.orders:
            return

        for order in list(self.inventory.orders):
            if hasattr(order, 'accepted_at') and order.accepted_at >= 0:
                elapsed = current_play_time - order.accepted_at
                order.update_time_remaining(elapsed)

                # Verificar expiración
                if order.time_remaining <= 0 and order.status != "delivered":
                    if self.debug:
                        print(f"[AI-{self.difficulty}] ⏰ Pedido {order.id[:8]} EXPIRÓ")

                    # Penalización idéntica a Player
                    self.reputation = max(0, self.reputation - 6)
                    self.orders_cancelled += 1
                    self.consecutive_on_time = 0

                    # Remover pedido
                    self.inventory.remove_order(order.id)

                    # Notificar
                    if self._last_game_ref and hasattr(self._last_game_ref, 'show_notification'):
                        try:
                            self._last_game_ref.show_notification(
                                f"IA perdió {order.id[:8]} (-6 rep)", 2.0
                            )
                        except:
                            pass

    # ==================== ACTUALIZACIÓN ====================

    def update(self, delta_time: float):
        """Override con timestamp para renderer"""
        super().update(delta_time)  # Maneja recuperación
        self._last_update_time = time.time()

        # Aplicar clima
        if self.world and hasattr(self.world, 'weather_system') and self.world.weather_system:
            weather_info = self.world.weather_system.get_weather_info()
            self.weather_speed_multiplier = weather_info.get('speed_multiplier', 1.0)
            self.weather_stamina_drain = weather_info.get('stamina_drain', 0.0)


    def update_with_strategy(self, game):
        """Actualizar usando la estrategia asignada"""
        if not self.strategy:
            return

        # IMPORTANTE: NO salimos si no puede moverse.
        # Queremos que la estrategia corra incluso exhausto para:
        # - mantener estado de descanso
        # - aceptar nuevos pedidos mientras descansa
        try:
            if hasattr(self.strategy, "world"):
                self.strategy.world.city = getattr(game, "city", None)
                self.strategy.world.weather_system = getattr(game, "weather_system", None)
        except Exception:
            pass

        # Decidir
        try:
            step = self.strategy.decide(self, game)
        except Exception as e:
            if self.debug:
                print(f"[AI-{self.difficulty}] Error en estrategia: {e}")
            step = (0, 0)

        if not step:
            step = (0, 0)

        dx, dy = step
        self._apply_step(dx, dy, game)
        self._handle_order_state_transitions(game)

    def update_ai(self, delta_time: float, game):
        """
        Actualización optimizada con cooldown.
        """
        game._last_delta_time = delta_time
        self.update(delta_time)
        self.update_order_timers(game.total_play_time)
        self._decision_cooldown -= delta_time
        if self._decision_cooldown <= 0:
            self._decision_cooldown = self._decision_interval
            self.update_with_strategy(game)

    def update_tick(self, delta_time: float, game):
        """Actualización cada frame (sin cooldown)"""
        game._last_delta_time = delta_time

        self.update(delta_time)
        self.update_with_strategy(game)

    # ==================== UTILIDADES ====================

    def get_sprite_direction(self) -> str:
        """Dirección actual del sprite (8 direcciones)"""
        return self.current_direction

    def try_accept_order_with_delay(self, order, current_time: float) -> bool:
        if not hasattr(self, '_last_order_accept_time'):
            self._last_order_accept_time = -999.0  # Valor muy negativo

        cooldown = 2.0
        if self.world and hasattr(self.world, 'app_config'):
            ai_config = self.world.app_config.get('ai', {})
            cooldowns = ai_config.get('order_accept_cooldown', {})
            cooldown = float(cooldowns.get(self.difficulty, 2.0))

        time_diff = current_time - self._last_order_accept_time

        # AGREGAR ESTE LOG TEMPORAL:
        if self.debug:
            print(f"[AI-{self.difficulty}] Intentando aceptar: current={current_time:.2f}, "
                  f"last={self._last_order_accept_time:.2f}, diff={time_diff:.2f}, "
                  f"cooldown={cooldown:.2f}, rechaza={time_diff < cooldown}")

        if time_diff < cooldown:
            return False

        if self.add_order_to_inventory(order):
            self._last_order_accept_time = current_time
            if self.debug:
                print(f"[AI-{self.difficulty}] ACEPTADO en t={current_time:.2f}")
            return True

        return False

    def enter_rest(self, reset_timer: bool = False):
        """Detener movimiento total durante descanso sin romper el cooldown en frames posteriores."""
        self.current_velocity = [0.0, 0.0]
        self.is_moving = False
        self._current_step = (0, 0)
        self.current_target = None
        if reset_timer:
            self.time_since_stopped = 0.0