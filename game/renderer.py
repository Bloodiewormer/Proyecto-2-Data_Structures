# python
import math
from pathlib import Path
from typing import Any, Tuple, Optional

import arcade
from game.city import CityMap


class RayCastRenderer:
    def __init__(self, city: CityMap, app_config: dict):
        self.city = city

        rendering = app_config.get("rendering", {}) or {}
        colors = app_config.get("colors", {}) or {}
        textures = app_config.get("textures", {}) or {}

        # Rendering params
        self.fov: float = float(rendering.get("fov", math.pi / 3))
        self.num_rays: int = int(rendering.get("num_rays", 160))
        self.floor_row_step: int = int(rendering.get("floor_row_step", 2))

        # Colors
        self.col_street: Tuple[int, int, int] = tuple(colors.get("street", (105, 105, 105)))
        self.col_building: Tuple[int, int, int] = tuple(colors.get("building", (0, 0, 0)))
        self.col_park: Tuple[int, int, int] = tuple(colors.get("park", (144, 238, 144)))
        self.col_player: Tuple[int, int, int] = tuple(colors.get("player", (255, 255, 0)))
        self.col_sky: Tuple[int, int, int] = arcade.color.SKY_BLUE

        # Optional textures
        def _load_tex(p: Optional[str]):
            if not p:
                return None
            try:
                return arcade.load_texture(p)
            except Exception:
                return None

        self.color_map = {
            "C": tuple(app_config.get("colors", {}).get("street", (105, 105, 105))),
            "B": tuple(app_config.get("colors", {}).get("building", (198, 134, 110))),
            "P": tuple(app_config.get("colors", {}).get("park", (144, 238, 144))),
            "player": tuple(app_config.get("colors", {}).get("player", (255, 255, 0))),
        }
        self._minimap_shapes: Optional[arcade.shape_list.ShapeElementList] = None
        self._minimap_cache_key: Optional[Tuple] = None

        self.tex_sky: Optional[arcade.Texture] = _load_tex(textures.get("sky"))
        self.tex_wall: Optional[arcade.Texture] = _load_tex(textures.get("wall"))

    def _get_player(self, player: Any) -> Tuple[float, float, float]:
        px = getattr(player, "x", None)
        py = getattr(player, "y", None)
        if (px is None or py is None) and hasattr(player, "position"):
            try:
                px, py = player.position
            except Exception:
                px, py = 0.0, 0.0
        if px is None or py is None:
            px, py = 0.0, 0.0

        ang = getattr(player, "angle", None)
        if ang is None and hasattr(player, "get_forward_vector"):
            try:
                fx, fy = player.get_forward_vector()
                ang = math.atan2(fy, fx)
            except Exception:
                ang = 0.0
        if ang is None:
            ang = 0.0
        return float(px), float(py), float(ang)

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

        side = 0  # 0 = vertical side, 1 = horizontal side
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
                if side == 0:
                    denom = dir_x if dir_x != 0.0 else 1e-6
                    dist = (map_x - pos_x + (1 - step_x) / 2) / denom
                else:
                    denom = dir_y if dir_y != 0.0 else 1e-6
                    dist = (map_y - pos_y + (1 - step_y) / 2) / denom
                if dist <= 0:
                    dist = 0.0001
                return dist, side
        return None, None

    def _floor_color_for(self, mx: int, my: int) -> Tuple[int, int, int]:
        t = self.city.get_tile_at(mx, my)
        if t == "P":
            return self.col_park
        return self.col_street

    def render_world(self, player: Any, weather_system: Any = None):
        win = arcade.get_window()
        if not win:
            return

        width = win.width
        height = win.height
        horizon = height // 2
        posZ = height / 2.0

        # Draw sky (top half). Texture if available, else sky color shows via background.
        if self.tex_sky:
            cx = width * 0.5
            cy = height - (horizon * 0.5)
            arcade.draw_texture_rect(self.tex_sky, arcade.XYWH(cx, cy, width, horizon))

        px, py, pang = self._get_player(player)
        column_width_f = width / float(self.num_rays)

        for ray in range(self.num_rays):
            # Ray dir
            ray_angle = pang - self.fov / 2.0 + (ray / float(self.num_rays)) * self.fov
            dir_x = math.cos(ray_angle)
            dir_y = math.sin(ray_angle)

            # Column bounds
            left = int(ray * column_width_f)
            right = int((ray + 1) * column_width_f)
            if right <= left:
                right = left + 1

            dist, side = self._cast_wall_dda(px, py, dir_x, dir_y)

            wall_bottom = 0
            if dist is not None:
                slice_h = int(height / max(dist, 1e-4))
                half = slice_h // 2
                bottom = max(0, horizon - half)
                top = min(height, horizon + half)
                cx = (left + right) * 0.5
                cy = (bottom + top) * 0.5
                w = max(1, right - left)
                h = max(1, top - bottom)

                if self.tex_wall:
                    arcade.draw_texture_rect(self.tex_wall, arcade.XYWH(cx, cy, w, h))
                else:
                    wall_color = self.col_building
                    if side == 1:
                        wall_color = (
                            max(0, wall_color[0] - 20),
                            max(0, wall_color[1] - 20),
                            max(0, wall_color[2] - 20),
                        )
                    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, wall_color)
                wall_bottom = bottom
            else:
                wall_bottom = horizon

            # Floor fill (streets/parks)
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

    def _ensure_minimap_cache(self, x: int, y: int, size: int):
        """
        Build a ShapeElementList with all minimap tiles and border.
        Rebuild only if x/y/size, map size or colors change.
        """
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