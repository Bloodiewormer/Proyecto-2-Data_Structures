import arcade
from typing import List, Optional, Dict, Any
from game.orders import Order
    
class Inventory:    

    def __init__(self, max_weight: float = 10.0):
        self.max_weight = max_weight
        self.orders: List[Order] = []
        self.current_index = 0  # Índice del pedido actualmente seleccionado
        self.sort_mode = "priority"  # Modo de ordenamiento: 'priority', 'deadline'

         # Estado del panel desplegable
        self.is_open = False
        self.animation_progress = 0.0  # 0.0 = cerrado, 1.0 = abierto
        self.animation_speed = 5.0  # Velocidad de la animación
        
        # Dimensiones del panel
        self.panel_width = 450
        self.panel_height = 400
        self.target_x = 0
        self.target_y = 0

    @property
    def current_weight(self) -> float:
        """Calcula el peso total actual del inventario"""
        return sum(order.weight for order in self.orders)
    
    @property
    def can_add_more(self) -> bool:
        """Verifica si se pueden agregar más pedidos sin exceder el peso máximo"""
        return self.current_weight < self.max_weight
    
    def add_order(self, order: Order) -> bool:
        """Agrega un pedido al inventario si no excede el peso máximo"""
        try:
            if self.current_weight + order.weight <= self.max_weight:
                order.status = "in_progress"
                self.orders.append(order)
                self.sort_orders()  # Reordenar al agregar una nueva orden
                print(f"Pedido {order.id} añadido al inventario. Peso: {self.current_weight}/{self.max_weight}")
                return True
            else:
                print(f"No hay capacidad para el pedido {order.id}. Peso actual: {self.current_weight}")
                return False
        except Exception as e:
            print(f"Error añadiendo pedido al inventario: {e}")
            return False
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Quita un pedido del inventario por su ID"""
        try:
            for i, order in enumerate(self.orders):
                if order.id == order_id:
                    removed_order = self.orders.pop(i)
                    print(f"Pedido {order_id} removido del inventario")
                    return removed_order
            print(f"Pedido {order_id} no encontrado en el inventario")
            return None
        except Exception as e:
            print(f"Error removiendo pedido: {e}")
            return None

    def get_current_order(self) -> Optional[Order]:
        """Obtiene el pedido actualmente seleccionado"""
        if not self.orders:
            return None
        return self.orders[self.current_index]
    
    def next_order(self):
        """Selecciona el siguiente pedido en el inventario"""
        if not self.orders:
            return
        self.current_index = (self.current_index + 1) % len(self.orders)

    def previous_order(self):
        """Selecciona el pedido anterior en el inventario"""
        if not self.orders:
            return
        self.current_index = (self.current_index - 1) % len(self.orders)

    def sort_by_priority(self):
        """Ordena los pedidos por prioridad (mayor prioridad primero)"""
        try:
            self.orders.sort(key=lambda x: x.priority, reverse=True)
            self.sort_mode = "priority"
            self.current_index = 0
            print("Inventario ordenado por prioridad")
        except Exception as e:
            print(f"Error ordenando por prioridad: {e}")
    
    def sort_by_deadline(self):
        """Ordena los pedidos por fecha límite (mas proximo primero)"""
        try:
            self.orders.sort(key=lambda x: x.deadline)
            self.sort_mode = "deadline"
            self.current_index = 0
            print("Inventario ordenado por fecha límite")
        except Exception as e:
            print(f"Error ordenando por fecha límite: {e}")

    def sort_orders(self):
        """Ordena los pedidos según el modo de ordenamiento actual"""
        try:
            if self.sort_mode == "priority":
                self.sort_by_priority()
            elif self.sort_mode == "deadline":
                self.sort_by_deadline()
        except Exception as e:
            print(f"Error en _sort_orders: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del inventario"""
        return {
            "total_orders": len(self.orders),
            "current_weight": self.current_weight,
            "max_weight": self.max_weight,
            "sort_mode": self.sort_mode,
            "current_index": self.current_index,
            "is_open": self.is_open
        }
    
    def toggle_open(self):
        """Alterna entre abierto y cerrado"""
        self.is_open = not self.is_open
    
    def update_animation(self, delta_time: float):
        """Actualiza la animación de apertura/cierre"""
        target_progress = 1.0 if self.is_open else 0.0
        if self.animation_progress < target_progress:
            self.animation_progress = min(self.animation_progress + self.animation_speed * delta_time, target_progress)
        elif self.animation_progress > target_progress:
            self.animation_progress = max(self.animation_progress - self.animation_speed * delta_time, target_progress)
    
    def set_target_position(self, x: int, y: int):
        """Establece la posición objetivo del panel"""
        self.target_x = x
        self.target_y = y
    
    def get_current_position(self) -> tuple:
        """Obtiene la posición actual interpolada para la animación"""
        # Cuando está cerrado, el panel está fuera de la pantalla a la derecha
        closed_x = self.target_x + self.panel_width
        current_x = closed_x + (self.target_x - closed_x) * self.animation_progress
        return current_x, self.target_y
    

    def draw_inventory(self, x: int, y: int, width: int, height: int):
        """Dibuja el inventario en la pantalla en la posición y tamaño recibidos"""
        #fondo del inventario
         # Actualizar dimensiones si son diferentes
        if width != self.panel_width or height != self.panel_height:
            self.panel_width = width
            self.panel_height = height
        
        # Establecer posición objetivo
        self.set_target_position(x, y)
        
        # Obtener posición actual interpolada
        current_x, current_y = self.get_current_position()
        
        # Si está completamente cerrado, no dibujar
        if self.animation_progress <= 0:
            return
        
        # Fondo del inventario con transparencia basada en la animación
        alpha = int(255 * self.animation_progress)
        arcade.draw_lbwh_rectangle_filled(
            current_x + width // 2,
            current_y + height // 2,
            width,
            height,
            (161, 130, 98, alpha)
        )

        # Borde
        arcade.draw_lbwh_rectangle_outline(
            current_x + width // 2,
            current_y + height // 2,
            width,
            height,
            (255, 255, 255, alpha),
            2
        )

        # Título
        arcade.draw_text(
            "Inventario",
            current_x + width // 2 + 5,
            current_y + height - 20,
            (255, 255, 255, alpha),
            14,
            bold=True
        )

        # Info de capacidad
        weight_text = f"Peso: {self.current_weight:.1f}/{self.max_weight:.1f} kg"
        arcade.draw_text(
            weight_text,
            current_x + width - 130,
            current_y + height - 20,
            (255, 255, 255, alpha),
            12
        )

        # Si no hay pedidos
        if not self.orders:
            arcade.draw_text(
                "No hay pedidos",
                current_x + width // 2 + 10,
                current_y + height - 50,
                (200, 200, 200, alpha),
                12
            )
            return
        
        # Encabezados de las columnas
        arcade.draw_text("ID", current_x + 250, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Prioridad", current_x + 275, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Pago", current_x + 340, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Peso", current_x + 380, current_y + height - 50, (255, 255, 0, alpha), 10)
        arcade.draw_text("Estado", current_x + 430, current_y + height - 50, (255, 255, 0, alpha), 10)

        # Lista de pedidos (máximo 8 visibles)
        start_y = current_y + height - 70
        line_height = 20
        max_display = 8

        for i, order in enumerate(self.orders[:max_display]):
            y_pos = start_y - (i * line_height)

            # Resaltar el pedido seleccionado
            if i == self.current_index:
                arcade.draw_lbwh_rectangle_filled(
                    current_x + width // 2,
                    y_pos - 2,
                    width - 20,
                    16,
                    (255, 0, 0, int(128 * self.animation_progress))
                )

            # Detalles del pedido
            order_id_short = order.id[:8] + "..." if len(order.id) > 8 else order.id
            arcade.draw_text(order_id_short, current_x + 230, y_pos, (255, 255, 255, alpha), 10)

            # Prioridad con color
            priority_color = (0, 255, 0, alpha)  # Verde
            if order.priority >= 2:
                priority_color = (255, 165, 0, alpha)  # Naranja
            if order.priority >= 3:
                priority_color = (255, 0, 0, alpha)  # Rojo

            arcade.draw_text(
                str(order.priority), 
                current_x + 290, 
                y_pos, 
                priority_color, 
                10
            )

            # Pago
            arcade.draw_text(
                f"${order.payout:.0f}", 
                current_x + 340, y_pos, 
                (255, 255, 255, alpha), 
                10
            )

            # Peso
            arcade.draw_text(
                f"{order.weight:.1f} kg", 
                current_x + 380, 
                y_pos, 
                (255, 255, 255, alpha), 
                10
            )
            
            # Estado
            status_color = (0, 255, 0, alpha) if order.status == "in_progress" else (255, 255, 0, alpha)
            arcade.draw_text(
                order.status,
                current_x + 430,
                y_pos,
                status_color,
                10
            )

        # Indicador si hay más pedidos que no se muestran
        if len(self.orders) > max_display:
            arcade.draw_text(
                f"... y {len(self.orders) - max_display} más",
                current_x + 20,
                start_y - (max_display * line_height),
                (255, 0, 0, alpha),
                10
            )

        # Modo de ordenamiento
        sort_text = f"Orden: {self.sort_mode}"
        arcade.draw_text(
            sort_text,
            current_x + 230,
            current_y + 430,
            (255, 0, 0, alpha),
            10
        )
