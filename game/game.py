import time
import arcade
from typing import Optional
import math
import random
import os
import json

from api.client import APIClient
from game.city import CityMap
from game.player import Player
from game.renderer import RayCastRenderer
from game.weather import WeatherSystem
from game.utils import find_nearest_building, format_time
from game.gamestate import GameStateManager, GameState, MainMenu, PauseMenu
from game.saveManager import saveManager
from .inventory import Order


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.files_conf = app_config.get("files", {})
        self.frame_times = []
        self.performance_counter = 0
        self.orders_data = {}

        self.state_manager = GameStateManager(self)
        self.save_manager = saveManager(app_config)

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

    # Game Lifecycle / State Entry
    def setup(self):
        self.state_manager.change_state(GameState.MAIN_MENU)

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
            self.state_manager.change_state(GameState.PLAYING)
            self.show_notification("Partida cargada")
        except Exception as e:
            print(f"Error al cargar partida: {e}")
            self.show_notification("Error al cargar partida")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def save_game(self):
        try:
            if not self.player or not self.city:
                return False
            current_time = time.time()
            if self.game_start_time > 0:
                self.total_play_time += current_time - self.last_update_time
                self.game_stats["play_time"] = self.total_play_time
                self.game_stats["time_remaining"] = self.time_remaining
            success = self.save_manager.save_game(
                self.player, self.city, self.orders_data, self.game_stats
            )
            if success:
                self.show_notification("Partida guardada")
            else:
                self.show_notification("Error al guardar")
            return success
        except Exception as e:
            print(f"Error crítico al guardar: {e}")
            self.show_notification("Error al guardar")
            return False

    # State Control (Pause / Resume / Menu)
    def pause_game(self):
        if self.state_manager.current_state == GameState.PLAYING:
            self.state_manager.change_state(GameState.PAUSED)

    def resume_game(self):
        if self.state_manager.current_state == GameState.PAUSED:
            self.state_manager.change_state(GameState.PLAYING)

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
        self.state_manager.change_state(GameState.MAIN_MENU)

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

    def _setup_orders(self):
        cache_dir = self.files_conf.get("cache_directory") or os.path.join(os.getcwd(), "api_cache")
        os.makedirs(cache_dir, exist_ok=True)
        orders_path = os.path.join(cache_dir, "pedidos.json")

        orders_raw = []
        try:
            with open(orders_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                orders_raw = data.get("orders", [])
                if self.debug:
                    print(f"Cargados {len(orders_raw)} pedidos de {orders_path}")
        except Exception as e:
            if self.debug:
                print(f"No se pudo leer {orders_path}: {e}")
            # Fallback simple
            orders_raw = [
                {"id": 1, "pickup": [20, 19], "dropoff": [10, 22], "payout": 120, "weight": 1.2, "deadline": "2025-01-01T10:00:00Z"},
                {"id": 2, "pickup": [27, 24], "dropoff": [4, 6], "payout": 240, "weight": 2.5, "deadline": "2025-01-01T10:10:00Z"}
            ]

        active_orders_serializable = []

        for od in orders_raw:
            t_order_start = time.perf_counter()
            try:
                order_obj = Order(
                    id=str(od.get("id")),
                    pickup_location=list(od.get("pickup", [])),
                    dropoff_location=list(od.get("dropoff", [])),
                    payout=float(od.get("payout", 0)),
                    weight=float(od.get("weight", 0)),
                    deadline=str(od.get("deadline", "")),
                    priority=int(od.get("priority", 0)),
                    release_time=int(od.get("release_time", 0)),
                )

                if self.player:
                    t0 = time.perf_counter()
                    self.player.add_order_to_inventory(order_obj)
                    t1 = time.perf_counter()
                    self._perf_accum_game["inventory"] += (t1 - t0)

                if self.renderer and self.city:
                    for coord in (order_obj.pickup_location, order_obj.dropoff_location):
                        if not coord:
                            continue
                        try:
                            x, y = coord
                            pos = find_nearest_building(self.city, x, y)
                            if pos and self.city.tiles[pos[1]][pos[0]] == "B":
                                self.renderer.generate_door_at(*pos)
                        except Exception as e2:
                            if self.debug:
                                print(f"No se pudo generar puerta para {coord}: {e2}")

                active_orders_serializable.append({
                    "id": order_obj.id,
                    "pickup": order_obj.pickup_location,
                    "dropoff": order_obj.dropoff_location,
                    "payout": order_obj.payout,
                    "weight": order_obj.weight,
                    "deadline": order_obj.deadline,
                    "priority": order_obj.priority,
                    "release_time": order_obj.release_time
                })
            except Exception as e:
                print(f"Error creando/agregando pedido {od}: {e}")
            finally:
                t_order_end = time.perf_counter()
                self._perf_accum_game["orders"] += (t_order_end - t_order_start)

        self.orders_data = {"active_orders": active_orders_serializable}
        if self.debug:
            print(f"{len(active_orders_serializable)} pedidos activos cargados")

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
        self._draw_notifications()

    def _draw_game(self):
        if not self.renderer or not self.player:
            return
        self.renderer.render_world(self.player, weather_system=self.weather_system)
        self.renderer.render_minimap(10, 10, 160, self.player)
        self._draw_hud()
        if self.player and self.city:
            self._draw_bike_speedometer()

    def _draw_hud(self):
        earnings = self.player.earnings if self.player else 0.0
        reputation = self.player.reputation if self.player else 0.0

        if self.player:
            inventory_width = 450
            inventory_height = 400
            inventory_x = self.width - inventory_width - 50
            inventory_y = self.height - inventory_height - 50
            self.player.inventory.draw_inventory(inventory_x, inventory_y, inventory_width, inventory_height)

        if self.frame_times:
            dt_list = self.frame_times[-60:]
            avg_dt = (sum(dt_list) / len(dt_list)) if dt_list else 0.0
            avg_fps = (1.0 / avg_dt) if avg_dt > 0 else 0.0
            self.hud_performance.position = (10, self.height - 60)
            rays = self.renderer.num_rays if self.renderer else 0
            self.hud_performance.text = f"FPS: {avg_fps:.1f} | Rays: {rays}"
            self.hud_performance.draw()

        self.hud_player_location.position = (10, self.height - 80)
        if self.player:
            self.hud_player_location.text = f"Pos: ({self.player.x:.1f}, {self.player.y:.1f}) Angle: {self.player.angle:.2f} rad"
            self.hud_player_location.draw()

        self.hud_stats.position = (10, self.height - 40)
        self.hud_stats.text = f"$ {earnings:.0f} | rep: {reputation:.0f}"
        self.hud_stats.draw()

        # NUEVO: Mostrar información del clima
        if self.weather_system:
            weather_info = self.weather_system.get_weather_info()
            self.hud_weather.position = (10, self.height - 100)
            weather_name = self.weather_system.get_weather_name()
            speed_effect = f"{weather_info['speed_multiplier']:.0%}"
            time_remaining = weather_info['time_remaining']
            self.hud_weather.text = f"Clima: {weather_name} | Velocidad: {speed_effect} | Cambio en: {time_remaining:.0f}s"
            self.hud_weather.draw()

        # NUEVO: Mostrar tiempo restante del juego
        self.hud_time.position = (10, self.height - 120)
        time_str = format_time(self.time_remaining)
        goal_earnings = getattr(self.city, 'goal', 3000) if self.city else 3000
        progress = (earnings / goal_earnings) * 100 if goal_earnings > 0 else 0

        # Color del tiempo basado en urgencia
        if self.time_remaining < 120:  # Menos de 2 minutos - rojo
            time_color = arcade.color.RED
        elif self.time_remaining < 300:  # Menos de 5 minutos - amarillo
            time_color = arcade.color.YELLOW
        else:
            time_color = arcade.color.WHITE

        self.hud_time.color = time_color
        self.hud_time.text = f"Tiempo: {time_str} | Meta: ${goal_earnings:.0f} ({progress:.1f}%)"
        self.hud_time.draw()

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
                arcade.draw_lrbt_rectangle_filled(bar_x, bar_x + green_width, bar_y, bar_y + bar_height,
                                                  arcade.color.GREEN)
            arcade.draw_lrbt_rectangle_outline(bar_x, bar_x + bar_width, bar_y, bar_y + bar_height, arcade.color.WHITE,
                                               2)
            stamina_text = f"{stamina:.0f}/{max_stamina:.0f}"
            arcade.draw_text(stamina_text, bar_x + bar_width + 10, bar_y + (bar_height // 2) - 6, arcade.color.WHITE,
                             12)

        if self.player:
            rep_bar_width = 200
            rep_bar_height = 20
            rep_bar_x = self.width - rep_bar_width - 80
            rep_bar_y = 60
            reputation = self.player.reputation
            max_reputation = 100
            rep_percent = max(0.0, min(1.0, reputation / max_reputation))
            arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y,
                                              rep_bar_y + rep_bar_height, arcade.color.BLACK)
            if rep_percent > 0:
                color = arcade.color.YELLOW if rep_percent < 0.7 else arcade.color.PINK
                fill_width = int(rep_bar_width * rep_percent)
                arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + fill_width, rep_bar_y,
                                                  rep_bar_y + rep_bar_height, color)
            arcade.draw_lrbt_rectangle_outline(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y,
                                               rep_bar_y + rep_bar_height, arcade.color.WHITE, 2)
            rep_text = f"{reputation:.0f}/100"
            arcade.draw_text(rep_text, rep_bar_x + rep_bar_width + 10, rep_bar_y + (rep_bar_height // 2) - 6,
                             arcade.color.WHITE, 12)

        # NUEVO: Indicador visual del clima actual
        if self.weather_system:
            weather_info = self.weather_system.get_weather_info()
            weather_icon_x = self.width - 150
            weather_icon_y = self.height - 50

            # Fondo del indicador
            arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 20, (0, 0, 0, 150))
            arcade.draw_circle_outline(weather_icon_x, weather_icon_y, 20, arcade.color.WHITE, 2)

            # Icono simple basado en el clima
            condition = weather_info['condition']
            if condition == "clear":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (255, 255, 0))  # Sol
            elif condition == "clouds":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (169, 169, 169))  # Nube gris
            elif condition in ["rain", "rain_light"]:
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (100, 149, 237))  # Azul lluvia
            elif condition == "storm":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (75, 0, 130))  # Morado tormenta
            elif condition == "fog":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (220, 220, 220))  # Gris claro niebla
            elif condition == "wind":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (173, 216, 230))  # Azul claro viento
            elif condition == "heat":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (255, 69, 0))  # Naranja calor
            elif condition == "cold":
                arcade.draw_circle_filled(weather_icon_x, weather_icon_y, 12, (175, 238, 238))  # Azul pálido frío

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
        if self.notification_timer > 0:
            self.notification_timer -= delta_time
        if self.state_manager.current_state != GameState.PLAYING:
            return

        current_time = time.time()
        if self.game_start_time > 0:
            if self.last_update_time == 0:
                self.last_update_time = current_time
            else:
                frame_time = current_time - self.last_update_time
                self.total_play_time += frame_time
                self.time_remaining -= frame_time  # NUEVO: Reducir tiempo restante
                self.last_update_time = current_time

        # NUEVO: Verificar condiciones de fin de juego
        self._check_game_end_conditions()

        if self.player and hasattr(self.player, 'inventory'):
            self.player.inventory.update_animation(delta_time)

        # NUEVO: Actualizar sistema de clima
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


    # Input Handling

    def on_key_press(self, symbol: int, modifiers: int):
        # ESC handling
        if symbol == arcade.key.ESCAPE:
            if self.state_manager.current_state == GameState.PLAYING:
                self.pause_game()
            elif self.state_manager.current_state == GameState.PAUSED:
                self.resume_game()
            elif self.state_manager.current_state == GameState.MAIN_MENU:
                arcade.exit()
            return

        state = self.state_manager.current_state
        if state == GameState.PLAYING:
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
                # Q cycles orders; Shift+Q backwards
                self._cycle_inventory_order(reverse=bool(modifiers & arcade.key.MOD_SHIFT))
            elif symbol == arcade.key.TAB:
                # TAB toggles sort mode (Shift also just toggles since only 2 modes)
                self._toggle_inventory_sort()
            elif symbol == arcade.key.I:
                self._toggle_inventory()
            # NUEVO: Teclas de debug para clima (solo si debug está activado)
            elif symbol == arcade.key.KEY_1 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("clear")
                self.show_notification("Clima forzado: Despejado")
            elif symbol == arcade.key.KEY_2 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("rain")
                self.show_notification("Clima forzado: Lluvia")
            elif symbol == arcade.key.KEY_3 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("storm")
                self.show_notification("Clima forzado: Tormenta")
            elif symbol == arcade.key.KEY_4 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("fog")
                self.show_notification("Clima forzado: Niebla")
            elif symbol == arcade.key.KEY_5 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("wind")
                self.show_notification("Clima forzado: Viento")
            elif symbol == arcade.key.KEY_6 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("heat")
                self.show_notification("Clima forzado: Calor")
            elif symbol == arcade.key.KEY_7 and self.debug and self.weather_system:
                self.weather_system.force_weather_change("cold")
                self.show_notification("Clima forzado: Frío")
        if state == GameState.MAIN_MENU and self.state_manager.main_menu:
            self.state_manager.main_menu.handle_key_press(symbol, modifiers)
        elif state == GameState.PAUSED and self.state_manager.pause_menu:
            self.state_manager.pause_menu.handle_key_press(symbol, modifiers)


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
