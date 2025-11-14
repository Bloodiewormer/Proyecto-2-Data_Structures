import math
import random
import heapq
from typing import Optional, Tuple, List
from game.entities.player import Player
from game.core.orders import Order


class AIPlayer(Player):
    """
    Jugador controlado por IA que extiende Player.
    Comparte las mismas reglas: stamina, reputación, inventario, etc.
    """

    def __init__(self, start_x: float, start_y: float, config: dict, difficulty: str = "easy"):
        super().__init__(start_x, start_y, config)
        self.difficulty = difficulty.lower()
        self.is_ai = True

        # Estado de decisión
        self.current_target: Optional[Tuple[int, int]] = None
        self.current_path: List[Tuple[int, int]] = []
        self.decision_cooldown = 0.0
        self.decision_interval = 0.5  # Tomar decisiones cada 0.5s

        # Para dificultad media: horizonte de planificación
        self.lookahead_depth = 2 if self.difficulty == "medium" else 0

    def update_ai(self, delta_time: float, game):
        """
        Actualización principal de la IA. Llamar desde game.on_update()
        """
        # Actualizar física del jugador (stamina, estado, etc)
        self.update(delta_time)

        # Control de decisiones
        self.decision_cooldown -= delta_time
        if self.decision_cooldown <= 0:
            self.decision_cooldown = self.decision_interval
            self._make_decision(game)

        # Ejecutar movimiento hacia el objetivo
        if self.current_target:
            self._move_towards_target(delta_time, game.city)

    def _make_decision(self, game):
        """Tomar decisión según dificultad"""
        if self.difficulty == "easy":
            self._decide_easy(game)
        elif self.difficulty == "medium":
            self._decide_medium(game)
        elif self.difficulty == "hard":
            self._decide_hard(game)

    # ============ FÁCIL: Decisiones aleatorias ============
    def _decide_easy(self, game):
        """
        Lógica aleatoria:
        - Si no tiene pedidos, toma uno al azar
        - Si tiene pedido, se mueve aleatoriamente hacia pickup/dropoff
        """
        # ¿Necesita pedido?
        if not self.inventory.orders and game.pending_orders:
            # Tomar pedido aleatorio
            order = random.choice(game.pending_orders)
            if self.add_order_to_inventory(order):
                game.pending_orders.remove(order)
                if game.orders_manager:
                    game.orders_manager.pending_orders = game.pending_orders
                # Iniciar timer
                if hasattr(order, 'start_timer'):
                    order.start_timer(game.total_play_time)

        # Mover hacia objetivo actual o elegir uno nuevo
        if self.inventory.orders:
            order = self.inventory.orders[0]
            if order.status == "in_progress":
                self.current_target = order.pickup_pos
            elif order.status == "picked_up":
                self.current_target = order.dropoff_pos
        else:
            # Sin pedidos, moverse aleatoriamente
            self._random_walk(game.city)

    def _random_walk(self, city):
        """Caminar en dirección aleatoria (evitando paredes)"""
        # Intentar nueva dirección aleatoria
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(directions)

        for dx, dy in directions:
            new_x = self.x + dx
            new_y = self.y + dy
            if not city.is_wall(new_x, new_y):
                self.current_target = (int(new_x), int(new_y))
                return

    # ============ MEDIO: Evaluación greedy/expectimax ============
    def _decide_medium(self, game):
        """
        Evaluación greedy con horizonte limitado:
        - Evalúa múltiples opciones de pedidos
        - Calcula score = α*payout - β*distance - γ*weather_penalty
        - Elige la mejor opción
        """
        # Si ya tiene pedidos, continuar con ellos
        if self.inventory.orders:
            order = self.inventory.orders[0]
            if order.status == "in_progress":
                self.current_target = order.pickup_pos
            elif order.status == "picked_up":
                self.current_target = order.dropoff_pos
            return

        # Evaluar pedidos disponibles
        if not game.pending_orders:
            self._random_walk(game.city)
            return

        best_order = None
        best_score = float('-inf')

        # Pesos para la función de evaluación
        alpha = 1.0  # Importancia del pago
        beta = 0.5  # Penalización por distancia
        gamma = 0.3  # Penalización por clima

        for order in game.pending_orders:
            # Calcular distancia a pickup
            dist = self._manhattan_distance(
                (self.x, self.y),
                order.pickup_pos
            )

            # Factor de clima (más penalización si clima es malo)
            weather_penalty = 0.0
            if game.weather_system:
                speed_mult = game.weather_system._get_interpolated_speed_multiplier()
                weather_penalty = (1.0 - speed_mult) * 100

            # Score
            score = alpha * order.payout - beta * dist - gamma * weather_penalty

            if score > best_score:
                best_score = score
                best_order = order

        # Aceptar mejor pedido
        if best_order and self.add_order_to_inventory(best_order):
            game.pending_orders.remove(best_order)
            if game.orders_manager:
                game.orders_manager.pending_orders = game.pending_orders
            if hasattr(best_order, 'start_timer'):
                best_order.start_timer(game.total_play_time)
            self.current_target = best_order.pickup_pos

    # ============ DIFÍCIL: Algoritmos de grafos (A*) ============
    def _decide_hard(self, game):
        """
        Usa A* para encontrar rutas óptimas considerando:
        - Peso de superficies (calles vs parques)
        - Clima (aumenta costo de aristas)
        - Planificación de secuencia de entregas
        """
        # Si tiene pedido, ejecutar ruta óptima
        if self.inventory.orders:
            order = self.inventory.orders[0]
            if order.status == "in_progress":
                target = order.pickup_pos
            elif order.status == "picked_up":
                target = order.dropoff_pos
            else:
                return

            # Calcular ruta con A* si no hay path o cambió objetivo
            if not self.current_path or self.current_target != target:
                self.current_target = target
                self.current_path = self._astar_path(game.city, game.weather_system, target)

            # Seguir path
            if self.current_path:
                next_pos = self.current_path[0]
                dist = math.hypot(next_pos[0] - self.x, next_pos[1] - self.y)
                if dist < 0.5:  # Llegó al siguiente nodo
                    self.current_path.pop(0)
            return

        # Sin pedidos: elegir el mejor según TSP aproximado
        if not game.pending_orders:
            self._random_walk(game.city)
            return

        # Evaluar pedidos con costo real de ruta
        best_order = None
        best_cost = float('inf')

        for order in game.pending_orders:
            # Costo = distancia_a_pickup + distancia_pickup_a_dropoff - payout
            path_to_pickup = self._astar_path(game.city, game.weather_system, order.pickup_pos)
            path_delivery = self._astar_path_between(
                game.city, game.weather_system,
                order.pickup_pos, order.dropoff_pos
            )

            cost_pickup = len(path_to_pickup) if path_to_pickup else 999
            cost_delivery = len(path_delivery) if path_delivery else 999
            total_cost = cost_pickup + cost_delivery - order.payout * 0.1

            if total_cost < best_cost:
                best_cost = total_cost
                best_order = order

        if best_order and self.add_order_to_inventory(best_order):
            game.pending_orders.remove(best_order)
            if game.orders_manager:
                game.orders_manager.pending_orders = game.pending_orders
            if hasattr(best_order, 'start_timer'):
                best_order.start_timer(game.total_play_time)
            self.current_target = best_order.pickup_pos
            self.current_path = self._astar_path(game.city, game.weather_system, self.current_target)

    # ============ UTILIDADES ============
    def _move_towards_target(self, delta_time: float, city):
        """Mover hacia current_target"""
        if not self.current_target:
            return

        dx = self.current_target[0] - self.x
        dy = self.current_target[1] - self.y
        dist = math.hypot(dx, dy)

        if dist < 0.1:  # Llegó
            self.current_target = None
            return

        # Normalizar dirección
        dx /= dist
        dy /= dist

        # Aplicar movimiento
        self.move(dx, dy, delta_time, city)

    def _manhattan_distance(self, pos1: Tuple[float, float], pos2: Tuple[int, int]) -> float:
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _astar_path(self, city, weather_system, target: Tuple[int, int]) -> List[Tuple[int, int]]:
        """A* desde posición actual a target"""
        start = (int(self.x), int(self.y))
        return self._astar_path_between(city, weather_system, start, target)

    def _astar_path_between(self, city, weather_system, start: Tuple[int, int],
                            goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        A* genérico considerando:
        - Costo base por tile (surface_weight)
        - Penalización por clima
        """
        # Factor de clima
        weather_cost = 1.0
        if weather_system:
            speed_mult = weather_system._get_interpolated_speed_multiplier()
            weather_cost = 2.0 - speed_mult  # Más lento = más costo

        def heuristic(pos):
            return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])

        def cost(pos):
            """Costo de estar en esta posición"""
            surface = city.get_surface_weight(pos[0], pos[1])
            return (2.0 - surface) * weather_cost

        # A*
        frontier = []
        heapq.heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}

        while frontier:
            _, current = heapq.heappop(frontier)

            if current == goal:
                break

            # Vecinos (4 direcciones)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)

                # Verificar validez
                if city.is_wall(neighbor[0], neighbor[1]):
                    continue

                new_cost = cost_so_far[current] + cost(neighbor)

                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + heuristic(neighbor)
                    heapq.heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current

        # Reconstruir path
        if goal not in came_from:
            return []

        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()

        return path

