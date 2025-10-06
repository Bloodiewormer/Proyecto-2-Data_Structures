import arcade
from enum import Enum
from pathlib import Path


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
        if not self.main_menu:
            self.main_menu = MainMenu(self.game)

    def _resume_game(self):
        pass

    def _show_pause_menu(self):
        if not self.pause_menu:
            self.pause_menu = PauseMenu(self.game)

    def _show_game_over(self):
        pass

    def is_game_active(self) -> bool:
        return self.current_state == GameState.PLAYING

    def is_game_paused(self) -> bool:
        return self.current_state == GameState.PAUSED


class MainMenu:

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0
        self.options = ["Nuevo Juego", "Cargar Partida", "Configuración", "Salir"]

        # Verificar si existe una partida guardada
        self.has_saved_game = self._check_saved_game()

        if not self.has_saved_game:
            self.disabled_options = [1]
        else:
            self.disabled_options = []

        self.background_texture = None
        self._load_background_image()

    def _check_saved_game(self) -> bool:
        try:
            save_dir = Path(self.game.app_config.get("files", {}).get("save_directory", "saves"))
            save_file = save_dir / "savegame.sav"
            return save_file.exists() and save_file.stat().st_size > 0
        except:
            return False

    def _load_background_image(self):
        try:
            bg_path = Path("assets/images/menu_background.png")

            if bg_path.exists():
                self.background_texture = arcade.load_texture(str(bg_path))
                print(f"Imagen de fondo cargada: {bg_path}")
            else:
                print(f"Imagen de fondo no encontrada en: {bg_path}")
                print("Usando fondo por defecto")
        except Exception as e:
            print(f"Error al cargar imagen de fondo: {e}")
            self.background_texture = None

    def draw(self):
        width = self.game.width
        height = self.game.height

        # Dibujar imagen de fondo si existe
        if self.background_texture:
            # Escalar la imagen para cubrir toda la ventana
            arcade.draw_texture_rect(
                self.background_texture,
                arcade.LRBT(0, width, 0, height)
            )

            # Overlay oscuro semi-transparente para mejorar legibilidad
            arcade.draw_lrbt_rectangle_filled(
                0, width, 0, height,
                (0, 0, 0, 100)  # Negro con 40% de opacidad
            )
        else:
            # Fondo degradado por defecto
            arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (15, 25, 45))
            arcade.draw_lrbt_rectangle_filled(0, width, 0, height // 3, (25, 35, 55))

        # Panel semi-transparente detrás del menú para mejor legibilidad
        panel_width = 600
        panel_height = 500
        panel_x = (width - panel_width) // 2
        panel_y = (height - panel_height) // 2

        arcade.draw_lrbt_rectangle_filled(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            (20, 30, 50, 180)  # Azul oscuro semi-transparente
        )

        # Borde del panel
        arcade.draw_lrbt_rectangle_outline(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            (255, 255, 255, 200), 3
        )

        # Título principal con sombra para mejor legibilidad
        title_y = panel_y + panel_height - 80

        # Sombra del título
        arcade.draw_text(
            "COURIER QUEST",
            width // 2 + 3, title_y - 3,
            (0, 0, 0, 180), 56,
            anchor_x="center", font_name="Kenney Future"
        )

        # Título principal
        arcade.draw_text(
            "COURIER QUEST",
            width // 2, title_y,
            (255, 220, 100), 56,  # Amarillo dorado
            anchor_x="center", font_name="Kenney Future", bold=True
        )

        # Subtítulo con sombra
        subtitle_y = title_y - 50
        arcade.draw_text(
            "Entrega. Explora. Sobrevive.",
            width // 2 + 2, subtitle_y - 2,
            (0, 0, 0, 180), 20,
            anchor_x="center"
        )
        arcade.draw_text(
            "Entrega. Explora. Sobrevive.",
            width // 2, subtitle_y,
            (200, 220, 255), 20,
            anchor_x="center", bold=True
        )

        # Opciones del menú
        menu_start_y = panel_y + panel_height // 2 + 20
        option_spacing = 60

        for i, option in enumerate(self.options):
            y_pos = menu_start_y - (i * option_spacing)

            # Determinar color y estilo de la opción
            is_selected = (i == self.selected_option)
            is_disabled = (i in self.disabled_options)

            if is_disabled:
                # Opción deshabilitada
                text = f"  {option}"
                # Sombra
                arcade.draw_text(
                    text,
                    width // 2 + 2, y_pos - 2,
                    (0, 0, 0, 100), 24,
                    anchor_x="center"
                )
                # Texto
                arcade.draw_text(
                    text,
                    width // 2, y_pos,
                    (80, 80, 80), 24,
                    anchor_x="center"
                )
            elif is_selected:
                # Opción seleccionada con fondo
                text = f"> {option} <"

                # Fondo de selección
                text_width = len(text) * 15
                arcade.draw_lrbt_rectangle_filled(
                    width // 2 - text_width // 2 - 10,
                    width // 2 + text_width // 2 + 10,
                    y_pos - 5,
                    y_pos + 25,
                    (255, 255, 100, 50)
                )

                # Sombra del texto
                arcade.draw_text(
                    text,
                    width // 2 + 2, y_pos - 2,
                    (0, 0, 0, 200), 26,
                    anchor_x="center", bold=True
                )

                # Texto seleccionado
                arcade.draw_text(
                    text,
                    width // 2, y_pos,
                    (255, 255, 100), 26,
                    anchor_x="center", bold=True
                )
            else:
                # Opción normal
                text = f"  {option}"

                # Sombra
                arcade.draw_text(
                    text,
                    width // 2 + 2, y_pos - 2,
                    (0, 0, 0, 150), 24,
                    anchor_x="center"
                )

                # Texto
                arcade.draw_text(
                    text,
                    width // 2, y_pos,
                    (255, 255, 255), 24,
                    anchor_x="center"
                )

        # Información de partida guardada
        if self.has_saved_game and self.selected_option == 1:
            save_info = self._get_save_info()
            if save_info:
                info_y = panel_y + 80

                # Fondo para la información
                arcade.draw_lrbt_rectangle_filled(
                    width // 2 - 150, width // 2 + 150,
                    info_y - 10, info_y + 20,
                    (0, 0, 0, 120)
                )

                arcade.draw_text(
                    f"Última partida: {save_info}",
                    width // 2, info_y,
                    (180, 220, 255), 14,
                    anchor_x="center", bold=True
                )

        # Instrucciones en la parte inferior del panel
        instructions_y = panel_y + 30

        # Fondo para instrucciones
        arcade.draw_lrbt_rectangle_filled(
            panel_x + 10, panel_x + panel_width - 10,
            instructions_y - 10, instructions_y + 20,
            (0, 0, 0, 100)
        )

        arcade.draw_text(
            "↑/↓ - Navegar    ENTER - Seleccionar    ESC - Salir",
            width // 2, instructions_y,
            (200, 220, 255), 16,
            anchor_x="center", bold=True
        )

    def _get_save_info(self) -> str:
        """Obtener información básica de la partida guardada"""
        try:
            from game.SaveManager import SaveManager
            save_manager = SaveManager(self.game.app_config)
            info = save_manager.get_save_info()
            if info:
                timestamp = info.get("timestamp", "").split("T")[0]
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
        if self.selected_option in self.disabled_options:
            return

        option = self.options[self.selected_option]

        if option == "Nuevo Juego":
            self.game.start_new_game()
        elif option == "Cargar Partida":
            self.game.load_game()
        elif option == "Configuración":
            from game.gamestate import GameState
            self.game.state_manager.change_state(GameState.SETTINGS)
        elif option == "Salir":
            arcade.exit()


class PauseMenu:
    """Menú de pausa durante el juego"""

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0
        self.options = ["Continuar", "Guardar Partida", "Configuración", "Menú Principal", "Salir"]

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
                color = (255, 255, 100)
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

        # Mensaje de guardado
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
            from game.gamestate import GameState
            self.game.state_manager.change_state(GameState.SETTINGS)
        elif option == "Menú Principal":
            self.game.return_to_main_menu()
        elif option == "Salir":
            arcade.exit()

    def show_save_message(self, message: str):
        """Mostrar mensaje temporal de guardado"""
        self.save_message = message
        self.save_message_timer = 2.0