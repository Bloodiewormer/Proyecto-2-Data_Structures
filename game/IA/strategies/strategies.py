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
        self.policy = RandomChoicePolicy(world, bias=0.35)
        self.current_order_id = None
        self.debug = getattr(world, 'debug', False)

        # NUEVO: Personalidad aleatoria de stamina
        import random
        self.stamina_awareness = random.uniform(0.2, 0.6)  # Qué tan consciente es de su stamina (20%-60%)
        self.panic_threshold = random.randint(5, 25)  # Cuándo entra en pánico (5-25)
        self.rest_threshold = random.randint(15, 40)  # Cuándo considera descansar (30-60)

        if self.debug:
            print(f"[EASY] Personalidad: awareness={self.stamina_awareness:.2f}, "
                  f"panic={self.panic_threshold}, rest={self.rest_threshold}")

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # Debug periódico
        if self.debug and int(now) % 3 == 0 and int(now) != getattr(self, '_last_debug_time', -1):
            self._last_debug_time = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            print(f"[EASY] 📊 t={int(now)}s Pos=({ai.x:.1f},{ai.y:.1f}) Stamina={ai.stamina:.1f} "
                  f"Pedido={order_str} $={ai.earnings:.0f}")

        # NUEVO: Sistema de decisiones torpe y variable
        import random

        # Pánico: Si stamina MUY baja, entrar en pánico (pero a veces lo ignora)
        if ai.stamina < self.panic_threshold:
            # 70% de probabilidad de entrar en pánico
            if random.random() < 0.7:
                if self.debug and not hasattr(self, '_panic_logged'):
                    print(f"[EASY] 😰 ¡PÁNICO! Stamina={ai.stamina:.1f} (umbral={self.panic_threshold})")
                    self._panic_logged = True
                ai.current_target = None
                return (0, 0)
            else:
                # 30% del tiempo ignora el pánico y sigue (torpe)
                if self.debug:
                    print(f"[EASY] 🤪 Ignorando stamina baja={ai.stamina:.1f} (imprudente)")
        elif ai.stamina > self.panic_threshold + 10:
            if hasattr(self, '_panic_logged'):
                delattr(self, '_panic_logged')

        # Descanso: Considera descansar cuando stamina está "baja" (pero no siempre)
        if ai.stamina < self.rest_threshold and not ai.inventory.orders:
            # Probabilidad de descansar basada en awareness
            if random.random() < self.stamina_awareness:
                if self.debug:
                    print(f"[EASY] 💤 Decidió descansar (stamina={ai.stamina:.1f})")
                ai.current_target = None
                return (0, 0)
            # Si no, ignora y busca pedidos (imprudente)

        # 1. Si no tiene pedido, tomar el primero disponible
        if not ai.inventory.orders and game.pending_orders:
            order = game.pending_orders[0]

            # Verificar capacidad
            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                if self.debug:
                    print(f"[EASY] Pedido {order.id[:8]} muy pesado")
                ai.current_target = None
                return (0, 0)

            # A veces acepta pedidos incluso con stamina baja (torpe)
            stamina_ok = ai.stamina > 25 or random.random() > 0.6  # 40% ignora stamina baja

            if stamina_ok:
                if ai.try_accept_order_with_delay(order, now):
                    order.start_timer(now)
                    order.status = "in_progress"
                    game.pending_orders.remove(order)

                    if hasattr(game.orders_manager, 'pending_orders'):
                        game.orders_manager.pending_orders = game.pending_orders

                    self.current_order_id = order.id
                    ai.current_target = order.pickup_pos

                    if self.debug:
                        print(f"[EASY] Aceptó {order.id[:8]} (stamina={ai.stamina:.1f})")
            else:
                if self.debug:
                    print(f"[EASY] Rechazó pedido por stamina baja")
                ai.current_target = None
                return (0, 0)

        # 2. Actualizar target según estado del pedido
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            if order.status == "picked_up":
                ai.current_target = order.dropoff_pos
            else:
                ai.current_target = order.pickup_pos
        else:
            ai.current_target = None

        # 3. Movimiento aleatorio SOLO si hay target
        if ai.current_target:
            return self.policy.decide_step(ai)

        return (0, 0)


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

        # NUEVO: Sistema adaptativo de stamina
        self.stamina_strategy = "balanced"  # balanced, aggressive, conservative
        self.critical_stamina = 10
        self.low_stamina = 25
        self.safe_stamina = 50
        self.last_stamina_decision = 0.0

    def _update_stamina_strategy(self, ai: "AIPlayer"):
        """
        Adapta la estrategia de stamina según el estado del juego.
        """
        # Si tiene buen desempeño (alta reputación + ganancias), ser más agresivo
        if ai.reputation > 80 and ai.earnings > 300:
            self.stamina_strategy = "aggressive"
            self.critical_stamina = 8
            self.low_stamina = 18
        # Si está mal (baja reputación), ser conservador
        elif ai.reputation < 50:
            self.stamina_strategy = "conservative"
            self.critical_stamina = 15
            self.low_stamina = 35
        else:
            self.stamina_strategy = "balanced"
            self.critical_stamina = 10
            self.low_stamina = 25

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # Actualizar estrategia cada 10 segundos
        if now - self.last_stamina_decision > 10.0:
            self._update_stamina_strategy(ai)
            self.last_stamina_decision = now

            if self.debug:
                print(f"[MEDIUM] Estrategia stamina: {self.stamina_strategy} "
                      f"(crit={self.critical_stamina}, low={self.low_stamina})")

        if self.debug and int(now) % 5 == 0 and int(now) != getattr(self, '_last_debug_second', -1):
            self._last_debug_second = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            print(f"[MEDIUM] 📊 Pos=({ai.x:.1f},{ai.y:.1f}), Stamina={ai.stamina:.1f}, "
                  f"Strategy={self.stamina_strategy}, Pedido={order_str}")

        # NUEVO: Sistema de decisiones adaptativo
        import random

        # Crítico: Descansar si stamina está por debajo del umbral crítico
        if ai.stamina < self.critical_stamina:
            # En modo agresivo, a veces arriesga un poco más
            if self.stamina_strategy == "aggressive" and ai.inventory.orders and random.random() < 0.3:
                if self.debug:
                    print(f"[MEDIUM] ⚠️  Arriesgando con stamina={ai.stamina:.1f} (modo agresivo)")
                # Continuar pero lento
            else:
                if self.debug and not hasattr(self, '_resting_logged'):
                    print(f"[MEDIUM] 💤 Descansando (stamina crítica: {ai.stamina:.1f})")
                    self._resting_logged = True
                ai.current_target = None
                return (0, 0)
        elif ai.stamina > self.critical_stamina + 15:
            if hasattr(self, '_resting_logged'):
                delattr(self, '_resting_logged')

        # 1. Si tiene pedido activo
        if ai.inventory.orders:
            order = ai.inventory.orders[0]

            # Considerar cancelar pedidos según estrategia y stamina
            should_cancel = False

            if self.stamina_strategy == "conservative" and ai.stamina < self.low_stamina:
                # Conservador: cancela fácilmente
                should_cancel = order.priority == 0
                reason = "conservative + low stamina"
            elif self.stamina_strategy == "balanced" and ai.stamina < 15:
                # Balanceado: cancela solo si es muy bajo
                should_cancel = order.priority == 0 and random.random() < 0.6
                reason = "balanced + very low stamina"
            elif self.stamina_strategy == "aggressive" and ai.stamina < 8:
                # Agresivo: rara vez cancela
                should_cancel = order.priority == 0 and random.random() < 0.3
                reason = "aggressive + critical stamina"

            if should_cancel:
                if self.debug:
                    print(f"[MEDIUM] ⚠️  Cancelando {order.id[:8]} ({reason})")
                ai.cancel_order()
                ai.inventory.remove_order(order.id)
                game.orders_manager.mark_canceled(order.id)
                ai.current_target = None
                return (0, 0)

            # Evaluar cambio de pedido (solo si no está en modo conservador)
            if (self.stamina_strategy != "conservative" and
                    now - self.last_evaluation > self.evaluation_interval and
                    order.priority == 0 and
                    game.pending_orders):

                best_alt = self._find_best_order(ai, game.pending_orders, game)

                if best_alt:
                    current_score = self._score_order(ai, order, game)
                    alt_score = self._score_order(ai, best_alt, game)

                    # Umbral de cambio según estrategia
                    threshold = 1.5 if self.stamina_strategy == "conservative" else 1.3

                    if alt_score > current_score * threshold:
                        if self.debug:
                            print(f"[MEDIUM] Cambiando {order.id[:8]} por {best_alt.id[:8]}")

                        ai.cancel_order()
                        ai.inventory.remove_order(order.id)
                        game.orders_manager.mark_canceled(order.id)

                        if ai.try_accept_order_with_delay(best_alt, now):
                            best_alt.start_timer(now)
                            best_alt.status = "in_progress"
                            game.pending_orders.remove(best_alt)
                            if hasattr(game.orders_manager, 'pending_orders'):
                                game.orders_manager.pending_orders = game.pending_orders
                            order = best_alt

                self.last_evaluation = now

            # Actualizar target
            ai.current_target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos

            if ai.current_target:
                return self.policy.decide_step(ai)
            return (0, 0)

        # 2. Si no tiene pedido
        else:
            best = self._find_best_order(ai, game.pending_orders, game)

            if best:
                if ai.try_accept_order_with_delay(best, now):
                    best.start_timer(now)
                    best.status = "in_progress"
                    game.pending_orders.remove(best)

                    if hasattr(game.orders_manager, 'pending_orders'):
                        game.orders_manager.pending_orders = game.pending_orders

                    ai.current_target = best.pickup_pos

                    if self.debug:
                        print(f"[MEDIUM] Aceptó {best.id[:8]} (score={self._score_order(ai, best, game):.1f})")

                    return self.policy.decide_step(ai)

            ai.current_target = None
            return (0, 0)

    def _score_order(self, ai: "AIPlayer", order, game) -> float:
        """Score con penalización dinámica de stamina"""
        dist_to_pickup = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])

        weather_penalty = 0.0
        if hasattr(game, 'weather_system') and game.weather_system:
            try:
                speed_mult = game.weather_system._get_interpolated_speed_multiplier()
                weather_penalty = (1.0 - speed_mult) * 100
            except Exception:
                pass

        # Penalización de stamina según estrategia
        stamina_penalty = 0.0
        if self.stamina_strategy == "aggressive":
            # Agresivo: poca penalización
            if ai.stamina < 30:
                stamina_penalty = (30 - ai.stamina) * 0.8
        elif self.stamina_strategy == "conservative":
            # Conservador: alta penalización
            if ai.stamina < 60:
                stamina_penalty = (60 - ai.stamina) * 2.5
        else:  # balanced
            if ai.stamina < 50:
                stamina_penalty = (50 - ai.stamina) * 1.5

        priority_bonus = order.priority * 50

        score = (
                float(getattr(order, 'payout', getattr(order, 'payment', 0.0)))
                + priority_bonus
                - (dist_to_pickup * 0.5)
                - (weather_penalty * 0.3)
                - (stamina_penalty * 0.4)
        )

        return score

    def _find_best_order(self, ai: "AIPlayer", orders, game) -> Optional[Any]:
        """Filtros dinámicos según estrategia"""
        if not orders:
            return None

        # Umbral mínimo según estrategia
        min_stamina = {
            "aggressive": 12,
            "balanced": 25,
            "conservative": 40
        }.get(self.stamina_strategy, 25)

        if ai.stamina < min_stamina:
            if self.debug:
                print(f"[MEDIUM] Stamina {ai.stamina:.1f} < {min_stamina} ({self.stamina_strategy}), esperando")
            return None

        best_order = None
        best_score = float("-inf")

        for order in orders:
            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                continue

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
        self.planner: AStarPlanner = AStarPlanner(world)  # ← Agregar type hint aquí
        self.planned_sequence: List[str] = []
        self.last_replan: float = 0.0
        self.replan_interval: float = 10.0
        self.last_climate_mult: float = 1.0
        self.debug: bool = getattr(world, 'debug', False)

        # NUEVO: Sistema predictivo de stamina
        self.stamina_reserve: int = 30
        self.optimal_stamina_range: Tuple[int, int] = (45, 85)
        self.stamina_prediction_window: float = 20.0

    def _find_best_order(self, ai: "AIPlayer", orders, game) -> Optional[Any]:
        """Filtros dinámicos según estrategia"""
        if not orders:
            return None

        # Umbral mínimo según estrategia
        min_stamina = {
            "aggressive": 12,
            "balanced": 25,
            "conservative": 40
        }.get(self.stamina_strategy, 25)

        if ai.stamina < min_stamina:
            if self.debug:
                print(f"[MEDIUM] Stamina {ai.stamina:.1f} < {min_stamina} ({self.stamina_strategy}), esperando")
            return None

        best_order = None
        best_score = float("-inf")

        for order in orders:
            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                continue

            score = self._score_order(ai, order, game)

            if score > best_score:
                best_score = score
                best_order = order

        return best_order

    def _is_order_viable(self, ai: "AIPlayer", order) -> bool:
        """Verifica viabilidad con predicción de stamina"""
        # Peso
        new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
        if new_weight > ai.inventory.max_weight:
            return False

        # Estimar distancia total (pickup + delivery)
        dist_to_pickup = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])
        dist_delivery = abs(order.pickup_pos[0] - order.dropoff_pos[0]) + abs(
            order.pickup_pos[1] - order.dropoff_pos[1])
        total_distance = dist_to_pickup + dist_delivery

        # Predecir costo de stamina
        predicted_cost = self._predict_stamina_cost(ai, total_distance)

        # Verificar que tenga suficiente stamina + reserva
        if ai.stamina < predicted_cost + self.stamina_reserve:
            if self.debug:
                print(f"[HARD] Pedido {order.id[:8]} rechazado: stamina={ai.stamina:.1f}, "
                      f"costo={predicted_cost:.1f}, reserva={self.stamina_reserve}")
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