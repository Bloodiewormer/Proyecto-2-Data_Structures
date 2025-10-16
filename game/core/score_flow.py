from game.core.score_manager import ScoreManager
from game.ui.score_screen import ScoreScreen
from game.core.gamestate import GameState

class ScoreFlow:
    """
    Encapsula el cierre de partida, cálculo de score y despliegue de la ScoreScreen.
    """
    def __init__(self, files_conf: dict):
        self.files_conf = files_conf

    def end_game(self, game, victory: bool, message: str):
        # Notificación
        game.show_notification(f" {message}")

        try:
            # Usar el ScoreManager del juego si existe, sino crear uno local
            score_manager: ScoreManager = getattr(game, "score_manager", None) or ScoreManager(self.files_conf)

            entry = score_manager.calculate_score(
                game.player,
                game.time_remaining,
                game.time_limit,
                victory,
                getattr(game, "total_play_time", 0.0),
            )
            leaderboard = score_manager.add_score(entry)

            game.game_over_active = True
            game.score_screen = ScoreScreen(game, entry, leaderboard)

            game.state_manager.change_state(GameState.PAUSED)
            if getattr(game, 'audio_manager', None):
                game.audio_manager.pause_music()

        except Exception as e:
            print(f"Error generando score: {e}")
            game.return_to_main_menu()