import math
import time
import random
from typing import Any, Tuple, List
import arcade
from game.core.city import CityMap
from game.core.utils import normalize_angle


class RayCastRenderer:
    """
    Renderer de mundo (raycasting estilo Wolfenstein) sin responsabilidades de UI.
    El minimapa fue extraído a game.ui.minimap.MinimapRenderer.
    """
    def __init__(self, city: CityMap, app_config: dict):
        self.city = city
        rendering = app_config.get("rendering", {}) or {}
        colors = app_config.get("colors", {}) or {}

        # Core params
        self.fov: float = float(rendering.get("fov", math.pi / 3))
        self.num_rays: int = int(rendering.get("num_rays", 120))
        self.floor_row_step: int = int(rendering.get("floor_row_step", 2))

        # Colors
        self.col_street = tuple(colors.get("street", (105, 105, 105)))
        self.col_building = tuple(colors.get("building", (160, 120, 80)))
        self.col_park = tuple(colors.get("park", (144, 238, 144)))
        self.col_sky = tuple(colors.get("sky", (135, 206, 235)))
        self.col_cloud = tuple(colors.get("cloud", (255, 255, 255)))
        self.col_wall = tuple(colors.get("wall", (200, 200, 200)))
        self.col_wall_dark = tuple(colors.get("wall_dark", (160, 160, 160)))
        self.col_door = tuple(colors.get("door", (139, 69, 19)))

        # Clouds
        map_span = max(30, max(self.city.width, self.city.height))
        random.seed(3)
        self.cloud_groups = []
        for _ in range(5):
            cx = random.uniform(0, map_span)
            cy = random.uniform(0, map_span)
            puffs = []
            for _p in range(14):
                jx = random.randint(-22, 22)
                jy = random.randint(-10, 10)
                scale = random.uniform(0.45, 1.0)
                puffs.append((jx, jy, scale))
            self.cloud_groups.append((cx, cy, puffs))

        # Doors
        self.door_positions = set()

        # Floor precomputation
        self._cached_floor_height = None
        self._cached_floor_step = None
        self._floor_sample_rows: List[int] = []
        self._floor_row_dist: List[float] = []

        # Rays cache
        self._ray_dirs: List[Tuple[float, float]] = []
        self._ray_last_angle = None
        self._ray_last_num = None

        # Perf
        self.debug = bool(app_config.get("debug", False))
        self._perf_accum = {"clouds": 0.0, "walls": 0.0, "floor": 0.0, "frames": 0}
        self._last_perf_report = time.perf_counter()

        # limits
        self.MAX_FLOOR_DIST = 25

    # ---------- Utility ----------
    def _get_player(self, player: Any) -> Tuple[float, float, float]:
        return float(getattr(player, "x", 0.0)), float(getattr(player, "y", 0.0)), float(getattr(player, "angle", 0.0))

    def _prepare_rays(self, pang: float):
        if self._ray_last_angle == pang and self._ray_last_num == self.num_rays:
            return
        dirs = []
        fov = self.fov
        start = pang - fov * 0.5
        if self.num_rays <= 1:
            dirs.append((math.cos(pang), math.sin(pang)))
        else:
            for i in range(self.num_rays):
                ang = start + (i / (self.num_rays - 1)) * fov
                dirs.append((math.cos(ang), math.sin(ang)))
        self._ray_dirs = dirs
        self._ray_last_angle = pang
        self._ray_last_num = self.num_rays

    def _prepare_floor_rows(self, height: int, horizon: int):
        if (self._cached_floor_height == (height, horizon)
                and self._cached_floor_step == self.floor_row_step):
            return
        posZ = height * 0.5
        step = max(1, self.floor_row_step)
        sample_rows = list(range(0, horizon, step))
        dists = []
        maxd = self.MAX_FLOOR_DIST
        for y in sample_rows:
            denom = (horizon - (y + 0.5))
            if denom <= 0:
                d = None
            else:
                dist = posZ / denom
                if maxd and dist > maxd:
                    dist = maxd
                dists.append(dist)
        valid_len = min(len(dists), len(sample_rows))
        self._floor_sample_rows = sample_rows[:valid_len]
        self._floor_row_dist = dists[:valid_len]
        self._cached_floor_height = (height, horizon)
        self._cached_floor_step = self.floor_row_step

    def set_horizon_ratio(self, ratio: float):
        ratio = max(0.1, min(0.9, float(ratio)))
        if abs(ratio - getattr(self, 'horizon_ratio', 0.5)) > 1e-4:
            self.horizon_ratio = ratio
            self._cached_floor_height = None

    # ---------- Sky ----------
    def _render_sky(self, width: int, height: int, horizon: int, weather_system):
        col = self.col_sky
        if weather_system:
            col = weather_system.sky_color
        arcade.draw_lrbt_rectangle_filled(0, width, horizon, height, col)

    # ---------- Clouds ----------
    def _render_clouds(self, width: int, height: int, px: float, py: float, pang: float, weather_system):
        col_cloud = self.col_cloud
        if weather_system:
            col_cloud = weather_system.cloud_color
        cloud_y = int(height * 0.75)
        half_fov = self.fov * 0.5
        draw_ellipse = arcade.draw_ellipse_filled
        for (cx, cy, puffs) in self.cloud_groups:
            dx = cx - px
            dy = cy - py
            dist = math.hypot(dx, dy)
            if dist > 140:
                continue
            bearing = math.atan2(dy, dx)
            delta = normalize_angle(bearing - pang)
            if abs(delta) > (half_fov + 0.2):
                continue
            sx = int(((delta / self.fov) + 0.5) * width)
            size_base = max(8, int(260 / (18 + dist)))
            if dist > 100:
                skip = 0.75
            elif dist > 70:
                skip = 0.5
            elif dist > 50:
                skip = 0.25
            else:
                skip = 0.0
            for (jx, jy, s) in puffs:
                if skip and random.random() < skip:
                    continue
                w = int(size_base * 0.4 * (1 + s))
                h = int(size_base * 0.18 * (1 + s))
                if w < 2 or h < 2:
                    continue
                draw_ellipse(sx + jx, cloud_y + jy, w * 2, h, col_cloud)

    # ---------- Walls ----------
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
        max_iter = (self.city.width + self.city.height) * 4
        it = 0
        while 0 <= map_x < self.city.width and 0 <= map_y < self.city.height and it < max_iter:
            tile = self.city.tiles[map_y][map_x]
            if tile == "B":
                if side == 0:
                    perp = (map_x - pos_x + (1 - step_x) * 0.5) / (dir_x if dir_x != 0 else 1e-6)
                else:
                    perp = (map_y - pos_y + (1 - step_y) * 0.5) / (dir_y if dir_y != 0 else 1e-6)
                return abs(perp), side, (map_x, map_y) in self.door_positions
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            it += 1
        return None, None, False

    def _gather_walls(self, width: int, height: int, horizon: int, px: float, py: float):
        wall_slices = []
        column_width_f = width / float(self.num_rays)
        for ray, (dir_x, dir_y) in enumerate(self._ray_dirs):
            left = int(ray * column_width_f)
            right = int((ray + 1) * column_width_f)
            if right <= left:
                continue
            dist, side, is_door = self._cast_wall_dda(px, py, dir_x, dir_y)
            if dist is None or dist <= 0:
                continue
            line_h = int(height / max(0.0001, dist))
            half = line_h // 2
            top = min(height, horizon + half)
            bottom = max(0, horizon - half)
            if bottom < top:
                col = self.col_door if is_door else (self.col_wall_dark if side else self.col_wall)
                wall_slices.append((left, right, bottom, top, col))

        # Merge horizontal
        merged = []
        if wall_slices:
            cur = list(wall_slices[0])
            for s in wall_slices[1:]:
                if s[2] == cur[2] and s[3] == cur[3] and s[4] == cur[4] and s[0] == cur[1]:
                    cur[1] = s[1]
                else:
                    merged.append(tuple(cur))
                    cur = list(s)
            merged.append(tuple(cur))
        return merged

    def _draw_walls(self, wall_slices):
        draw_rect = arcade.draw_lrbt_rectangle_filled
        for l, r, b, t, c in wall_slices:
            draw_rect(l, r, b, t, c)

    # ---------- Floor ----------
    def _render_floor(self, width: int, height: int, horizon: int, px: float, py: float):
        # Fill base street once
        draw_rect = arcade.draw_lrbt_rectangle_filled
        draw_rect(0, width, 0, horizon, self.col_street)

        # Prepare rows and rays
        self._prepare_floor_rows(height, horizon)
        if not self._floor_sample_rows or not self._ray_dirs:
            return

        # Local refs for speed
        tiles = self.city.tiles
        W = self.city.width
        H = self.city.height
        park_col = self.col_park
        rays = self._ray_dirs
        num_rays = self.num_rays
        step = max(1, self.floor_row_step)

        # Precompute screen column pixel bounds once
        column_width_f = width / float(num_rays)
        col_left = [int(i * column_width_f) for i in range(num_rays)]
        col_right = [int((i + 1) * column_width_f) for i in range(num_rays)]
        last_right = col_right[-1] if num_rays > 0 else 0

        # For each sampled row, draw contiguous park spans as single rects
        for idx, y in enumerate(self._floor_sample_rows):
            dist = self._floor_row_dist[idx]
            if dist is None:
                continue

            bottom = max(0, y)
            top = min(horizon, y + step)
            if bottom >= top:
                continue

            in_span = False
            span_left_px = 0

            # Scan all rays and group consecutive park columns
            for r in range(num_rays):
                dir_x, dir_y = rays[r]
                wx = px + dir_x * dist
                wy = py + dir_y * dist
                tx = int(wx)
                ty = int(wy)
                is_park = (0 <= tx < W) and (0 <= ty < H) and (tiles[ty][tx] == "P")

                if is_park:
                    if not in_span:
                        in_span = True
                        span_left_px = col_left[r]
                else:
                    if in_span:
                        in_span = False
                        right_px = col_right[r - 1] if r > 0 else col_right[0]
                        if right_px > span_left_px:
                            draw_rect(span_left_px, right_px, bottom, top, park_col)

            # Flush tail span if it reaches the last column
            if in_span and last_right > span_left_px:
                draw_rect(span_left_px, last_right, bottom, top, park_col)

    # ---------- Public world render ----------
    def render_world(self, player, weather_system=None, delta_time=0.016):
        """
        Renderiza el mundo 3D completo

        Args:
            player: Objeto del jugador
            weather_system: Sistema de clima (opcional)
            delta_time: Tiempo desde el último frame (default: 0.016 = 60fps)
        """
        win = arcade.get_window()
        if not win:
            return
        width = win.width
        height = win.height
        horizon = int(height * 0.5)
        px, py, pang = self._get_player(player)

        self._prepare_rays(pang)

        # Sky first
        self._render_sky(width, height, horizon, weather_system)

        # Clouds
        t0 = time.perf_counter()
        self._render_clouds(width, height, px, py, pang, weather_system)
        t_clouds = time.perf_counter()
        self._perf_accum["clouds"] += (t_clouds - t0)

        # Floor - BEFORE walls to avoid overlaps
        t0 = time.perf_counter()
        self._render_floor(width, height, horizon, px, py)
        t_floor = time.perf_counter()
        self._perf_accum["floor"] += (t_floor - t0)

        # Walls - AFTER floor
        t0 = time.perf_counter()
        wall_slices = self._gather_walls(width, height, horizon, px, py)
        self._draw_walls(wall_slices)
        t_walls = time.perf_counter()
        self._perf_accum["walls"] += (t_walls - t0)

        # ============ RENDERIZAR AI PLAYERS ============
        t0 = time.perf_counter()
        if hasattr(win, 'ai_players') and win.ai_players:
            # Inicializar renderer de AIs si no existe
            if not hasattr(self, 'ai_sprite_renderer'):
                try:
                    from game.rendering.ai_sprite_renderer import AISpriteRenderer
                    self.ai_sprite_renderer = AISpriteRenderer({"debug": self.debug})
                    if self.debug:
                        print("[WorldRenderer] AI Sprite Renderer inicializado")
                except Exception as e:
                    if self.debug:
                        print(f"[WorldRenderer] Error inicializando AI renderer: {e}")
                    self.ai_sprite_renderer = None

            # Renderizar AIs
            if self.ai_sprite_renderer:
                try:
                    self.ai_sprite_renderer.render_ai_in_world(
                        win.ai_players,
                        px, py, pang,
                        width, height,
                        self.fov,
                        delta_time
                    )
                except Exception as e:
                    if self.debug:
                        print(f"[WorldRenderer] Error renderizando AIs: {e}")

        t_ai = time.perf_counter()
        if "ai" not in self._perf_accum:
            self._perf_accum["ai"] = 0.0
        self._perf_accum["ai"] += (t_ai - t0)
        # ===============================================

        self._perf_accum["frames"] += 1
        now = time.perf_counter()
        if now - self._last_perf_report > 2.0 and self.debug:
            f = max(1, self._perf_accum["frames"])
            clouds_ms = (self._perf_accum["clouds"] / f) * 1000
            walls_ms = (self._perf_accum["walls"] / f) * 1000
            floor_ms = (self._perf_accum["floor"] / f) * 1000
            ai_ms = (self._perf_accum.get("ai", 0.0) / f) * 1000
            total_ms = clouds_ms + walls_ms + floor_ms + ai_ms
            print(
                f"[WorldRenderer] clouds:{clouds_ms:.2f}ms floor:{floor_ms:.2f}ms walls:{walls_ms:.2f}ms ai:{ai_ms:.2f}ms total:{total_ms:.2f}ms")
            self._perf_accum = {"clouds": 0.0, "walls": 0.0, "floor": 0.0, "ai": 0.0, "frames": 0}
            self._last_perf_report = now

    def get_perf_snapshot(self):
        f = max(1, self._perf_accum.get("frames", 0))
        if f <= 0:
            return {"clouds_ms": 0.0, "floor_ms": 0.0, "walls_ms": 0.0, "total_ms": 0.0}
        clouds_ms = (self._perf_accum["clouds"] / f) * 1000.0
        floor_ms = (self._perf_accum["floor"] / f) * 1000.0
        walls_ms = (self._perf_accum["walls"] / f) * 1000.0
        return {
            "clouds_ms": clouds_ms,
            "floor_ms": floor_ms,
            "walls_ms": walls_ms,
            "total_ms": clouds_ms + floor_ms + walls_ms,
        }

    # ---------- Content ----------
    def generate_door_at(self, tile_x: int, tile_y: int):
        if not self.city:
            return
        if not (0 <= tile_x < self.city.width and 0 <= tile_y < self.city.height):
            return
        if self.city.tiles[tile_y][tile_x] != "B":
            return
        self.door_positions.add((tile_x, tile_y))