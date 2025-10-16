import arcade


class NotificationManager:
    """
    Maneja las notificaciones en pantalla y su temporizador.
    """
    def __init__(self):
        self.message = ""
        self.timer = 0.0

    def show(self, message: str, duration: float = 2.0):
        self.message = message
        self.timer = duration

    def update(self, delta_time: float):
        if self.timer > 0:
            self.timer -= delta_time
            if self.timer < 0:
                self.timer = 0

    def draw(self, game):
        if self.timer > 0 and self.message:
            msg_width = len(self.message) * 12 + 20
            msg_height = 40
            msg_x = (game.width - msg_width) // 2
            msg_y = game.height - 150
            arcade.draw_lrbt_rectangle_filled(msg_x, msg_x + msg_width, msg_y, msg_y + msg_height, (0, 0, 0, 180))
            arcade.draw_lrbt_rectangle_outline(msg_x, msg_x + msg_width, msg_y, msg_y + msg_height, arcade.color.WHITE, 2)
            arcade.draw_text(self.message, game.width // 2, msg_y + msg_height // 2 - 6, arcade.color.WHITE, 16, anchor_x="center")