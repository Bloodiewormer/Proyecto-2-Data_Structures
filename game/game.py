import arcade
from typing import Optional
import math
import random  # Para la variación del velocímetro

from api.client import APIClient
from game.city import CityMap
from game.player import Player
from game.renderer import RayCastRenderer
from game.utils import find_nearest_building


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.frame_times = []
        self.performance_counter = 0

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

        self.api_client: Optional[APIClient] = None
        self.city: Optional[CityMap] = None
        self.player: Optional[Player] = None
        self.renderer: Optional[RayCastRenderer] = None

        # Input
        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        # Velocidad suavizada
        self.displayed_speed = 0.0
        self.speed_smoothing = 3.0

        self.set_update_rate(1 / 60)

        # HUD
        self.hud_fps = arcade.Text("", 10, self.height - 20, arcade.color.WHITE, 12)
        self.hud_stats = arcade.Text("", 10, self.height - 40, arcade.color.WHITE, 12)
        self.hud_performance = arcade.Text("", 10, self.height - 60, arcade.color.YELLOW, 10)
        self.hud_player_location = arcade.Text("", 10, self.height - 80, arcade.color.WHITE, 12)

    def setup(self):
        api_conf = dict(self.app_config.get("api", {}))
        files_conf = self.app_config.get("files", {})
        if files_conf.get("cache_directory"):
            api_conf["cache_directory"] = files_conf["cache_directory"]
        self.api_client = APIClient(api_conf)

        self.city = CityMap(self.api_client, self.app_config)
        self.city.load_map()

        sx, sy = self.city.get_spawn_position()
        self.player = Player(sx, sy, self.app_config.get("player", {}))

        self.renderer = RayCastRenderer(self.city, self.app_config)
        orders = [
            {"pickup": [20, 19], "dropoff": [10, 22]},
            {"pickup": [27, 24], "dropoff": [4, 6]},
            {"pickup": [23, 9], "dropoff": [26, 5]},
            {"pickup": [20, 22], "dropoff": [7, 18]},
            {"pickup": [20, 21], "dropoff": [10, 20]},
        ]

        for order in orders:
            for coord in [order["pickup"], order["dropoff"]]:
                x, y = coord
                pos = find_nearest_building(self.city, x, y)
                if pos and self.city.tiles[pos[1]][pos[0]] == "B" and self.renderer:
                    print(f"Puerta para {coord} en {pos}")
                    self.renderer.generate_door_at(*pos)

    def on_draw(self):
        self.clear()

        if self.renderer and self.player:
            self.renderer.render_world(self.player, weather_system=None)
            self.renderer.render_minimap(10, 10, 160, self.player)

        earnings = self.player.earnings if self.player else 0.0
        reputation = self.player.reputation if self.player else 0.0

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
            max_reputation = 100  # Puedes ajustar si hay un máximo diferente
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

        if self.player and self.city:
            self._draw_bike_speedometer()

    def on_update(self, delta_time: float):
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
            move_scale = math.hypot(dx, dy)  # 1.0 adelante, backward_factor atrás
            self.last_move_scale = move_scale
            target_speed = base_speed * move_scale
        else:
            target_speed = 0.0
            self.last_move_scale = 0.0

        # Suavizado
        speed_diff = target_speed - self.displayed_speed
        self.displayed_speed += speed_diff * self.speed_smoothing * delta_time
        if abs(speed_diff) < 0.01:
            self.displayed_speed = target_speed
        if not moved and abs(self.displayed_speed) < 0.05:
            self.displayed_speed = 0.0

        # Update jugador (estado / stamina)
        self.player.update(delta_time)

    def on_key_press(self, symbol: int, modifiers: int):
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

    def on_key_release(self, symbol: int, modifiers: int):
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


        # Posición (a la derecha, sobre la barra de stamina)
        bar_x = self.width - 200 - 80
        center_x = bar_x + 235
        center_y = 150
        radius = 35

        # Variación aleatoria
        max_jitter_kmh = 1.5
        jitter_units = max_jitter_kmh / 10.0  # conversión
        if speed > 0.05:
            variation_intensity = min(1.0, speed / max(0.001, self.player.base_speed))
            speed_variation = random.uniform(-jitter_units, jitter_units) * variation_intensity
            varied_speed = max(0.0, speed + speed_variation)
            varied_speed_percent = min(1.0, varied_speed / max_speed)
        else:
            varied_speed = speed
            varied_speed_percent = speed_percent

        # Fondo
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

        # Marcas
        for i in range(5):
            mark_percent = i / 4.0
            mark_angle = start_angle + (end_angle - start_angle) * mark_percent
            radm = math.radians(mark_angle)
            x1 = center_x + math.cos(radm) * (radius - 4)
            y1 = center_y + math.sin(radm) * (radius - 4)
            x2 = center_x + math.cos(radm) * (radius - 1)
            y2 = center_y + math.sin(radm) * (radius - 1)
            arcade.draw_line(x1, y1, x2, y2, arcade.color.WHITE, 2)

        # Texto (km/h ficticios)
        speed_kmh = varied_speed * 10.0
        arcade.draw_text(f"{speed_kmh:.0f}", center_x, center_y - 10,
                         arcade.color.WHITE, 14, anchor_x="center")
        arcade.draw_text("km/h", center_x, center_y - 22,
                         arcade.color.LIGHT_GRAY, 8, anchor_x="center")

        # Estado jugador
        state_colors = {
            "normal": arcade.color.GREEN,
            "tired": arcade.color.YELLOW,
            "exhausted": arcade.color.RED
        }
        state_color = state_colors.get(self.player.state, arcade.color.WHITE)
        arcade.draw_circle_filled(center_x, center_y + 18, 4, state_color)

