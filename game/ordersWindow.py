import arcade
from typing import List, Optional
from game.orders import Order

class ordersWindow:
    def __init__(self, game):
        self.game = game  # Referencia al juego principal
        self.pending_orders: List[Order] = []
        self.selected_order_index = 0
        self.is_open = False
        self.animation_progress = 0.0
        self.animation_speed = 5.0
        
        # Dimensiones del panel
        self.panel_width = 500
        self.panel_height = 500
        self.target_x = 0
        self.target_y = 0

    def set_pending_orders(self, orders: List[Order]):
        """Establecer la lista de pedidos pendientes"""
        self.pending_orders = orders
        self.selected_order_index = 0

    def ensure_initial_position(self, screen_width: int, screen_height: int):
        """Asegurar que la posición inicial esté centrada"""
        if not hasattr(self, '_position_initialized') or not self._position_initialized:
            self.target_x = (screen_width - self.panel_width) // 2
            self.target_y = (screen_height - self.panel_height) // 2
            self._position_initialized = True

    def toggle_open(self):
        """Alternar entre abierto y cerrado"""
        if self.pending_orders:  # Solo abrir si hay pedidos pendientes
            if not hasattr(self, '_position_initialized') or not self._position_initialized:
                if self.game:
                    self.ensure_initial_position(self.game.width, self.game.height)
        
            self.is_open = not self.is_open
            return True
        else:
            # Mostrar mensaje si no hay pedidos
            if self.game and hasattr(self.game, 'show_notification'):
                self.game.show_notification("No hay pedidos disponibles")
            return False

    def update_animation(self, delta_time: float):
        """Actualizar la animación de apertura/cierre"""
        target_progress = 1.0 if self.is_open else 0.0
        if self.animation_progress < target_progress:
            self.animation_progress = min(self.animation_progress + self.animation_speed * delta_time, target_progress)
        elif self.animation_progress > target_progress:
            self.animation_progress = max(self.animation_progress - self.animation_speed * delta_time, target_progress)

    def set_target_position(self, x: int, y: int):
        """Establecer la posición objetivo del panel"""
        self.target_x = x
        self.target_y = y

    def get_current_position(self) -> tuple:
        """Obtener la posición actual interpolada para la animación"""
        closed_x = self.target_x + self.panel_width
        current_x = closed_x + (self.target_x - closed_x) * self.animation_progress
        return current_x, self.target_y

    def accept_order(self) -> bool:
        """Aceptar el pedido seleccionado"""
        if not self.pending_orders or self.selected_order_index >= len(self.pending_orders):
            return False
        
        order = self.pending_orders[self.selected_order_index]
        
        # Intentar agregar al inventario
        if self.game.player and self.game.player.add_order_to_inventory(order):
            # Remover de pedidos pendientes
            self.pending_orders.pop(self.selected_order_index)
            
            # Ajustar índice si es necesario
            if self.selected_order_index >= len(self.pending_orders) and self.pending_orders:
                self.selected_order_index = len(self.pending_orders) - 1
            elif not self.pending_orders:
                self.selected_order_index = 0
                self.is_open = False  # Cerrar ventana si no hay más pedidos
            
            self.game.show_notification(f"Pedido {order.id} aceptado")
            return True
        
        return False

    def cancel_order(self):
        """Cancelar el pedido seleccionado (baja reputación)"""
        if not self.pending_orders or self.selected_order_index >= len(self.pending_orders):
            return
        
        order = self.pending_orders[self.selected_order_index]
        
        # Bajar reputación del jugador
        if self.game.player:
            self.game.player.cancel_order()
        
        # Remover de pedidos pendientes
        self.pending_orders.pop(self.selected_order_index)
        
        # Ajustar índice si es necesario
        if self.selected_order_index >= len(self.pending_orders) and self.pending_orders:
            self.selected_order_index = len(self.pending_orders) - 1
        elif not self.pending_orders:
            self.selected_order_index = 0
            self.is_open = False  # Cerrar ventana si no hay más pedidos
        
        self.game.show_notification(f"Pedido {order.id} cancelado (-4 reputación)")

    def next_order(self):
        """Seleccionar el siguiente pedido"""
        if not self.pending_orders:
            return
        self.selected_order_index = (self.selected_order_index + 1) % len(self.pending_orders)

    def previous_order(self):
        """Seleccionar el pedido anterior"""
        if not self.pending_orders:
            return
        self.selected_order_index = (self.selected_order_index - 1) % len(self.pending_orders)

    def draw(self):
        """Dibujar la ventana de pedidos pendientes"""
        if not self.is_open and self.animation_progress <= 0:
            return

        # Obtener posición actual interpolada
        current_x, current_y = self.get_current_position()
        
        # Fondo del panel con transparencia
        alpha = int(255 * self.animation_progress)
        arcade.draw_lrbt_rectangle_filled(
            current_x,
            current_x + self.panel_width,
            current_y,
            current_y + self.panel_height,
            (40, 40, 60, alpha)
        )


        

        # Borde
        arcade.draw_lrbt_rectangle_outline(
            current_x,
            current_x + self.panel_width,
            current_y,
            current_y + self.panel_height,
            (255, 255, 255, alpha),
            3
        )

        # Título
        arcade.draw_text(
            "Pedidos Disponibles",
            current_x + self.panel_width // 2,
            current_y + self.panel_height - 30,
            (255, 255, 255, alpha),
            20,
            bold=True,
            anchor_x="center"
        )

        # Si no hay pedidos
        if not self.pending_orders:
            arcade.draw_text(
                "No hay pedidos disponibles",
                current_x + self.panel_width // 2,
                current_y + self.panel_height // 2,
                (200, 200, 200, alpha),
                16,
                anchor_x="center"
            )
            return

        # Pedido seleccionado
        order = self.pending_orders[self.selected_order_index]
        
        # Información del pedido
        info_y = current_y + self.panel_height - 80
        line_height = 25
        
        details = [
            f"ID: {order.id}",
            f"Pago: ${order.payout:.0f}",
            f"Peso: {order.weight:.1f} kg",
            f"Prioridad: {order.priority}",
            f"Recoger en: ({order.pickup_pos[0]}, {order.pickup_pos[1]})",
            f"Entregar en: ({order.dropoff_pos[0]}, {order.dropoff_pos[1]})",
            f"Tiempo límite: {order.time_limit:.0f}s"
        ]
        
        for i, detail in enumerate(details):
            arcade.draw_text(
                detail,
                current_x + 20,
                info_y - (i * line_height),
                (255, 255, 255, alpha),
                14
            )

        # Indicador de pedidos (ej: "1/3")
        orders_count = f"{self.selected_order_index + 1}/{len(self.pending_orders)}"
        arcade.draw_text(
            orders_count,
            current_x + self.panel_width - 40,
            current_y + self.panel_height - 30,
            (255, 255, 255, alpha),
            16
        )

        # Botones de acción
        button_width = 120
        button_height = 40
        button_y = current_y + 60

        # Centro de cada botón
        accept_cx = current_x + self.panel_width // 4
        cancel_cx = current_x + 3 * self.panel_width // 4
        accept_cy = cancel_cy = button_y + button_height // 2
        
        # Botón Aceptar
        accept_color = (0, 150, 0, alpha) if self.game.player and self.game.player.inventory.can_add_more else (100, 100, 100, alpha)
        l = accept_cx - button_width // 2
        r = accept_cx + button_width // 2
        b = accept_cy - button_height // 2
        t = accept_cy + button_height // 2
        arcade.draw_lrbt_rectangle_filled(
            l,
            r,
            b,
            t,
            accept_color
        )
        arcade.draw_lrbt_rectangle_outline(
            l, 
            r, 
            b, 
            t, 
            (255, 255, 255, alpha), 
            2
        )
        arcade.draw_text(
            "Aceptar (A)",
            accept_cx,
            accept_cy,
            (255, 255, 255, alpha),
            14,
            anchor_x="center",
            anchor_y="center"
        )

        # Botón Cancelar
        l = cancel_cx - button_width // 2
        r = cancel_cx + button_width // 2
        b = cancel_cy - button_height // 2
        t = cancel_cy + button_height // 2
        arcade.draw_lrbt_rectangle_filled(
            l,
            r,
            b,
            t,
            (150, 0, 0, alpha)
        )
        arcade.draw_lrbt_rectangle_outline(
            l, 
            r, 
            b, 
            t, 
            (255, 255, 255, alpha), 
            2
        )

        arcade.draw_text(
            "Cancelar (C)",
            cancel_cx,
            cancel_cy,
            (255, 255, 255, alpha),
            14,
            anchor_x="center",
            anchor_y="center"
        )

        # Instrucciones
        arcade.draw_text(
            "↑/↓: Navegar  |  A: Aceptar  |  C: Cancelar  |  O: Cerrar",
            current_x + self.panel_width // 2,
            current_y + 20,
            (200, 200, 255, alpha),
            12,
            anchor_x="center"
        )