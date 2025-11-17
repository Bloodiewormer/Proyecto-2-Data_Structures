from __future__ import annotations
from typing import Optional, Tuple

from game.IA.interfaces import StepPolicy, PathPlanner
from game.IA.policies.random_choice import RandomChoicePolicy
from game.IA.policies.greedy import GreedyPolicy
from game.IA.planner.astar import AStarPlanner


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
    Estrategia fácil: RandomChoicePolicy con sesgo a current_target si existe.
    También intenta aceptar el primer pedido disponible si no tiene ninguno,
    respetando el delay configurado en AIPlayer (try_accept_order_with_delay).
    """
    def __init__(self, world):
        self.world = world
        self.policy: StepPolicy = RandomChoicePolicy(world)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        # Tomar pedido si no tiene (pero respetando el delay)
        if not ai.inventory.orders and game.pending_orders:
            order = game.pending_orders[0]
            now = getattr(game, "total_play_time", None)
            if ai.try_accept_order_with_delay(order, now):
                # si realmente fue aceptado, remover de pending
                try:
                    game.pending_orders.remove(order)
                    if game.orders_manager:
                        game.orders_manager.pending_orders = game.pending_orders
                except Exception:
                    pass
                try:
                    if hasattr(order, 'start_timer'):
                        order.start_timer(game.total_play_time)
                except Exception:
                    pass
                ai.current_target = order.pickup_pos

        # Si tiene pedido, decidir target según estado
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            ai.current_target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos
        else:
            # Sin pedidos: target None y camina aleatorio
            ai.current_target = None

        # Paso discreto
        return self.policy.decide_step(ai)


class MediumStrategy(BaseStrategy):
    """
    Estrategia media: selección de pedido por heurística y movimiento Greedy.
    Usa try_accept_order_with_delay para respetar delays antes de aceptar.
    """
    def __init__(self, world, lookahead_depth: int = 2, climate_weight: float = 0.5):
        self.world = world
        self.policy: StepPolicy = GreedyPolicy(world, climate_weight=climate_weight, lookahead_depth=lookahead_depth)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        # Si ya tiene pedidos, seguirlos
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            ai.current_target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos
        else:
            # Elegir mejor pedido disponible (payout - distancia - clima)
            if game.pending_orders:
                alpha, beta, gamma = 1.0, 0.5, 0.3
                best, best_score = None, float("-inf")
                for order in game.pending_orders:
                    dist = abs(ai.x - order.pickup_pos[0]) + abs(ai.y - order.pickup_pos[1])
                    weather_penalty = 0.0
                    if game.weather_system:
                        try:
                            speed_mult = game.weather_system._get_interpolated_speed_multiplier()
                            weather_penalty = (1.0 - speed_mult) * 100
                        except Exception:
                            pass
                    score = alpha * float(getattr(order, "payout", getattr(order, "payment",
                                                                           0.0))) - beta * dist - gamma * weather_penalty
                    if score > best_score:
                        best, best_score = order, score

                if best:
                    now = getattr(game, "total_play_time", None)
                    if ai.try_accept_order_with_delay(best, now):
                        try:
                            game.pending_orders.remove(best)
                            if game.orders_manager:
                                game.orders_manager.pending_orders = game.pending_orders
                        except Exception:
                            pass
                        try:
                            if hasattr(best, 'start_timer'):
                                best.start_timer(game.total_play_time)
                        except Exception:
                            pass
                        ai.current_target = best.pickup_pos
            else:
                ai.current_target = None

        return self.policy.decide_step(ai)


class HardStrategy(BaseStrategy):
    """
    Estrategia difícil: planificación con A* (PathPlanner).
    Selecciona pedido considerando costo de rutas (aproximado) y usa planner para el step.
    """
    def __init__(self, world):
        self.world = world
        self.planner: PathPlanner = AStarPlanner(world)

    def decide(self, ai: "AIPlayer", game) -> Optional[Tuple[int, int]]:
        # Si ya tiene pedido, ir a pickup o dropoff
        if ai.inventory.orders:
            order = ai.inventory.orders[0]
            target = order.dropoff_pos if order.status == "picked_up" else order.pickup_pos
            ai.current_target = target
            self.planner.set_goal(target)
            return self.planner.next_step(ai)

        # Elegir pedido por costo de ruta (pickup + dropoff)
        if not game.pending_orders:
            ai.current_target = None
            self.planner.set_goal(None)
            return (0, 0)

        best_order, best_cost = None, float("inf")

        # Estimar costo con longitudes de A* (replan interno)
        for order in game.pending_orders:
            # set_goal para pickup y medir longitud explorada utilizando planner
            self.planner.set_goal(order.pickup_pos)
            step_pick = self.planner.next_step(ai)  # fuerza replan; no importa el step en sí
            len_pick = len(getattr(self.planner, "_path", [])) or 999

            # Simular tramo pickup->dropoff: replan desde pickup
            start_backup = (int(ai.x), int(ai.y))
            # replan directo para tramo siguiente
            self.planner.replan(order.pickup_pos, order.dropoff_pos)
            len_drop = len(getattr(self.planner, "_path", [])) or 999

            payout = float(getattr(order, "payout", getattr(order, "payment", 0.0)))
            cost = len_pick + len_drop - 0.1 * payout
            if cost < best_cost:
                best_cost, best_order = cost, order

            # restaurar estado de start del planner para siguientes iteraciones
            self.planner.replan(start_backup, order.pickup_pos)  # no crítico, solo para consistencia

        if best_order and ai.add_order_to_inventory(best_order):
            game.pending_orders.remove(best_order)
            if game.orders_manager:
                game.orders_manager.pending_orders = game.pending_orders
            if hasattr(best_order, 'start_timer'):
                best_order.start_timer(game.total_play_time)
            ai.current_target = best_order.pickup_pos
            self.planner.set_goal(ai.current_target)
            return self.planner.next_step(ai)

        return (0, 0)