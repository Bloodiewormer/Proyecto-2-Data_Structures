import arcade
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Order:
    """Representa un pedido con su ID, destino y peso"""
    id: str
    pickup_location: List[int] # [x, y]
    dropoff_location: List[int] # [x, y]
    payout: float
    weight: float
    deadline: str
    priority: int
    release_time: int
    accepted_time: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, delivered, cancelled

    def is_overdue(self, current_time: datetime) -> bool:
        """Determina si el pedido está atrasado según el tiempo actual"""
        return self.get_time_remaining(current_time) <= 0

    def get_time_remaining(self, current_time: datetime) -> float:
        """Obtiene el tiempo restante para el pedido"""
        deadline = datetime.fromisoformat(self.deadline.replace("Z", "+00:00"))
        return (deadline - current_time).total_seconds()
    


class Inventory:    
    """Maneja el inventario del jugador, incluyendo capacidad y peso"""
    def __init__(self, max_weight: float = 10.0):
        self.max_weight = max_weight
        self.orders: List[Order] = []
        self.current_index = 0  # Índice del pedido actualmente seleccionado
        self.sort_mode = "priority"  # Modo de ordenamiento: 'priority', 'deadline'

    @property # property hace que se pueda acceder como atributo (no como método)
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
                order.accepted_time = datetime.now()
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
            elif self.sort_mode == "payout":
                self.sort_by_payout()
        except Exception as e:
            print(f"Error en _sort_orders: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del inventario"""
        return {
            "total_orders": len(self.orders),
            "current_weight": self.current_weight,
            "max_weight": self.max_weight,
            "sort_mode": self.sort_mode,
            "current_index": self.current_index
        }
    
    def draw_inventory(self, x: int, y: int, width: int, height: int):
        """Dibuja el inventario en la pantalla en la posición y tamaño recibidos"""
        #fondo del inventario
        arcade.draw_lbwh_rectangle_filled(
            x + width // 2,
            y + height // 2,
            width,
            height,
            (161, 130, 98)
        )

        #borde
        arcade.draw_lbwh_rectangle_filled(
            x + width // 2,
            y + height // 2,
            width,
            height,
            (161, 130, 98)
        )

        #titulo
        arcade.draw_text(
            "Inventario",
            x + 250,
            y + height,
            arcade.color.WHITE,
            14
        )

        #info de capacidad
        weight_text = f"Peso: {self.current_weight:.1f}/{self.max_weight:.1f} kg"
        arcade.draw_text(
            weight_text,
            x + width - 100,
            y + height,
            arcade.color.WHITE,
            12
        )

        #lista de pedidos
        if not self.orders:
            arcade.draw_text(
                "No hay pedidos",
                x + 250,
                y + height - 15,
                arcade.color.LIGHT_GRAY,
                12
            )
            return
        
        #encabezados de las columnas
        arcade.draw_text("ID", x + 250, y + height - 50, arcade.color.YELLOW, 10)
        arcade.draw_text("Prioridad", x + 270, y + height - 50, arcade.color.YELLOW, 10)
        arcade.draw_text("Pago", x + 340, y + height - 50, arcade.color.YELLOW, 10)
        arcade.draw_text("Peso", x + 380, y + height - 50, arcade.color.YELLOW, 10)

        #lista de pedidos (máximo 5 visibles)
        start_y = y + height - 70
        line_height = 20
        max_display = 5

        for i, order in enumerate(self.orders[:max_display]):
            y_pos = start_y - (i * line_height)

            #resaltar el pedido seleccionado
            if i == self.current_index and i < len(self.orders):
                arcade.draw_lbwh_rectangle_filled(
                    x + width // 2,
                    y_pos + 5,
                    width - 10,
                    16,
                    arcade.color.RED
                )

            #detalles del pedido
            order_id_short = order.id[:8] + "..." if len(order.id) > 8 else order.id # Mostrar solo los primeros 8 caracteres del ID si es muy largo
            arcade.draw_text(order_id_short, x + 230, y_pos, arcade.color.WHITE, 10)

            #prioridad
            priority_color = arcade.color.GREEN 
            if order.priority >= 2:
                priority_color = arcade.color.ORANGE
            if order.priority >= 3:
                priority_color = arcade.color.RED

            arcade.draw_text(
                str(order.priority), 
                x + 280, 
                y_pos, 
                priority_color, 
                10
            )

            #pago
            arcade.draw_text(
                f"${order.payout}", 
                x + 340, y_pos, 
                arcade.color.WHITE, 
                10
            )

            #peso
            arcade.draw_text(
                f"{order.weight:.1f} kg", 
                x + 380, 
                y_pos, 
                arcade.color.WHITE, 
                10
            )

            #por si hay más pedidos que no se muestran
        if len(self.orders) > max_display:
            arcade.draw_text(
                f"... y {len(self.orders) - max_display} más",
                x + 15,
                start_y - (max_display * line_height),
                arcade.color.RED,
                10
            )

        #modo de ordenamiento
        sort_text = f"Orden: {self.sort_mode}"
        arcade.draw_text(
            sort_text,
            x + 230,
            y + 430,
            arcade.color.RED,
            10
        )
