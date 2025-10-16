import arcade
from pathlib import Path
from game.core.gamestate import GameState

class MainMenu:
    def __init__(self, game_instance):
        self.game = game_instance
        self.options = ["Nuevo Juego", "Cargar Partida", "Configuración", "Información", "Salir"]
        self.selected_option = 0
        self.show_info = False

        # Verificar si existe una partida guardada
        self.has_saved_game = self._check_saved_game()
        self.disabled_options = []
        self._refresh_save_available()

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
                if getattr(self.game, "debug", False):
                    print(f"Imagen de fondo cargada: {bg_path}")
            else:
                if getattr(self.game, "debug", False):
                    print(f"Imagen de fondo no encontrada en: {bg_path}")
                    print("Usando fondo por defecto")
        except Exception as e:
            if getattr(self.game, "debug", False):
                print(f"Error al cargar imagen de fondo: {e}")
            self.background_texture = None

    def _refresh_save_available(self):
        was = getattr(self, "has_saved_game", False)
        self.has_saved_game = self._check_saved_game()
        self.disabled_options = []
        try:
            load_idx = self.options.index("Cargar Partida")
            if not self.has_saved_game:
                self.disabled_options.append(load_idx)
        except ValueError:
            pass
        # Si estamos en una opción deshabilitada, muévete
        if self.selected_option in self.disabled_options:
            self._move_selection(1)

    def _move_selection(self, delta: int):
        n = len(self.options)
        if n == 0:
            return
        for _ in range(n):
            self.selected_option = (self.selected_option + delta) % n
            if self.selected_option not in getattr(self, "disabled_options", []):
                break

    def draw(self):
        self._refresh_save_available()
        width = self.game.width
        height = self.game.height

        # Si show_info, dibuja overlay de información a pantalla completa
        if self.show_info:
            w, h = self.game.width, self.game.height
            arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 200))
            arcade.draw_text("Información", w // 2, h - 80, (255, 220, 180), 28, anchor_x="center", bold=True)
            lines = [
                "Controles:",
                "  WASD/Flechas: Mover | ESC: Pausa/Menú | F5: Guardado rápido",
                "  I: Inventario | O: Pedidos | U o CTRL+Z: Deshacer",
                "",
                "Desarrolladores:",
                "  - David Alberto González Cordoba",
                "  - Felipe Ugalde Vallejos",
                "  - Brandon Brenes Umaña",
                "",
                "ENTER para volver"
            ]
            y = h - 140
            for s in lines:
                arcade.draw_text(s, w // 2, y, arcade.color.LIGHT_GRAY, 16, anchor_x="center")
                y -= 28
            return  # no dibujar el resto debajo del overlay

        # Fondo / imagen
        if self.background_texture:
            arcade.draw_texture_rect(
                self.background_texture,
                arcade.LRBT(0, width, 0, height)
            )
            arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (0, 0, 0, 100))
        else:
            arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (15, 25, 45))
            arcade.draw_lrbt_rectangle_filled(0, width, 0, height // 3, (25, 35, 55))

        # Panel
        panel_width = 600
        panel_height = 500
        panel_x = (width - panel_width) // 2
        panel_y = (height - panel_height) // 2

        arcade.draw_lrbt_rectangle_filled(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, (20, 30, 50, 180))
        arcade.draw_lrbt_rectangle_outline(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, (255, 255, 255, 200), 3)

        # Título y subtítulo
        title_y = panel_y + panel_height - 80
        arcade.draw_text("COURIER QUEST", width // 2 + 3, title_y - 3, (0, 0, 0, 180), 56, anchor_x="center", font_name="Kenney Future")
        arcade.draw_text("COURIER QUEST", width // 2, title_y, (255, 220, 100), 56, anchor_x="center", font_name="Kenney Future", bold=True)

        subtitle_y = title_y - 50
        arcade.draw_text("Entrega. Explora. Sobrevive.", width // 2 + 2, subtitle_y - 2, (0, 0, 0, 180), 20, anchor_x="center")
        arcade.draw_text("Entrega. Explora. Sobrevive.", width // 2, subtitle_y, (200, 220, 255), 20, anchor_x="center", bold=True)

        # Opciones
        menu_start_y = panel_y + panel_height // 2 + 20
        option_spacing = 60
        for i, option in enumerate(self.options):
            y_pos = menu_start_y - (i * option_spacing)
            is_selected = (i == self.selected_option)
            is_disabled = (i in self.disabled_options)
            if is_disabled:
                text = f"  {option}"
                arcade.draw_text(text, width // 2 + 2, y_pos - 2, (0, 0, 0, 100), 24, anchor_x="center")
                arcade.draw_text(text, width // 2, y_pos, (80, 80, 80), 24, anchor_x="center")
            elif is_selected:
                text = f"> {option} <"
                text_width = len(text) * 15
                arcade.draw_lrbt_rectangle_filled(width // 2 - text_width // 2 - 10, width // 2 + text_width // 2 + 10, y_pos - 5, y_pos + 25, (255, 255, 100, 50))
                arcade.draw_text(text, width // 2 + 2, y_pos - 2, (0, 0, 0, 200), 26, anchor_x="center", bold=True)
                arcade.draw_text(text, width // 2, y_pos, (255, 255, 100), 26, anchor_x="center", bold=True)
            else:
                text = f"  {option}"
                arcade.draw_text(text, width // 2 + 2, y_pos - 2, (0, 0, 0, 150), 24, anchor_x="center")
                arcade.draw_text(text, width // 2, y_pos, (255, 255, 255), 24, anchor_x="center")

        # Info de partida guardada
        if self.has_saved_game and self.selected_option == 1:
            save_info = self._get_save_info()
            if save_info:
                info_y = panel_y + 80
                arcade.draw_lrbt_rectangle_filled(width // 2 - 150, width // 2 + 150, info_y - 10, info_y + 20, (0, 0, 0, 120))
                arcade.draw_text(f"Última partida: {save_info}", width // 2, info_y, (180, 220, 255), 14, anchor_x="center", bold=True)

        # Instrucciones
        instructions_y = panel_y + 30
        arcade.draw_lrbt_rectangle_filled(panel_x + 10, panel_x + panel_width - 10, instructions_y - 10, instructions_y + 20, (0, 0, 0, 100))
        arcade.draw_text("↑/↓ - Navegar    ENTER - Seleccionar    ESC - Salir", width // 2, instructions_y, (200, 220, 255), 16, anchor_x="center", bold=True)

        # Overlay de información
        if self.show_info:
            w, h = self.game.width, self.game.height
            arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 200))
            arcade.draw_text("Información", w // 2, h - 80, (255, 220, 180), 28, anchor_x="center", bold=True)
            lines = [
                "Controles:",
                "  WASD/Flechas: Mover | ESC: Pausa/Menú | F5: Guardado rápido",
                "  I: Inventario | O: Pedidos | U o CTRL+Z: Deshacer",
                "",
                "Desarrolladores:",
                "  - Tu Nombre 1",
                "  - Tu Nombre 2",
                "",
                "ENTER/ESC para volver"
            ]
            y = h - 140
            for s in lines:
                arcade.draw_text(s, w // 2, y, arcade.color.LIGHT_GRAY, 16, anchor_x="center")
                y -= 28

    def _get_save_info(self) -> str:
        try:
            from game.core.save_manager import SaveManager
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
        if self.show_info:
            # Cerrar info con Enter/Esc
            if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.ESCAPE):
                self.show_info = False
            return
        if symbol == arcade.key.UP:
            self._move_selection(-1)
        elif symbol == arcade.key.DOWN:
            self._move_selection(1)
        elif symbol == arcade.key.ENTER:
            self._execute_option()
        elif symbol == arcade.key.ESCAPE:
            arcade.exit()

    def _execute_option(self):
        if self.selected_option in getattr(self, "disabled_options", []):
            return
        option = self.options[self.selected_option]
        if option == "Nuevo Juego":
            self.game.start_new_game()
        elif option == "Cargar Partida":
            self.game.load_game()
        elif option == "Configuración":
            from game.core.gamestate import GameState
            self.game.state_manager.change_state(GameState.SETTINGS)
        elif option == "Información":
            self.show_info = True
        elif option == "Salir":
            arcade.exit()