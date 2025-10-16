import arcade
from enum import Enum

class GameState(Enum):
    MAIN_MENU = "main_menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    LOADING = "loading"
    SETTINGS = "settings"


class GameStateManager:

    def __init__(self, game_instance):
        self.settings_menu = None
        self.game = game_instance
        self.current_state = GameState.MAIN_MENU
        self.previous_state = None
        self.main_menu = None
        self.pause_menu = None
        self.settings_menu = None

    def change_state(self, new_state: GameState):
        print(f"Cambiando estado: {self.current_state.value} -> {new_state.value}")

        self.previous_state = self.current_state
        self.current_state = new_state

        # Ejecutar transiciones específicas
        if new_state == GameState.MAIN_MENU:
            self._show_main_menu()
        elif new_state == GameState.PLAYING:
            self._resume_game()
        elif new_state == GameState.PAUSED:
            self._show_pause_menu()
        elif new_state == GameState.GAME_OVER:
            self._show_game_over()
        elif new_state == GameState.SETTINGS:
            self._show_settings()

    def _show_settings(self):
        if not self.settings_menu:
            from game.settings import SettingsMenu
            self.settings_menu = SettingsMenu(self.game)
        print("Menú de settings inicializado")

    def _show_main_menu(self):
        #Lazy Import  para evitar ciclo de imports
        if not self.main_menu:
            from game.ui.menus.main_menu import MainMenu
            self.main_menu = MainMenu(self.game)

    def _resume_game(self):
        pass

    def _show_pause_menu(self):
        # Lazy Import  para evitar ciclo de imports
        if not self.pause_menu:
            from game.ui.menus.pause_menu import PauseMenu
            self.pause_menu = PauseMenu(self.game)

    def _show_game_over(self):
        pass

    def is_game_active(self) -> bool:
        return self.current_state == GameState.PLAYING

    def is_game_paused(self) -> bool:
        return self.current_state == GameState.PAUSED