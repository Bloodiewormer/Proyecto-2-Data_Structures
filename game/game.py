import arcade
from typing import Optional

from api.client import APIClient
from game.city import CityMap
from game.player import Player
from game.renderer import RayCastRenderer


class CourierGame(arcade.Window):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.frame_times = []
        self.performance_counter = 0


        display = app_config.get("display", {})
        super().__init__(
            width=display.get("width", 800),
            height=display.get("height", 600),
            title=display.get("title", "Courier Quest"),
            resizable=display.get("resizable", False),
        )

        self.background_color = arcade.color.SKY_BLUE

        # Core members
        self.api_client: Optional[APIClient] = None
        self.city: Optional[CityMap] = None
        self.player: Optional[Player] = None
        self.renderer: Optional[RayCastRenderer] = None

        # Input state
        self._move_forward = False
        self._move_backward = False
        self._turn_left = False
        self._turn_right = False

        # HUD (create after Window init so height/ctx exist)
        self.hud_fps = arcade.Text("", 10, self.height - 20, arcade.color.WHITE, 12)
        self.hud_stats = arcade.Text("", 10, self.height - 40, arcade.color.WHITE, 12)
        self.hud_performance = arcade.Text("", 10, self.height - 60, arcade.color.YELLOW, 10)

        # Target update rate
        self.set_update_rate(1 / 60)

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

    def on_draw(self):
        self.clear()

        if self.renderer and self.player:
            self.renderer.render_world(self.player, weather_system=None)
            self.renderer.render_minimap(10, 10, 160, self.player)

        earnings = self.player.earnings if self.player else 0.0
        stamina = self.player.stamina if self.player else 0.0
        reputation = self.player.reputation if self.player else 0.0

        if self.frame_times:
            dt_list = self.frame_times[-60:]
            avg_dt = (sum(dt_list) / len(dt_list)) if dt_list else 0.0
            avg_fps = (1.0 / avg_dt) if avg_dt > 0 else 0.0
            self.hud_performance.position = (10, self.height - 60)
            rays = self.renderer.num_rays if self.renderer else 0
            self.hud_performance.text = f"FPS: {avg_fps:.1f} | Rays: {rays}"
            self.hud_performance.draw()

        self.hud_stats.position = (10, self.height - 40)
        self.hud_stats.text = f"$ {earnings:.0f} | stamina: {stamina:.0f} | rep: {reputation:.0f}"
        self.hud_stats.draw()

    def on_update(self, delta_time: float):
        # Track frame times for FPS
        self.frame_times.append(delta_time)
        if len(self.frame_times) > 240:
            self.frame_times.pop(0)

        if not self.player or not self.city:
            return

        if self._turn_left:
            self.player.turn_left(delta_time)
        if self._turn_right:
            self.player.turn_right(delta_time)

        dx = dy = 0.0
        if self._move_forward or self._move_backward:
            fx, fy = self.player.get_forward_vector()
            if self._move_forward:
                dx += fx
                dy += fy
            if self._move_backward:
                dx -= fx
                dy -= fy

        if dx != 0.0 or dy != 0.0:
            self.player.move(dx, dy, delta_time, self.city)

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
