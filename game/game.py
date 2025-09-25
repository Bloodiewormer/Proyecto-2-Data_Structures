# file: game/game.py (MODIFICADO)
import arcade
from typing import Optional
import math
import random
import time
import os
import json


from api.client import APIClient
from game.city import CityMap
from game.player import Player
from game.renderer import RayCastRenderer
from game.utils import find_nearest_building
from game.gamestate import GameStateManager, GameState, MainMenu, PauseMenu
from game.SaveManager import SaveManager

from .inventory import Order, Inventory


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.frame_times = []
        self.performance_counter = 0
        self.state_manager = GameStateManager(self)
        self.save_manager = SaveManager(app_config)

        # Factor de velocidad al retroceder (30% de la normal)
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

        # Sistemas principales
        self.api_client: Optional[APIClient] = None
        self.city: Optional[CityMap] = None
        self.player: Optional[Player] = None
        self.renderer: Optional[RayCastRenderer] = None

        # Sistema de estados y guardado
        self.state_manager = GameStateManager(self)
        self.save_manager = SaveManager(app_config)

        # Control de tiempo de juego
        self.game_start_time = 0
        self.total_play_time = 0
        self.last_update_time = 0

        # Input
        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        # Velocidad suavizada
        self.displayed_speed = 0.0
        self.speed_smoothing = 3.0

        # Datos de pedidos/órdenes (para guardar)
        self.orders_data = {}
        self.game_stats = {}

        self.set_update_rate(1 / 60)

        # HUD
        self.hud_fps = arcade.Text("", 10, self.height - 20, arcade.color.WHITE, 12)
        self.hud_stats = arcade.Text("", 10, self.height - 40, arcade.color.WHITE, 12)
        self.hud_performance = arcade.Text("", 10, self.height - 60, arcade.color.YELLOW, 10)
        self.hud_player_location = arcade.Text("", 10, self.height - 80, arcade.color.WHITE, 12)

        # Mensaje temporal para notificaciones
        self.notification_message = ""
        self.notification_timer = 0

    def setup(self):
        # Iniciar directamente una nueva partida al arrancar
        self.start_new_game()

    def start_new_game(self):
        """Inicializar una nueva partida"""
        try:
            # Inicializar sistemas de juego
            self._initialize_game_systems()

            # Configurar órdenes/pedidos de ejemplo
            self._setup_orders()

            # Inicializar estadísticas
            self.game_start_time = time.time()
            self.total_play_time = 0
            self.game_stats = {
                "start_time": self.game_start_time,
                "play_time": 0,
                "level": 1
            }

            # Cambiar a estado de juego
            self.state_manager.change_state(GameState.PLAYING)

            print("Nueva partida iniciada")
            self.show_notification("Nueva partida iniciada")

        except Exception as e:
            print(f"Error al inicializar nueva partida: {e}")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def load_game(self):
        """Cargar partida guardada"""
        try:
            save_data = self.save_manager.load_game()
            if not save_data:
                print("No se pudo cargar la partida")
                self.show_notification("Error al cargar partida")
                return

            # Inicializar sistemas de juego
            self._initialize_game_systems()

            # Restaurar estado del jugador
            if "player" in save_data:
                self.save_manager.restore_player(self.player, save_data["player"])

            # Restaurar estado de la ciudad
            if "city" in save_data:
                self.save_manager.restore_city(self.city, save_data["city"])

            # Restaurar datos de órdenes
            if "orders" in save_data:
                self.orders_data = save_data["orders"]

            # Restaurar estadísticas del juego
            if "game_stats" in save_data:
                self.game_stats = save_data["game_stats"]
                self.total_play_time = self.game_stats.get("play_time", 0)

            # Configurar órdenes si es necesario
            self._setup_orders()

            # Cambiar a estado de juego
            self.state_manager.change_state(GameState.PLAYING)

            print("Partida cargada exitosamente")
            self.show_notification("Partida cargada")

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            self.show_notification("Error al cargar partida")
            self.state_manager.change_state(GameState.MAIN_MENU)

    def save_game(self):
        """Guardar partida actual"""
        try:
            if not self.player or not self.city:
                print("No hay partida activa para guardar")
                return False

            # Actualizar tiempo de juego
            current_time = time.time()
            if self.game_start_time > 0:
                self.total_play_time += current_time - self.last_update_time
                self.game_stats["play_time"] = self.total_play_time

            # Guardar partida
            success = self.save_manager.save_game(
                self.player,
                self.city,
                self.orders_data,
                self.game_stats
            )

            if success:
                self.show_notification("Partida guardada")
                print("Partida guardada exitosamente")
            else:
                self.show_notification("Error al guardar")
                print("Error al guardar partida")

            return success

        except Exception as e:
            print(f"Error crítico al guardar: {e}")
            self.show_notification("Error al guardar")
            return False

    def pause_game(self):
        """Pausar el juego"""
        if self.state_manager.current_state == GameState.PLAYING:
            self.state_manager.change_state(GameState.PAUSED)

    def resume_game(self):
        """Reanudar el juego desde pausa"""
        if self.state_manager.current_state == GameState.PAUSED:
            self.state_manager.change_state(GameState.PLAYING)

    def return_to_main_menu(self):
        """Volver al menú principal"""
        # Limpiar estado del juego actual
        self.player = None
        self.city = None
        self.renderer = None
        if self.api_client:
            self.api_client.__exit__(None, None, None)
            self.api_client = None

        # Resetear variables de tiempo
        self.game_start_time = 0
        self.total_play_time = 0

        # Cambiar al menú principal
        self.state_manager.change_state(GameState.MAIN_MENU)

    def _initialize_game_systems(self):
        """Inicializar todos los sistemas necesarios para el juego"""
        # API Client
        api_conf = dict(self.app_config.get("api", {}))
        files_conf = self.app_config.get("files", {})
        if files_conf.get("cache_directory"):
            api_conf["cache_directory"] = files_conf["cache_directory"]
        self.api_client = APIClient(api_conf)

        # City Map
        self.city = CityMap(self.api_client, self.app_config)
        self.city.load_map()

        # Player
        sx, sy = self.city.get_spawn_position()
        self.player = Player(sx, sy, self.app_config.get("player", {}))

        # Renderer
        self.renderer = RayCastRenderer(self.city, self.app_config)


    def _setup_orders(self):
        """Configurar órdenes/pedidos del juego"""

        """orders = [

            {"pickup": [20, 19], "dropoff": [10, 22]},
            {"pickup": [27, 24], "dropoff": [4, 6]},
            {"pickup": [23, 9], "dropoff": [26, 5]},
            {"pickup": [20, 22], "dropoff": [7, 18]},
            {"pickup": [20, 21], "dropoff": [10, 20]},

        ]

        # Generar puertas para las órdenes
        for order in orders:
            for coord in [order["pickup"], order["dropoff"]]:
                x, y = coord
                pos = find_nearest_building(self.city, x, y)
                if pos and self.city.tiles[pos[1]][pos[0]] == "B" and self.renderer:
                    self.renderer.generate_door_at(*pos)

        ]"""
        
        cache_dir = files_conf.get("cache_directory") or os.path.join(os.getcwd(), "api_cache")
        orders_path = os.path.join(cache_dir, "pedidos.json")
        orders_data = []
        try:
            with open(orders_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                orders_data = data.get("orders", [])
                print(f"Cargados {len(orders_data)} pedidos de {orders_path}")
        except Exception as e:
            print(f"No se pudo leer {orders_path}: {e}")

        for o in orders_data:
            try:
                order_obj = Order(
                    id=str(o["id"]),
                    pickup_location=list(o["pickup"]),
                    dropoff_location=list(o["dropoff"]),
                    payout=float(o["payout"]),
                    weight=float(o["weight"]),
                    deadline=str(o["deadline"]),
                    priority=int(o.get("priority", 0)),
                    release_time=int(o.get("release_time", 0)),
                )
                if self.player:
                    self.player.add_order_to_inventory(order_obj)
            except Exception as e:
                print(f"Error creando/agregando pedido {o}: {e}")    

        for coord in (o.get("pickup"), o.get("dropoff")):
                try:
                    if not coord or not self.renderer:
                        continue
                    x, y = coord
                    pos = find_nearest_building(self.city, x, y)
                    if pos and self.city.tiles[pos[1]][pos[0]] == "B":
                        self.renderer.generate_door_at(*pos)
                except Exception as e:
                    print(f"No se pudo generar puerta para {coord}: {e}")

        # Guardar órdenes para el sistema de guardado
        self.orders_data = {"active_orders": orders}

    def show_notification(self, message: str, duration: float = 2.0):
        """Mostrar mensaje de notificación temporal"""
        self.notification_message = message
        self.notification_timer = duration

    def on_draw(self):
        self.clear()

        if self.state_manager.current_state == GameState.MAIN_MENU:
            if self.state_manager.main_menu:
                self.state_manager.main_menu.draw()

        elif self.state_manager.current_state == GameState.PLAYING:
            self._draw_game()

        elif self.state_manager.current_state == GameState.PAUSED:
            # Dibujar el juego de fondo
            self._draw_game()
            # Dibujar menú de pausa encima
            if self.state_manager.pause_menu:
                self.state_manager.pause_menu.draw()

        # Dibujar notificaciones
        self._draw_notifications()

    def _draw_game(self):
        """Dibujar el juego principal"""
        if not self.renderer or not self.player:
            return

        # Renderizar mundo 3D
        self.renderer.render_world(self.player, weather_system=None)
        self.renderer.render_minimap(10, 10, 160, self.player)

        # HUD del juego
        self._draw_hud()

        # Velocímetro
        if self.player and self.city:
            self._draw_bike_speedometer()


    def _draw_hud(self):
        """Dibujar interfaz de usuario del juego"""
        earnings = self.player.earnings if self.player else 0.0
        reputation = self.player.reputation if self.player else 0.0

        # FPS y performance


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

        # Posición del jugador
        self.hud_player_location.position = (10, self.height - 80)
        if self.player:
            self.hud_player_location.text = f"Pos: ({self.player.x:.1f}, {self.player.y:.1f}) Angle: {self.player.angle:.2f} rad"
            self.hud_player_location.draw()

        # Estadísticas
        self.hud_stats.position = (10, self.height - 40)
        self.hud_stats.text = f"$ {earnings:.0f} | rep: {reputation:.0f}"
        self.hud_stats.draw()

        # Barra de stamina
        if self.player:
            bar_width = 200
            bar_height = 20
            bar_x = self.width - bar_width - 80
            bar_y = 30

            stamina = self.player.stamina
            max_stamina = getattr(self.player, 'max_stamina', 100)
            stamina_percent = max(0.0, min(1.0, stamina / max_stamina))

            arcade.draw_lrbt_rectangle_filled(
                bar_x, bar_x + bar_width,
                bar_y, bar_y + bar_height,
                arcade.color.BLACK
            )

            if stamina_percent > 0:
                green_width = int(bar_width * stamina_percent)
                arcade.draw_lrbt_rectangle_filled(
                    bar_x, bar_x + green_width,
                    bar_y, bar_y + bar_height,
                    arcade.color.GREEN
                )

            arcade.draw_lrbt_rectangle_outline(
                bar_x, bar_x + bar_width,
                bar_y, bar_y + bar_height,
                arcade.color.WHITE, 2
            )
            stamina_text = f"{stamina:.0f}/{max_stamina:.0f}"
            arcade.draw_text(
                stamina_text,
                bar_x + bar_width + 10,
                bar_y + (bar_height // 2) - 6,
                arcade.color.WHITE,
                12
            )

        # Barra de reputación
        if self.player:
            rep_bar_width = 200
            rep_bar_height = 20
            rep_bar_x = self.width - rep_bar_width - 80
            rep_bar_y = 60  # Encima de la barra de stamina

            reputation = self.player.reputation
            max_reputation = 100
            rep_percent = max(0.0, min(1.0, reputation / max_reputation))

            arcade.draw_lrbt_rectangle_filled(
                rep_bar_x, rep_bar_x + rep_bar_width,
                rep_bar_y, rep_bar_y + rep_bar_height,
                arcade.color.BLACK
            )
            if rep_percent > 0:
                color = arcade.color.YELLOW if rep_percent < 0.7 else arcade.color.PINK
                fill_width = int(rep_bar_width * rep_percent)
                arcade.draw_lrbt_rectangle_filled(
                    rep_bar_x, rep_bar_x + fill_width,
                    rep_bar_y, rep_bar_y + rep_bar_height,
                    color
                )
            arcade.draw_lrbt_rectangle_outline(
                rep_bar_x, rep_bar_x + rep_bar_width,
                rep_bar_y, rep_bar_y + rep_bar_height,
                arcade.color.WHITE, 2
            )
            rep_text = f"{reputation:.0f}/100"
            arcade.draw_text(
                rep_text,
                rep_bar_x + rep_bar_width + 10,
                rep_bar_y + (rep_bar_height // 2) - 6,
                arcade.color.WHITE,
                12
            )

        # Instrucciones de pausa
        arcade.draw_text(
            "ESC - Pausa",
            self.width - 100, self.height - 30,
            arcade.color.WHITE, 12,
            anchor_x="center"
        )

    def _draw_notifications(self):
        """Dibujar notificaciones temporales"""
        if self.notification_timer > 0 and self.notification_message:
            # Fondo semi-transparente
            msg_width = len(self.notification_message) * 12 + 20
            msg_height = 40
            msg_x = (self.width - msg_width) // 2
            msg_y = self.height - 150

            arcade.draw_lrbt_rectangle_filled(
                msg_x, msg_x + msg_width,
                msg_y, msg_y + msg_height,
                (0, 0, 0, 180)
            )
            arcade.draw_lrbt_rectangle_outline(
                msg_x, msg_x + msg_width,
                msg_y, msg_y + msg_height,
                arcade.color.WHITE, 2
            )

            # Texto
            arcade.draw_text(
                self.notification_message,
                self.width // 2, msg_y + msg_height // 2 - 6,
                arcade.color.WHITE, 16,
                anchor_x="center"
            )

    def on_update(self, delta_time: float):
        # Actualizar temporizador de notificaciones
        if self.notification_timer > 0:
            self.notification_timer -= delta_time

        # Solo actualizar el juego si está en estado PLAYING
        if self.state_manager.current_state != GameState.PLAYING:
            return

        # Actualizar tiempo de juego
        current_time = time.time()
        if self.game_start_time > 0:
            if self.last_update_time == 0:
                self.last_update_time = current_time
            else:
                self.total_play_time += current_time - self.last_update_time
                self.last_update_time = current_time

        # FPS
        self.frame_times.append(delta_time)
        if len(self.frame_times) > 240:
            self.frame_times.pop(0)

        if not self.player or not self.city:
            return

        # Rotación
        if self._turn_left:
            self.player.turn_left(delta_time)
        if self._turn_right:
            self.player.turn_right(delta_time)

        # Movimiento
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

        # Suavizado de velocidad
        speed_diff = target_speed - self.displayed_speed
        self.displayed_speed += speed_diff * self.speed_smoothing * delta_time
        if abs(speed_diff) < 0.01:
            self.displayed_speed = target_speed
        if not moved and abs(self.displayed_speed) < 0.05:
            self.displayed_speed = 0.0

        # Actualizar jugador
        self.player.update(delta_time)

    def on_key_press(self, symbol: int, modifiers: int):

        # Manejar entrada según el estado actual
        if self.state_manager.current_state == GameState.MAIN_MENU:
            if self.state_manager.main_menu:
                self.state_manager.main_menu.handle_key_press(symbol, modifiers)

        elif self.state_manager.current_state == GameState.PAUSED:
            if self.state_manager.pause_menu:
                self.state_manager.pause_menu.handle_key_press(symbol, modifiers)

        elif self.state_manager.current_state == GameState.PLAYING:
            # Controles del juego
            if symbol in (arcade.key.W, arcade.key.UP):
                self._move_forward = True
            elif symbol in (arcade.key.S, arcade.key.DOWN):
                self._move_backward = True
            elif symbol in (arcade.key.A, arcade.key.LEFT):
                self._turn_left = True
            elif symbol in (arcade.key.D, arcade.key.RIGHT):
                self._turn_right = True
            elif symbol == arcade.key.ESCAPE:
                self.pause_game()
            elif symbol == arcade.key.F5:  # Guardado rápido
                self.save_game()

        if symbol in (arcade.key.W, arcade.key.UP):
            self._move_forward = True
        elif symbol in (arcade.key.S, arcade.key.DOWN):
            self._move_backward = True
        elif symbol in (arcade.key.A, arcade.key.LEFT):
            self._turn_left = True
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self._turn_right = True
        elif symbol == arcade.key.ESCAPE:
            arcade.exit()
        # Controles del inventario
        elif symbol == arcade.key.TAB and modifiers & arcade.key.MOD_SHIFT:
            # Shift+Tab: ordenar por prioridad
            if self.player:
                self.player.inventory.sort_by_priority()
        elif symbol == arcade.key.TAB:
            # Tab: alternar modo de ordenamiento
            if self.player:
                # Alterna entre 'priority' y 'deadline'
                if self.player.inventory.sort_mode == "priority":
                    self.player.inventory.sort_mode = "deadline"
                    self.player.inventory.sort_by_deadline()
                else:
                    self.player.inventory.sort_mode = "priority"
                    self.player.inventory.sort_by_priority()
        elif symbol == arcade.key.E:
            # E: siguiente pedido
            if self.player:
                self.player.inventory.next_order()
        elif symbol == arcade.key.Q:
            # Q: pedido anterior
            if self.player:
                self.player.inventory.previous_order()


    def on_key_release(self, symbol: int, modifiers: int):
        # Solo procesar liberación de teclas en estado de juego
        if self.state_manager.current_state == GameState.PLAYING:
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

    def _draw_bike_speedometer(self):
        """Velocímetro con jitter reducido ±1.5 km/h"""
        speed = self.displayed_speed
        max_speed = self.player.base_speed * 1.2
        speed_percent = min(1.0, speed / max_speed)

        # Posición
        bar_x = self.width - 200 - 80
        center_x = bar_x + 235
        center_y = 150
        radius = 35

        # Variación aleatoria
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

        # Fondo del velocímetro
        arcade.draw_circle_filled(center_x, center_y, radius + 3, (40, 40, 40))
        arcade.draw_circle_outline(center_x, center_y, radius + 3, arcade.color.WHITE, 2)

        start_angle = 135
        end_angle = 405

        # Arco base
        for angle in range(start_angle, end_angle, 3):
            rad = math.radians(angle)
            x1 = center_x + math.cos(rad) * (radius - 6)
            y1 = center_y + math.sin(rad) * (radius - 6)
            x2 = center_x + math.cos(rad) * (radius - 2)
            y2 = center_y + math.sin(rad) * (radius - 2)
            arcade.draw_line(x1, y1, x2, y2, (80, 80, 80), 2)

        # Arco activo
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

        # Aguja
        needle_angle = start_angle + (end_angle - start_angle) * varied_speed_percent
        needle_rad = math.radians(needle_angle)
        needle_x = center_x + math.cos(needle_rad) * (radius - 8)
        needle_y = center_y + math.sin(needle_rad) * (radius - 8)
        arcade.draw_line(center_x, center_y, needle_x, needle_y, arcade.color.WHITE, 2)
        arcade.draw_circle_filled(center_x, center_y, 3, arcade.color.WHITE)

        # Marcas de velocidad
        for i in range(5):
            mark_percent = i / 4.0
            mark_angle = start_angle + (end_angle - start_angle) * mark_percent
            radm = math.radians(mark_angle)
            x1 = center_x + math.cos(radm) * (radius - 4)
            y1 = center_y + math.sin(radm) * (radius - 4)
            x2 = center_x + math.cos(radm) * (radius - 1)
            y2 = center_y + math.sin(radm) * (radius - 1)
            arcade.draw_line(x1, y1, x2, y2, arcade.color.WHITE, 2)

        # Texto de velocidad
        speed_kmh = varied_speed * 10.0
        arcade.draw_text(f"{speed_kmh:.0f}", center_x, center_y - 10,
                         arcade.color.WHITE, 14, anchor_x="center")
        arcade.draw_text("km/h", center_x, center_y - 22,
                         arcade.color.LIGHT_GRAY, 8, anchor_x="center")

        # Indicador de estado del jugador
        state_colors = {
            "normal": arcade.color.GREEN,
            "tired": arcade.color.YELLOW,
            "exhausted": arcade.color.RED
        }
        state_color = state_colors.get(self.player.state, arcade.color.WHITE)
        arcade.draw_circle_filled(center_x, center_y + 18, 4, state_color)

