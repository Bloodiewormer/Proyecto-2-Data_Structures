# file: game/gamestate.py
import arcade
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path


class GameState(Enum):
    """Estados posibles del juego"""
    MAIN_MENU = "main_menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    LOADING = "loading"
    SETTINGS = "settings"


class GameStateManager:
    """Administrador de estados del juego"""

    def __init__(self, game_instance):
        self.game = game_instance
        self.current_state = GameState.MAIN_MENU
        self.previous_state = None

        # Referencias a menús
        self.main_menu = None
        self.pause_menu = None

    def change_state(self, new_state: GameState):
        """Cambiar el estado del juego"""
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

    def _show_main_menu(self):
        """Mostrar menú principal"""
        if not self.main_menu:
            self.main_menu = MainMenu(self.game)

    def _resume_game(self):
        """Reanudar el juego"""
        # El juego ya está corriendo, solo cambiar estado
        pass

    def _show_pause_menu(self):
        """Mostrar menú de pausa"""
        if not self.pause_menu:
            self.pause_menu = PauseMenu(self.game)

    def _show_game_over(self):
        """Mostrar pantalla de game over"""
        # TODO: Implementar pantalla de game over
        pass

    def is_game_active(self) -> bool:
        """Verificar si el juego está activo (no en menú)"""
        return self.current_state == GameState.PLAYING

    def is_game_paused(self) -> bool:
        """Verificar si el juego está pausado"""
        return self.current_state == GameState.PAUSED


class MainMenu:
    """Menú principal del juego"""

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0
        self.options = ["Nuevo Juego", "Cargar Partida", "Configuración", "Salir"]

        # Verificar si existe una partida guardada
        self.has_saved_game = self._check_saved_game()

        # Si no hay partida guardada, deshabilitar "Cargar Partida"
        if not self.has_saved_game:
            self.disabled_options = [1]  # Índice de "Cargar Partida"
        else:
            self.disabled_options = []

    def _check_saved_game(self) -> bool:
        """Verificar si existe una partida guardada"""
        try:
            save_dir = Path(self.game.app_config.get("files", {}).get("save_directory", "saves"))
            save_file = save_dir / "savegame.json"
            return save_file.exists() and save_file.stat().st_size > 0
        except:
            return False

    def draw(self):
        """Dibujar el menú principal"""
        width = self.game.width
        height = self.game.height

        # Fondo degradado
        arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (15, 25, 45))
        arcade.draw_lrbt_rectangle_filled(0, width, 0, height // 3, (25, 35, 55))

        # Título principal
        arcade.draw_text(
            "COURIER QUEST",
            width // 2, height - 80,
            arcade.color.WHITE, 56,
            anchor_x="center", font_name="Kenney Future"
        )

        # Subtítulo
        arcade.draw_text(
            "Entrega. Explora. Sobrevive.",
            width // 2, height - 120,
            (200, 200, 255), 20,
            anchor_x="center"
        )

        # Opciones del menú
        menu_start_y = height // 2 + 80
        option_spacing = 50

        for i, option in enumerate(self.options):
            y_pos = menu_start_y - (i * option_spacing)

            # Determinar color de la opción
            is_selected = (i == self.selected_option)
            is_disabled = (i in self.disabled_options)

            if is_disabled:
                color = (100, 100, 100)  # Gris para deshabilitado
                text = f"  {option}"
            elif is_selected:
                color = (255, 255, 100)  # Amarillo para seleccionado
                text = f"> {option} <"
            else:
                color = arcade.color.WHITE
                text = f"  {option}"

            arcade.draw_text(
                text,
                width // 2, y_pos,
                color, 24,
                anchor_x="center"
            )

        # Información de partida guardada
        if self.has_saved_game and self.selected_option == 1:
            save_info = self._get_save_info()
            if save_info:
                info_y = menu_start_y - 250
                arcade.draw_text(
                    f"Última partida: {save_info}",
                    width // 2, info_y,
                    (180, 180, 255), 14,
                    anchor_x="center"
                )

        # Instrucciones
        arcade.draw_text(
            "↑/↓ - Navegar    ENTER - Seleccionar    ESC - Salir",
            width // 2, 40,
            (150, 150, 200), 16,
            anchor_x="center"
        )

    def _get_save_info(self) -> str:
        """Obtener información básica de la partida guardada"""
        try:
            from game.saveManager import SaveManager
            save_manager = SaveManager(self.game.app_config)
            info = save_manager.get_save_info()
            if info:
                timestamp = info.get("timestamp", "").split("T")[0]  # Solo fecha
                earnings = info.get("player_earnings", 0)
                return f"{timestamp} - ${earnings:.0f}"
        except:
            pass
        return "Disponible"

    def handle_key_press(self, symbol: int, modifiers: int):
        """Manejar entrada de teclado en el menú"""
        if symbol == arcade.key.UP:
            self.selected_option = (self.selected_option - 1) % len(self.options)
        elif symbol == arcade.key.DOWN:
            self.selected_option = (self.selected_option + 1) % len(self.options)
        elif symbol == arcade.key.ENTER:
            self._execute_option()
        elif symbol == arcade.key.ESCAPE:
            arcade.exit()

    def _execute_option(self):
        """Ejecutar la opción seleccionada"""
        # No ejecutar si está deshabilitada
        if self.selected_option in self.disabled_options:
            return

        option = self.options[self.selected_option]

        if option == "Nuevo Juego":
            self.game.start_new_game()
        elif option == "Cargar Partida":
            self.game.load_game()
        elif option == "Configuración":
            # TODO: Implementar menú de configuración
            print("Configuración - No implementado aún")
        elif option == "Salir":
            arcade.exit()


class PauseMenu:
    """Menú de pausa durante el juego"""

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0
        self.options = ["Continuar", "Guardar Partida", "Configuración", "Menú Principal", "Salir"]

        # Estado del guardado
        self.save_message = ""
        self.save_message_timer = 0

    def draw(self):
        """Dibujar el menú de pausa"""
        width = self.game.width
        height = self.game.height

        # Fondo semi-transparente sobre el juego
        arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (0, 0, 0, 150))

        # Panel del menú
        panel_width = 500
        panel_height = 400
        panel_x = (width - panel_width) // 2
        panel_y = (height - panel_height) // 2

        # Fondo del panel
        arcade.draw_lrbt_rectangle_filled(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            (30, 40, 60)
        )

        # Borde del panel
        arcade.draw_lrbt_rectangle_outline(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            arcade.color.WHITE, 3
        )

        # Título
        arcade.draw_text(
            "PAUSA",
            width // 2, panel_y + panel_height - 60,
            arcade.color.WHITE, 36,
            anchor_x="center"
        )

        # Opciones del menú
        menu_start_y = panel_y + panel_height - 120
        option_spacing = 45

        for i, option in enumerate(self.options):
            y_pos = menu_start_y - (i * option_spacing)

            if i == self.selected_option:
                color = (255, 255, 100)  # Amarillo para seleccionado
                text = f"> {option} <"
            else:
                color = arcade.color.WHITE
                text = f"  {option}"

            arcade.draw_text(
                text,
                width // 2, y_pos,
                color, 20,
                anchor_x="center"
            )

        # Mensaje de guardado (si existe)
        if self.save_message and self.save_message_timer > 0:
            message_y = panel_y + 30
            arcade.draw_text(
                self.save_message,
                width // 2, message_y,
                (100, 255, 100), 16,
                anchor_x="center"
            )

        # Instrucciones
        arcade.draw_text(
            "↑/↓ - Navegar    ENTER - Seleccionar    ESC - Continuar",
            width // 2, panel_y - 30,
            (180, 180, 255), 14,
            anchor_x="center"
        )

    def update(self, delta_time: float):
        """Actualizar el menú de pausa"""
        if self.save_message_timer > 0:
            self.save_message_timer -= delta_time
            if self.save_message_timer <= 0:
                self.save_message = ""

    def handle_key_press(self, symbol: int, modifiers: int):
        """Manejar entrada de teclado en el menú de pausa"""
        if symbol == arcade.key.UP:
            self.selected_option = (self.selected_option - 1) % len(self.options)
        elif symbol == arcade.key.DOWN:
            self.selected_option = (self.selected_option + 1) % len(self.options)
        elif symbol == arcade.key.ENTER:
            self._execute_option()
        elif symbol == arcade.key.ESCAPE:
            self.game.resume_game()

    def _execute_option(self):
        """Ejecutar la opción seleccionada"""
        option = self.options[self.selected_option]

        if option == "Continuar":
            self.game.resume_game()
        elif option == "Guardar Partida":
            success = self.game.save_game()
            if success:
                self.save_message = "✓ Partida guardada exitosamente"
            else:
                self.save_message = "✗ Error al guardar partida"
            self.save_message_timer = 2.0
        elif option == "Configuración":
            # TODO: Implementar configuración
            self.save_message = "Configuración - No implementado"
            self.save_message_timer = 1.0
        elif option == "Menú Principal":
            self.game.return_to_main_menu()
        elif option == "Salir":
            arcade.exit()

    def show_save_message(self, message: str):
        """Mostrar mensaje temporal de guardado"""
        self.save_message = message
        self.save_message_timer = 2.0