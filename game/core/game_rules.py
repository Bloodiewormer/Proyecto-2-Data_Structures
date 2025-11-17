from dataclasses import dataclass

@dataclass
class GameRulesConfig:
    goal_earnings: float
    time_limit: float

class GameRules:
    """
    Reglas de fin de juego y chequeos por frame.
    Encapsula la lógica que antes estaba en _check_game_end_conditions.
    """
    def __init__(self, get_config_callable):
        """
        get_config_callable: función/callable sin argumentos que retorna GameRulesConfig
        para leer valores actuales desde app_config o el juego.
        """
        self._get_cfg = get_config_callable
        self._ai_victory_triggered = False  # Nuevo flag

    def _check_ai_monopoly(self, game):
        """
        Determina si alguna IA ha COMPLETADO todos los pedidos del juego.
        Condiciones para victoria de IA:
        - No hay pending_orders disponibles.
        - El jugador no tiene pedidos activos.
        - Existe una IA que ha ENTREGADO (delivered) todos sus pedidos.
        - La IA tiene al menos 1 entrega completada.
        Retorna la IA ganadora o None.
        """
        try:
            if self._ai_victory_triggered:
                return None

            # Validaciones base
            if not getattr(game, "ai_players", None):
                return None

            # CRÍTICO: Solo verificar monopolio si NO hay pedidos pendientes
            if game.pending_orders:
                return None

            # CRÍTICO: Solo verificar si el jugador NO tiene pedidos activos
            if getattr(game.player, "inventory", None) and game.player.inventory.orders:
                return None

            # Buscar IA ganadora: debe tener todos sus pedidos ENTREGADOS y al menos 1 entrega
            for ai in game.ai_players:
                inv = getattr(ai, "inventory", None)

                # La IA ganadora NO debe tener pedidos activos
                if inv and inv.orders:
                    continue


                deliveries = getattr(ai, "deliveries_completed", 0)
                if deliveries >= 1:
                    # Esta IA completó sus entregas y no quedan pedidos disponibles
                    return ai

            return None
        except Exception as e:
            if getattr(game, 'debug', False):
                print(f"[GameRules] Error en _check_ai_monopoly: {e}")
            return None

    def check_and_handle(self, game) -> None:
        """
        Chequea condiciones y, si corresponde, invoca game._end_game(...)
        Mantiene exactamente el mismo comportamiento previo + condición de victoria IA.
        """
        if not getattr(game, "player", None):
            return

        # 1. Tiempo agotado
        if game.time_remaining <= 0:
            game._end_game(False, "¡Tiempo agotado!")
            return

        # 2. Reputación crítica
        if game.player.is_reputation_critical():
            game._end_game(False, "¡Reputación muy baja!")
            return

        # 3. Victoria por monopolio de IA (antes de la meta de ganancias del jugador)
        ai_winner = self._check_ai_monopoly(game)
        if ai_winner:
            self._ai_victory_triggered = True
            msg = f"La IA (dificultad: {getattr(ai_winner, 'difficulty', 'desconocida')}) recogió todos los pedidos. ¡Has perdido!"
            # Marcamos derrota del jugador
            game._end_game(False, msg)
            return

        # 4. Meta de ganancias del jugador
        cfg = self._get_cfg()
        goal_earnings = float(cfg.goal_earnings)
        if game.player.earnings >= goal_earnings:
            time_bonus = max(0, game.time_remaining / max(1e-9, cfg.time_limit))
            bonus_message = f"¡Victoria! Bonus de tiempo: +{time_bonus * 100:.0f}%"
            game._end_game(True, bonus_message)
            return