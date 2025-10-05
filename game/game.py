import api.client
import time
import arcade
from typing import Optional
import math
import random
import os
import json

from datetime import datetime, timezone
from api.client import APIClient
from game.city import CityMap
from game.player import Player
from game.renderer import RayCastRenderer
from game.weather import WeatherSystem
from game.utils import find_nearest_building, format_time
from game.gamestate import GameStateManager, GameState
from game.saveManager import saveManager
from game.audio import AudioManager
from . import utils
from .orders import Order
from .ordersWindow import ordersWindow


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.files_conf = app_config.get("files", {})
        self.frame_times = []
        self.performance_counter = 0
        self.orders_data = {}

        self.state_manager = GameStateManager(self)
        self.save_manager = saveManager(app_config)
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

        # Core game objects
        self.api_client: Optional[APIClient] = None
        self.city: Optional[CityMap] = None
        self.player: Optional[Player] = None
        self.renderer: Optional[RayCastRenderer] = None
        self.weather_system: Optional[WeatherSystem] = None

        # Timing
        self.game_start_time = 0
        self.total_play_time = 0
        self.last_update_time = 0
        self.time_limit = app_config.get("game", {}).get("time_limit_minutes", 15) * 60  # Convertir a segundos
        self.time_remaining = self.time_limit

        # radio para recoger/entregar en tiles
        self.pickup_radius = self.app_config.get("game", {}).get("pickup_radius", 1.5)

        # Input state
        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        # Movement metrics
        self.displayed_speed = 0.0
        self.speed_smoothing = 3.0

        # Data containers
        self.orders_data = {}
        self.game_stats = {}

        # Update rate
        self.set_update_rate(1 / 60) # 60 FPS

        # HUD text objects
        self.hud_fps = arcade.Text("", 10, self.height - 20, arcade.color.WHITE, 12)
        self.hud_stats = arcade.Text("", 10, self.height - 40, arcade.color.WHITE, 12)
        self.hud_performance = arcade.Text("", 10, self.height - 60, arcade.color.YELLOW, 10)
        self.hud_player_location = arcade.Text("", 10, self.height - 80, arcade.color.WHITE, 12)
        self.hud_weather = arcade.Text("", 10, self.height - 100, arcade.color.WHITE, 12)
        self.hud_time = arcade.Text("", 10, self.height - 120, arcade.color.WHITE, 14)

        # Notifications
        self.notification_message = ""
        self.notification_timer = 0

        # Performance accumulators
        self._perf_accum_game = {"api": 0.0, "inventory": 0.0, "orders": 0.0, "weather": 0.0, "frames": 0}
        self._last_perf_report_game = time.perf_counter()

        # Flags
        self.debug = bool(self.app_config.get("debug", False))

        self.orders_window = None
        self.orders_window_active = False

    # Game Lifecycle / State Entry
    def setup(self):
        self.state_manager.change_state(GameState.MAIN_MENU)
        menu_music = self.app_config.get("audio", {}).get("menu_music")
        if menu_music:
            self.audio_manager.play_music(menu_music, loop=True)

    def start_new_game(self):
        try:
            self._initialize_game_systems()
            self._setup_orders()
            self.game_start_time = time.time()
            self.total_play_time = 0
            self.time_remaining = self.time_limit  # Reiniciar tiempo límite
            self.game_stats = {
                "start_time": self.game_start_time,
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
        try:
            save_data = self.save_manager.load_game()
            if not save_data:
                self.show_notification("Error al cargar partida")
                return

            self._initialize_game_systems()

            if "player" in save_data:
                self.save_manager.restore_player(self.player, save_data["player"])

            if "city" in save_data:
                self.save_manager.restore_city(self.city, save_data["city"])

            if "orders" in save_data:
                self.orders_data = save_data["orders"]

            if "game_stats" in save_data:
                self.game_stats = save_data["game_stats"]
                self.total_play_time = self.game_stats.get("play_time", 0)
                self.time_remaining = self.game_stats.get("time_remaining", self.time_limit)

            self._setup_orders()


            self.game_start_time = time.time() - self.total_play_time
            self.last_update_time = time.time()

            self.state_manager.change_state(GameState.PLAYING)
            self.show_notification("Partida cargada")

            game_music = self.app_config.get("audio", {}).get("game_music")
            if game_music:
                self.audio_manager.play_music(game_music, loop=True)

            if self.debug:
                print(f"Partida cargada - Tiempo restante: {self.time_remaining:.1f}s")
                print(f"Total jugado: {self.total_play_time:.1f}s")

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification("Error al cargar partida")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def save_game(self):
        try:
            if not self.player or not self.city:
                return False

            # Actualizar estadísticas antes de guardar
            current_time = time.time()
            if self.game_start_time > 0 and self.last_update_time > 0:
                frame_time = current_time - self.last_update_time
                self.total_play_time += frame_time
                self.last_update_time = current_time  # Actualizar para que no haya saltos

            # Guardar estadísticas actualizadas
            self.game_stats["play_time"] = self.total_play_time
            self.game_stats["time_remaining"] = self.time_remaining

            success = self.save_manager.save_game(
                self.player, self.city, self.orders_data, self.game_stats
            )

            if success:
                self.show_notification("Partida guardada")
                if self.debug:
                    print(f"Guardado - Tiempo restante: {self.time_remaining:.1f}s")
                    print(f"Total jugado: {self.total_play_time:.1f}s")
            else:
                self.show_notification("Error al guardar")

            return success

        except Exception as e:
            print(f"Error crítico al guardar: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification("Error al guardar")
            return False

    # State Control (Pause / Resume / Menu)
    def pause_game(self):
        if self.state_manager.current_state == GameState.PLAYING:
            self.state_manager.change_state(GameState.PAUSED)
            if hasattr(self, 'audio_manager'):
                self.audio_manager.pause_music()

    def resume_game(self):
        if self.state_manager.current_state == GameState.PAUSED:
            self.state_manager.change_state(GameState.PLAYING)
            if hasattr(self, 'audio_manager'):
                self.audio_manager.resume_music()

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

        # Cambiar estado PRIMERO
        self.state_manager.change_state(GameState.MAIN_MENU)

        # LUEGO cambiar música del menú
        menu_music = self.app_config.get("audio", {}).get("menu_music")
        if menu_music:
            self.audio_manager.play_music(menu_music, loop=True)

    # Initialization Helpers

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

        t0 = time.perf_counter()
        self.weather_system = WeatherSystem(self.api_client, self.app_config)
        t1 = time.perf_counter()
        self._perf_accum_game["weather"] += (t1 - t0)

        self.orders_window = ordersWindow(self)
        if hasattr(self, 'width') and hasattr(self, 'height'):
            self.orders_window.ensure_initial_position(self.width, self.height)

    # python
    # file: 'game/game.py'
    def _setup_orders(self):
        # Reset
        self.pending_orders = []
        orders_list = []

        # 1) Try API

        try:
            if self.debug:
                print("Loading orders (API -> cache -> backup)...")
            data = self.api_client.get_orders() if self.api_client else None
        except Exception as e:
            if self.debug:
                print(f"Orders load error: {e}")
            data = None

        # Extract list from API shape
        if isinstance(data, dict) and isinstance(data.get("orders"), list):
            orders_list = data["orders"]
        elif isinstance(data, list):
            orders_list = data

        # 2) Manual local fallback without editing API:
        # Try 'api_cache/pedidos.json' first, then 'data/pedidos.json'
        if not orders_list:
            cache_dir = self.files_conf.get("cache_directory") or os.path.join(os.getcwd(), "api_cache")
            candidates = [
                os.path.join(cache_dir, "pedidos.json"),
                os.path.join(os.getcwd(), "data", "pedidos.json"),
            ]
            for path in candidates:
                try:
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            local = json.load(f)
                        if isinstance(local, dict) and isinstance(local.get("orders"), list):
                            orders_list = local["orders"]
                        elif isinstance(local, list):
                            orders_list = local
                        if orders_list:
                            if self.debug:
                                print(f"Loaded orders from backup: {path} ({len(orders_list)})")
                            break
                except Exception as e:
                    if self.debug:
                        print(f"Backup load failed {path}: {e}")

        if self.debug:
            print(f"Orders fetched: {len(orders_list)}")

        def _parse_xy(v):
            if isinstance(v, (list, tuple)) and len(v) == 2:
                return int(v[0]), int(v[1])
            return None

        def _time_limit_from_deadline(deadline_str: str, default_sec: float = 600.0) -> float:
            if not deadline_str:
                return default_sec
            try:
                s = str(deadline_str)
                if s.endswith("Z"):
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                else:
                    dt = datetime.fromisoformat(s)
                    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                return max(60.0, (dt - now).total_seconds())
            except Exception:
                return default_sec

        # Build Order objects (attributes para ordersWindow)
        orders_objs = []
        for it in orders_list:
            try:
                oid = str(it.get("id") or f"ORD-{random.randint(1000, 9999)}")
                pickup = _parse_xy(it.get("pickup"))
                dropoff = _parse_xy(it.get("dropoff"))
                if not pickup or not dropoff:
                    continue

                payout = float(it.get("payout", 0))
                deadline = str(it.get("deadline", ""))
                time_limit = _time_limit_from_deadline(deadline, 600.0)

                order = Order(
                    order_id=oid,
                    pickup_pos=pickup,
                    dropoff_pos=dropoff,
                    payment=payout,
                    time_limit=time_limit,
                    weight=it.get("weight"),
                    priority=int(it.get("priority", 0)),
                    deadline=deadline,
                    release_time=int(it.get("release_time", 0)),
                )
                orders_objs.append(order)

                # *** AGREGAR GENERACIÓN DE PUERTAS AQUÍ ***
                if self.renderer and self.city:
                    px, py = pickup
                    if 0 <= px < self.city.width and 0 <= py < self.city.height:
                        p1, p2 = utils.find_nearest_building(self.city, px, py)
                        if 0 <= p1 < self.city.width and 0 <= p2 < self.city.height:
                            self.renderer.generate_door_at(p1, p2)


                    # Generate door at dropoff
                    dx, dy = dropoff
                    if 0 <= dx < self.city.width and 0 <= dy < self.city.height:
                        d1, d2 = utils.find_nearest_building(self.city, dx, dy)
                        if 0 <= d1 < self.city.width and 0 <= d2 < self.city.height:
                            self.renderer.generate_door_at(d1, d2)

            except Exception as e:
                if self.debug:
                    print(f"Skipping invalid order: {e}")
        self.pending_orders = orders_objs
        if self.orders_window:
            self.orders_window.set_pending_orders(self.pending_orders)
        if self.debug:
            print(f"{len(self.pending_orders)} active orders ready")

    # Notifications
    def show_notification(self, message: str, duration: float = 2.0):
        self.notification_message = message
        self.notification_timer = duration
        if self.debug:
            f = max(1, self._perf_accum_game["frames"])
            api_ms = (self._perf_accum_game["api"] / f) * 1000
            inv_ms = (self._perf_accum_game["inventory"] / f) * 1000
            orders_ms = (self._perf_accum_game["orders"] / f) * 1000
            weather_ms = (self._perf_accum_game["weather"] / f) * 1000
            print(
                f"[GamePerf] (setup) api={api_ms:.2f}ms inventory={inv_ms:.2f}ms orders={orders_ms:.2f}ms weather={weather_ms:.2f}ms")

    def _check_game_end_conditions(self):
        """Verificar condiciones de victoria/derrota"""
        if not self.player:
            return

        # Verificar tiempo agotado
        if self.time_remaining <= 0:
            self._end_game(False, "¡Tiempo agotado!")
            return

        # Verificar reputación crítica
        if self.player.is_reputation_critical():
            self._end_game(False, "¡Reputación muy baja!")
            return

        # Verificar victoria (meta de dinero alcanzada)
        goal_earnings = getattr(self.city, 'goal', self.app_config.get("game", {}).get("goal_earnings", 3000))
        if self.player.earnings >= goal_earnings:
            # Calcular bonus por terminar temprano
            time_bonus = max(0, self.time_remaining / self.time_limit)
            bonus_message = f"¡Victoria! Bonus de tiempo: +{time_bonus * 100:.0f}%"
            self._end_game(True, bonus_message)
            return

    def _end_game(self, victory: bool, message: str):
        """Terminar el juego con victoria o derrota"""
        if victory:
            self.show_notification(f"🎉 {message}")
        else:
            self.show_notification(f"💀 {message}")

        # TODO: Aquí se podría cambiar a un estado de GAME_OVER
        # Por ahora volvemos al menú principal después de un delay
        self.return_to_main_menu()

    # Frame Rendering

    def on_draw(self):
        self.clear()
        state = self.state_manager.current_state
        if state == GameState.MAIN_MENU and self.state_manager.main_menu:
            self.state_manager.main_menu.draw()
        elif state == GameState.PLAYING:
            self._draw_game()
        elif state == GameState.PAUSED:
            self._draw_game()
            if self.state_manager.pause_menu:
                self.state_manager.pause_menu.draw()
        elif state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.draw()

        self._draw_notifications()

        # Dibujar ventana de pedidos si existe

    def _draw_game(self):
        if not self.renderer or not self.player:
            return
        self.renderer.render_world(self.player, weather_system=self.weather_system)
        self.renderer.render_minimap(10, 10, 160, self.player)

        # Asegurar coordenadas de pantalla para HUD/ventanas

        self._draw_hud()
        if self.player and self.city:
            self._draw_bike_speedometer()
        if self.orders_window and (self.orders_window.is_open or self.orders_window.animation_progress > 0):
            self.orders_window.draw()

    def _draw_earnings_progress_top(self, earnings: float, goal_earnings: float):
        """Centered, compact earnings bar at the top."""
        bar_width = 260
        bar_height = 18
        center_x = self.width // 2
        bar_x1 = center_x - bar_width // 2 - 10
        bar_x2 = bar_x1 + bar_width
        bar_y1 = self.height - 44
        bar_y2 = bar_y1 + bar_height

        # Background
        arcade.draw_lrbt_rectangle_filled(bar_x1, bar_x2, bar_y1, bar_y2, (0, 0, 0, 180))
        arcade.draw_lrbt_rectangle_outline(bar_x1, bar_x2, bar_y1, bar_y2, arcade.color.WHITE, 2)

        # Progress
        progress = max(0.0, min(1.0, (earnings / goal_earnings) if goal_earnings > 0 else 0.0))
        fill_w = int((bar_x2 - bar_x1 - 2) * progress)
        if fill_w > 0:
            if progress < 0.33:
                fill_color = arcade.color.DARK_RED
            elif progress < 0.66:
                fill_color = arcade.color.YELLOW
            else:
                fill_color = arcade.color.GREEN
            arcade.draw_lrbt_rectangle_filled(bar_x1 + 1, bar_x1 + 1 + fill_w, bar_y1 + 1, bar_y2 - 1, fill_color)

        # Label
        pct = progress * 100.0
        label = f"${earnings:.0f} / ${goal_earnings:.0f} ({pct:.1f}%)"
        label_x = bar_x1 + (bar_x2 - bar_x1) // 2
        label_y = bar_y1 + 2
        arcade.draw_text(label, label_x, label_y, arcade.color.WHITE, 12, anchor_x="center")

    def _draw_time_countdown_top(self, time_str: str, time_color: tuple):
        arcade.draw_text(f"Time: {time_str}", 10, self.height - 22, time_color, 18)


    def _speedo_anchor(self):
        """Approximate speedometer area anchor (center and radius)."""
        right_margin = 80
        bottom_margin = 30
        radius = 70
        center_x = self.width - right_margin - radius
        center_y = bottom_margin + 90
        return center_x, center_y, radius


    def _draw_hud(self):
        earnings = self.player.earnings if self.player else 0.0
        reputation = self.player.reputation if self.player else 0.0

        if self.player:
            inventory_width = 450
            inventory_height = 400
            inventory_x = self.width - inventory_width - 50
            inventory_y = self.height - inventory_height - 50
            self.player.inventory.draw_inventory(inventory_x, inventory_y, inventory_width, inventory_height)

        #only if debug = True
        if self.frame_times and self.debug:
            dt_list = self.frame_times[-60:]
            avg_dt = (sum(dt_list) / len(dt_list)) if dt_list else 0.0
            avg_fps = (1.0 / avg_dt) if avg_dt > 0 else 0.0
            self.hud_performance.position = (10, self.height - 60)
            rays = self.renderer.num_rays if self.renderer else 0
            self.hud_performance.text = f"FPS: {avg_fps:.1f} | Rays: {rays}"
            self.hud_performance.draw()

        self.hud_player_location.position = (10, self.height - 80)
        if self.player and self.debug:
            self.hud_player_location.text = f"Pos: ({self.player.x:.1f}, {self.player.y:.1f}) Angle: {self.player.angle:.2f} rad"
            self.hud_player_location.draw()


        # Remaining game time (text + color, top-left info line)

        time_str = format_time(self.time_remaining)
        goal_earnings = getattr(self.city, 'goal', 3000) if self.city else 3000
        progress = (earnings / goal_earnings) * 100 if goal_earnings > 0 else 0

        if self.time_remaining < 120:
            time_color = arcade.color.RED
        elif self.time_remaining < 300:
            time_color = arcade.color.YELLOW
        else:
            time_color = arcade.color.WHITE

        # Top-left countdown (kept) and centered compact earnings bar
        self._draw_earnings_progress_top(earnings, goal_earnings)
        self._draw_time_countdown_bottom(time_str, time_color)

        # Stamina bar (bottom-right)
        if self.player:
            bar_width = 200
            bar_height = 20
            bar_x = self.width - bar_width - 80
            bar_y = 30
            stamina = self.player.stamina
            max_stamina = getattr(self.player, 'max_stamina', 100)
            stamina_percent = max(0.0, min(1.0, stamina / max_stamina))
            arcade.draw_lrbt_rectangle_filled(bar_x, bar_x + bar_width, bar_y, bar_y + bar_height, arcade.color.BLACK)
            if stamina_percent > 0:
                green_width = int(bar_width * stamina_percent)
                arcade.draw_lrbt_rectangle_filled(bar_x, bar_x + green_width, bar_y, bar_y + bar_height, arcade.color.GREEN)
            arcade.draw_lrbt_rectangle_outline(bar_x, bar_x + bar_width, bar_y, bar_y + bar_height, arcade.color.WHITE, 2)
            stamina_text = f"{stamina:.0f}/{max_stamina:.0f}"
            arcade.draw_text(stamina_text, bar_x + bar_width + 10, bar_y + (bar_height // 2) - 6, arcade.color.WHITE, 12)

        # Reputation bar (bottom-right)
        if self.player:
            rep_bar_width = 200
            rep_bar_height = 20
            rep_bar_x = self.width - rep_bar_width - 80
            rep_bar_y = 60
            reputation = self.player.reputation
            max_reputation = 100
            rep_percent = max(0.0, min(1.0, reputation / max_reputation))
            arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y, rep_bar_y + rep_bar_height, arcade.color.BLACK)
            if rep_percent > 0:
                color = arcade.color.YELLOW if rep_percent < 0.7 else arcade.color.PINK
                fill_width = int(rep_bar_width * rep_percent)
                arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + fill_width, rep_bar_y, rep_bar_y + rep_bar_height, color)
            arcade.draw_lrbt_rectangle_outline(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y, rep_bar_y + rep_bar_height, arcade.color.WHITE, 2)
            rep_text = f"{reputation:.0f}/100"
            arcade.draw_text(rep_text, rep_bar_x + rep_bar_width + 10, rep_bar_y + (rep_bar_height // 2) - 6, arcade.color.WHITE, 12)

        # Weather icon: to the right of the speedometer (above the bars)
        self._draw_weather_icon_right_of_speedometer()
        arcade.draw_text("ESC - Pausa", self.width - 100, self.height - 30, arcade.color.WHITE, 12, anchor_x="center")

    def _draw_notifications(self):
        if self.notification_timer > 0 and self.notification_message:
            msg_width = len(self.notification_message) * 12 + 20
            msg_height = 40
            msg_x = (self.width - msg_width) // 2
            msg_y = self.height - 150
            arcade.draw_lrbt_rectangle_filled(msg_x, msg_x + msg_width, msg_y, msg_y + msg_height, (0, 0, 0, 180))
            arcade.draw_lrbt_rectangle_outline(msg_x, msg_x + msg_width, msg_y, msg_y + msg_height, arcade.color.WHITE, 2)
            arcade.draw_text(self.notification_message, self.width // 2, msg_y + msg_height // 2 - 6, arcade.color.WHITE, 16, anchor_x="center")

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


    # Per-Frame Update

    def on_update(self, delta_time: float):
        # Actualizar notificaciones siempre (independiente del estado)
        if self.notification_timer > 0:
            self.notification_timer -= delta_time

        # Actualizar menú de settings si está activo
        if self.state_manager.current_state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.update(delta_time)
            return  # No procesar el resto si estamos en settings

        # Si no estamos jugando, no actualizar el juego
        if self.state_manager.current_state != GameState.PLAYING:
            return

        # --- A PARTIR DE AQUÍ SOLO SE EJECUTA SI state == PLAYING ---

        current_time = time.time()
        if self.game_start_time > 0:
            if self.last_update_time == 0:
                self.last_update_time = current_time
            else:
                frame_time = current_time - self.last_update_time
                self.total_play_time += frame_time
                self.time_remaining -= frame_time  # Reducir tiempo restante
                self.last_update_time = current_time

        # Verificar condiciones de fin de juego
        self._check_game_end_conditions()

        # Actualizar animación del inventario
        if self.player and hasattr(self.player, 'inventory'):
            self.player.inventory.update_animation(delta_time)

        # Actualizar sistema de clima
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

        # Rotación del jugador
        if self._turn_left:
            self.player.turn_left(delta_time)
        if self._turn_right:
            self.player.turn_right(delta_time)

        # Movimiento del jugador
        prev_x, prev_y = self.player.x, self.player.y
        dx = dy = 0.0
        if self._move_forward or self._move_backward:
            fx, fy = self.player.get_forward_vector()
            if self._move_forward:
                dx += fx
                dy += fy
            if self._move_backward:
                dx -= fx * self.backward_factor
                dy -= fy * self.backward_factor
        if dx != 0.0 or dy != 0.0:
            self.player.move(dx, dy, delta_time, self.city)

        # Calcular velocidad para el speedometer
        moved = (abs(self.player.x - prev_x) > 1e-5) or (abs(self.player.y - prev_y) > 1e-5)
        if moved:
            base_speed = self.player.calculate_effective_speed(self.city)
            move_scale = math.hypot(dx, dy)
            self.last_move_scale = move_scale
            target_speed = base_speed * move_scale
        else:
            target_speed = 0.0
            self.last_move_scale = 0.0

        # Suavizar velocidad mostrada
        speed_diff = target_speed - self.displayed_speed
        self.displayed_speed += speed_diff * self.speed_smoothing * delta_time
        if abs(speed_diff) < 0.01:
            self.displayed_speed = target_speed
        if not moved and abs(self.displayed_speed) < 0.05:
            self.displayed_speed = 0.0

        # Actualizar estado del jugador
        self.player.update(delta_time)

        # recoger/entregar pedidos al estar cerca de las casillas
        self._check_pickup_and_delivery()


        if self.orders_window:
            self.orders_window.update_animation(delta_time)


    # Input Handling

    def on_key_press(self, symbol: int, modifiers: int):
        # ESC handling PRIMERO (antes de verificar estados)
        if symbol == arcade.key.ESCAPE:
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
        # Manejar input según el estado actual
        state = self.state_manager.current_state
        if state == GameState.PLAYING:
            # Teclas de movimiento
            if symbol in (arcade.key.W, arcade.key.UP):
                self._move_forward = True
            elif symbol in (arcade.key.S, arcade.key.DOWN):
                self._move_backward = True
            elif symbol in (arcade.key.A, arcade.key.LEFT):
                self._turn_left = True
            elif symbol in (arcade.key.D, arcade.key.RIGHT):
                self._turn_right = True
            elif symbol == arcade.key.F5:
                self.save_game()
            elif symbol == arcade.key.Q:
                self._cycle_inventory_order(reverse=bool(modifiers & arcade.key.MOD_SHIFT))
            elif symbol == arcade.key.TAB:
                self._toggle_inventory_sort()
            elif symbol == arcade.key.I:
                self._toggle_inventory()
            # *** MOVER LA TECLA O AQUÍ (estado PLAYING) ***
            elif symbol == arcade.key.O:
                if self.orders_window:
                    self.orders_window.ensure_initial_position(self.width, self.height)
                    if self.orders_window.toggle_open():
                        if self.orders_window.is_open:
                            window_x = (self.width - self.orders_window.panel_width) // 2
                            window_y = (self.height - self.orders_window.panel_height) // 2
                            self.orders_window.set_target_position(window_x, window_y)
                            self.show_notification("Ventana de pedidos abierta")
                        else:
                            self.show_notification("Ventana de pedidos cerrada")
                return  # Importante: return para evitar procesamiento adicional
            # Navegación en ventana de pedidos (solo si está abierta)
            if self.orders_window and self.orders_window.is_open:
                if symbol == arcade.key.UP:
                    self.orders_window.previous_order()
                    return
                elif symbol == arcade.key.DOWN:
                    self.orders_window.next_order()
                    return
                elif symbol == arcade.key.A:  # Aceptar pedido
                    if not self.orders_window.accept_order():
                        self.show_notification("No hay capacidad para este pedido")
                    return
                elif symbol == arcade.key.C:  # Cancelar pedido
                    self.orders_window.cancel_order()
                    return
            # Debug keys para clima (solo si debug está activo)
            if self.debug:
                if symbol == arcade.key.KEY_1 and self.weather_system:
                    self.weather_system.force_weather_change("clear")
                    self.show_notification("Clima forzado: Despejado")
                elif symbol == arcade.key.KEY_2 and self.weather_system:
                    self.weather_system.force_weather_change("rain")
                    self.show_notification("Clima forzado: Lluvia")
                elif symbol == arcade.key.KEY_3 and self.weather_system:
                    self.weather_system.force_weather_change("storm")
                    self.show_notification("Clima forzado: Tormenta")
                elif symbol == arcade.key.KEY_4 and self.weather_system:
                    self.weather_system.force_weather_change("fog")
                    self.show_notification("Clima forzado: Niebla")
                elif symbol == arcade.key.KEY_5 and self.weather_system:
                    self.weather_system.force_weather_change("wind")
                    self.show_notification("Clima forzado: Viento")
                elif symbol == arcade.key.KEY_6 and self.weather_system:
                    self.weather_system.force_weather_change("heat")
                    self.show_notification("Clima forzado: Calor")
                elif symbol == arcade.key.KEY_7 and self.weather_system:
                    self.weather_system.force_weather_change("cold")
                    self.show_notification("Clima forzado: Frío")
        elif state == GameState.MAIN_MENU:
            if self.state_manager.main_menu:
                self.state_manager.main_menu.handle_key_press(symbol, modifiers)
        elif state == GameState.PAUSED:
            if self.state_manager.pause_menu:
                self.state_manager.pause_menu.handle_key_press(symbol, modifiers)
        elif state == GameState.SETTINGS:
            if self.state_manager.settings_menu:
                self.state_manager.settings_menu.handle_key_press(symbol, modifiers)

    def _toggle_inventory(self):
        """Alterna la visibilidad del inventario"""
        if self.player and hasattr(self.player, 'inventory'):
            self.player.inventory.toggle_open()
            if self.player.inventory.is_open:
                self.show_notification("Inventario abierto")
            else:
                self.show_notification("Inventario cerrado")

    def on_key_release(self, symbol: int, modifiers: int):
        if self.state_manager.current_state != GameState.PLAYING:
            return
        if symbol in (arcade.key.W, arcade.key.UP):
            self._move_forward = False
        elif symbol in (arcade.key.S, arcade.key.DOWN):
            self._move_backward = False
        elif symbol in (arcade.key.A, arcade.key.LEFT):
            self._turn_left = False
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self._turn_right = False

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        self.hud_fps.position = (10, height - 20)
        self.hud_stats.position = (10, height - 40)
        self.hud_performance.position = (10, height - 60)
        self.hud_weather.position = (10, height - 100)
        self.hud_time.position = (10, height - 120)

    # Inventory / Orders Helpers

    def _cycle_inventory_order(self, reverse: bool = False):
        """Select next or previous order in player's inventory."""
        if not self.player or not getattr(self.player, "inventory", None):
            return
        inv = self.player.inventory
        if not inv.orders:
            self.show_notification("Sin pedidos", 1.0)
            return
        if reverse:
            inv.previous_order()
        else:
            inv.next_order()
        cur = inv.get_current_order()
        if cur:
            self.show_notification(f"Pedido: {cur.id[:8]}  $ {cur.payout:.0f}", 1.2)

    def _toggle_inventory_sort(self):
        """Toggle sort mode between priority and deadline."""
        if not self.player or not getattr(self.player, "inventory", None):
            return
        inv = self.player.inventory
        if inv.sort_mode == "priority":
            inv.sort_by_deadline()
        else:
            inv.sort_by_priority()
        self.show_notification(f"Orden: {inv.sort_mode}", 1.2)

        



    # HUD Components

    def _draw_bike_speedometer(self):
        speed = self.displayed_speed
        max_speed = self.player.base_speed * 1.2
        speed_percent = min(1.0, speed / max_speed)

        bar_x = self.width - 200 - 80
        center_x = bar_x + 235
        center_y = 150
        radius = 35

        max_jitter_kmh = 1.5
        jitter_units = max_jitter_kmh / 10.0
        if speed > 0.05:
            variation_intensity = min(1.0, speed / max(0.001, self.player.base_speed))
            speed_variation = random.uniform(-jitter_units, jitter_units) * variation_intensity
            varied_speed = max(0.0, speed + speed_variation)
            varied_speed_percent = min(1.0, varied_speed / max_speed)
        else:
            varied_speed = speed
            varied_speed_percent = speed_percent

        arcade.draw_circle_filled(center_x, center_y, radius + 3, (40, 40, 40))
        arcade.draw_circle_outline(center_x, center_y, radius + 3, arcade.color.WHITE, 2)

        start_angle = 135
        end_angle = 405

        for angle in range(start_angle, end_angle, 3):
            rad = math.radians(angle)
            x1 = center_x + math.cos(rad) * (radius - 6)
            y1 = center_y + math.sin(rad) * (radius - 6)
            x2 = center_x + math.cos(rad) * (radius - 2)
            y2 = center_y + math.sin(rad) * (radius - 2)
            arcade.draw_line(x1, y1, x2, y2, (80, 80, 80), 2)

        speed_angle_range = int((end_angle - start_angle) * varied_speed_percent)
        for angle in range(start_angle, start_angle + speed_angle_range, 3):
            rad = math.radians(angle)
            x1 = center_x + math.cos(rad) * (radius - 6)
            y1 = center_y + math.sin(rad) * (radius - 6)
            x2 = center_x + math.cos(rad) * (radius - 2)
            y2 = center_y + math.sin(rad) * (radius - 2)
            if varied_speed_percent < 0.3:
                color = arcade.color.GREEN
            elif varied_speed_percent < 0.7:
                color = arcade.color.YELLOW
            else:
                color = arcade.color.RED
            arcade.draw_line(x1, y1, x2, y2, color, 3)

        needle_angle = start_angle + (end_angle - start_angle) * varied_speed_percent
        needle_rad = math.radians(needle_angle)
        needle_x = center_x + math.cos(needle_rad) * (radius - 8)
        needle_y = center_y + math.sin(needle_rad) * (radius - 8)
        arcade.draw_line(center_x, center_y, needle_x, needle_y, arcade.color.WHITE, 2)
        arcade.draw_circle_filled(center_x, center_y, 3, arcade.color.WHITE)

        for i in range(5):
            mark_percent = i / 4.0
            mark_angle = start_angle + (end_angle - start_angle) * mark_percent
            radm = math.radians(mark_angle)
            x1 = center_x + math.cos(radm) * (radius - 4)
            y1 = center_y + math.sin(radm) * (radius - 4)
            x2 = center_x + math.cos(radm) * (radius - 1)
            y2 = center_y + math.sin(radm) * (radius - 1)
            arcade.draw_line(x1, y1, x2, y2, arcade.color.WHITE, 2)

        speed_kmh = varied_speed * 10.0
        arcade.draw_text(f"{speed_kmh:.0f}", center_x, center_y - 10, arcade.color.WHITE, 14, anchor_x="center")
        arcade.draw_text("km/h", center_x, center_y - 22, arcade.color.LIGHT_GRAY, 8, anchor_x="center")

        state_colors = {
            "normal": arcade.color.GREEN,
            "tired": arcade.color.YELLOW,
            "exhausted": arcade.color.RED
        }
        state_color = state_colors.get(self.player.state, arcade.color.WHITE)
        arcade.draw_circle_filled(center_x, center_y + 18, 4, state_color)


    def _draw_time_countdown_bottom(self, time_str: str, time_color: tuple):
        """Bottom-center countdown pill."""
        pill_width = 220
        pill_height = 26
        cx = self.width // 2
        y_bottom = 10
        x1 = cx - pill_width // 2
        x2 = cx + pill_width // 2
        y1 = y_bottom
        y2 = y_bottom + pill_height

        arcade.draw_lrbt_rectangle_filled(x1, x2, y1, y2, (0, 0, 0, 160))
        arcade.draw_lrbt_rectangle_outline(x1, x2, y1, y2, arcade.color.WHITE, 2)
        arcade.draw_text(f"Remaining: {time_str}", cx, y1 + 5, time_color, 14, anchor_x="center")

    def _speedo_anchor(self):
        """Approximate speedometer area anchor (center and radius)."""
        right_margin = 80
        bottom_margin = 30
        radius = 70
        center_x = self.width - right_margin - radius
        center_y = bottom_margin + 90
        return center_x, center_y, radius

    # python
    # file: 'game/game.py'

    def _draw_weather_icon_chip_bg(self, x: int, y: int, w: int, h: int):
        """Draw the icon chip background at top-left (x,y)."""
        arcade.draw_lrbt_rectangle_filled(x, x + w, y, y + h, (0, 0, 0, 140))
        arcade.draw_lrbt_rectangle_outline(x, x + w, y, y + h, arcade.color.WHITE, 2)

    def _draw_weather_cloud(self, cx: int, cy: int, scale: float = 1.0, color=(255, 255, 255)):
        """Draw a cloud centered at (cx, cy)."""
        w = int(40 * scale)
        h = int(20 * scale)
        arcade.draw_circle_filled(cx - w // 3, cy, h // 2 + 6, color)
        arcade.draw_circle_filled(cx, cy + 4, h // 2 + 8, color)
        arcade.draw_circle_filled(cx + w // 3, cy, h // 2 + 6, color)
        arcade.draw_ellipse_filled(cx, cy - 4, w, h, color)

    def _draw_weather_rain(self, cx: int, cy: int, drops: int = 6, spread: int = 34, length: int = 10,
                           color=(120, 180, 255)):
        """Draw rain centered horizontally at (cx, cy)."""
        left = cx - spread // 2
        step = max(1, spread // max(1, drops - 1))
        for i in range(drops):
            x = left + i * step
            y1r = cy - 6
            y2r = y1r - int(length * (0.8 + 0.4 * random.random()))
            arcade.draw_line(x, y1r, x, y2r, color, 2)

    def _draw_weather_lightning(self, cx: int, cy: int, color=(255, 255, 100)):
        """Draw a simple lightning bolt around (cx, cy)."""
        p1 = (cx - 6, cy + 6)
        p2 = (cx + 0, cy + 2)
        p3 = (cx - 3, cy - 2)
        p4 = (cx + 5, cy - 8)
        arcade.draw_line(*p1, *p2, color, 3)
        arcade.draw_line(*p2, *p3, color, 3)
        arcade.draw_line(*p3, *p4, color, 3)

    def _draw_weather_sun(self, cx: int, cy: int, radius: int = 10, color=(255, 220, 100)):
        """Draw a sun centered at (cx, cy)."""
        arcade.draw_circle_filled(cx, cy, radius, color)
        rays = 8
        for i in range(rays):
            ang = i * (360 / rays)
            rad = math.radians(ang)
            x1r = cx + math.cos(rad) * (radius + 2)
            y1r = cy + math.sin(rad) * (radius + 2)
            x2r = cx + math.cos(rad) * (radius + 8)
            y2r = cy + math.sin(rad) * (radius + 8)
            arcade.draw_line(x1r, y1r, x2r, y2r, color, 2)

    def _draw_weather_fog(self, cx: int, cy: int, bands: int = 3,
                          band_width: int = 52, band_height: int = 6,
                          color=(220, 220, 220, 160)):
        """Draw fog as soft horizontal bands around (cx, cy)."""
        if bands <= 0:
            return
        top = cy + 10
        for i in range(bands):
            yb = top - i * 10
            arcade.draw_lrbt_rectangle_filled( cx - band_width // 2, cx + band_width // 2, yb - band_height // 2, yb + band_height // 2, color)

    def _draw_weather_wind(self, cx: int, cy: int, swirls: int = 2, color=(200, 220, 255)):
        """Draw wind swirls around (cx, cy)."""
        for i in range(swirls):
            yb = cy + (i * 8) - 6
            arcade.draw_arc_outline(cx, yb, 40, 16, color, 10, 170, 2)
            arcade.draw_arc_outline(cx + 8, yb - 4, 28, 12, color, 10, 170, 2)

    def _draw_weather_snowflake(self, cx: int, cy: int, size: int = 10, color=(220, 240, 255)):
        """Draw a simple asterisk snowflake centered at (cx, cy)."""
        for ang in (0, 60, 120):
            rad = math.radians(ang)
            dx = math.cos(rad) * size
            dy = math.sin(rad) * size
            arcade.draw_line(cx - dx, cy - dy, cx + dx, cy + dy, color, 2)

    def _draw_weather_icon_at(self, x: int, y: int, width: int = 64, height: int = 48):
        """Draw the weather icon chip at top-left (x,y)."""
        if not self.weather_system:
            return

        info = self.weather_system.get_weather_info()
        cond = str(info.get("condition", "clear")).lower()
        intensity = float(info.get("intensity", 0.2))
        cloud_color = tuple(info.get("cloud_color", (255, 255, 255)))
        sky_color = tuple(info.get("sky_color", (135, 206, 235)))

        # Background chip
        self._draw_weather_icon_chip_bg(x, y, width, height)

        # Icon center
        icx = x + width // 2
        icy = y + height // 2

        # Scale by intensity
        t = max(0.1, min(1.0, intensity))
        rain_drops = 4 + int(6 * t)
        cloud_scale = 0.9 + 0.4 * t

        # Draw by condition
        if cond in ("clear",):
            arcade.draw_circle_filled(icx, icy, 18, (sky_color[0], sky_color[1], sky_color[2], 60))
            self._draw_weather_sun(icx, icy, radius=10 + int(4 * t), color=(255, 220, 100))
        elif cond in ("clouds",):
            self._draw_weather_cloud(icx, icy, scale=cloud_scale, color=cloud_color)
        elif cond in ("rain_light",):
            self._draw_weather_cloud(icx, icy, scale=0.95, color=cloud_color)
            self._draw_weather_rain(icx, icy - 6, drops=rain_drops // 2, length=8 + int(6 * t))
        elif cond in ("rain",):
            self._draw_weather_cloud(icx, icy, scale=1.05, color=cloud_color)
            self._draw_weather_rain(icx, icy - 6, drops=rain_drops, length=10 + int(10 * t))
        elif cond in ("storm",):
            self._draw_weather_cloud(icx, icy + 2, scale=1.05, color=(80, 80, 80))
            self._draw_weather_rain(icx, icy - 4, drops=rain_drops, length=12 + int(10 * t), color=(140, 180, 255))
            self._draw_weather_lightning(icx, icy - 2)
        elif cond in ("fog",):
            self._draw_weather_fog(icx, icy, bands=3 + (1 if t > 0.6 else 0))

        elif cond in ("wind",):
            self._draw_weather_cloud(icx - 6, icy + 2, scale=0.8, color=cloud_color)
            self._draw_weather_wind(icx + 6, icy - 2)
        elif cond in ("heat",):
            self._draw_weather_sun(icx, icy, radius=11 + int(3 * t), color=(255, 210, 90))
            arcade.draw_arc_outline(icx, icy + 10, 36, 10, (255, 220, 150), 0, 180, 2)
        elif cond in ("cold",):
            self._draw_weather_cloud(icx, icy + 6, scale=0.9, color=cloud_color)
            self._draw_weather_snowflake(icx, icy - 8, size=8 + int(4 * t))
        else:
            self._draw_weather_cloud(icx, icy, scale=0.9, color=cloud_color)
            arcade.draw_circle_filled(icx + 18, icy - 12, 3, arcade.color.WHITE)

    def _draw_weather_icon_right_of_speedometer(self):
        """Compute position relative to speedometer and draw the weather icon chip."""
        if not self.weather_system:
            return

        # Chip size
        chip_w, chip_h = 64, 48

        # Base position: to the right of the speedometer
        cx, cy, r = self._speedo_anchor()
        base_x = cx + r + 12  # to the right edge of the dial
        base_y_center = cy + 28  # slightly above dial center (over the bars)

        x = int(base_x - 100)
        x = max(10, min(self.width - chip_w - 10, x))

        y = int(base_y_center - chip_h // 2)
        y = max(10, min(self.height - chip_h - 10, y))

        # Draw at computed position
        self._draw_weather_icon_at(x, y, chip_w, chip_h)




    def _distance_player_to(self, tx: float, ty: float) -> float:
        """Calculate distance from player to (x,y)."""
        if not self.player:
            return float('inf')
        dx = self.player.x - tx
        dy = self.player.y - ty
        return math.hypot(dx, dy)
    
    def _check_pickup_and_delivery(self):
        """Check if player is near any pickup or dropoff point to pick up or deliver orders."""
         # Asegurarse de que el jugador y el inventario existen
        if not self.player or not getattr(self.player, "inventory", None):
            return
        inv = self.player.inventory
        radius = getattr(self, "pickup_radius", 1.5)

        # Copia porque podemos eliminar pedidos al entregar
        for order in list(inv.orders):
            # 1) Recoger: pedido aceptado pero no recogido aún
            if getattr(order, "status", "") == "in_progress":
                px, py = order.pickup_pos
                if self._distance_player_to(px, py) <= radius:
                    order.pickup()  # cambia a PICKED_UP
                    self.show_notification(f"Recogido {order.id}")
                    continue  # pasar a siguiente

            # 2) Entregar: pedido ya recogido
            if getattr(order, "status", "") == "picked_up":
                dx, dy = order.dropoff_pos
                if self._distance_player_to(dx, dy) <= radius:
                    order.deliver()
                    payout = float(getattr(order, "payout", getattr(order, "payment", 0.0)))
                    self.player.add_earnings(payout)
                    self.player.update_reputation_for_delivery(order)
                    self.player.remove_order_from_inventory(order.id)
                    self.show_notification(f"Entregado {order.id}  +${payout:.0f}")
