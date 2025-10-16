import time
import arcade
from typing import Optional

from api.client import APIClient
from game.core.city import CityMap
from game.input.handler import InputHandler
from game.ui.hud import HUDRenderer
from game.entities.player import Player
from game.rendering.world_renderer import RayCastRenderer
from game.ui.minimap import MinimapRenderer
from game.ui.notifications import NotificationManager
from game.core.weather import WeatherSystem
from game.gamestate import GameStateManager, GameState
from game.core.save_manager import SaveManager
from game.core.audio import AudioManager
from game.core.timer import GameTimer
from game.core.orders_manager import OrdersManager
from game.core.delivery import DeliverySystem
from game.core.player_controller import PlayerController
from game.core.game_rules import GameRules, GameRulesConfig
from game.core.save_flow import SaveFlow
from game.core.score_flow import ScoreFlow
from game.core.orders import Order
from game.ui.orders_window import ordersWindow
from game.core.score_manager import ScoreManager
from game.ui.score_screen import ScoreScreen


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.files_conf = app_config.get("files", {})
        self.frame_times = []
        self.performance_counter = 0
        self.orders_data = {}
        game_config = app_config.get("game", {})

        self.state_manager = GameStateManager(self)
        self.save_manager = SaveManager(app_config)
        self.audio_manager = AudioManager(app_config)

        self.backward_factor = 0.3
        self.last_move_scale = 0.0

        display = app_config.get("display", {})
        super().__init__(
            width=display.get("width", 800),
            height=display.get("height", 600),
            title=display.get("title", "Courier Quest"),
            resizable=display.get("resizable", False),
        )

        self.background_color = arcade.color.SKY_BLUE

        self.api_client: Optional[APIClient] = None
        self.city: Optional[CityMap] = None
        self.player: Optional[Player] = None
        self.renderer: Optional[RayCastRenderer] = None
        self.weather_system: Optional[WeatherSystem] = None
        # UI renderers and input
        self.minimap: Optional[MinimapRenderer] = None
        self.hud = HUDRenderer(self.app_config, debug=bool(self.app_config.get("debug", False)))
        self.notifications = NotificationManager()
        self.input_handler = InputHandler(self)

        self.game_start_time = 0
        self.total_play_time = 0
        self.last_update_time = 0
        self.time_limit = game_config.get("time_limit_minutes", 15) * 60
        self.time_remaining = self.time_limit

        # Timer central del juego
        self.timer = GameTimer(time_limit_seconds=self.time_limit)

        self.pickup_radius = self.app_config.get("game", {}).get("pickup_radius", 1.5)

        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        self.displayed_speed = 0.0
        self.speed_smoothing = 3.0

        # Instancias core adicionales: controlador de jugador y reglas de juego
        self.player_controller = PlayerController(
            backward_factor=self.backward_factor,
            speed_smoothing=self.speed_smoothing
        )
        self.game_rules = GameRules(lambda: GameRulesConfig(
            goal_earnings=float(self.app_config.get("game", {}).get("goal_earnings", 500)),
            time_limit=float(self.time_limit),
        ))

        self.orders_data = {}
        self.game_stats = {}

        self.set_update_rate(1 / 60)

        # HUD legacy texts (kept for compatibility; HUDRenderer draws the HUD now)
        self.hud_fps = arcade.Text("", 10, self.height - 20, arcade.color.WHITE, 12)
        self.hud_stats = arcade.Text("", 10, self.height - 40, arcade.color.WHITE, 12)
        self.hud_performance = arcade.Text("", 10, self.height - 60, arcade.color.YELLOW, 10)
        self.hud_player_location = arcade.Text("", 10, self.height - 80, arcade.color.WHITE, 12)
        self.hud_weather = arcade.Text("", 10, self.height - 100, arcade.color.WHITE, 12)
        self.hud_time = arcade.Text("", 10, self.height - 120, arcade.color.WHITE, 14)

        # Legacy notification fields (managed by NotificationManager now)
        self.notification_message = ""
        self.notification_timer = 0

        self._perf_accum_game = {"api": 0.0, "inventory": 0.0, "orders": 0.0, "weather": 0.0, "frames": 0}
        self._last_perf_report_game = time.perf_counter()

        self.debug = bool(self.app_config.get("debug", False))

        # Flujos de guardado y score
        self.save_flow = SaveFlow(self.app_config, debug=self.debug)
        self.score_flow = ScoreFlow(self.files_conf)

        self.orders_window = None
        self.orders_window_active = False

        self.score_manager = ScoreManager(self.files_conf)
        self.score_screen: Optional[ScoreScreen] = None
        self.game_over_active = False

        self.order_release_interval = self.app_config.get("game", {}).get("order_release_seconds", 120)
        self._orders_queue: list[tuple[float, Order]] = []
        self.pending_orders: list[Order] = []

        # Sistemas core
        self.orders_manager = OrdersManager()
        self.delivery_system = DeliverySystem()

    def setup(self):

        self.state_manager.change_state(GameState.MAIN_MENU)
        menu_music = self.app_config.get("audio", {}).get("menu_music")
        if menu_music:
            self.audio_manager.play_music(menu_music, loop=True)

    def start_new_game(self):
        try:
            self._initialize_game_systems()
            # Reemplaza _setup_orders por OrdersManager
            self.orders_manager.setup_orders(self.api_client, self.files_conf, self.app_config, self.city, self.renderer, self.debug)
            self.pending_orders = self.orders_manager.pending_orders

            # Timer centralizado
            self.timer = GameTimer(time_limit_seconds=self.time_limit)
            self.timer.start_new()
            self.total_play_time = 0.0
            self.time_remaining = self.time_limit
            self.last_update_time = 0

            self.game_stats = {
                "start_time": time.time(),
                "play_time": 0,
                "level": 1
            }
            self.state_manager.change_state(GameState.PLAYING)
            game_music = self.app_config.get("audio", {}).get("game_music")
            if game_music:
                self.audio_manager.play_music(game_music, loop=True)
            if self.debug:
                print("Nueva partida iniciada")
            self.show_notification("Nueva partida iniciada")
        except Exception as e:
            print(f"Error al inicializar nueva partida: {e}")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def load_game(self):
        return self.save_flow.load_game(self)

    def save_game(self):
        return self.save_flow.save_game(self)

    def _end_game(self, victory: bool, message: str):
        self.score_flow.end_game(self, victory, message)

    def return_to_main_menu(self):
        self.player = None
        self.city = None
        self.renderer = None
        self.weather_system = None
        if self.api_client:
            self.api_client.__exit__(None, None, None)
            self.api_client = None
        self.game_start_time = 0
        self.total_play_time = 0
        self.time_remaining = self.time_limit

        self.game_over_active = False
        self.score_screen = None

        self.state_manager.change_state(GameState.MAIN_MENU)

        menu_music = self.app_config.get("audio", {}).get("menu_music")
        if menu_music:
            self.audio_manager.play_music(menu_music, loop=True)

    def _initialize_game_systems(self):
        api_conf = dict(self.app_config.get("api", {}))
        if self.files_conf.get("cache_directory"):
            api_conf["cache_directory"] = self.files_conf["cache_directory"]
        t0 = time.perf_counter()
        self.api_client = APIClient(api_conf)
        t1 = time.perf_counter()
        self._perf_accum_game["api"] += (t1 - t0)
        self.city = CityMap(self.api_client, self.app_config)
        self.city.load_map()
        sx, sy = self.city.get_spawn_position()
        self.player = Player(sx, sy, self.app_config.get("player", {}))
        self.renderer = RayCastRenderer(self.city, self.app_config)
        # Initialize UI helpers dependent on city
        self.minimap = MinimapRenderer(self.city, self.app_config)

        t0 = time.perf_counter()
        self.weather_system = WeatherSystem(self.api_client, self.app_config)
        t1 = time.perf_counter()
        self._perf_accum_game["weather"] += (t1 - t0)

        self.orders_window = ordersWindow(self)
        if hasattr(self, 'width') and hasattr(self, 'height'):
            self.orders_window.ensure_initial_position(self.width, self.height)
        # Conectar ventana de pedidos al manager
        self.orders_manager.attach_window(self.orders_window)

    def show_notification(self, message: str, duration: float = 2.0):
        # Delegate to NotificationManager
        self.notifications.show(message, duration)
        if self.debug:
            f = max(1, self._perf_accum_game["frames"])
            api_ms = (self._perf_accum_game["api"] / f) * 1000
            inv_ms = (self._perf_accum_game["inventory"] / f) * 1000
            orders_ms = (self._perf_accum_game["orders"] / f) * 1000
            weather_ms = (self._perf_accum_game["weather"] / f) * 1000
            print(
                f"[GamePerf] (setup) api={api_ms:.2f}ms inventory={inv_ms:.2f}ms orders={orders_ms:.2f}ms weather={weather_ms:.2f}ms")

    def on_draw(self):
        self.clear()
        state = self.state_manager.current_state
        if state == GameState.MAIN_MENU and self.state_manager.main_menu:
            self.state_manager.main_menu.draw()
        elif state == GameState.PLAYING:
            self._draw_game()
        elif state == GameState.PAUSED:
            self._draw_game()
            if self.game_over_active and self.score_screen:
                self.score_screen.draw()
            elif self.state_manager.pause_menu:
                self.state_manager.pause_menu.draw()
        elif state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.draw()

        self._draw_notifications()

    def _draw_game(self):
        if not self.renderer or not self.player:
            return
        self.renderer.render_world(self.player, weather_system=self.weather_system)
        # Minimapa: ahora delegado a MinimapRenderer
        if self.minimap and self.player:
            self.minimap.render(10, 10, 160, self.player)

        # HUD: delegado al HUDRenderer
        self.hud.draw(self)

        if self.orders_window and (self.orders_window.is_open or self.orders_window.animation_progress > 0):
            self.orders_window.draw()

    def _draw_notifications(self):
        # Dibujo de notificaciones
        self.notifications.draw(self)

        # Contadores de rendimiento (debug)
        self._perf_accum_game["frames"] += 1
        now = time.perf_counter()
        if now - self._last_perf_report_game > 2.0 and self.debug:
            f = max(1, self._perf_accum_game["frames"])
            api_ms = (self._perf_accum_game["api"] / f) * 1000
            inv_ms = (self._perf_accum_game["inventory"] / f) * 1000
            orders_ms = (self._perf_accum_game["orders"] / f) * 1000
            weather_ms = (self._perf_accum_game["weather"] / f) * 1000
            print(f"[GamePerf] api={api_ms:.2f}ms inventory={inv_ms:.2f}ms orders={orders_ms:.2f}ms weather={weather_ms:.2f}ms")
            self._perf_accum_game = {"api": 0.0, "inventory": 0.0, "orders": 0.0, "weather": 0.0, "frames": 0}
            self._last_perf_report_game = now

    def on_update(self, delta_time: float):
        # Actualización de notificaciones
        self.notifications.update(delta_time)

        if self.state_manager.current_state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.update(delta_time)
            return

        if self.state_manager.current_state != GameState.PLAYING:
            return

        # Avance de tiempo centralizado
        self.timer.advance(delta_time)
        self.total_play_time = self.timer.total_play_time
        self.time_remaining = self.timer.time_remaining

        # Guardar estados para undo
        if self.player:
            self.player.save_undo_state_if_needed(time.time())

        # Reemplaza check local por reglas encapsuladas
        self.game_rules.check_and_handle(self)
        # Liberación de pedidos centralizada
        self.orders_manager.release_orders(self.total_play_time, lambda msg: self.show_notification(msg))
        self.pending_orders = self.orders_manager.pending_orders

        if self.player and hasattr(self.player, 'inventory'):
            self.hud.update(delta_time, self)

        if self.weather_system and self.player:
            t0 = time.perf_counter()
            self.weather_system.update(delta_time, self.player)
            t1 = time.perf_counter()
            self._perf_accum_game["weather"] += (t1 - t0)

        self.frame_times.append(delta_time)
        if len(self.frame_times) > 240:
            self.frame_times.pop(0)

        if not self.player or not self.city:
            return

        # Movimiento y velocidad mostrada delegados
        self.displayed_speed = self.player_controller.update(
            self.player, self.city, delta_time,
            self._move_forward, self._move_backward,
            self._turn_left, self._turn_right
        )

        # Actualización del jugador (estados internos)
        self.player.update(delta_time)

        if self.orders_window:
            self.orders_window.update_animation(delta_time)

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE:
            if self.state_manager.current_state == GameState.PAUSED and self.game_over_active and self.score_screen:
                if self.score_screen.handle_key_press(symbol, modifiers):
                    return
            state = self.state_manager.current_state
            if state == GameState.PLAYING:
                self.pause_game()
            elif state == GameState.PAUSED:
                self.resume_game()
            elif state == GameState.SETTINGS:
                if self.state_manager.settings_menu:
                    self.state_manager.settings_menu.handle_key_press(symbol, modifiers)
            elif state == GameState.MAIN_MENU:
                arcade.exit()
            return

        state = self.state_manager.current_state
        if state == GameState.PLAYING:
            # Delegar manejo de entrada al InputHandler
            if self.input_handler.on_key_press(symbol, modifiers):
                return
        elif state == GameState.MAIN_MENU:
            if self.state_manager.main_menu:
                self.state_manager.main_menu.handle_key_press(symbol, modifiers)
        elif state == GameState.PAUSED:
            if self.game_over_active and self.score_screen:
                if self.score_screen.handle_key_press(symbol, modifiers):
                    return
            if self.state_manager.pause_menu:
                self.state_manager.pause_menu.handle_key_press(symbol, modifiers)
        elif state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.handle_key_press(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        if self.state_manager.current_state != GameState.PLAYING:
            return
        if self.input_handler.on_key_release(symbol, modifiers):
            return
