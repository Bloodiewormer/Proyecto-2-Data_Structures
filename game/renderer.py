import arcade
import math
from typing import Dict, Any, Tuple, Optional

from .utils import clamp


class RayCastRenderer:
    def __init__(self, city_map, config: Dict[str, Any]):
        self.city = city_map
        self.config = config

        # Rendering config
        render_config = config.get("rendering", {})
        self.fov = render_config.get("fov", math.pi / 3)  # ~60 deg
        self.num_rays = render_config.get("num_rays", 160)
        self.floor_row_step = int(render_config.get("floor_row_step", 1))
        self.max_view_distance = float(render_config.get("maxViewDistance", 64.0))

        # Display config
        display_config = config.get("display", {})
        self.screen_width = display_config.get("width", 800)
        self.screen_height = display_config.get("height", 600)

        # Colors
        colors = config.get("colors", {})
        self.color_map = {
            "C": tuple(colors.get("street", [105, 105, 105])),
            "B": tuple(colors.get("building", [0, 0, 0])),
            "P": tuple(colors.get("park", [144, 238, 144])),
            "player": tuple(colors.get("player", [255, 255, 0])),
            "pickup": tuple(colors.get("pickup", [0, 255, 0])),
            "dropoff": tuple(colors.get("dropoff", [255, 0, 0])),
        }

        # Cached values independent of ray count
        self.horizon = self.screen_height // 2
        self.pos_z = self.screen_height / 2  # camera plane height

        arcade.set_background_color(arcade.color.SKY_BLUE)

        # Minimap cache (Arcade 3.2.2 API via arcade.shape_list)
        self._minimap_shapes: Optional[Any] = None
        self._minimap_cache_key: Optional[Tuple] = None

    def render_world(self, player, weather_system=None):
        if not self.city or not getattr(self.city, "tiles", None):
            return

        # Recompute so changing num_rays at runtime works
        self.num_rays = max(1, int(self.num_rays))
        column_width = self.screen_width / self.num_rays

        visibility = weather_system.get_visibility_multiplier() if weather_system else 1.0

        for ray in range(self.num_rays):
            self._render_column(ray, player, visibility, column_width)

    def _render_column(self, ray_index: int, player, visibility: float, column_width: float):
        # Center rays inside their column
        ray_angle = player.angle - self.fov * 0.5 + ((ray_index + 0.5) / self.num_rays) * self.fov
        dir_x = math.cos(ray_angle)
        dir_y = math.sin(ray_angle)

        # Pixel column bounds
        left = int(ray_index * column_width)
        right = int((ray_index + 1) * column_width)
        if right <= left:
            right = left + 1

        # Clamp work to the map AABB
        exit_dist = self._ray_exit_distance(player.x, player.y, dir_x, dir_y)
        ray_max_dist = min(self.max_view_distance, exit_dist)

        # 1) Cast to wall with DDA (bounded)
        wall_distance, wall_side = self._cast_wall_ray(player.x, player.y, dir_x, dir_y, ray_max_dist)

        # 2) Draw wall slice (if any)
        floor_limit_y = self.horizon  # if no wall, limit is horizon
        if wall_distance is not None:
            floor_limit_y = self._render_wall_slice(left, right, wall_distance, wall_side, visibility)

        # 3) Floor slice via cell-DDA (bounded)
        self._render_floor_slice(left, right, floor_limit_y, player, dir_x, dir_y, visibility, ray_max_dist)

    def _ray_exit_distance(self, px: float, py: float, dx: float, dy: float) -> float:
        """
        Forward distance along the ray until it exits the map AABB.
        Prevents rays/floor from marching 'to infinity' outside the map.
        """
        w, h = self.city.width, self.city.height

        # Distances to vertical boundaries
        if dx > 0.0:
            tx = (w - px) / dx
        elif dx < 0.0:
            tx = (0.0 - px) / dx
        else:
            tx = float("inf")

        # Distances to horizontal boundaries
        if dy > 0.0:
            ty = (h - py) / dy
        elif dy < 0.0:
            ty = (0.0 - py) / dy
        else:
            ty = float("inf")

        exit_d = min(tx if tx > 0 else float("inf"), ty if ty > 0 else float("inf"))
        if not math.isfinite(exit_d):
            return self.max_view_distance
        return max(1e-6, exit_d)

    def _cast_wall_ray(
        self,
        start_x: float,
        start_y: float,
        dir_x: float,
        dir_y: float,
        max_dist: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[int]]:
        pos_x, pos_y = start_x, start_y
        map_x, map_y = int(pos_x), int(pos_y)

        width = self.city.width
        height = self.city.height
        tiles = self.city.tiles

        # Ray unit step distances
        delta_dist_x = abs(1.0 / dir_x) if dir_x != 0.0 else 1e30
        delta_dist_y = abs(1.0 / dir_y) if dir_y != 0.0 else 1e30

        # Step direction and initial side distances
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

        side = 0  # 0 = vertical, 1 = horizontal
        # A ray can cross at most width+height grid lines inside the box
        max_steps = self.city.width + self.city.height + 2
        steps = 0

        while 0 <= map_x < width and 0 <= map_y < height and steps < max_steps:
            steps += 1

            # Early-out by next boundary distance
            next_boundary_dist = side_dist_x if side_dist_x < side_dist_y else side_dist_y
            if max_dist is not None and next_boundary_dist > max_dist:
                break

            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if not (0 <= map_x < width and 0 <= map_y < height):
                break

            if tiles[map_y][map_x] == "B":
                # Perpendicular distance (avoid fish-eye)
                if side == 0:
                    denom = dir_x if dir_x != 0 else 1e-6
                    dist = (map_x - pos_x + (1 - step_x) * 0.5) / denom
                else:
                    denom = dir_y if dir_y != 0 else 1e-6
                    dist = (map_y - pos_y + (1 - step_y) * 0.5) / denom
                if max_dist is not None and dist > max_dist:
                    break
                return max(dist, 1e-6), side

        return None, None

    def _render_wall_slice(self, left: int, right: int, distance: float, side: int, visibility: float) -> int:
        # Compute wall size
        safe_dist = max(distance, 1e-6)
        wall_height = int(self.screen_height / safe_dist)
        half_height = wall_height // 2

        # Screen-space slice
        draw_bottom = max(0, int(self.horizon - half_height))                   # lower y
        draw_top = min(self.screen_height, int(self.horizon + half_height))     # higher y

        # Shade by side/depth/visibility (stable, not per-row)
        base = self.color_map["B"]
        depth_factor = 1.0 / (1.0 + safe_dist * 0.10)
        side_factor = 0.85 if side == 1 else 1.0
        visibility_factor = clamp(visibility, 0.3, 1.0)
        total = clamp(depth_factor * side_factor * visibility_factor, 0.2, 1.0)
        wall_color = (int(base[0] * total), int(base[1] * total), int(base[2] * total))

        arcade.draw_lrbt_rectangle_filled(left, right, draw_bottom, draw_top, wall_color)
        return draw_bottom

    def _render_floor_slice(
        self,
        left: int,
        right: int,
        floor_limit_y: int,
        player,
        dir_x: float,
        dir_y: float,
        visibility: float,
        max_dist: float,
    ):
        # Render floor by sweeping cells (DDA)
        horizon = self.horizon
        if floor_limit_y <= 0 or horizon <= 0:
            return

        y_limit = min(horizon - 1, int(floor_limit_y))
        if y_limit <= 0:
            return

        px = player.x
        py = player.y
        pos_z = self.pos_z

        width = self.city.width
        height = self.city.height
        tiles = self.city.tiles
        col_street = self.color_map["C"]
        col_park = self.color_map["P"]

        levels = 32
        att = 0.05
        clamp_vis = clamp(visibility, 0.2, 1.0)
        step_y_quant = max(1, int(self.floor_row_step))

        map_x = int(px)
        map_y = int(py)
        delta_x = abs(1.0 / dir_x) if dir_x != 0.0 else 1e30
        delta_y = abs(1.0 / dir_y) if dir_y != 0.0 else 1e30

        if dir_x < 0:
            step_x = -1
            side_dist_x = (px - map_x) * delta_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - px) * delta_x

        if dir_y < 0:
            step_y = -1
            side_dist_y = (py - map_y) * delta_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - py) * delta_y

        # Start distance at the bottom scanline
        d_prev = max(1e-6, pos_z / max(1.0, float(horizon)))  # ~1.0

        def y_from_dist(d: float) -> int:
            return int(horizon - (pos_z / max(d, 1e-6)))

        draw_rect = arcade.draw_lrbt_rectangle_filled
        last_color = None
        seg_bottom = None
        seg_top = None

        # A ray crosses at most width+height cells before exiting the map
        max_steps = width + height + 2
        steps = 0

        while steps < max_steps:
            steps += 1

            use_x = side_dist_x < side_dist_y
            d_next = side_dist_x if use_x else side_dist_y

            # Cap to max distance
            if d_next > max_dist:
                d_next = max_dist

            y0 = y_from_dist(d_prev)
            y1 = y_from_dist(d_next)
            if y1 < y0:
                y0, y1 = y1, y0

            y0 = max(0, min(y0, y_limit))
            y1 = max(0, min(y1, y_limit))

            if y1 > y0:
                if 0 <= map_x < width and 0 <= map_y < height:
                    t = tiles[map_y][map_x]
                    base = col_park if t == "P" else col_street
                else:
                    # Outside map -> don't shade further; break after flushing
                    base = col_street

                d_mid = 0.5 * (d_prev + d_next)
                raw = (1.0 / (1.0 + d_mid * att)) * clamp_vis
                q = max(0, min(levels, int(raw * levels)))
                factor = q / levels
                color = (int(base[0] * factor), int(base[1] * factor), int(base[2] * factor))

                y0q = (y0 // step_y_quant) * step_y_quant
                y1q = min(y_limit, ((y1 + step_y_quant - 1) // step_y_quant) * step_y_quant)

                if y1q > y0q:
                    if last_color is None:
                        last_color = color
                        seg_bottom = y0q
                        seg_top = y1q
                    elif color == last_color and y0q <= seg_top:
                        seg_top = max(seg_top, y1q)
                    else:
                        draw_rect(left, right, seg_bottom, seg_top, last_color)
                        last_color = color
                        seg_bottom = y0q
                        seg_top = y1q

            d_prev = d_next

            # Stop if we've filled the column, hit max distance, or left the map
            if y_from_dist(d_prev) >= y_limit or d_prev >= max_dist:
                break

            if use_x:
                side_dist_x += delta_x
                map_x += step_x
            else:
                side_dist_y += delta_y
                map_y += step_y

            if not (0 <= map_x < width and 0 <= map_y < height):
                # Outside map; stop sweeping further
                break

        # Flush last merged segment
        if last_color is not None and seg_bottom is not None and seg_top is not None and seg_top > seg_bottom:
            draw_rect(left, right, seg_bottom, seg_top, last_color)

    def _get_floor_base_color(self, map_x: int, map_y: int) -> Tuple[int, int, int]:
        if not (0 <= map_x < self.city.width and 0 <= map_y < self.city.height):
            return self.color_map["C"]
        t = self.city.tiles[map_y][map_x]
        return self.color_map["P"] if t == "P" else self.color_map["C"]

    def _get_floor_color(self, map_x: int, map_y: int, distance: float, visibility: float) -> Tuple[int, int, int]:
        base = self._get_floor_base_color(map_x, map_y)
        depth_factor = clamp(1.0 - (distance * 0.05), 0.1, 1.0)
        visibility_factor = clamp(visibility, 0.2, 1.0)
        factor = clamp(depth_factor * visibility_factor, 0.1, 1.0)
        return tuple(int(c * factor) for c in base)

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
