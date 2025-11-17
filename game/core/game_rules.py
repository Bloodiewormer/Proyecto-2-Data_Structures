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
        Determina si alguna IA tiene TODOS los pedidos del juego (monopolio).
        Condiciones:
        - No hay pending_orders.
        - El jugador no tiene pedidos.
        - Existe una IA con al menos un pedido y todos sus pedidos están en estado 'picked_up' o 'delivered'.
        - Las demás IA (si hubiera más de una) no tienen pedidos.
        Retorna la IA ganadora o None.
        """
        try:
            if self._ai_victory_triggered:
                return None
            # Validaciones base
            if not getattr(game, "ai_players", None):
                return None
            if game.pending_orders:
                return None
            if getattr(game.player, "inventory", None) and game.player.inventory.orders:
                return None

            # Filtrar IAs candidatas
            candidates = []
            for ai in game.ai_players:
                inv = getattr(ai, "inventory", None)
                if not inv or not inv.orders:
                    continue
                # Todos los pedidos de la IA están al menos recogidos (picked_up) o ya entregados (delivered)
                if all(getattr(o, "status", "") in ("picked_up", "delivered") for o in inv.orders):
                    candidates.append(ai)

            if not candidates:
                return None

            # Verificar que ninguna otra IA tenga pedidos 'in_progress'
            for ai in game.ai_players:
                if ai not in candidates:
                    inv = getattr(ai, "inventory", None)
                    if inv and inv.orders:
                        # Otra IA también tiene pedidos → no monopolio claro
                        return None

            # Si hay exactamente una IA candidata con monopolio
            if len(candidates) == 1:
                return candidates[0]

            # Si hubiera más de una con todos recogidos, se puede escoger la primera para efecto de mensaje.
            return candidates[0] if candidates else None
        except Exception:
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