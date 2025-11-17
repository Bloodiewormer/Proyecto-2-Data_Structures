from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

from game.IA.interfaces import StepPolicy, PathPlanner
from game.IA.policies.random_choice import RandomChoicePolicy
from game.IA.policies.greedy import GreedyPolicy
from game.IA.planner.astar import AStarPlanner


def _manhattan(a: Tuple[int,int], b: Tuple[int,int]) -> int:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def _neighbors4(x: int, y: int) -> List[Tuple[int,int]]:
    return [(x+1,y), (x-1,y), (x,y+1), (x,y-1)]

def _is_walkable(city, x: int, y: int) -> bool:
    try:
        # city.is_wall(x,y) existe en el repo
        return not city.is_wall(x, y)
    except Exception:
        # Fallback leyendo tiles si hiciera falta
        if x < 0 or y < 0 or x >= city.width or y >= city.height:
            return False
        return getattr(city, "tiles", [[]])[y][x] != "B"

def _nearest_door(city, gx: int, gy: int, max_expansion: int = 32) -> Optional[Tuple[int,int]]:
    """Puerta = celda caminable más cercana al target (gx,gy)."""
    if _is_walkable(city, gx, gy):
        return (gx, gy)
    from collections import deque
    q = deque([(gx, gy)])
    seen = {(gx, gy)}
    steps = 0
    while q and steps < max_expansion:
        for _ in range(len(q)):
            x, y = q.popleft()
            for nx, ny in _neighbors4(x, y):
                if (nx, ny) in seen:
                    continue
                seen.add((nx, ny))
                if nx < 0 or ny < 0 or nx >= city.width or ny >= city.height:
                    continue
                if _is_walkable(city, nx, ny):
                    return (nx, ny)
                q.append((nx, ny))
        steps += 1
    return None

def _best_step_towards(city, cx: int, cy: int, tx: int, ty: int, last_step: Tuple[int,int]) -> Tuple[int,int]:
    """Paso cardinal que minimiza Manhattan hacia (tx,ty), evitando paredes."""
    cand = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = cx + dx, cy + dy
        if _is_walkable(city, nx, ny):
            cand.append((dx, dy, _manhattan((nx, ny), (tx, ty))))
    if not cand:
        return (0, 0)
    # Preferir el que más reduce distancia; pequeño bonus a mantener dirección
    best = None
    best_score = 10**9
    for dx, dy, dist in cand:
        score = dist
        if (dx, dy) == last_step:
            score -= 0.1
        if score < best_score:
            best_score = score
            best = (dx, dy)
    return best or (0, 0)

def _best_step_away(city, cx: int, cy: int, fromx: int, fromy: int) -> Tuple[int,int]:
    """Paso cardinal que aumenta Manhattan respecto a (fromx,fromy), evitando paredes."""
    cand = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = cx + dx, cy + dy
        if _is_walkable(city, nx, ny):
            cand.append((dx, dy, _manhattan((nx, ny), (fromx, fromy))))
    if not cand:
        return (0, 0)
    # Maximiza la distancia
    cand.sort(key=lambda t: -t[2])
    return (cand[0][0], cand[0][1])


class BaseStrategy:
    """
    Contrato: decide(ai, game) puede:
    - retornar (dx,dy) para un paso directo
    - y/o actualizar ai.current_target / ai.current_path
    """
    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        raise NotImplementedError


class EasyStrategy(BaseStrategy):
    """
    Estrategia fácil: Acepta el primer pedido disponible y se mueve aleatoriamente
    con sesgo hacia el objetivo.
    """

    def __init__(self, world):
        self.world = world
        self.policy = RandomChoicePolicy(world, bias=0.70)
        self.current_order_id = None  # Tracking del pedido actual
        self.debug = getattr(world, 'debug', False)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        # 1. Si no tiene pedido, tomar el primero disponible
        if not ai.inventory.orders and game.pending_orders:
            order = game.pending_orders[0]

            # Verificar capacidad básica
            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                # Peso excedido, esperar
                if self.debug:
                    print(f"[EASY] Pedido {order.id[:8]} muy pesado ({order.weight}kg)")
                ai.current_target = None
                return (0, 0)

            # Intentar aceptar con delay
            if ai.try_accept_order_with_delay(order, game.total_play_time):
                order.start_timer(game.total_play_time)
                order.status = "in_progress"
                game.pending_orders.remove(order)

                if hasattr(game.orders_manager, 'pending_orders'):
                    game.orders_manager.pending_orders = game.pending_orders

                self.current_order_id = order.id
                ai.current_target = order.pickup_pos

                if self.debug:
                    print(f"[EASY] Aceptó {order.id[:8]} (payout: ${order.payout:.0f})")

        # 2. Actualizar target según estado del pedido
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            if order.status == "picked_up":
                ai.current_target = order.dropoff_pos
            else:
                ai.current_target = order.pickup_pos
        else:
            ai.current_target = None

        # 3. Movimiento aleatorio con sesgo hacia target
        return self.policy.decide_step(ai)


class MediumStrategy(BaseStrategy):
    """
    Estrategia intermedia: Evalúa pedidos con heurística considerando
    distancia, payout, clima y estado del jugador.
    """

    def __init__(self, world, lookahead_depth: int = 2, climate_weight: float = 0.5):
        self.world = world
        self.policy = GreedyPolicy(world, climate_weight=climate_weight, lookahead_depth=lookahead_depth)
        self.last_evaluation = 0.0
        self.evaluation_interval = 5.0
        self.debug = getattr(world, 'debug', False)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # 1. Si tiene pedido activo
        if ai.inventory.orders:
            order = ai.inventory.orders[0]

            # Evaluar si debería abandonar el pedido actual (solo low priority)
            if (now - self.last_evaluation > self.evaluation_interval and
                    order.priority == 0 and
                    game.pending_orders):

                best_alt = self._find_best_order(ai, game.pending_orders, game)

                if best_alt:
                    current_score = self._score_order(ai, order, game)
                    alt_score = self._score_order(ai, best_alt, game)

                    # Cambiar solo si la alternativa es 30% mejor
                    if alt_score > current_score * 1.3:
                        if self.debug:
                            print(
                                f"[MEDIUM] Cambiando {order.id[:8]} por {best_alt.id[:8]} (score {current_score:.1f} -> {alt_score:.1f})")

                        # Cancelar actual
                        ai.cancel_order()
                        ai.inventory.remove_order(order.id)
                        game.orders_manager.mark_canceled(order.id)

                        # Aceptar nuevo
                        if ai.add_order_to_inventory(best_alt):
                            best_alt.start_timer(now)
                            game.pending_orders.remove(best_alt)
                            if hasattr(game.orders_manager, 'pending_orders'):
                                game.orders_manager.pending_orders = game.pending_orders
                            order = best_alt

                self.last_evaluation = now

            # Actualizar target según estado
            ai.current_target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos

        # 2. Si no tiene pedido, elegir el mejor disponible
        else:
            best = self._find_best_order(ai, game.pending_orders, game)

            if best:
                # Usar el método con delay para respetar cooldowns
                if ai.try_accept_order_with_delay(best, now):
                    best.start_timer(now)
                    best.status = "in_progress"
                    game.pending_orders.remove(best)

                    if hasattr(game.orders_manager, 'pending_orders'):
                        game.orders_manager.pending_orders = game.pending_orders

                    ai.current_target = best.pickup_pos

                    if self.debug:
                        print(f"[MEDIUM] Aceptó {best.id[:8]} (score {self._score_order(ai, best, game):.1f})")
            else:
                ai.current_target = None

        # 3. Movimiento greedy
        return self.policy.decide_step(ai)

    def _score_order(self, ai: "AIPlayer", order, game) -> float:
        """
        Calcula score heurístico de un pedido.
        Mayor score = mejor pedido.
        """
        # Distancia Manhattan al pickup
        dist_to_pickup = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])

        # Penalización por clima adverso
        weather_penalty = 0.0
        if hasattr(game, 'weather_system') and game.weather_system:
            try:
                speed_mult = game.weather_system._get_interpolated_speed_multiplier()
                # A menor velocidad, mayor penalización
                weather_penalty = (1.0 - speed_mult) * 100
            except Exception:
                pass

        # Penalización por bajo stamina
        stamina_penalty = 0.0
        if ai.stamina < 50:
            stamina_penalty = (50 - ai.stamina) * 0.5

        # Bonus por prioridad
        priority_bonus = order.priority * 50

        # Score final: payout + priority - distancia - clima - stamina
        score = (
                float(getattr(order, 'payout', getattr(order, 'payment', 0.0)))
                + priority_bonus
                - (dist_to_pickup * 0.5)
                - (weather_penalty * 0.3)
                - (stamina_penalty * 0.2)
        )

        return score

    def _find_best_order(self, ai: "AIPlayer", orders, game) -> Optional[Any]:
        """
        Encuentra el mejor pedido según heurística.
        Filtra por capacidad y stamina.
        """
        if not orders:
            return None

        # Filtros básicos
        # 1. Stamina mínima requerida
        if ai.stamina < 30:
            if self.debug:
                print(f"[MEDIUM] Stamina muy baja ({ai.stamina:.1f}), esperando recuperación")
            return None

        best_order = None
        best_score = float("-inf")

        for order in orders:
            # 2. Verificar capacidad de peso
            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                continue

            # 3. Calcular score
            score = self._score_order(ai, order, game)

            if score > best_score:
                best_score = score
                best_order = order

        return best_order


class HardStrategy(BaseStrategy):
    """
    Estrategia avanzada: Usa A* para calcular rutas exactas y
    planifica secuencias de múltiples pedidos.
    """

    def __init__(self, world):
        self.world = world
        self.planner = AStarPlanner(world)
        self.planned_sequence = []  # Lista de order IDs
        self.last_replan = 0.0
        self.replan_interval = 10.0
        self.last_climate_mult = 1.0
        self.debug = getattr(world, 'debug', False)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # 1. Detectar si necesita replanificar
        climate_changed = self._climate_changed_significantly(game)
        time_to_replan = (now - self.last_replan) > self.replan_interval

        if (time_to_replan or climate_changed) and not ai.inventory.orders:
            if self.debug:
                print(f"[HARD] Replanificando... (clima_changed={climate_changed})")
            self._plan_order_sequence(ai, game)
            self.last_replan = now

        # 2. Si tiene pedido activo, usar A* para navegar
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos

            # Actualizar goal si cambió
            if ai.current_target != target:
                ai.current_target = target
                self.planner.set_goal(target)
                if self.debug:
                    print(f"[HARD] Nuevo target: {target} para {order.id[:8]}")

            # Obtener siguiente paso de A*
            return self.planner.next_step(ai)

        # 3. Si no tiene pedido pero hay secuencia planeada, tomar el siguiente
        if self.planned_sequence and game.pending_orders:
            next_id = self.planned_sequence[0]
            order = next((o for o in game.pending_orders if o.id == next_id), None)

            if order:
                # Verificar que aún sea viable (peso, stamina)
                if self._is_order_viable(ai, order):
                    if ai.add_order_to_inventory(order):
                        order.start_timer(now)
                        order.status = "in_progress"
                        game.pending_orders.remove(order)

                        if hasattr(game.orders_manager, 'pending_orders'):
                            game.orders_manager.pending_orders = game.pending_orders

                        self.planned_sequence.pop(0)
                        ai.current_target = order.pickup_pos
                        self.planner.set_goal(order.pickup_pos)

                        if self.debug:
                            print(f"[HARD] Tomó pedido planeado {order.id[:8]}")

                        return self.planner.next_step(ai)
                else:
                    # Ya no es viable, descartar y replanificar
                    self.planned_sequence.clear()

        # 4. Si no hay secuencia, planificar una nueva
        if not ai.inventory.orders and game.pending_orders:
            self._plan_order_sequence(ai, game)

        return (0, 0)

    def _is_order_viable(self, ai: "AIPlayer", order) -> bool:
        """Verifica si un pedido sigue siendo viable"""
        # Peso
        new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
        if new_weight > ai.inventory.max_weight:
            return False

        # Stamina mínima
        if ai.stamina < 40:
            return False

        return True

    def _plan_order_sequence(self, ai: "AIPlayer", game):
        """
        Planifica la mejor secuencia de 2-3 pedidos usando A*.
        Considera rutas reales, no distancias Manhattan.
        """
        if not game.pending_orders or len(game.pending_orders) < 1:
            self.planned_sequence = []
            return

        # Limitar búsqueda a los 5 pedidos más cercanos (por performance)
        candidates = sorted(
            game.pending_orders[:8],
            key=lambda o: abs(ai.x - o.pickup_pos[0]) + abs(ai.y - o.pickup_pos[1])
        )[:5]

        best_sequence = []
        best_value = float("-inf")

        # Evaluar secuencias de 1 pedido (base case)
        for o1 in candidates:
            if not self._is_order_viable(ai, o1):
                continue

            value = self._evaluate_sequence(ai, [o1], game)
            if value > best_value:
                best_sequence = [o1.id]
                best_value = value

        # Evaluar secuencias de 2 pedidos (si hay tiempo)
        if len(candidates) >= 2:
            for i, o1 in enumerate(candidates):
                if not self._is_order_viable(ai, o1):
                    continue

                for o2 in candidates[i + 1:]:
                    # Verificar viabilidad combinada
                    combined_weight = (
                            float(getattr(o1, 'weight', 0.0)) +
                            float(getattr(o2, 'weight', 0.0))
                    )
                    if combined_weight > ai.inventory.max_weight:
                        continue

                    value = self._evaluate_sequence(ai, [o1, o2], game)
                    if value > best_value:
                        best_sequence = [o1.id, o2.id]
                        best_value = value

        self.planned_sequence = best_sequence

        if self.debug:
            print(f"[HARD] Secuencia planeada: {[oid[:8] for oid in best_sequence]} (value={best_value:.1f})")

    def _evaluate_sequence(self, ai: "AIPlayer", orders, game) -> float:
        """
        Calcula el valor de una secuencia de pedidos.
        Usa A* para obtener distancias reales.
        """
        total_payout = sum(float(getattr(o, 'payout', getattr(o, 'payment', 0.0)))
                           for o in orders)
        total_distance = 0.0
        total_time_estimate = 0.0

        current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))

        for order in orders:
            # 1. Distancia a pickup
            self.planner.replan(current_pos, order.pickup_pos)
            path_len_pickup = len(self.planner._path) if self.planner._path else 999

            if path_len_pickup >= 999:
                # No hay camino válido, descartar esta secuencia
                return float("-inf")

            total_distance += path_len_pickup

            # 2. Distancia pickup → dropoff
            self.planner.replan(order.pickup_pos, order.dropoff_pos)
            path_len_delivery = len(self.planner._path) if self.planner._path else 999

            if path_len_delivery >= 999:
                return float("-inf")

            total_distance += path_len_delivery

            # 3. Estimar tiempo (considerando velocidad actual)
            speed = ai.calculate_effective_speed(game.city) if hasattr(game, 'city') else 3.0
            time_for_this_order = (path_len_pickup + path_len_delivery) / max(speed, 0.1)
            total_time_estimate += time_for_this_order

            # Actualizar posición para siguiente iteración
            current_pos = order.dropoff_pos

        # 4. Penalización por tiempo (verificar deadlines)
        time_penalty = 0.0
        for order in orders:
            time_limit = float(getattr(order, 'time_limit', 600.0))
            if total_time_estimate > time_limit * 0.8:  # Si va a llegar con poco margen
                time_penalty += 100

        # 5. Bonus por prioridad
        priority_bonus = sum(o.priority * 50 for o in orders)

        # Score final
        value = (
                total_payout
                + priority_bonus
                - (total_distance * 0.5)  # Costo por distancia
                - time_penalty
        )

        return value

    def _climate_changed_significantly(self, game) -> bool:
        """Detecta cambios drásticos de clima que requieren replanificación"""
        if not hasattr(game, 'weather_system') or not game.weather_system:
            return False

        try:
            current_mult = game.weather_system._get_interpolated_speed_multiplier()
            prev_mult = self.last_climate_mult
            self.last_climate_mult = current_mult

            # Si el cambio es mayor a 15%, replanificar
            return abs(current_mult - prev_mult) > 0.15
        except Exception:
            return False