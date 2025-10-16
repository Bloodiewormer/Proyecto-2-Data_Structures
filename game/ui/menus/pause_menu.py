import arcade
from game.core.gamestate import GameState

class PauseMenu:
    """Menú de pausa durante el juego"""

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0
        self.options = ["Continuar", "Guardar Partida", "Configuración", "Menú Principal", "Salir"]

        self.save_message = ""
        self.save_message_timer = 0

    def draw(self):
        width = self.game.width
        height = self.game.height

        arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (0, 0, 0, 150))

        panel_width = 500
        panel_height = 400
        panel_x = (width - panel_width) // 2
        panel_y = (height - panel_height) // 2

        arcade.draw_lrbt_rectangle_filled(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, (30, 40, 60))
        arcade.draw_lrbt_rectangle_outline(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, arcade.color.WHITE, 3)

        arcade.draw_text("PAUSA", width // 2, panel_y + panel_height - 60, arcade.color.WHITE, 36, anchor_x="center")

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

            arcade.draw_text(text, width // 2, y_pos, color, 20, anchor_x="center")

        if self.save_message and self.save_message_timer > 0:
            message_y = panel_y + 30
            arcade.draw_text(self.save_message, width // 2, message_y, (100, 255, 100), 16, anchor_x="center")

        arcade.draw_text("↑/↓ - Navegar    ENTER - Seleccionar    ESC - Continuar", width // 2, panel_y - 30, (180, 180, 255), 14, anchor_x="center")

    def update(self, delta_time: float):
        if self.save_message_timer > 0:
            self.save_message_timer -= delta_time
            if self.save_message_timer <= 0:
                self.save_message = ""

    def handle_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.UP:
            self.selected_option = (self.selected_option - 1) % len(self.options)
        elif symbol == arcade.key.DOWN:
            self.selected_option = (self.selected_option + 1) % len(self.options)
        elif symbol == arcade.key.ENTER:
            self._execute_option()
        elif symbol == arcade.key.ESCAPE:
            self.game.resume_game()

    def _execute_option(self):
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
            self.game.state_manager.change_state(GameState.SETTINGS)
        elif option == "Menú Principal":
            self.game.return_to_main_menu()
        elif option == "Salir":
            arcade.exit()