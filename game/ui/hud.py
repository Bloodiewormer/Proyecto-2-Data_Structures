import math
import random
import arcade
from game.core.utils import format_time
from game.ui.inventory_panel import InventoryPanel


class HUDRenderer:
    """
    Dibuja el HUD completo (earnings, tiempo, stamina, reputación, velocímetro, icono del clima,
    textos de ayuda y métricas de debug). Mantiene posiciones originales.
    """
    def __init__(self, app_config: dict, debug: bool = False):
        self.app_config = app_config
        self.debug = bool(debug)
        self._inv_panel = None
        self._last_game = None

    # --------- Public ---------
    def draw(self, game):
        # Solo debug: mostrar FPS, rays y métricas de rendimiento
        if getattr(game, "debug", False):
            # FPS / Rays
            dt_list = game.frame_times[-60:] if hasattr(game, "frame_times") else []
            avg_dt = (sum(dt_list) / len(dt_list)) if dt_list else 0.0
            avg_fps = (1.0 / avg_dt) if avg_dt > 0 else 0.0
            rays = getattr(game.renderer, "num_rays", 0)
            arcade.draw_text(f"FPS: {avg_fps:.1f} | Rays: {rays}", 10, game.height - 20, arcade.color.YELLOW, 12)

            # Perf renderer y minimapa
            rx = 10
            ry = game.height - 40
            if getattr(game, "renderer", None) and hasattr(game.renderer, "get_perf_snapshot"):
                snap = game.renderer.get_perf_snapshot()
                arcade.draw_text(f"World ms - clouds:{snap['clouds_ms']:.2f} floor:{snap['floor_ms']:.2f} walls:{snap['walls_ms']:.2f} total:{snap['total_ms']:.2f}",
                                 rx, ry - 16, arcade.color.LIGHT_GRAY, 10)
            if getattr(game, "minimap", None) and hasattr(game.minimap, "get_perf_snapshot"):
                ms = game.minimap.get_perf_snapshot().get("render_ms", 0.0)
                arcade.draw_text(f"Minimap ms:{ms:.2f}", rx, ry - 32, arcade.color.LIGHT_GRAY, 10)

        self._last_game = game
        self.ensure_inventory_panel(game)
        # Inventario (panel) en esquina superior derecha
        if self._inv_panel:
            inventory_width = 450
            inventory_height = 400
            inventory_x = game.width - inventory_width - 50
            inventory_y = game.height - inventory_height - 50
            self._inv_panel.draw(inventory_x, inventory_y, inventory_width, inventory_height)

        # Métricas rápidas (solo debug)
        if self.debug and game.frame_times:
            dt_list = game.frame_times[-60:]
            avg_dt = (sum(dt_list) / len(dt_list)) if dt_list else 0.0
            avg_fps = (1.0 / avg_dt) if avg_dt > 0 else 0.0
            rays = game.renderer.num_rays if game.renderer else 0
            arcade.draw_text(f"FPS: {avg_fps:.1f} | Rays: {rays}", 10, game.height - 60, arcade.color.YELLOW, 10)

        # Posición del jugador (solo debug)
        if self.debug and game.player:
            arcade.draw_text(
                f"Pos: ({game.player.x:.1f}, {game.player.y:.1f}) Angle: {game.player.angle:.2f} rad",
                10, game.height - 80, arcade.color.WHITE, 12
            )

        # Tiempo y earnings
        earnings = game.player.earnings if game.player else 0.0
        time_str = format_time(game.time_remaining)
        goal_earnings = int(self.app_config.get("game", {}).get("goal_earnings", 500))
        time_color = arcade.color.WHITE
        if game.time_remaining < 120:
            time_color = arcade.color.RED
        elif game.time_remaining < 300:
            time_color = arcade.color.YELLOW

        self._draw_earnings_progress_top(game, earnings, goal_earnings)
        self._draw_time_countdown_bottom(game, time_str, time_color)

        # Barras: stamina y reputación
        if game.player:
            self._draw_stamina_bar(game)
            self._draw_reputation_bar(game)

        # Velocímetro + icono de clima
        if game.player:
            self._draw_bike_speedometer(game)
            self._draw_weather_icon_right_of_speedometer(game)

        # Atajos
        _y = game.height - 350
        _h = 18
        arcade.draw_text("ESC - Pausa", game.width - 100, game.height - 30, arcade.color.WHITE, 12, anchor_x="center")
        arcade.draw_text(" I - Inventario", game.width - 60, _y - _h, arcade.color.WHITE, 12, anchor_x="center")
        arcade.draw_text(" O - Pedidos", game.width - 60, _y - 2 * _h, arcade.color.WHITE, 12, anchor_x="center")
        arcade.draw_text(" U - Devolverse", game.width - 60, _y - 3 * _h, arcade.color.WHITE, 12, anchor_x="center")

        self._draw_pending_bell(game)

    # --------- Private (helpers) ---------
    def _draw_earnings_progress_top(self, game, earnings: float, goal_earnings: float):
        bar_width = 260
        bar_height = 18
        center_x = game.width // 2
        bar_x1 = center_x - bar_width // 2 - 10
        bar_x2 = bar_x1 + bar_width
        bar_y1 = game.height - 44
        bar_y2 = bar_y1 + bar_height

        arcade.draw_lrbt_rectangle_filled(bar_x1, bar_x2, bar_y1, bar_y2, (0, 0, 0, 180))
        arcade.draw_lrbt_rectangle_outline(bar_x1, bar_x2, bar_y1, bar_y2, arcade.color.WHITE, 2)

        progress = max(0.0, min(1.0, (earnings / goal_earnings) if goal_earnings > 0 else 0.0))
        fill_w = int((bar_x2 - bar_x1 - 2) * progress)
        if fill_w > 0:
            if progress < 0.33:
                fill_color = arcade.color.DARK_RED
            elif progress < 0.66:
                fill_color = arcade.color.YELLOW
            else:
                fill_color = arcade.color.GREEN
            arcade.draw_lrbt_rectangle_filled(bar_x1 + 1, bar_x1 + 1 + fill_w, bar_y1 + 1, bar_y2 - 1, fill_color)

        pct = progress * 100.0
        label = f"${earnings:.0f} / ${goal_earnings:.0f} ({pct:.1f}%)"
        label_x = bar_x1 + (bar_x2 - bar_x1) // 2
        label_y = bar_y1 + 2
        arcade.draw_text(label, label_x, label_y, arcade.color.WHITE, 12, anchor_x="center")

    def _draw_time_countdown_bottom(self, game, time_str: str, time_color: tuple):
        pill_width = 220
        pill_height = 26
        cx = game.width // 2
        y_bottom = 10
        x1 = cx - pill_width // 2
        x2 = cx + pill_width // 2
        y1 = y_bottom
        y2 = y_bottom + pill_height

        arcade.draw_lrbt_rectangle_filled(x1, x2, y1, y2, (0, 0, 0, 160))
        arcade.draw_lrbt_rectangle_outline(x1, x2, y1, y2, arcade.color.WHITE, 2)
        arcade.draw_text(f"Remaining: {time_str}", cx, y1 + 5, time_color, 14, anchor_x="center")

    def _draw_stamina_bar(self, game):
        bar_width = 200
        bar_height = 20
        bar_x = game.width - bar_width - 80
        bar_y = 30
        stamina = game.player.stamina
        max_stamina = getattr(game.player, 'max_stamina', 100)
        stamina_percent = max(0.0, min(1.0, stamina / max_stamina))
        arcade.draw_lrbt_rectangle_filled(bar_x, bar_x + bar_width, bar_y, bar_y + bar_height, arcade.color.BLACK)
        if stamina_percent > 0:
            green_width = int(bar_width * stamina_percent)
            arcade.draw_lrbt_rectangle_filled(bar_x, bar_x + green_width, bar_y, bar_y + bar_height, arcade.color.GREEN)
        arcade.draw_lrbt_rectangle_outline(bar_x, bar_x + bar_width, bar_y, bar_y + bar_height, arcade.color.WHITE, 2)
        stamina_text = f"{stamina:.0f}/{max_stamina:.0f}"
        arcade.draw_text(stamina_text, bar_x + bar_width + 10, bar_y + (bar_height // 2) - 6, arcade.color.WHITE, 12)

    def _draw_reputation_bar(self, game):
        rep_bar_width = 200
        rep_bar_height = 20
        rep_bar_x = game.width - rep_bar_width - 80
        rep_bar_y = 60
        reputation = game.player.reputation
        max_reputation = 100
        rep_percent = max(0.0, min(1.0, reputation / max_reputation))
        arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y, rep_bar_y + rep_bar_height, arcade.color.BLACK)
        if rep_percent > 0:
            color = arcade.color.YELLOW if rep_percent < 0.7 else arcade.color.PINK
            fill_width = int(rep_bar_width * rep_percent)
            arcade.draw_lrbt_rectangle_filled(rep_bar_x, rep_bar_x + fill_width, rep_bar_y, rep_bar_y + rep_bar_height, color)
        arcade.draw_lrbt_rectangle_outline(rep_bar_x, rep_bar_x + rep_bar_width, rep_bar_y, rep_bar_y + rep_bar_height, arcade.color.WHITE, 2)
        rep_text = f"{reputation:.0f}/100"
        arcade.draw_text(rep_text, rep_bar_x + rep_bar_width + 10, rep_bar_y + (rep_bar_height // 2) - 6, arcade.color.WHITE, 12)

    def _speedo_anchor(self, game):
        right_margin = 80
        bottom_margin = 30
        radius = 70
        center_x = game.width - right_margin - radius
        center_y = bottom_margin + 90
        return center_x, center_y, radius

    def _draw_bike_speedometer(self, game):
        speed = game.displayed_speed
        max_speed = game.player.base_speed * 1.2
        speed_percent = min(1.0, speed / max_speed)

        bar_x = game.width - 200 - 80
        center_x = bar_x + 235
        center_y = 150
        radius = 35

        max_jitter_kmh = 1.5
        jitter_units = max_jitter_kmh / 10.0
        if speed > 0.05:
            variation_intensity = min(1.0, speed / max(0.001, game.player.base_speed))
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
        state_color = state_colors.get(game.player.state, arcade.color.WHITE)
        arcade.draw_circle_filled(center_x, center_y + 18, 4, state_color)

    def _draw_weather_icon_right_of_speedometer(self, game):
        if not game.weather_system:
            return
        chip_w, chip_h = 64, 48
        cx, cy, r = self._speedo_anchor(game)
        base_x = cx + r + 12
        base_y_center = cy + 28
        x = int(base_x - 100)
        x = max(10, min(game.width - chip_w - 10, x))
        y = int(base_y_center - chip_h // 2)
        y = max(10, min(game.height - chip_h - 10, y))
        self._draw_weather_icon_at(game, x, y, chip_w, chip_h)

    # ---- Weather icon helpers ----
    def _draw_weather_icon_chip_bg(self, x: int, y: int, w: int, h: int):
        arcade.draw_lrbt_rectangle_filled(x, x + w, y, y + h, (0, 0, 0, 140))
        arcade.draw_lrbt_rectangle_outline(x, x + w, y, y + h, arcade.color.WHITE, 2)

    def _draw_weather_cloud(self, cx: int, cy: int, scale: float = 1.0, color=(255, 255, 255)):
        w = int(40 * scale)
        h = int(20 * scale)
        arcade.draw_circle_filled(cx - w // 3, cy, h // 2 + 6, color)
        arcade.draw_circle_filled(cx, cy + 4, h // 2 + 8, color)
        arcade.draw_circle_filled(cx + w // 3, cy, h // 2 + 6, color)
        arcade.draw_ellipse_filled(cx, cy - 4, w, h, color)

    def _draw_weather_rain(self, cx: int, cy: int, drops: int = 6, spread: int = 34, length: int = 10,
                           color=(120, 180, 255)):
        left = cx - spread // 2
        step = max(1, spread // max(1, drops - 1))
        for i in range(drops):
            x = left + i * step
            y1r = cy - 6
            y2r = y1r - int(length * (0.8 + 0.4 * random.random()))
            arcade.draw_line(x, y1r, x, y2r, color, 2)

    def _draw_weather_lightning(self, cx: int, cy: int, color=(255, 255, 100)):
        p1 = (cx - 6, cy + 6)
        p2 = (cx + 0, cy + 2)
        p3 = (cx - 3, cy - 2)
        p4 = (cx + 5, cy - 8)
        arcade.draw_line(*p1, *p2, color, 3)
        arcade.draw_line(*p2, *p3, color, 3)
        arcade.draw_line(*p3, *p4, color, 3)

    def _draw_weather_sun(self, cx: int, cy: int, radius: int = 10, color=(255, 220, 100)):
        arcade.draw_circle_filled(cx, cy, radius, color)
        rays = 8
        for i in range(rays):
            ang = i * (360 / rays)
            rad = math.radians(ang)
            x1r = cx + math.cos(rad) * (radius + 2)
            y1r = cy + math.sin(rad) * (radius + 2)
            x2r = cx + math.cos(rad) * (radius + 8)
            y2r = cy + math.sin(rad) * (radius + 8)
            arcade.draw_line(x1r, y1r, x2r, y2r, color, 2)

    def _draw_weather_fog(self, cx: int, cy: int, bands: int = 3,
                          band_width: int = 52, band_height: int = 6,
                          color=(220, 220, 220, 160)):
        if bands <= 0:
            return
        top = cy + 10
        for i in range(bands):
            yb = top - i * 10
            arcade.draw_lrbt_rectangle_filled(
                cx - band_width // 2, cx + band_width // 2, yb - band_height // 2, yb + band_height // 2, color
            )

    def _draw_weather_wind(self, cx: int, cy: int, swirls: int = 2, color=(200, 220, 255)):
        for i in range(swirls):
            yb = cy + (i * 8) - 6
            arcade.draw_arc_outline(cx, yb, 40, 16, color, 10, 170, 2)
            arcade.draw_arc_outline(cx + 8, yb - 4, 28, 12, color, 10, 170, 2)

    def _draw_weather_snowflake(self, cx: int, cy: int, size: int = 10, color=(220, 240, 255)):
        for ang in (0, 60, 120):
            rad = math.radians(ang)
            dx = math.cos(rad) * size
            dy = math.sin(rad) * size
            arcade.draw_line(cx - dx, cy - dy, cx + dx, cy + dy, color, 2)

    def _draw_weather_icon_at(self, game, x: int, y: int, width: int = 64, height: int = 48):
        info = game.weather_system.get_weather_info()
        cond = str(info.get("condition", "clear")).lower()
        intensity = float(info.get("intensity", 0.2))
        cloud_color = tuple(info.get("cloud_color", (255, 255, 255)))
        sky_color = tuple(info.get("sky_color", (135, 206, 235)))

        self._draw_weather_icon_chip_bg(x, y, width, height)

        icx = x + width // 2
        icy = y + height // 2

        t = max(0.1, min(1.0, intensity))
        rain_drops = 4 + int(6 * t)
        cloud_scale = 0.9 + 0.4 * t

        if cond in ("clear",):
            arcade.draw_circle_filled(icx, icy, 18, (sky_color[0], sky_color[1], sky_color[2], 60))
            self._draw_weather_sun(icx, icy, radius=10 + int(4 * t), color=(255, 220, 100))
        elif cond in ("clouds",):
            self._draw_weather_cloud(icx, icy, scale=cloud_scale, color=cloud_color)
        elif cond in ("rain_light",):
            self._draw_weather_cloud(icx, icy, scale=0.95, color=cloud_color)
            self._draw_weather_rain(icx, icy - 6, drops=rain_drops // 2, length=8 + int(6 * t))
        elif cond in ("rain",):
            self._draw_weather_cloud(icx, icy, scale=1.05, color=cloud_color)
            self._draw_weather_rain(icx, icy - 6, drops=rain_drops, length=10 + int(10 * t))
        elif cond in ("storm",):
            self._draw_weather_cloud(icx, icy + 2, scale=1.05, color=(80, 80, 80))
            self._draw_weather_rain(icx, icy - 4, drops=rain_drops, length=12 + int(10 * t), color=(140, 180, 255))
            self._draw_weather_lightning(icx, icy - 2)
        elif cond in ("fog",):
            self._draw_weather_fog(icx, icy, bands=3 + (1 if t > 0.6 else 0))
        elif cond in ("wind",):
            self._draw_weather_cloud(icx - 6, icy + 2, scale=0.8, color=cloud_color)
            self._draw_weather_wind(icx + 6, icy - 2)
        elif cond in ("heat",):
            self._draw_weather_sun(icx, icy, radius=11 + int(3 * t), color=(255, 210, 90))
            arcade.draw_arc_outline(icx, icy + 10, 36, 10, (255, 220, 150), 0, 180, 2)
        elif cond in ("cold",):
            self._draw_weather_cloud(icx, icy + 6, scale=0.9, color=cloud_color)
            self._draw_weather_snowflake(icx, icy - 8, size=8 + int(4 * t))
        else:
            self._draw_weather_cloud(icx, icy, scale=0.9, color=cloud_color)
            arcade.draw_circle_filled(icx + 18, icy - 12, 3, arcade.color.WHITE)

    def ensure_inventory_panel(self, game):
        """
        Asegura que el panel del inventario exista y apunte al inventario actual del jugador.
        """
        if not game or not getattr(game, "player", None) or not getattr(game.player, "inventory", None):
            return
        if self._inv_panel is None or self._inv_panel.inventory is not game.player.inventory:
            self._inv_panel = InventoryPanel(game.player.inventory)

    def toggle_inventory(self, game=None):
        """
        Alterna el panel de inventario. Si se pasa game, se usa para inicializar el panel al vuelo.
        """
        if game is not None:
            self._last_game = game
            self.ensure_inventory_panel(game)
        elif self._inv_panel is None and self._last_game is not None:
            self.ensure_inventory_panel(self._last_game)
        if self._inv_panel:
            self._inv_panel.toggle()

    def is_inventory_open(self) -> bool:
        return bool(self._inv_panel and self._inv_panel.is_open)

    def update(self, delta_time: float, game):
        """
        Actualiza animaciones de UI (incluye inventario).
        """
        self._last_game = game
        if self._inv_panel is None:
            self.ensure_inventory_panel(game)
        if self._inv_panel:
            self._inv_panel.update(delta_time)

    def _draw_pending_bell(self, game):
        # Mostrar solo si el panel de inventario está cerrado
        inv_panel_open = getattr(self, "_inv_panel", None) and self._inv_panel.is_open
        if inv_panel_open:
            return
        pending = len(getattr(game, "pending_orders", []) or [])
        # Posición cerca del panel de inventario (margen superior derecho)
        box_w, box_h = 48, 48
        box_x = game.width - box_w - 70
        box_y = game.height - box_h - 50
        # Fondo café
        arcade.draw_lrbt_rectangle_filled(box_x, box_x + box_w, box_y, box_y + box_h, (161, 130, 98, 220))
        arcade.draw_lrbt_rectangle_outline(box_x, box_x + box_w, box_y, box_y + box_h, arcade.color.WHITE, 2)
        # Campana simple (gris/blanca)
        cx = box_x + box_w // 2
        cy = box_y + box_h // 2
        # cuerpo
        arcade.draw_triangle_filled(cx - 10, cy - 4, cx + 10, cy - 4, cx, cy + 10, arcade.color.LIGHT_GRAY)
        # badajo
        arcade.draw_circle_filled(cx, cy - 8, 3, arcade.color.SILVER)
        # Badge rojo con número
        if pending > 0:
            badge_r = 10
            bx = box_x + box_w - badge_r + 2
            by = box_y + box_h - badge_r + 2
            arcade.draw_circle_filled(bx, by, badge_r, arcade.color.RED)
            arcade.draw_text(str(pending), bx, by - 6, arcade.color.WHITE, 12, anchor_x="center")
