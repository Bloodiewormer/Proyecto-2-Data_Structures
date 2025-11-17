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

        # NUEVO: Sistema de descanso variable
        import random
        self.stamina_awareness = random.uniform(0.2, 0.6)
        self.rest_start_threshold = random.randint(10, 30)  # Cuándo empieza a descansar
        self.rest_target = random.randint(50, 80)  # Cuánta stamina recuperar
        self.is_resting = False

        if self.debug:
            print(f"[EASY] Personalidad stamina: rest_at={self.rest_start_threshold}, "
                  f"target={self.rest_target}, awareness={self.stamina_awareness:.2f}")

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # Debug periódico
        if self.debug and int(now) % 3 == 0 and int(now) != getattr(self, '_last_debug_time', -1):
            self._last_debug_time = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            rest_status = "💤" if self.is_resting else ""
            print(f"[EASY] {rest_status} t={int(now)}s Pos=({ai.x:.1f},{ai.y:.1f}) "
                  f"Stamina={ai.stamina:.1f} Pedido={order_str} $={ai.earnings:.0f}")

        import random

        # NUEVO: Sistema de descanso completo
        if self.is_resting:
            # Está descansando, verificar si ya recuperó suficiente
            if ai.stamina >= self.rest_target:
                self.is_resting = False
                if self.debug:
                    print(f"[EASY] ✅ Descanso completo! {ai.stamina:.1f}/{self.rest_target}")
            else:
                # Seguir descansando
                if self.debug and int(now * 2) % 5 == 0:  # Debug cada 2.5s
                    print(f"[EASY] 💤 Descansando... {ai.stamina:.1f}/{self.rest_target}")
                ai.current_target = None
                return (0, 0)
        else:
            # No está descansando, verificar si debe empezar
            if ai.stamina < self.rest_start_threshold:
                # A veces ignora la stamina baja (torpe)
                if random.random() < self.stamina_awareness:
                    self.is_resting = True
                    if self.debug:
                        print(f"[EASY] 💤 Empezando descanso (stamina={ai.stamina:.1f}, "
                              f"objetivo={self.rest_target})")
                    ai.current_target = None
                    return (0, 0)
                else:
                    # Imprudente: sigue moviéndose con stamina baja
                    if self.debug and not hasattr(self, '_imprudent_logged'):
                        print(f"[EASY] 🤪 Ignorando stamina baja ({ai.stamina:.1f}) - imprudente")
                        self._imprudent_logged = True
            elif ai.stamina > self.rest_start_threshold + 10:
                if hasattr(self, '_imprudent_logged'):
                    delattr(self, '_imprudent_logged')

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

            # A veces acepta pedidos con stamina baja (torpe)
            stamina_ok = ai.stamina > 40 or random.random() > 0.5

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
                    print(f"[EASY] Rechazó pedido (stamina={ai.stamina:.1f})")
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

        # 3. Movimiento aleatorio SOLO si hay target Y no está descansando
        if ai.current_target and not self.is_resting:
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

        # NUEVO: Sistema adaptativo de descanso
        self.stamina_strategy = "balanced"
        self.is_resting = False
        self.rest_start_threshold = 20  # Cuándo empieza a descansar
        self.rest_target = 60  # Cuánta stamina recuperar
        self.last_stamina_decision = 0.0

    def _update_stamina_strategy(self, ai: "AIPlayer"):
        """Adapta umbrales de descanso según desempeño"""
        if ai.reputation > 80 and ai.earnings > 300:
            # Alto desempeño: descansa menos, más agresivo
            self.stamina_strategy = "aggressive"
            self.rest_start_threshold = 12
            self.rest_target = 45
        elif ai.reputation < 50:
            # Bajo desempeño: descansa más, conservador
            self.stamina_strategy = "conservative"
            self.rest_start_threshold = 35
            self.rest_target = 70
        else:
            # Balanceado
            self.stamina_strategy = "balanced"
            self.rest_start_threshold = 20
            self.rest_target = 60

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # Actualizar estrategia cada 10 segundos
        if now - self.last_stamina_decision > 10.0:
            self._update_stamina_strategy(ai)
            self.last_stamina_decision = now

            if self.debug:
                print(f"[MEDIUM] Estrategia: {self.stamina_strategy} "
                      f"(rest_at={self.rest_start_threshold}, target={self.rest_target})")

        if self.debug and int(now) % 5 == 0 and int(now) != getattr(self, '_last_debug_second', -1):
            self._last_debug_second = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            rest_status = "💤" if self.is_resting else ""
            print(f"[MEDIUM] {rest_status} Pos=({ai.x:.1f},{ai.y:.1f}), Stamina={ai.stamina:.1f}, "
                  f"Strategy={self.stamina_strategy}, Pedido={order_str}")

        import random

        # NUEVO: Sistema de descanso inteligente
        if self.is_resting:
            # Descansando, verificar si ya recuperó suficiente
            if ai.stamina >= self.rest_target:
                self.is_resting = False
                if self.debug:
                    print(f"[MEDIUM] ✅ Descanso completo! {ai.stamina:.1f}/{self.rest_target}")
            else:
                # Seguir descansando
                if self.debug and int(now * 2) % 5 == 0:
                    remaining = self.rest_target - ai.stamina
                    print(f"[MEDIUM] 💤 Descansando... {ai.stamina:.1f}/{self.rest_target} "
                          f"(faltan {remaining:.1f})")
                ai.current_target = None
                return (0, 0)
        else:
            # No está descansando, verificar si debe empezar
            if ai.stamina < self.rest_start_threshold:
                # Modo agresivo: a veces arriesga un poco más
                if self.stamina_strategy == "aggressive" and ai.inventory.orders:
                    if random.random() < 0.25:  # 25% de probabilidad de arriesgar
                        if self.debug:
                            print(f"[MEDIUM] ⚠️  Arriesgando con stamina baja ({ai.stamina:.1f})")
                    else:
                        self.is_resting = True
                        if self.debug:
                            print(f"[MEDIUM] 💤 Empezando descanso ({self.stamina_strategy})")
                        ai.current_target = None
                        return (0, 0)
                else:
                    # Otros modos: descansa siempre
                    self.is_resting = True
                    if self.debug:
                        print(f"[MEDIUM] 💤 Empezando descanso (stamina={ai.stamina:.1f}, "
                              f"objetivo={self.rest_target})")
                    ai.current_target = None
                    return (0, 0)

        # 1. Si tiene pedido activo
        if ai.inventory.orders:
            order = ai.inventory.orders[0]

            # Evaluar cambio de pedido (NO cancelar por stamina)
            if (now - self.last_evaluation > self.evaluation_interval and
                    order.priority == 0 and
                    game.pending_orders):

                best_alt = self._find_best_order(ai, game.pending_orders, game)

                if best_alt:
                    current_score = self._score_order(ai, order, game)
                    alt_score = self._score_order(ai, best_alt, game)

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

            if ai.current_target and not self.is_resting:
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

                    if not self.is_resting:
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
        """Filtros dinámicos - NO bloquear por stamina baja si está descansando"""
        if not orders:
            return None

        # Si está descansando, no aceptar nuevos pedidos
        if self.is_resting:
            return None

        # Umbral mínimo según estrategia
        min_stamina = {
            "aggressive": 15,
            "balanced": 30,
            "conservative": 45
        }.get(self.stamina_strategy, 30)

        if ai.stamina < min_stamina:
            if self.debug:
                print(f"[MEDIUM] Stamina {ai.stamina:.1f} < {min_stamina}, no acepta pedidos")
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
        self.planner: AStarPlanner = AStarPlanner(world)
        self.planned_sequence: List[str] = []
        self.last_replan: float = 0.0
        self.replan_interval: float = 10.0
        self.last_climate_mult: float = 1.0
        self.debug: bool = getattr(world, 'debug', False)

        # Sistema predictivo de descanso - AUMENTADO
        self.stamina_reserve: int = 20
        self.rest_start_threshold: int = 35  # Antes: 25 - descansa antes
        self.rest_target: int = 80  # Antes: 70 - recupera más
        self.optimal_stamina_range: Tuple[int, int] = (50, 90)  # Antes: (40, 85)
        self.is_resting: bool = False

    def _predict_stamina_cost(self, ai: "AIPlayer", distance: float) -> float:
        """Predice cuánta stamina costará recorrer una distancia"""
        base_cost = distance * 1.2

        if ai.total_weight > 3:
            base_cost *= (1.0 + (ai.total_weight - 3) * 0.1)

        if hasattr(self.world, 'weather_system') and self.world.weather_system:
            try:
                speed_mult = self.world.weather_system._get_interpolated_speed_multiplier()
                if speed_mult < 1.0:
                    base_cost *= (1.5 - speed_mult * 0.5)
            except Exception:
                pass

        return base_cost

    def _calculate_rest_target(self, ai: "AIPlayer", upcoming_task_cost: float = 0) -> int:
        """Calcula cuánta stamina debe recuperar según la tarea próxima"""
        if upcoming_task_cost > 0:
            # Recuperar suficiente para la tarea + margen generoso
            target = int(upcoming_task_cost * 1.3 + self.stamina_reserve)  # Antes: + 10
            return min(target, 95)  # Antes: optimal_range[1]
        else:
            # Sin tarea específica, recuperar bastante
            return 75  # Antes: optimal_range[0] (50)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        # Debug periódico
        if self.debug and int(now) % 5 == 0 and int(now) != getattr(self, '_last_debug_second', -1):
            self._last_debug_second = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            rest_status = "[REST]" if self.is_resting else ""
            print(f"[HARD] {rest_status} t={int(now)}s Pos=({ai.x:.1f},{ai.y:.1f}) "
                  f"Stamina={ai.stamina:.1f} Pedido={order_str} Earnings=${ai.earnings:.0f}")

        # Sistema de descanso predictivo
        upcoming_distance = 0
        if ai.current_target:
            upcoming_distance = abs(ai.x - ai.current_target[0]) + abs(ai.y - ai.current_target[1])

        predicted_cost = self._predict_stamina_cost(ai, upcoming_distance)

        if self.is_resting:
            rest_target = self._calculate_rest_target(ai, predicted_cost)

            if ai.stamina >= rest_target:
                self.is_resting = False
                if self.debug:
                    print(f"[HARD] Descanso completo: {ai.stamina:.1f}/{rest_target}")
            else:
                if self.debug and int(now * 2) % 5 == 0:
                    remaining = rest_target - ai.stamina
                    eta = remaining / 5.0
                    print(f"[HARD] Descansando... {ai.stamina:.1f}/{rest_target} (ETA: {eta:.1f}s)")
                ai.current_target = None
                self.planner._path = []
                self.planner._goal = None
                return (0, 0)
        else:
            should_rest = False

            if ai.stamina < self.rest_start_threshold:
                should_rest = True
                reason = f"stamina baja ({ai.stamina:.1f})"

            elif ai.inventory.orders and predicted_cost > 0:
                min_needed = predicted_cost * 0.8 + self.stamina_reserve
                if ai.stamina < min_needed:
                    should_rest = True
                    reason = f"insuficiente para pedido (necesita {min_needed:.1f})"

            elif not ai.inventory.orders and ai.stamina < self.optimal_stamina_range[0]:
                should_rest = True
                reason = f"bajo rango optimo ({ai.stamina:.1f} < {self.optimal_stamina_range[0]})"

            if should_rest:
                self.is_resting = True
                rest_target = self._calculate_rest_target(ai, predicted_cost)
                if self.debug:
                    print(f"[HARD] Empezando descanso ({reason}), objetivo={rest_target}")
                ai.current_target = None
                self.planner._path = []
                self.planner._goal = None
                return (0, 0)

        # Detectar si necesita replanificar
        climate_changed = self._climate_changed_significantly(game)
        time_to_replan = (now - self.last_replan) > self.replan_interval

        if (time_to_replan or climate_changed) and not ai.inventory.orders and not self.is_resting:
            if self.debug:
                print(f"[HARD] Replanificando...")
            self._plan_order_sequence(ai, game)
            self.last_replan = now

        # Si tiene pedido activo, usar A* para navegar
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos

            if ai.current_target != target:
                ai.current_target = target
                self.planner.set_goal(target)
                if self.debug:
                    print(f"[HARD] Nuevo target: {target} para {order.id[:8]}")

            if not self.is_resting:
                return self.planner.next_step(ai)
            else:
                return (0, 0)

        # Si no tiene pedido pero hay secuencia planeada, tomar el siguiente
        if self.planned_sequence and game.pending_orders and not self.is_resting:
            next_id = self.planned_sequence[0]
            order = next((o for o in game.pending_orders if o.id == next_id), None)

            if order:
                if self._is_order_viable(ai, order):
                    if ai.try_accept_order_with_delay(order, now):
                        order.start_timer(now)
                        order.status = "in_progress"
                        game.pending_orders.remove(order)

                        if hasattr(game.orders_manager, 'pending_orders'):
                            game.orders_manager.pending_orders = game.pending_orders

                        self.planned_sequence.pop(0)
                        ai.current_target = order.pickup_pos
                        self.planner.set_goal(order.pickup_pos)

                        if self.debug:
                            print(f"[HARD] Tomo pedido planeado {order.id[:8]}")

                        return self.planner.next_step(ai)
                else:
                    self.planned_sequence.clear()

        # Si no hay secuencia, planificar una nueva
        if not ai.inventory.orders and game.pending_orders and not self.is_resting:
            self._plan_order_sequence(ai, game)

        # CRITICO: Sin nada que hacer, limpiar y quedarse quieto
        ai.current_target = None
        self.planner._path = []
        self.planner._goal = None
        return (0, 0)

    def _is_order_viable(self, ai: "AIPlayer", order) -> bool:
        """Verifica si un pedido sigue siendo viable con predicción de stamina"""
        new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
        if new_weight > ai.inventory.max_weight:
            return False

        if self.is_resting:
            return False

        dist_to_pickup = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])
        dist_delivery = abs(order.pickup_pos[0] - order.dropoff_pos[0]) + abs(
            order.pickup_pos[1] - order.dropoff_pos[1])
        total_distance = dist_to_pickup + dist_delivery

        predicted_cost = self._predict_stamina_cost(ai, total_distance)

        # Requiere 70% del costo + reserva (antes: 60%)
        min_stamina_needed = predicted_cost * 0.7 + self.stamina_reserve

        if ai.stamina < min_stamina_needed:
            if self.debug:
                print(f"[HARD] Pedido {order.id[:8]} rechazado: stamina={ai.stamina:.1f}, "
                      f"min_necesario={min_stamina_needed:.1f} (costo={predicted_cost:.1f})")
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

        candidates = sorted(
            game.pending_orders[:8],
            key=lambda o: abs(ai.x - o.pickup_pos[0]) + abs(ai.y - o.pickup_pos[1])
        )[:5]

        best_sequence = []
        best_value = float("-inf")

        for o1 in candidates:
            if not self._is_order_viable(ai, o1):
                continue

            value = self._evaluate_sequence(ai, [o1], game)
            if value > best_value:
                best_sequence = [o1.id]
                best_value = value

        if len(candidates) >= 2:
            for i, o1 in enumerate(candidates):
                if not self._is_order_viable(ai, o1):
                    continue

                for o2 in candidates[i + 1:]:
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

        self.planner._path = []
        self.planner._goal = None

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
            self.planner.replan(current_pos, order.pickup_pos)
            path_len_pickup = len(self.planner._path) if self.planner._path else 999

            if path_len_pickup >= 999:
                return float("-inf")

            total_distance += path_len_pickup

            self.planner.replan(order.pickup_pos, order.dropoff_pos)
            path_len_delivery = len(self.planner._path) if self.planner._path else 999

            if path_len_delivery >= 999:
                return float("-inf")

            total_distance += path_len_delivery

            speed = ai.calculate_effective_speed(game.city) if hasattr(game, 'city') else 3.0
            time_for_this_order = (path_len_pickup + path_len_delivery) / max(speed, 0.1)
            total_time_estimate += time_for_this_order

            current_pos = order.dropoff_pos

        predicted_stamina_cost = self._predict_stamina_cost(ai, total_distance)

        time_penalty = 0.0
        stamina_penalty = 0.0

        for order in orders:
            time_limit = float(getattr(order, 'time_limit', 600.0))
            if total_time_estimate > time_limit * 0.8:
                time_penalty += 100

        stamina_after = ai.stamina - predicted_stamina_cost
        if stamina_after < 0:
            stamina_penalty = abs(stamina_after) * 5
        elif stamina_after < self.stamina_reserve:
            stamina_penalty = (self.stamina_reserve - stamina_after) * 2

        priority_bonus = sum(o.priority * 50 for o in orders)

        value = (
                total_payout
                + priority_bonus
                - (total_distance * 0.5)
                - time_penalty
                - stamina_penalty
        )

        if self.debug:
            print(f"[HARD] Secuencia evaluada: dist={total_distance:.0f}, "
                  f"stamina_cost={predicted_stamina_cost:.1f}, value={value:.1f}")

        return value

    def _climate_changed_significantly(self, game) -> bool:
        """Detecta cambios drásticos de clima que requieren replanificación"""
        if not hasattr(game, 'weather_system') or not game.weather_system:
            return False

        try:
            current_mult = game.weather_system._get_interpolated_speed_multiplier()
            prev_mult = self.last_climate_mult
            self.last_climate_mult = current_mult

            return abs(current_mult - prev_mult) > 0.15
        except Exception:
            return False