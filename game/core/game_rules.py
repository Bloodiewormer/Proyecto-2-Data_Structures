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

    def check_and_handle(self, game) -> None:
        """
        Chequea condiciones y, si corresponde, invoca game._end_game(...)
        Mantiene exactamente el mismo comportamiento.
        """
        if not getattr(game, "player", None):
            return

        # Tiempo
        if game.time_remaining <= 0:
            game._end_game(False, "¡Tiempo agotado!")
            return

        # Reputación crítica
        if game.player.is_reputation_critical():
            game._end_game(False, "¡Reputación muy baja!")
            return

        # Meta de ganancias
        cfg = self._get_cfg()
        goal_earnings = float(cfg.goal_earnings)
        if game.player.earnings >= goal_earnings:
            time_bonus = max(0, game.time_remaining / max(1e-9, cfg.time_limit))
            bonus_message = f"¡Victoria! Bonus de tiempo: +{time_bonus * 100:.0f}%"
            game._end_game(True, bonus_message)
            return