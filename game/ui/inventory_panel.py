import arcade
from game.core.inventory import Inventory


class InventoryPanel:
    """
    Vista/Panel del inventario. Contiene estado de apertura, animación y dibujo.
    Mantiene visual y posiciones idénticas al inventario anterior.
    """
    def __init__(self, inventory: Inventory):
        self.inventory = inventory

        # Estado de panel
        self.is_open = False
        self.animation_progress = 0.0  # 0.0 = cerrado, 1.0 = abierto
        self.animation_speed = 5.0

        # Dimensiones y posición objetivo
        self.panel_width = 450
        self.panel_height = 400
        self.target_x = 0
        self.target_y = 0

    # Control de apertura
    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def toggle(self):
        self.is_open = not self.is_open

    # Animación
    def update(self, delta_time: float):
        target_progress = 1.0 if self.is_open else 0.0
        if self.animation_progress < target_progress:
            self.animation_progress = min(self.animation_progress + self.animation_speed * delta_time, target_progress)
        elif self.animation_progress > target_progress:
            self.animation_progress = max(self.animation_progress - self.animation_speed * delta_time, target_progress)

    # Posicionamiento
    def set_target_position(self, x: int, y: int):
        self.target_x = x
        self.target_y = y

    def get_current_position(self) -> tuple:
        # Cuando está cerrado, el panel está fuera de la pantalla a la derecha
        closed_x = self.target_x + self.panel_width
        current_x = closed_x + (self.target_x - closed_x) * self.animation_progress
        return current_x, self.target_y

    # Dibujo
    def draw(self, x: int, y: int, width: int, height: int):
        if width != self.panel_width or height != self.panel_height:
            self.panel_width = width
            self.panel_height = height

        self.set_target_position(x, y)

        current_x, current_y = self.get_current_position()

        if self.animation_progress <= 0:
            return

        alpha = int(255 * self.animation_progress)

        arcade.draw_lbwh_rectangle_filled(
            current_x + width // 2,
            current_y + height // 2,
            width,
            height,
            (161, 130, 98, alpha)
        )

        arcade.draw_lbwh_rectangle_outline(
            current_x + width // 2,
            current_y + height // 2,
            width,
            height,
            (255, 255, 255, alpha),
            2
        )

        arcade.draw_text(
            "Inventario",
            current_x + width // 2 + 5,
            current_y + height - 20,
            (255, 255, 255, alpha),
            14,
            bold=True
        )

        weight_text = f"Peso: {self.inventory.current_weight:.1f}/{self.inventory.max_weight:.1f} kg"
        arcade.draw_text(
            weight_text,
            current_x + width - 130,
            current_y + height - 20,
            (255, 255, 255, alpha),
            12
        )

        if not self.inventory.orders:
            arcade.draw_text(
                "No hay pedidos",
                current_x + width // 2 + 10,
                current_y + height - 50,
                (200, 200, 200, alpha),
                12
            )
            return

        arcade.draw_text("ID", current_x + 250, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Prioridad", current_x + 275, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Pago", current_x + 340, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Peso", current_x + 380, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Estado", current_x + 430, current_y + height - 50, (255, 255, 0, alpha), 10)

        start_y = current_y + height - 70
        line_height = 20
        max_display = 8

        for i, order in enumerate(self.inventory.orders[:max_display]):
            y_pos = start_y - (i * line_height)

            if i == self.inventory.current_index:
                arcade.draw_lbwh_rectangle_filled(
                    current_x + width // 2,
                    y_pos - 2,
                    width - 20,
                    16,
                    (255, 0, 0, int(128 * self.animation_progress))
                )

            order_id_short = order.id[:8] + "..." if len(order.id) > 8 else order.id
            arcade.draw_text(order_id_short, current_x + 230, y_pos, (255, 255, 255, alpha), 10)

            priority_color = (0, 255, 0, alpha)
            if order.priority >= 2:
                priority_color = (255, 165, 0, alpha)
            if order.priority >= 3:
                priority_color = (255, 0, 0, alpha)

            arcade.draw_text(str(order.priority), current_x + 290, y_pos, priority_color, 10)

            arcade.draw_text(f"${order.payout:.0f}", current_x + 340, y_pos, (255, 255, 255, alpha), 10)

            weight_str = f"{order.weight:.1f} kg" if getattr(order, "status", "") == "picked_up" else ""
            arcade.draw_text(weight_str, current_x + 380, y_pos, (255, 255, 255, alpha), 10)

            status_color = (0, 255, 0, alpha) if order.status == "in_progress" else (255, 255, 0, alpha)
            arcade.draw_text(order.status, current_x + 430, y_pos, status_color, 10)

        if len(self.inventory.orders) > max_display:
            arcade.draw_text(
                f"... y {len(self.inventory.orders) - max_display} más",
                current_x + 20,
                start_y - (max_display * line_height),
                (255, 0, 0, alpha),
                10
            )

        sort_text = f"Orden: {self.inventory.sort_mode}"
        arcade.draw_text(
            sort_text,
            current_x + 230,
            current_y + 430,
            (255, 0, 0, alpha),
            10
        )