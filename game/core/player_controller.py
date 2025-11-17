import math

class PlayerController:
    """
    Controla movimiento, giros y suavizado de la velocidad mostrada.
    Mantiene el mismo comportamiento que tenía game.py.
    """
    def __init__(self, backward_factor: float = 0.3, speed_smoothing: float = 3.0):
        self.backward_factor = float(backward_factor)
        self.speed_smoothing = float(speed_smoothing)
        self.displayed_speed: float = 0.0
        self.last_move_scale: float = 0.0

    def update(self, player, city, delta_time: float,
               move_forward: bool, move_backward: bool,
               turn_left: bool, turn_right: bool) -> float:
        """
        Aplica entrada y retorna la velocidad mostrada suavizada.
        No llama a player.update(delta_time) para mantener la responsabilidad separada.
        """
        if not player or not city:
            self.displayed_speed = 0.0
            self.last_move_scale = 0.0
            return self.displayed_speed

        # Giros
        if turn_left:
            player.turn_left(delta_time)
        if turn_right:
            player.turn_right(delta_time)

        # Movimiento
        prev_x, prev_y = player.x, player.y
        dx = dy = 0.0
        if move_forward or move_backward:
            fx, fy = player.get_forward_vector()
            if move_forward:
                dx += fx
                dy += fy
            if move_backward:
                dx -= fx * self.backward_factor
                dy -= fy * self.backward_factor

        if dx != 0.0 or dy != 0.0:
            player.move(dx, dy, delta_time, city)
        else:
            player.is_moving = False

        moved = (abs(player.x - prev_x) > 1e-5) or (abs(player.y - prev_y) > 1e-5)
        if moved:
            base_speed = player.calculate_effective_speed(city)
            move_scale = math.hypot(dx, dy)
            self.last_move_scale = move_scale
            target_speed = base_speed * move_scale
        else:
            target_speed = 0.0
            self.last_move_scale = 0.0

        # Suavizado de odómetro (idéntico a game.py)
        speed_diff = target_speed - self.displayed_speed
        self.displayed_speed += speed_diff * self.speed_smoothing * delta_time
        if abs(speed_diff) < 0.01:
            self.displayed_speed = target_speed
        if not moved and abs(self.displayed_speed) < 0.05:
            self.displayed_speed = 0.0

        return self.displayed_speed