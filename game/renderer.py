import math
from typing import Any, Tuple
import arcade
from game.city import CityMap


class RayCastRenderer:
    def __init__(self, city: CityMap, app_config: dict):
        # Configuración básica
        self.city = city
        rendering = app_config.get("rendering", {}) or {}
        colors = app_config.get("colors", {}) or {}

        self.fov: float = float(rendering.get("fov", math.pi / 3))
        self.num_rays = int(rendering.get("num_rays", 160))
        self.floor_row_step: int = int(rendering.get("floor_row_step", 2))

        # Colores del mundo
        self.col_street = tuple(colors.get("street", (105, 105, 105)))
        self.col_building = tuple(colors.get("building", (0, 0, 0)))
        self.col_park = tuple(colors.get("park", (144, 238, 144)))
        self.col_sky = arcade.color.SKY_BLUE
        self.col_wall1 = (180, 180, 180)
        self.col_door = tuple(colors.get("door", (139, 69, 19)))

        # Colores del minimapa
        self.color_map = {
            "C": tuple(colors.get("street", (105, 105, 105))),
            "B": tuple(colors.get("building", (198, 134, 110))),
            "P": tuple(colors.get("park", (144, 238, 144))),
            "player": tuple(colors.get("player", (255, 255, 0))),
        }

        # Cache y estado
        self._minimap_shapes = None
        self._minimap_cache_key = None
        self.door_positions = set()

    # === UTILIDADES ===

    def _get_player(self, player: Any) -> Tuple[float, float, float]:
        px = getattr(player, "x", 0.0)
        py = getattr(player, "y", 0.0)
        ang = getattr(player, "angle", 0.0)
        return float(px), float(py), float(ang)

    def _floor_color_for(self, mx: int, my: int) -> Tuple[int, int, int]:
        t = self.city.get_tile_at(mx, my)
        if t == "P":
            return self.col_park
        return self.col_street

    # === RAYCASTING ===

    def _cast_wall_dda(self, pos_x: float, pos_y: float, dir_x: float, dir_y: float):
        map_x, map_y = int(pos_x), int(pos_y)
        delta_dist_x = 1e30 if dir_x == 0.0 else abs(1.0 / dir_x)
        delta_dist_y = 1e30 if dir_y == 0.0 else abs(1.0 / dir_y)

        if dir_x < 0:
            step_x = -1
            side_dist_x = (pos_x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - pos_x) * delta_dist_x
        if dir_y < 0:
            step_y = -1
            side_dist_y = (pos_y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - pos_y) * delta_dist_y

        side = 0
        while 0 <= map_x < self.city.width and 0 <= map_y < self.city.height:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            if not (0 <= map_x < self.city.width and 0 <= map_y < self.city.height):
                break
            if self.city.tiles[map_y][map_x] == "B":
                is_door = (map_x, map_y) in self.door_positions
                if side == 0:
                    denom = dir_x if dir_x != 0 else 1e-6
                    dist = (map_x - pos_x + (1 - step_x) / 2) / denom
                    wall_x = pos_y + dist * dir_y
                else:
                    denom = dir_y if dir_y != 0 else 1e-6
                    dist = (map_y - pos_y + (1 - step_y) / 2) / denom
                    wall_x = pos_x + dist * dir_x
                wall_x = wall_x - math.floor(wall_x)
                if dist <= 0:
                    dist = 0.0001
                return dist, side, is_door, wall_x
        return None, None, False, 0.0

    # === RENDERIZADO PRINCIPAL ===

    def render_world(self, player: Any, weather_system: Any = None):
        win = arcade.get_window()
        if not win:
            return

        width = win.width
        height = win.height
        horizon = height // 2
        posZ = height / 2.0

        # Cielo
        arcade.draw_lrbt_rectangle_filled(0, width, horizon, height, self.col_sky)

        px, py, pang = self._get_player(player)
        column_width_f = width / float(self.num_rays)

        for ray in range(self.num_rays):
            ray_angle = pang - self.fov / 2.0 + (ray / float(self.num_rays)) * self.fov
            dir_x = math.cos(ray_angle)
            dir_y = math.sin(ray_angle)

            left = int(ray * column_width_f)
            right = int((ray + 1) * column_width_f)
            if right <= left:
                right = left + 1

            dist, side, is_door, wall_x = self._cast_wall_dda(px, py, dir_x, dir_y)

            # Pared
            wall_bottom = 0
            if dist is not None:
                slice_h = int(height / max(dist, 1e-4))
                half = slice_h // 2
                bottom = max(0, horizon - half)
                top = min(height, horizon + half)

                wall_color = self.col_door if is_door else self.col_wall1
                if side == 1:
                    wall_color = (max(0, wall_color[0] - 20), max(0, wall_color[1] - 20), max(0, wall_color[2] - 20))
                arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, wall_color)
                wall_bottom = bottom
            else:
                wall_bottom = horizon

            # Suelo
            y_end = int(min(horizon, wall_bottom))
            if y_end <= 0:
                continue

            last_color = None
            seg_start = 0
            y = 0
            while y < y_end:
                denom = (horizon - y)
                if denom <= 0:
                    break

                row_dist = posZ / denom
                world_x = px + dir_x * row_dist
                world_y = py + dir_y * row_dist
                mx = int(world_x)
                my = int(world_y)

                color = self._floor_color_for(mx, my)

                if last_color is None:
                    last_color = color
                    seg_start = y
                elif color != last_color:
                    arcade.draw_lrbt_rectangle_filled(left, right, seg_start, y, last_color)
                    last_color = color
                    seg_start = y

                y += self.floor_row_step

            if last_color is not None and seg_start < y_end:
                arcade.draw_lrbt_rectangle_filled(left, right, seg_start, y_end, last_color)

    # === MINIMAPA ===

    def _ensure_minimap_cache(self, x: int, y: int, size: int):
        if not self.city or not getattr(self.city, "tiles", None):
            self._minimap_shapes = None
            self._minimap_cache_key = None
            return

        key = (
            x, y, size,
            self.city.width, self.city.height,
            self.color_map["C"], self.color_map["B"], self.color_map["P"]
        )
        if key == self._minimap_cache_key and self._minimap_shapes is not None:
            return

        scale_x = size / max(1, self.city.width)
        scale_y = size / max(1, self.city.height)

        shapes = arcade.shape_list.ShapeElementList()

        col_street = self.color_map["C"]
        col_build = self.color_map["B"]
        col_park = self.color_map["P"]

        for row in range(self.city.height):
            cy_bottom = y + row * scale_y
            cy_center_y = cy_bottom + scale_y * 0.5
            for col in range(self.city.width):
                t = self.city.tiles[row][col]
                color = col_build if t == "B" else (col_park if t == "P" else col_street)
                cx_left = x + col * scale_x
                cx_center_x = cx_left + scale_x * 0.5
                if len(color) == 3:
                    color = (*color, 255)
                rect = arcade.shape_list.create_rectangle_filled(
                    cx_center_x, cy_center_y, scale_x, scale_y, color
                )
                shapes.append(rect)

        border = arcade.shape_list.create_rectangle_outline(
            x + size * 0.5, y + size * 0.5, size, size, arcade.color.WHITE, border_width=2
        )
        shapes.append(border)

        self._minimap_shapes = shapes
        self._minimap_cache_key = key

    def render_minimap(self, x: int, y: int, size: int, player):
        self._ensure_minimap_cache(x, y, size)
        if not self._minimap_shapes:
            return

        self._minimap_shapes.draw()

        scale_x = size / max(1, self.city.width)
        scale_y = size / max(1, self.city.height)
        px = x + (player.x + 0.5) * scale_x
        py = y + (player.y + 0.5) * scale_y

        arcade.draw_circle_filled(px, py, max(2, int(min(scale_x, scale_y) * 0.3)), self.color_map["player"])
        fx = math.cos(player.angle)
        fy = math.sin(player.angle)
        arcade.draw_line(px, py, px + fx * 10, py + fy * 10, self.color_map["player"], 2)

    # === GENERACIÓN DE CONTENIDO ===

    def generate_door_at(self, tile_x: int, tile_y: int):
        if not self.city:
            return
        if not (0 <= tile_x < self.city.width and 0 <= tile_y < self.city.height):
            return
        if self.city.tiles[tile_y][tile_x] != "B":
            return
        self.door_positions.add((tile_x, tile_y))