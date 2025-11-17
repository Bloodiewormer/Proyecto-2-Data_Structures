import math
import arcade
import time
from typing import Optional
from game.core.city import CityMap


class MinimapRenderer:
    """
    Dibuja el minimapa. Extraído desde el renderer para separar responsabilidades (UI vs mundo).
    Mantiene posiciones y estilos originales.
    """
    def __init__(self, city: CityMap, app_config: dict):
        self.city = city
        colors = app_config.get("colors", {}) or {}
        self.col_street = tuple(colors.get("street", (105, 105, 105)))
        self.col_building = tuple(colors.get("building", (160, 120, 80)))
        self.col_park = tuple(colors.get("park", (144, 238, 144)))
        self.col_player = tuple(colors.get("player", (255, 255, 0)))

        self._minimap_shapes: Optional[object] = None
        self._minimap_cache_key = None

        # Debug/perf
        self.debug = bool(app_config.get("debug", False))
        self._perf_accum = {"render": 0.0, "frames": 0}
        self._last_perf_report = time.perf_counter()

    def set_debug(self, flag: bool):
        self.debug = bool(flag)

    def get_perf_snapshot(self):
        f = max(1, self._perf_accum.get("frames", 0))
        if f <= 0:
            return {"render_ms": 0.0}
        return {"render_ms": (self._perf_accum["render"] / f) * 1000.0}

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
                # Asegurar que el color tenga canal alpha (RGBA) para evitar advertencias
                try:
                    c4 = (c[0], c[1], c[2], 255) if len(c) == 3 else c
                except Exception:
                    c4 = (105, 105, 105, 255)
                cx = x + (col + 0.5) * scale_x
                cy = y + (row + 0.5) * scale_y
                shapes.append(create_rect(cx, cy, scale_x, scale_y, c4))

        border = arcade.shape_list.create_rectangle_outline(
            x + size / 2, y + size / 2, size, size, arcade.color.WHITE, border_width=2
        )
        shapes.append(border)

        self._minimap_shapes = shapes
        self._minimap_cache_key = key

    def render(self, x: int, y: int, size: int, player):
        t0 = time.perf_counter()

        self._ensure_minimap_cache(x, y, size)
        if not self._minimap_shapes:
            return

        self._minimap_shapes.draw()

        scale_x = size / max(1, self.city.width)
        scale_y = size / max(1, self.city.height)

        # Marcadores de pedidos según estado
        if hasattr(player, 'inventory') and player.inventory:
            for order in player.inventory.orders:
                if getattr(order, "status", None) == "in_progress":
                    pickup_x = x + (order.pickup_pos[0] + 0.5) * scale_x
                    pickup_y = y + (order.pickup_pos[1] + 0.5) * scale_y
                    r = max(4, int(min(scale_x, scale_y) * 0.4))
                    arcade.draw_circle_filled(pickup_x, pickup_y, r, arcade.color.YELLOW_ROSE)
                    arcade.draw_circle_outline(pickup_x, pickup_y, r, arcade.color.COOL_BLACK, 1.5)

                if getattr(order, "status", None) == "picked_up":
                    dropoff_x = x + (order.dropoff_pos[0] + 0.5) * scale_x
                    dropoff_y = y + (order.dropoff_pos[1] + 0.5) * scale_y
                    r = max(4, int(min(scale_x, scale_y) * 0.4))
                    arcade.draw_circle_filled(dropoff_x, dropoff_y, r, arcade.color.RED)
                    arcade.draw_circle_outline(dropoff_x, dropoff_y, r, arcade.color.COOL_BLACK, 1.5)

        # Jugador
        px = x + (player.x + 0.5) * scale_x
        py = y + (player.y + 0.5) * scale_y
        arcade.draw_circle_filled(px, py, max(2, int(min(scale_x, scale_y) * 0.3)), self.col_player)

        # Flecha de dirección
        fx = math.cos(player.angle)
        fy = math.sin(player.angle)
        arcade.draw_line(px, py, px + fx * 10, py + fy * 10, self.col_player, 2)

        # Dibujar jugadores IA en el minimapa (obtener la ventana de arcade)
        try:
            game = arcade.get_window()
            if hasattr(game, 'ai_players') and game.ai_players:
                for ai in game.ai_players:
                    ai_x = x + (ai.x + 0.5) * scale_x
                    ai_y = y + (ai.y + 0.5) * scale_y

                    # Color según dificultad
                    diff = getattr(ai, 'difficulty', 'easy')
                    if diff == 'easy':
                        color = (100, 255, 100)
                    elif diff == 'medium':
                        color = (255, 165, 0)
                    else:
                        color = (255, 50, 50)

                    r = max(2, int(min(scale_x, scale_y) * 0.3))
                    arcade.draw_circle_filled(ai_x, ai_y, r, color)

                    # Flecha de dirección
                    fx = math.cos(getattr(ai, 'angle', 0.0))
                    fy = math.sin(getattr(ai, 'angle', 0.0))
                    arcade.draw_line(ai_x, ai_y, ai_x + fx * 8, ai_y + fy * 8, color, 2)
        except Exception:
            # No bloquear el render si algo falla al dibujar las IA
            pass

        t1 = time.perf_counter()
        self._perf_accum["render"] += (t1 - t0)
        self._perf_accum["frames"] += 1
        now = time.perf_counter()
        if self.debug and now - self._last_perf_report > 2.0:
            f = max(1, self._perf_accum["frames"])
            render_ms = (self._perf_accum["render"] / f) * 1000
            print(f"[MinimapPerf] render={render_ms:.2f}ms")
            self._perf_accum = {"render": 0.0, "frames": 0}
            self._last_perf_report = now

        # ========== DEBUGGING VISUAL DE IA ==========
        try:
            game = arcade.get_window()

            if hasattr(game, 'debug') and game.debug and hasattr(game, 'ai_players'):
                scale_x = size / max(1, self.city.width)
                scale_y = size / max(1, self.city.height)

                for ai in game.ai_players:
                    # F1: Mostrar paths (líneas cyan)
                    if getattr(game, 'show_ai_paths', False):
                        if hasattr(ai, 'strategy'):
                            # Para estrategias con planner (Hard)
                            if hasattr(ai.strategy, 'planner') and ai.strategy.planner._path:
                                path = ai.strategy.planner._path
                                for i in range(len(path) - 1):
                                    p1 = path[i]
                                    p2 = path[i + 1]
                                    x1 = x + (p1[0] + 0.5) * scale_x
                                    y1 = y + (p1[1] + 0.5) * scale_y
                                    x2 = x + (p2[0] + 0.5) * scale_x
                                    y2 = y + (p2[1] + 0.5) * scale_y
                                    arcade.draw_line(x1, y1, x2, y2, arcade.color.CYAN, 1)

                    # F2: Mostrar targets (círculos rojos)
                    if getattr(game, 'show_ai_targets', False):
                        if ai.current_target:
                            tx = x + (ai.current_target[0] + 0.5) * scale_x
                            ty = y + (ai.current_target[1] + 0.5) * scale_y
                            arcade.draw_circle_outline(tx, ty, 5, arcade.color.RED, 2)

                            # Línea desde AI hasta target
                            ai_x = x + (ai.x + 0.5) * scale_x
                            ai_y = y + (ai.y + 0.5) * scale_y
                            arcade.draw_line(ai_x, ai_y, tx, ty, arcade.color.YELLOW, 1)

                    # F3: Mostrar stamina (texto sobre la IA)
                    if getattr(game, 'show_ai_stamina', False):
                        ai_x = x + (ai.x + 0.5) * scale_x
                        ai_y = y + (ai.y + 0.5) * scale_y

                        # Color según nivel de stamina
                        if ai.stamina > 60:
                            color = arcade.color.GREEN
                        elif ai.stamina > 30:
                            color = arcade.color.YELLOW
                        else:
                            color = arcade.color.RED

                        state_text = f"{ai.difficulty[0].upper()} S:{ai.stamina:.0f}"
                        arcade.draw_text(
                            state_text,
                            ai_x,
                            ai_y + 12,
                            color,
                            8,
                            anchor_x="center"
                        )
        except Exception as e:
            if self.debug:
                print(f"[Minimap] Error en debug visual: {e}")