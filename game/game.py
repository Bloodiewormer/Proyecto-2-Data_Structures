import traceback

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
from game.input.handler import InputHandler
from game.ui.hud import HUDRenderer
from game.player import Player
from game.rendering.world_renderer import RayCastRenderer
from game.ui.minimap import MinimapRenderer
from game.ui.notifications import NotificationManager
from game.weather import WeatherSystem
from game.gamestate import GameStateManager, GameState
from game.SaveManager import SaveManager
from game.audio import AudioManager
from . import utils
from .orders import Order
from .ordersWindow import ordersWindow
from game.score import ScoreManager, ScoreScreen


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

        self.pickup_radius = self.app_config.get("game", {}).get("pickup_radius", 1.5)

        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        self.displayed_speed = 0.0
        self.speed_smoothing = 3.0

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

        self.orders_window = None
        self.orders_window_active = False

        self.score_manager = ScoreManager(self.files_conf)
        self.score_screen: Optional[ScoreScreen] = None
        self.game_over_active = False

        self.order_release_interval = self.app_config.get("game", {}).get("order_release_seconds", 120)
        self._orders_queue: list[tuple[float, Order]] = []
        self.pending_orders: list[Order] = []

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
            self.time_remaining = self.time_limit
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
            traceback.print_exc()
            self.show_notification("Error al cargar partida")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def save_game(self):
        try:
            if not self.player or not self.city:
                return False

            current_time = time.time()
            if self.game_start_time > 0 and self.last_update_time > 0:
                frame_time = current_time - self.last_update_time
                self.total_play_time += frame_time
                self.last_update_time = current_time

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
            traceback.print_exc()
            self.show_notification("Error al guardar")
            return False

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

    def _setup_orders(self):
        self.pending_orders = []
        orders_list = []

        try:
            if self.debug:
                print("Cargando pedidos desde API...")
            data = self.api_client.get_orders() if self.api_client else None
        except Exception as e:
            if self.debug:
                print(f"Error al cargar pedidos desde API: {e}")
            data = None

        if isinstance(data, dict) and isinstance(data.get("data"), list):
            orders_list = data["data"]
        elif isinstance(data, list):
            orders_list = data

        if not orders_list:
            try:
                backup_file = os.path.join(self.files_conf.get("data_directory", "data"), "pedidos.json")
                if os.path.exists(backup_file):
                    with open(backup_file, "r", encoding="utf-8") as f:
                        local = json.load(f)

                    if isinstance(local, dict):
                        if isinstance(local.get("data"), list):
                            orders_list = local["data"]
                        elif isinstance(local.get("orders"), list):
                            orders_list = local["orders"]
                    elif isinstance(local, list):
                        orders_list = local

                    if orders_list and self.debug:
                        print(f"Pedidos cargados desde backup: {backup_file} ({len(orders_list)})")
            except Exception as e:
                if self.debug:
                    print(f"Error al cargar pedidos desde backup: {e}")

        if self.debug:
            print(f"Total de pedidos cargados: {len(orders_list)}")

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

        def _in_bounds(x, y):
            return 0 <= x < self.city.width and 0 <= y < self.city.height

        def _is_street(x, y):
            try:
                return self.city.tiles[y][x] == "C"
            except Exception:
                return False

        def _nearest_street_from(x0, y0, max_radius=64):
            if not self.city:
                return None
            if _in_bounds(x0, y0) and _is_street(x0, y0):
                return (x0, y0)

            best = None
            best_d2 = float("inf")
            for r in range(1, max_radius + 1):
                for dx in range(-r, r + 1):
                    for dy in (-r, r):
                        x, y = x0 + dx, y0 + dy
                        if _in_bounds(x, y) and _is_street(x, y):
                            d2 = (x - x0) * (x - x0) + (y - y0) * (y - y0)
                            if d2 < best_d2:
                                best, best_d2 = (x, y), d2
                for dy in range(-r + 1, r):
                    for dx in (-r, r):
                        x, y = x0 + dx, y0 + dy
                        if _in_bounds(x, y) and _is_street(x, y):
                            d2 = (x - x0) * (x - x0) + (y - y0) * (y - y0)
                            if d2 < best_d2:
                                best, best_d2 = (x, y), d2
                if best is not None:
                    return best
            return None

        def _snap_to_accessible_or_force(pos):
            if not self.city or not pos:
                return None
            px, py = pos

            if _in_bounds(px, py) and _is_street(px, py):
                nb = utils.find_nearest_building(self.city, px, py)
                return (px, py), nb

            nb = utils.find_nearest_building(self.city, px, py)
            bx, by = nb if nb else (px, py)

            for nx, ny in ((bx + 1, by), (bx - 1, by), (bx, by + 1), (bx, by - 1)):
                if _in_bounds(nx, ny) and _is_street(nx, ny):
                    return (nx, ny), nb

            for nx in (bx - 1, bx, bx + 1):
                for ny in (by - 1, by, by + 1):
                    if (nx, ny) != (bx, by) and _in_bounds(nx, ny) and _is_street(nx, ny):
                        return (nx, ny), nb

            near_street = _nearest_street_from(bx, by, max_radius=96)
            if near_street:
                return near_street, nb

            near_street = _nearest_street_from(px, py, max_radius=96)
            if near_street:
                nn_b = utils.find_nearest_building(self.city, near_street[0], near_street[1])
                return near_street, nn_b

            return None

        orders_objs = []
        for it in orders_list:
            try:
                oid = str(it.get("id") or f"ORD-{random.randint(1000, 9999)}")
                pickup_raw = _parse_xy(it.get("pickup"))
                dropoff_raw = _parse_xy(it.get("dropoff"))
                if not pickup_raw or not dropoff_raw:
                    if self.debug:
                        print(f"Saltando pedido {oid}: pickup/dropoff inválidos")
                    continue

                snap_p = _snap_to_accessible_or_force(pickup_raw)
                snap_d = _snap_to_accessible_or_force(dropoff_raw)

                if not snap_p or not snap_d:
                    if self.debug:
                        print(f"Forzado fallido para {oid}: no hay calles en el mapa")
                    continue

                (pickup_pos, p_building) = snap_p
                (dropoff_pos, d_building) = snap_d

                payout = float(it.get("payout", it.get("payment", 0)))
                deadline = str(it.get("deadline", ""))
                time_limit = _time_limit_from_deadline(deadline, 600.0)

                order = Order(
                    order_id=oid,
                    pickup_pos=pickup_pos,
                    dropoff_pos=dropoff_pos,
                    payment=payout,
                    time_limit=time_limit,
                    weight=it.get("weight"),
                    priority=int(it.get("priority", 0)),
                    deadline=deadline,
                    release_time=int(it.get("release_time", 0)),
                )
                orders_objs.append(order)

                if self.renderer and self.city:
                    if p_building:
                        pbx, pby = p_building
                        if _in_bounds(pbx, pby) and self.city.tiles[pby][pbx] == "B":
                            self.renderer.generate_door_at(pbx, pby)
                    if d_building:
                        dbx, dby = d_building
                        if _in_bounds(dbx, dby) and self.city.tiles[dby][dbx] == "B":
                            self.renderer.generate_door_at(dbx, dby)

            except Exception as e:
                if self.debug:
                    print(f"Saltando pedido inválido: {e}")

        self._orders_queue = []
        self.pending_orders = []
        elapsed = float(self.total_play_time) if self.total_play_time else 0.0

        for i, order in enumerate(orders_objs):
            unlock_at = i * float(self.order_release_interval)
            if unlock_at <= elapsed:
                self.pending_orders.append(order)
            else:
                self._orders_queue.append((unlock_at, order))

        self._orders_queue.sort(key=lambda x: x[0])

        if self.orders_window:
            self.orders_window.set_pending_orders(self.pending_orders)
        if self.debug:
            print(f"{len(self.pending_orders)} active orders ready")

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

    def _check_game_end_conditions(self):
        if not self.player:
            return

        if self.time_remaining <= 0:
            self._end_game(False, "¡Tiempo agotado!")
            return

        if self.player.is_reputation_critical():
            self._end_game(False, "¡Reputación muy baja!")
            return

        goal_earnings = float(self.app_config.get("game", {}).get("goal_earnings", 500))
        if self.player.earnings >= goal_earnings:
            time_bonus = max(0.0, self.time_remaining / self.time_limit)
            bonus_message = f"¡Victoria! Bonus de tiempo: +{time_bonus * 100:.0f}%"
            self._end_game(True, bonus_message)
            return

    def _end_game(self, victory: bool, message: str):
        self.show_notification(f" {message}")

        try:
            entry = self.score_manager.calculate_score(
                self.player,
                self.time_remaining,
                self.time_limit,
                victory,
                self.total_play_time,
            )
            leaderboard = self.score_manager.add_score(entry)
            self.game_over_active = True
            self.score_screen = ScoreScreen(self, entry, leaderboard)

            self.state_manager.change_state(GameState.PAUSED)
            if hasattr(self, 'audio_manager'):
                self.audio_manager.pause_music()
        except Exception as e:
            print(f"Error generando score: {e}")
            self.return_to_main_menu()

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

        current_time = time.time()

        if self.player:
            self.player.save_undo_state_if_needed(current_time)

        if self.game_start_time > 0:
            if self.last_update_time == 0:
                self.last_update_time = current_time
            else:
                frame_time = current_time - self.last_update_time
                self.total_play_time += frame_time
                self.time_remaining -= frame_time
                self.last_update_time = current_time

        self._check_game_end_conditions()
        self._release_orders_by_time()

        if self.player and hasattr(self.player, 'inventory'):
            self.player.inventory.update_animation(delta_time)

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

        if self._turn_left:
            self.player.turn_left(delta_time)
        if self._turn_right:
            self.player.turn_right(delta_time)

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

        moved = (abs(self.player.x - prev_x) > 1e-5) or (abs(self.player.y - prev_y) > 1e-5)
        if moved:
            base_speed = self.player.calculate_effective_speed(self.city)
            move_scale = math.hypot(dx, dy)
            self.last_move_scale = move_scale
            target_speed = base_speed * move_scale
        else:
            target_speed = 0.0
            self.last_move_scale = 0.0

        speed_diff = target_speed - self.displayed_speed
        self.displayed_speed += speed_diff * self.speed_smoothing * delta_time
        if abs(speed_diff) < 0.01:
            self.displayed_speed = target_speed
        if not moved and abs(self.displayed_speed) < 0.05:
            self.displayed_speed = 0.0

        self.player.update(delta_time)
        self._check_pickup_and_delivery()

        if self.orders_window:
            self.orders_window.update_animation(delta_time)

    def _release_orders_by_time(self):
        if not hasattr(self, "_orders_queue"):
            return
        released = 0
        elapsed = float(self.total_play_time)

        while self._orders_queue and self._orders_queue[0][0] <= elapsed:
            _, order = self._orders_queue.pop(0)
            self.pending_orders.append(order)
            released += 1
            self.show_notification(f"Nuevo pedido disponible: {order.id}")

        if released and self.orders_window:
            self.orders_window.set_pending_orders(self.pending_orders)

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
        # Solo gestionar en juego activo
        if self.state_manager.current_state != GameState.PLAYING:
            return
        if self.input_handler.on_key_release(symbol, modifiers):
            return

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        self.hud_fps.position = (10, height - 20)
        self.hud_stats.position = (10, height - 40)
        self.hud_performance.position = (10, height - 60)
        self.hud_weather.position = (10, height - 100)
        self.hud_time.position = (10, height - 120)

    def _distance_player_to(self, tx: float, ty: float) -> float:
        if not self.player:
            return float('inf')
        dx = self.player.x - tx
        dy = self.player.y - ty
        return math.hypot(dx, dy)
    
    def _check_pickup_and_delivery(self):
        if not self.player or not getattr(self.player, "inventory", None):
            return
        inv = self.player.inventory
        radius = getattr(self, "pickup_radius", 1.5)

        for order in list(inv.orders):
            if getattr(order, "status", "") == "in_progress":
                px, py = order.pickup_pos
                if self._distance_player_to(px, py) <= radius:
                    order.pickup()
                    self.show_notification(f"Recogido {order.id}")
                    continue

            if getattr(order, "status", "") == "picked_up":
                dx, dy = order.dropoff_pos
                if self._distance_player_to(dx, dy) <= radius:
                    order.deliver()
                    payout = float(getattr(order, "payout", getattr(order, "payment", 0.0)))
                    self.player.add_earnings(payout)
                    self.player.update_reputation_for_delivery(order)
                    self.player.remove_order_from_inventory(order.id)
                    self.show_notification(f"Entregado {order.id}  +${payout:.0f}")
