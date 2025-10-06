import arcade



class SettingsMenu:

    def __init__(self, game_instance):
        self.game = game_instance
        self.selected_option = 0

        self.options = [
            "Resolución",
            "Rayos (Calidad)",
            "Volumen",
            "Modo Debug",
            "Aplicar Cambios",
            "Volver"
        ]

        # Resoluciones disponibles
        self.resolutions = ["800x600", "1024x768", "1280x720", "1920x1080"]
        self.current_resolution_index = 0

        # Valores de rayos
        self.ray_counts = [60, 120, 180, 240]
        self.current_ray_index = 1  # Default 120

        # Valores de volumen
        self.volume_levels = [0, 25, 50, 75, 100]
        self.current_volume_index = 4  # Default 100%

        # Debug
        self.debug_enabled = bool(game_instance.app_config.get("debug", False))

        # Mensaje temporal
        self.message = ""
        self.message_timer = 0.0

        # Cargar configuración actual
        self._load_current_settings()

        print("SettingsMenu inicializado correctamente")

    def _load_current_settings(self):
        """Cargar configuración actual del juego"""
        try:
            # Resolución actual - con verificación de None
            current_width = self.game.width
            current_height = self.game.height

            # Verificar que width y height no sean None
            if current_width is not None and current_height is not None:
                current_res = f"{current_width}x{current_height}"
                if current_res in self.resolutions:
                    self.current_resolution_index = self.resolutions.index(current_res)
            else:
                # Cargar desde configuración si la ventana aún no está inicializada
                display_config = self.game.app_config.get("display", {})
                current_width = display_config.get("width", 800)
                current_height = display_config.get("height", 600)
                current_res = f"{current_width}x{current_height}"
                if current_res in self.resolutions:
                    self.current_resolution_index = self.resolutions.index(current_res)

            # Número de rayos actual
            if self.game.renderer and hasattr(self.game.renderer, 'num_rays'):
                current_rays = self.game.renderer.num_rays
                if current_rays in self.ray_counts:
                    self.current_ray_index = self.ray_counts.index(current_rays)
            else:
                # Cargar desde configuración si el renderer no está inicializado
                rendering_config = self.game.app_config.get("rendering", {})
                current_rays = rendering_config.get("num_rays", 120)
                if current_rays in self.ray_counts:
                    self.current_ray_index = self.ray_counts.index(current_rays)
            if hasattr(self.game, 'audio_manager'):
                current_volume_percent = self.game.audio_manager.get_music_volume_percent()
                # Encontrar el índice más cercano
                closest_index = min(range(len(self.volume_levels)),
                                    key=lambda i: abs(self.volume_levels[i] - current_volume_percent))
                self.current_volume_index = closest_index
        except Exception as e:
            print(f"Error al cargar configuración actual: {e}")
            # Usar valores por defecto si hay algún error

    def draw(self):
        """Dibujar menú de configuraciones"""
        width = self.game.width
        height = self.game.height

        # Fondo semi-transparente
        arcade.draw_lrbt_rectangle_filled(0, width, 0, height, (0, 0, 0, 180))

        # Panel de configuraciones
        panel_width = 600
        panel_height = 500
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
            "CONFIGURACIÓN",
            width // 2, panel_y + panel_height - 50,
            arcade.color.WHITE, 32,
            anchor_x="center", bold=True
        )

        # Opciones
        menu_start_y = panel_y + panel_height - 120
        option_spacing = 60

        for i, option in enumerate(self.options):
            y_pos = menu_start_y - (i * option_spacing)

            is_selected = (i == self.selected_option)

            # Nombre de la opción
            if is_selected:
                color = (255, 255, 100)
                prefix = "> "
                suffix = " <"
            else:
                color = arcade.color.WHITE
                prefix = "  "
                suffix = ""

            # Mostrar valor actual según la opción
            if option == "Resolución":
                value = self.resolutions[self.current_resolution_index]
                text = f"{prefix}{option}: {value}{suffix}"
            elif option == "Rayos (Calidad)":
                value = self.ray_counts[self.current_ray_index]
                text = f"{prefix}{option}: {value}{suffix}"
            elif option == "Modo Debug":
                value = "ON" if self.debug_enabled else "OFF"
                text = f"{prefix}{option}: {value}{suffix}"
            elif option == "Volumen":
                value = f"{self.volume_levels[self.current_volume_index]}%"
                text = f"{prefix}{option}: {value}{suffix}"
            else:
                text = f"{prefix}{option}{suffix}"

            arcade.draw_text(
                text,
                width // 2, y_pos,
                color, 20,
                anchor_x="center"
            )

        # Mensaje temporal
        if self.message and self.message_timer > 0:
            message_y = panel_y + 30
            arcade.draw_text(
                self.message,
                width // 2, message_y,
                (100, 255, 100), 16,
                anchor_x="center"
            )

        # Instrucciones
        arcade.draw_text(
            "↑/↓ - Navegar    ←/→ - Cambiar    ENTER - Confirmar    ESC - Volver",
            width // 2, panel_y - 30,
            (180, 180, 255), 14,
            anchor_x="center"
        )

    def update(self, delta_time: float):
        """Actualizar menú"""
        if self.message_timer > 0:
            self.message_timer -= delta_time
            if self.message_timer <= 0:
                self.message = ""

    def handle_key_press(self, symbol: int, modifiers: int):
        """Manejar entrada de teclado"""
        if symbol == arcade.key.UP:
            self.selected_option = (self.selected_option - 1) % len(self.options)

        elif symbol == arcade.key.DOWN:
            self.selected_option = (self.selected_option + 1) % len(self.options)

        elif symbol == arcade.key.LEFT:
            self._change_value(-1)

        elif symbol == arcade.key.RIGHT:
            self._change_value(1)

        elif symbol == arcade.key.ENTER:
            self._execute_option()

        elif symbol == arcade.key.ESCAPE:
            self._return_to_previous_menu()

    def _change_value(self, direction: int):
        """Cambiar valor de la opción seleccionada"""
        option = self.options[self.selected_option]

        if option == "Resolución":
            self.current_resolution_index = (self.current_resolution_index + direction) % len(self.resolutions)

        elif option == "Rayos (Calidad)":
            self.current_ray_index = (self.current_ray_index + direction) % len(self.ray_counts)

        elif option == "Modo Debug":
            self.debug_enabled = not self.debug_enabled

        elif option == "Volumen":
            self.current_volume_index = (self.current_volume_index + direction) % len(self.volume_levels)

    def _execute_option(self):
        """Ejecutar opción seleccionada"""
        option = self.options[self.selected_option]

        if option == "Aplicar Cambios":
            self._apply_changes()

        elif option == "Volver":
            self._return_to_previous_menu()

    def _apply_changes(self):
        """Aplicar cambios de configuración"""
        try:
            # Aplicar resolución
            new_res = self.resolutions[self.current_resolution_index]
            width, height = map(int, new_res.split('x'))

            if width != self.game.width or height != self.game.height:
                self.game.set_size(width, height)

            # Aplicar número de rayos
            if self.game.renderer:
                new_rays = self.ray_counts[self.current_ray_index]
                self.game.renderer.num_rays = new_rays

            # Aplicar debug
            self.game.debug = self.debug_enabled
            self.game.app_config["debug"] = self.debug_enabled

            # Actualizar configuración en memoria
            self.game.app_config["display"]["width"] = width
            self.game.app_config["display"]["height"] = height
            self.game.app_config["rendering"]["num_rays"] = self.ray_counts[self.current_ray_index]


            # Aplicar volumen
            if hasattr(self.game, 'audio_manager'):
                new_volume = self.volume_levels[self.current_volume_index]
                self.game.audio_manager.set_music_volume(new_volume)


            self.show_message(" Cambios aplicados exitosamente")

        except Exception as e:
            print(f"Error al aplicar cambios: {e}")
            self.show_message("✗ Error al aplicar cambios")

    def _return_to_previous_menu(self):
        """Volver al menú anterior"""
        from game.gamestate import GameState

        if self.game.state_manager.previous_state in (GameState.PAUSED, GameState.PLAYING):
            self.game.state_manager.change_state(GameState.PAUSED)
        else:
            # Si venimos del menú principal, volver allá
            self.game.state_manager.change_state(GameState.MAIN_MENU)

    def show_message(self, message: str):
        """Mostrar mensaje temporal"""
        self.message = message
        self.message_timer = 2.0