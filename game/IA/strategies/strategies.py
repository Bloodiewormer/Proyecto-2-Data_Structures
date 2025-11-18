from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any
import random

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
        return not city.is_wall(x, y)
    except Exception:
        if x < 0 or y < 0 or x >= city.width or y >= city.height:
            return False
        return getattr(city, "tiles", [[]])[y][x] != "B"

def _nearest_door(city, gx: int, gy: int, max_expansion: int = 32) -> Optional[Tuple[int,int]]:
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
    cand = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = cx + dx, cy + dy
        if _is_walkable(city, nx, ny):
            cand.append((dx, dy, _manhattan((nx, ny), (tx, ty))))
    if not cand:
        return (0, 0)
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
    cand = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = cx + dx, cy + dy
        if _is_walkable(city, nx, ny):
            cand.append((dx, dy, _manhattan((nx, ny), (fromx, fromy))))
    if not cand:
        return (0, 0)
    cand.sort(key=lambda t: -t[2])
    return (cand[0][0], cand[0][1])


class BaseStrategy:
    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        raise NotImplementedError


class EasyStrategy(BaseStrategy):
    def __init__(self, world):
        self.world = world
        self.policy = RandomChoicePolicy(world, bias=0.35)
        self.current_order_id = None
        self.debug = getattr(world, 'debug', False)

        import random
        self.stamina_awareness = random.uniform(0.2, 0.6)
        self.rest_start_threshold = random.randint(10, 30)
        self.rest_target = random.randint(50, 80)
        self.is_resting = False

        if self.debug:
            print(f"[EASY] Personalidad stamina: rest_at={self.rest_start_threshold}, "
                  f"target={self.rest_target}, awareness={self.stamina_awareness:.2f}")

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        if self.debug and int(now) % 3 == 0 and int(now) != getattr(self, '_last_debug_time', -1):
            self._last_debug_time = int(now)
            order_str = ai.inventory.orders[0].id[:8] if ai.inventory.orders else "Sin pedido"
            rest_status = "💤" if self.is_resting else ""
            print(f"[EASY] {rest_status} t={int(now)}s Pos=({ai.x:.1f},{ai.y:.1f}) "
                  f"Stamina={ai.stamina:.1f} Pedido={order_str} $={ai.earnings:.0f}")

        import random

        if self.is_resting:
            if ai.stamina >= self.rest_target:
                self.is_resting = False
                if self.debug:
                    print(f"[EASY] ✅ Descanso completo! {ai.stamina:.1f}/{self.rest_target}")
            else:
                if self.debug and int(now * 2) % 5 == 0:
                    print(f"[EASY] 💤 Descansando... {ai.stamina:.1f}/{self.rest_target}")
                ai.current_target = None
                return (0, 0)
        else:
            if ai.stamina < self.rest_start_threshold:
                if random.random() < self.stamina_awareness:
                    self.is_resting = True
                    if self.debug:
                        print(f"[EASY] 💤 Empezando descanso (stamina={ai.stamina:.1f}, "
                              f"objetivo={self.rest_target})")
                    ai.current_target = None
                    return (0, 0)
                else:
                    if self.debug and not hasattr(self, '_imprudent_logged'):
                        print(f"[EASY] 🤪 Ignorando stamina baja ({ai.stamina:.1f}) - imprudente")
                        self._imprudent_logged = True
            elif ai.stamina > self.rest_start_threshold + 10:
                if hasattr(self, '_imprudent_logged'):
                    delattr(self, '_imprudent_logged')

        if not ai.inventory.orders and game.pending_orders:
            order = game.pending_orders[0]

            new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
            if new_weight > ai.inventory.max_weight:
                if self.debug:
                    print(f"[EASY] Pedido {order.id[:8]} muy pesado")
                ai.current_target = None
                return (0, 0)

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

        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            if order.status == "picked_up":
                ai.current_target = order.dropoff_pos
            else:
                ai.current_target = order.pickup_pos
        else:
            ai.current_target = None

        if ai.current_target and not self.is_resting:
            return self.policy.decide_step(ai)

        return (0, 0)


class MediumStrategy(BaseStrategy):
    def __init__(self, world, lookahead_depth: int = 2, climate_weight: float = 0.5):
        self.world = world
        self.policy = GreedyPolicy(world, climate_weight=climate_weight, lookahead_depth=lookahead_depth)
        self.last_evaluation = 0.0
        self.evaluation_interval = 5.0
        self.debug = getattr(world, 'debug', False)

        self.is_resting = False
        self.rest_start_threshold = 0
        self.rest_target = 40

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time

        prev_resting = getattr(self, "_prev_resting", False)
        if not self.is_resting:
            if ai.stamina <= 0 or not ai.can_move():
                self.is_resting = True
                if hasattr(ai, "enter_rest"):
                    ai.enter_rest(reset_timer=True)
                self._prev_resting = True

        if self.is_resting:
            if not ai.inventory.orders and game.pending_orders:
                best = self._find_best_order(ai, game.pending_orders, game)
                if best and ai.try_accept_order_with_delay(best, now):
                    best.start_timer(now)
                    best.status = "in_progress"
                    game.pending_orders.remove(best)
                    if hasattr(game.orders_manager, 'pending_orders'):
                        game.orders_manager.pending_orders = game.pending_orders
                    ai.current_target = best.pickup_pos
                    if self.debug:
                        print(f"[MEDIUM] Aceptó {best.id[:8]} (mientras descansa)")

            if ai.stamina >= self.rest_target:
                self.is_resting = False
            else:
                ai.current_target = ai.current_target
                self._prev_resting = True
                return (0, 0)

        if prev_resting and not self.is_resting:
            pass

        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            ai.current_target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos
            return self.policy.decide_step(ai)

        best = self._find_best_order(ai, game.pending_orders, game)
        if best and ai.try_accept_order_with_delay(best, now):
            best.start_timer(now)
            best.status = "in_progress"
            game.pending_orders.remove(best)
            if hasattr(game.orders_manager, 'pending_orders'):
                game.orders_manager.pending_orders = game.pending_orders
            ai.current_target = best.pickup_pos
            return self.policy.decide_step(ai)

        ai.current_target = None
        return (0, 0)

    def _score_order(self, ai: "AIPlayer", order, game) -> float:
        dist_to_pickup = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])

        weather_penalty = 0.0
        if hasattr(game, 'weather_system') and game.weather_system:
            try:
                speed_mult = game.weather_system._get_interpolated_speed_multiplier()
                weather_penalty = (1.0 - speed_mult) * 100
            except Exception:
                pass

        stamina_penalty = 0.0
        if ai.stamina < 20:
            stamina_penalty = (20 - ai.stamina) * 0.8

        priority_bonus = order.priority * 50

        score = (
            float(getattr(order, 'payout', getattr(order, 'payment', 0.0)))
            + priority_bonus
            - (dist_to_pickup * 0.5)
            - (weather_penalty * 0.3)
            - (stamina_penalty * 0.2)
        )
        return score

    def _find_best_order(self, ai: "AIPlayer", orders, game) -> Optional[Any]:
        if not orders:
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

    Ajuste: fuerza descanso en el mismo ciclo en que se rechaza por viabilidad,
    y acepta pedidos durante el descanso.
    """

    def __init__(self, world):
        self.world = world
        self.planner: AStarPlanner = AStarPlanner(world)
        self.planned_sequence: List[str] = []
        self.last_replan: float = 0.0
        self.replan_interval: float = 10.0
        self.last_climate_mult: float = 1.0
        self.debug: bool = getattr(world, 'debug', False)

        # Descanso
        self.stamina_reserve: int = 20
        self.rest_target: int = 55
        self.optimal_stamina_range: Tuple[int, int] = (50, 90)
        self.is_resting: bool = False

        # Control de descanso forzado
        self._last_forced_rest_time: float = -999.0
        self._forced_rest_interval: float = 4.0  # evita flapping
        self._pending_forced_rest_cost: Optional[float] = None

    def _predict_stamina_cost(self, ai: "AIPlayer", distance: float) -> float:
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
        if upcoming_task_cost > 0:
            target = int(upcoming_task_cost * 0.6 + self.stamina_reserve + 8)
            return max(40, min(target, 90))
        else:
            return 75

    def _force_rest(self, ai: "AIPlayer", now: float, reference_cost: float = 0.0):
        if (now - self._last_forced_rest_time) < self._forced_rest_interval:
            return
        self._last_forced_rest_time = now

        self.is_resting = True
        if hasattr(ai, "enter_rest"):
            ai.enter_rest(reset_timer=True)

        self.rest_target = self._calculate_rest_target(ai, reference_cost)
        if self.debug:
            print(f"[HARD]  Descanso forzado: objetivo={self.rest_target} (ref_cost={reference_cost:.1f})")

    def _is_order_viable(self, ai: "AIPlayer", order) -> bool:
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

        # Umbral menos estricto pero suficiente
        min_stamina_needed = predicted_cost * 0.6 + self.stamina_reserve

        if ai.stamina < min_stamina_needed:
            if self.debug:
                print(f"[HARD] Pedido {order.id[:8]} rechazado: stamina={ai.stamina:.1f}, "
                      f"min_necesario={min_stamina_needed:.1f} (costo={predicted_cost:.1f})")
            # Señal para forzar descanso en decide()
            self._pending_forced_rest_cost = predicted_cost
            return False

        return True

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        now = game.total_play_time
        prev_resting = getattr(self, "_prev_resting", False)

        # Si hubo rechazo recientemente, fuerza descanso aquí mismo
        if (not self.is_resting) and (self._pending_forced_rest_cost is not None):
            self._force_rest(ai, now, self._pending_forced_rest_cost)
            self._pending_forced_rest_cost = None

        # Entrada a descanso si está exhausto
        if not self.is_resting and (ai.stamina <= 0 or not ai.can_move()):
            self._force_rest(ai, now, 0.0)
            self._prev_resting = True

        # Mientras descansa: puede aceptar pedido, pero no moverse
        if self.is_resting:
            if not ai.inventory.orders and game.pending_orders:
                candidates = sorted(
                    game.pending_orders,
                    key=lambda o: abs(ai.x - o.pickup_pos[0]) + abs(ai.y - o.pickup_pos[1])
                )
                for cand in candidates:
                    new_weight = ai.inventory.current_weight + float(getattr(cand, 'weight', 0.0))
                    if new_weight > ai.inventory.max_weight:
                        continue
                    if ai.try_accept_order_with_delay(cand, now):
                        cand.start_timer(now)
                        cand.status = "in_progress"
                        game.pending_orders.remove(cand)
                        if hasattr(game.orders_manager, 'pending_orders'):
                            game.orders_manager.pending_orders = game.pending_orders
                        ai.current_target = cand.pickup_pos
                        self.planner.set_goal(cand.pickup_pos)
                        if self.debug:
                            print(f"[HARD] Aceptó {cand.id[:8]} (mientras descansa)")
                        break

            if ai.stamina >= self.rest_target:
                self.is_resting = False
            else:
                self._prev_resting = True
                return (0, 0)

        # Replan inmediato al salir del descanso
        if prev_resting and not self.is_resting:
            if ai.current_target and hasattr(self.planner, "plan"):
                try:
                    sx, sy = int(ai.x + 0.5), int(ai.y + 0.5)
                    tx, ty = int(ai.current_target[0]), int(ai.current_target[1])
                    self.planner.plan((sx, sy), (tx, ty))
                except Exception:
                    pass

        climate_changed = self._climate_changed_significantly(game)
        time_to_replan = (now - self.last_replan) > self.replan_interval

        if (time_to_replan or climate_changed) and not ai.inventory.orders and not self.is_resting:
            if self.debug:
                print(f"[HARD] Replanificando...")
            self._plan_order_sequence(ai, game)
            self.last_replan = now

        # Pedido activo: seguir con A*
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos

            if ai.current_target != target:
                ai.current_target = target
                self.planner.set_goal(target)
                if self.debug:
                    print(f"[HARD] Nuevo target: {target} para {order.id[:8]}")

            return self.planner.next_step(ai)

        # Sin pedido pero hay secuencia
        if self.planned_sequence and game.pending_orders and not self.is_resting:
            next_id = self.planned_sequence[0]
            order = next((o for o in game.pending_orders if o.id == next_id), None)

            if order:
                new_weight = ai.inventory.current_weight + float(getattr(order, 'weight', 0.0))
                if new_weight <= ai.inventory.max_weight:
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
                            print(f"[HARD] Tomó pedido planeado {order.id[:8]}")
                        return self.planner.next_step(ai)
                else:
                    self.planned_sequence.clear()

        # Sin nada, intentar planificar
        if not ai.inventory.orders and game.pending_orders and not self.is_resting:
            self._plan_order_sequence(ai, game)

        # Idle
        ai.current_target = None
        self.planner._path = []
        self.planner._goal = None
        return (0, 0)

    def _plan_order_sequence(self, ai: "AIPlayer", game):
        if not game.pending_orders:
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
                    if not self._is_order_viable(ai, o2):
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
        if not hasattr(game, 'weather_system') or not game.weather_system:
            return False

        try:
            current_mult = game.weather_system._get_interpolated_speed_multiplier()
            prev_mult = self.last_climate_mult
            self.last_climate_mult = current_mult

            return abs(current_mult - prev_mult) > 0.15
        except Exception:
            return False