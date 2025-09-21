import arcade
import requests
import math

TILE_SIZE = 20

COLOR_MAP = {
    "C": arcade.color.DIM_GRAY,           # Street: darker gray
    "B": arcade.color.BLACK,              # Wall
    "P": arcade.color.APPLE_GREEN         # Park: bright green
}

#Para Calidad de piso y mejora de performance
FLOOR_ROW_STEP = 2

def get_map():
    url = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io/city/map"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]["tiles"]

class RayCastWindow(arcade.Window):
    def __init__(self, tiles):
        width = 600
        height = 400
        super().__init__(width, height, "Ray Casting Demo")
        self.tiles = tiles
        self.map_width = len(tiles[0])
        self.map_height = len(tiles)

        # Player in map-tile coordinates
        self.player_x = self.map_width / 2
        self.player_y = self.map_height / 2
        self.player_angle = 0.0
        self.fov = math.pi / 3  # 60 deg

        # Movement state
        self.move_forward = False
        self.move_back = False
        self.strafe_left = False
        self.strafe_right = False
        self.turn_left = False
        self.turn_right = False
        self.move_speed = 3.0     # tiles per second
        self.turn_speed = 1.5     # radians per second

        arcade.set_background_color(arcade.color.SKY_BLUE)

    def is_wall(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.map_width or iy >= self.map_height:
            return True
        return self.tiles[iy][ix] == "B"

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.W:
            self.move_forward = True
        elif symbol == arcade.key.S:
            self.move_back = True
        elif symbol == arcade.key.A:
            self.strafe_left = True
        elif symbol == arcade.key.D:
            self.strafe_right = True
        elif symbol == arcade.key.LEFT:
            self.turn_left = True
        elif symbol == arcade.key.RIGHT:
            self.turn_right = True

    def on_key_release(self, symbol, modifiers):
        if symbol == arcade.key.W:
            self.move_forward = False
        elif symbol == arcade.key.S:
            self.move_back = False
        elif symbol == arcade.key.A:
            self.strafe_left = False
        elif symbol == arcade.key.D:
            self.strafe_right = False
        elif symbol == arcade.key.LEFT:
            self.turn_left = False
        elif symbol == arcade.key.RIGHT:
            self.turn_right = False

    def on_update(self, delta_time: float):
        # Rotation
        if self.turn_left:
            self.player_angle -= self.turn_speed * delta_time
        if self.turn_right:
            self.player_angle += self.turn_speed * delta_time

        # Movement vectors
        forward_x = math.cos(self.player_angle)
        forward_y = math.sin(self.player_angle)
        right_x = math.cos(self.player_angle + math.pi / 2)
        right_y = math.sin(self.player_angle + math.pi / 2)

        dx = 0.0
        dy = 0.0
        if self.move_forward:
            dx += forward_x * self.move_speed * delta_time
            dy += forward_y * self.move_speed * delta_time
        if self.move_back:
            dx -= forward_x * self.move_speed * delta_time
            dy -= forward_y * self.move_speed * delta_time
        if self.strafe_right:
            dx += right_x * self.move_speed * delta_time
            dy += right_y * self.move_speed * delta_time
        if self.strafe_left:
            dx -= right_x * self.move_speed * delta_time
            dy -= right_y * self.move_speed * delta_time

        # Collide against walls: resolve per-axis
        next_x = self.player_x + dx
        next_y = self.player_y + dy
        if not self.is_wall(next_x, self.player_y):
            self.player_x = next_x
        if not self.is_wall(self.player_x, next_y):
            self.player_y = next_y

    # Fast DDA wall cast (avoids tiny step marching)
    def cast_wall_dda(self, dir_x: float, dir_y: float):
        pos_x, pos_y = self.player_x, self.player_y
        map_x, map_y = int(pos_x), int(pos_y)

        # Precompute distances to next grid lines
        if dir_x == 0.0:
            delta_dist_x = 1e30
        else:
            delta_dist_x = abs(1.0 / dir_x)
        if dir_y == 0.0:
            delta_dist_y = 1e30
        else:
            delta_dist_y = abs(1.0 / dir_y)

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

        side = 0  # 0 hit vertical side, 1 hit horizontal side
        # Walk the grid
        while 0 <= map_x < self.map_width and 0 <= map_y < self.map_height:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if not (0 <= map_x < self.map_width and 0 <= map_y < self.map_height):
                break

            if self.tiles[map_y][map_x] == "B":
                # Perpendicular wall distance (fish-eye corrected)
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

    def pick_floor_color(self, mx, my):
        if 0 <= mx < self.map_width and 0 <= my < self.map_height:
            t = self.tiles[my][mx]
            return COLOR_MAP["P"] if t == "P" else COLOR_MAP["C"]
        return COLOR_MAP["C"]

    def on_draw(self):
        self.clear()
        num_rays = 160
        column_width_f = self.width / num_rays
        horizon = self.height / 2
        posZ = self.height / 2

        for ray in range(num_rays):
            # Ray direction
            ray_angle = self.player_angle - self.fov / 2 + (ray / num_rays) * self.fov
            dir_x = math.cos(ray_angle)
            dir_y = math.sin(ray_angle)

            # Pixel column bounds
            left = int(ray * column_width_f)
            right = int((ray + 1) * column_width_f)
            if right <= left:
                right = left + 1

            # 1) Cast to wall with DDA and draw wall slice
            dist, side = self.cast_wall_dda(dir_x, dir_y)

            wall_bottom = 0
            if dist is not None:
                slice_height = int(self.height / dist)
                half = slice_height // 2
                bottom = max(0, horizon - half)
                top = min(self.height, horizon + half)

                # Optional simple shading for depth/side
                wall_color = COLOR_MAP["B"]
                if side == 1:
                    # Slightly dim the color for horizontal sides
                    wall_color = (max(0, wall_color[0] - 20),
                                  max(0, wall_color[1] - 20),
                                  max(0, wall_color[2] - 20))

                arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, wall_color)
                wall_bottom = bottom
            else:
                # No wall found: floor extends up to horizon
                wall_bottom = horizon

            # 2) Floor per-column with run-length compression (reduces draw calls)
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
                world_x = self.player_x + dir_x * row_dist
                world_y = self.player_y + dir_y * row_dist
                mx = int(world_x)
                my = int(world_y)

                # Pick floor color by tile; default to street if out-of-bounds/other
                if 0 <= mx < self.map_width and 0 <= my < self.map_height:
                    t = self.tiles[my][mx]
                    color = COLOR_MAP["P"] if t == "P" else COLOR_MAP["C"]
                else:
                    color = COLOR_MAP["C"]

                # Start or continue a segment
                if last_color is None:
                    last_color = color
                    seg_start = y
                elif color != last_color:
                    # Flush previous segment
                    arcade.draw_lrbt_rectangle_filled(
                        left, right, seg_start, y, last_color
                    )
                    last_color = color
                    seg_start = y

                y += FLOOR_ROW_STEP

            # Flush final segment to y_end
            if last_color is not None and seg_start < y_end:
                arcade.draw_lrbt_rectangle_filled(left, right, seg_start, y_end, last_color)

if __name__ == "__main__":
    tiles = get_map()
    window = RayCastWindow(tiles)
    arcade.run()
