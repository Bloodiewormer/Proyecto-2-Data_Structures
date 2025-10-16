import math
import arcade
from typing import Optional
from game.city import CityMap


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

        self._minimap_shapes: Optional[arcade.ShapeElementList] = None
        self._minimap_cache_key = None

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

    def render(self, x: int, y: int, size: int, player):
        """
        Dibuja el minimapa con marcadores de pedidos y el jugador.
        """
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