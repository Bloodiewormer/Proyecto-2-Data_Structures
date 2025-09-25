import math
import time
import random
from typing import Any, Tuple, List
import arcade
from game.city import CityMap
from game.utils import normalize_angle


#Wolfenstein‑style
class RayCastRenderer:
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

        self.color_map = {
            "C": self.col_street,
            "B": self.col_building,
            "P": self.col_park,
            "player": tuple(colors.get("player", (255, 255, 0))),
        }

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

        # Minimap cache


        self._minimap_shapes = None
        self._minimap_cache_key = None



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
        self._perf_accum = {"clouds": 0.0, "walls": 0.0, "floor": 0.0, "minimap": 0.0, "frames": 0}
        self._last_perf_report = time.perf_counter()

        #limits
        self.MAX_FLOOR_DIST = 25




    # ---------- Utility ----------
    #Trigonometria

    def _get_player(self, player: Any) -> Tuple[float, float, float]:
        return float(getattr(player, "x", 0.0)), float(getattr(player, "y", 0.0)), float(getattr(player, "angle", 0.0))

    #Topics: rayc asting etup, trigonometry, caching, optimization
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
        # If list shorter than sample_rows due to denom<=0 just truncate rows
        valid_len = min(len(dists), len(sample_rows))
        self._floor_sample_rows = sample_rows[:valid_len]
        self._floor_row_dist = dists[:valid_len]
        self._cached_floor_height = (height, horizon)
        self._cached_floor_step = self.floor_row_step

        def set_horizon_ratio(self, ratio: float):
            """Adjust horizon (camera eye height) at runtime; 0.1 .. 0.9."""
            ratio = max(0.1, min(0.9, float(ratio)))
            if abs(ratio - self.horizon_ratio) > 1e-4:
                self.horizon_ratio = ratio
                # Invalidate floor cache so distances recompute
                self._cached_floor_height = None

    # ---------- Sky ----------
    def _render_sky(self, width: int, height: int, horizon: int, weather_system):
        col = self.col_sky
        if weather_system:
            col = getattr(weather_system, "sky_color", col)
        arcade.draw_lrbt_rectangle_filled(0, width, horizon, height, col)

    # ---------- Clouds ----------
    def _render_clouds(self, width: int, height: int, px: float, py: float, pang: float, weather_system):
        col_cloud = self.col_cloud
        if weather_system:
            col_cloud = getattr(weather_system, "cloud_color", col_cloud)
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
    #Digital Differential Analyzer: DDA es un algoritmo que calcula los puntos intermedios entre dos puntos
    #en una cuadrícula, permitiendo dibujar líneas rectas de manera eficiente.
    #En este contexto, se utiliza para determinar qué paredes (o edificios) son visibles desde la posición
    #del jugador y a qué distancia están.


    #Temas: raycasting, DDA, grid traversal
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

    #Temas: raycasting
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
            bottom = max(horizon - half, 0)

            # Solape para evitar línea entre pared y piso
            if bottom > 0:
                bottom -= 1  # Overdraw 1 píxel sobre el piso

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

    #Temas: drawing, optimization
    def _draw_walls(self, wall_slices):
        draw_rect = arcade.draw_lrbt_rectangle_filled
        for l, r, b, t, c in wall_slices:
            draw_rect(l, r, b, t, c)

    # ---------- Floor ----------

    def _render_floor(self, width: int, height: int, horizon: int, px: float, py: float):
        posZ = height * 0.5
        inv_posZ = 1.0 / posZ
        max_dist = self.MAX_FLOOR_DIST
        tiles = self.city.tiles
        w_lim = self.city.width
        h_lim = self.city.height
        street_col = self.col_street
        park_col = self.col_park
        draw_rect = arcade.draw_lrbt_rectangle_filled
        column_width_f = width / float(self.num_rays)

        active_runs = []

        wall_dists = []
        for (dir_x, dir_y) in self._ray_dirs:
            dist, _, _ = self._cast_wall_dda(px, py, dir_x, dir_y)
            wall_dists.append(dist if dist is not None else max_dist + 1.0)

        for ray, (dir_x, dir_y) in enumerate(self._ray_dirs):
            left = int(ray * column_width_f)
            right = int((ray + 1) * column_width_f)
            if right <= left:
                continue

            # Guard zero
            if dir_x == 0.0:
                dir_x = 1e-9
            if dir_y == 0.0:
                dir_y = 1e-9

            map_x = int(px)
            map_y = int(py)

            delta_x = abs(1.0 / dir_x)
            delta_y = abs(1.0 / dir_y)

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

            wall_cut = wall_dists[ray]
            dist_enter = 0.0005
            cur_x = map_x
            cur_y = map_y

            segments = []
            max_iter = (w_lim + h_lim) * 4  # tighter cap

            for _ in range(max_iter):
                # Next boundary
                if side_dist_x < side_dist_y:
                    dist_exit = side_dist_x
                    side_dist_x += delta_x
                    map_x += step_x
                else:
                    dist_exit = side_dist_y
                    side_dist_y += delta_y
                    map_y += step_y

                if dist_exit <= dist_enter:
                    dist_enter = dist_exit + 1e-6
                    continue

                if dist_enter >= max_dist:
                    break
                if dist_exit > max_dist:
                    dist_exit = max_dist

                # Wall cutoff (do not draw behind wall slice)
                if wall_cut and dist_enter >= wall_cut:
                    break

                # y = horizon - posZ / dist  -> use inv to reduce divisions
                y0_f = horizon - (posZ * (1.0 / dist_enter))
                y1_f = horizon - (posZ * (1.0 / dist_exit))

                if y0_f < 0 and y1_f < 0:
                    dist_enter = dist_exit
                    cur_x, cur_y = map_x, map_y
                    continue

                if y1_f < 0:
                    y1_f = 0
                if y0_f > horizon and y1_f > horizon:
                    # Fully above region we draw
                    dist_enter = dist_exit
                    cur_x, cur_y = map_x, map_y
                    continue

                y0 = int(0 if y0_f < 0 else (horizon if y0_f > horizon else y0_f))
                y1 = int(0 if y1_f < 0 else (horizon if y1_f > horizon else y1_f))
                if y1 > y0:  # ensure proper span
                    if 0 <= cur_x < w_lim and 0 <= cur_y < h_lim:
                        color = park_col if tiles[cur_y][cur_x] == "P" else street_col
                    else:
                        color = street_col
                    if segments and segments[-1][2] == color and segments[-1][1] >= y0:
                        # merge
                        if y1 > segments[-1][1]:
                            segments[-1] = (segments[-1][0], y1, color)
                    else:
                        segments.append((y0, y1, color))

                dist_enter = dist_exit
                cur_x, cur_y = map_x, map_y
                if y0 >= horizon or dist_exit >= max_dist:
                    break

            # Merge horizontally with active runs
            new_active = []
            si = 0
            ai = 0
            slen = len(segments)
            alen = len(active_runs)
            while si < slen and ai < alen:
                y0, y1, col = segments[si]
                ay0, ay1, acol, aleft, aright = active_runs[ai]
                if y0 == ay0 and y1 == ay1 and col == acol:
                    # extend
                    new_active.append([y0, y1, col, aleft, right])
                    si += 1
                    ai += 1
                else:
                    # flush whichever is "smaller" in ordering
                    if (ay0, ay1, acol) < (y0, y1, col):
                        # flush active
                        if aright > aleft:
                            draw_rect(aleft, aright, ay0, ay1, acol)
                        ai += 1
                    else:
                        # new segment starts standalone
                        new_active.append([y0, y1, col, left, right])
                        si += 1
            # Flush remaining old active that didn't match
            for j in range(ai, alen):
                ay0, ay1, acol, aleft, aright = active_runs[j]
                if aright > aleft:
                    draw_rect(aleft, aright, ay0, ay1, acol)
            # Add any leftover new segments
            for j in range(si, slen):
                y0, y1, col = segments[j]
                new_active.append([y0, y1, col, left, right])

            active_runs = new_active

        # Flush remaining runs
        for y0, y1, col, left, right in active_runs:
            if right > left and y1 > y0:
                draw_rect(left, right, y0, y1, col)





    # ---------- Minimap ----------
    #El caching es una técnica utilizada para almacenar datos o resultados de cálculos
    #En este caso, se utiliza para almacenar la representación gráfica del minimapa
    #de la ciudad, de modo que no sea necesario recalcularlo en cada fotograma

    #Temas: caching, minimap rendering
    def _ensure_minimap_cache(self, x: int, y: int, size: int):
        key = (self.city.width, self.city.height, id(self.city.tiles), size)
        if key == self._minimap_cache_key and self._minimap_shapes is not None:
            return
        scale_x = size / max(1, self.city.width)
        scale_y = size / max(1, self.city.height)
        shapes = arcade.shape_list.ShapeElementList()
        create_rect = arcade.shape_list.create_rectangle_filled
        for row in range(self.city.height):
            line = self.city.tiles[row]
            for col in range(self.city.width):
                tile = line[col]
                if tile == "B":
                    c = self.col_building
                elif tile == "P":
                    c = self.col_park
                else:
                    c = self.col_street
                cx = x + (col + 0.5) * scale_x
                cy = y + (row + 0.5) * scale_y
                shapes.append(create_rect(cx, cy, scale_x, scale_y, c))
        border = arcade.shape_list.create_rectangle_outline(
            x + size / 2, y + size / 2, size, size, arcade.color.WHITE, border_width=2
        )
        shapes.append(border)
        self._minimap_shapes = shapes
        self._minimap_cache_key = key

    #Temas: minimap rendering, player indicator
    def render_minimap(self, x: int, y: int, size: int, player):
        t0 = time.perf_counter()
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
        t1 = time.perf_counter()
        self._perf_accum["minimap"] += (t1 - t0)

    # ---------- Public world render ----------
    def render_world(self, player: Any, weather_system: Any = None):
        win = arcade.get_window()
        if not win:
            return
        width = win.width
        height = win.height
        horizon = int(height * 0.5 )
        px, py, pang = self._get_player(player)

        frame_start = time.perf_counter()

        self._prepare_rays(pang)

        # Sky first
        self._render_sky(width, height, horizon, weather_system)

        # Clouds
        t0 = time.perf_counter()
        self._render_clouds(width, height, px, py, pang, weather_system)
        t_clouds = time.perf_counter()
        self._perf_accum["clouds"] += (t_clouds - t0)

        # Floor
        t0 = time.perf_counter()
        self._render_floor(width, height, horizon, px, py)
        t_floor = time.perf_counter()
        self._perf_accum["floor"] += (t_floor - t0)

        # Walls
        t0 = time.perf_counter()
        wall_slices = self._gather_walls(width, height, horizon, px, py)
        self._draw_walls(wall_slices)
        t_walls = time.perf_counter()
        self._perf_accum["walls"] += (t_walls - t0)



        self._perf_accum["frames"] += 1
        now = time.perf_counter()
        if now - self._last_perf_report > 2.0:
            f = max(1, self._perf_accum["frames"])
            clouds_ms = (self._perf_accum["clouds"] / f) * 1000
            walls_ms = (self._perf_accum["walls"] / f) * 1000
            floor_ms = (self._perf_accum["floor"] / f) * 1000
            minimap_ms = (self._perf_accum["minimap"] / f) * 1000
            total_ms = clouds_ms + walls_ms + floor_ms + minimap_ms
            if self.debug:
                print(
                    f"[RendPerf] clouds={clouds_ms:.2f}ms walls={walls_ms:.2f}ms floor={floor_ms:.2f}ms minimap={minimap_ms:.2f}ms total≈{total_ms:.2f}ms"
                )
            self._perf_accum = {"clouds": 0.0, "walls": 0.0, "floor": 0.0, "minimap": 0.0, "frames": 0}
            self._last_perf_report = now

    # ---------- Content ----------
    def generate_door_at(self, tile_x: int, tile_y: int):
        if not self.city:
            return
        if not (0 <= tile_x < self.city.width and 0 <= tile_y < self.city.height):
            return
        if self.city.tiles[tile_y][tile_x] != "B":
            return
        self.door_positions.add((tile_x, tile_y))
