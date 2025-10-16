# file: game/orders.py
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import random


class OrderStatus:
    PENDING = "pending"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    IN_PROGRESS = "in_progress"


class Order:
    def __init__(self, order_id: str, pickup_pos: Tuple[int, int],
                 dropoff_pos: Tuple[int, int], payment: float,
                 time_limit: float = 600.0,
                 weight: float = None,
                 priority: int = 0,
                 deadline: str = "",
                 release_time: int = 0):
        self.id = order_id
        self.pickup_pos = pickup_pos
        self.dropoff_pos = dropoff_pos
        self.payment = payment
        self.time_limit = time_limit
        self.status = OrderStatus.PENDING

        # Tiempos
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=time_limit)
        self.picked_up_at = None
        self.delivered_at = None

        # Datos del pedido
        self.description = "Entrega urgente"
        if weight is not None:
            self.weight = weight
        else:
            self.weight = random.uniform(0.5, 3.0)  # kg
        
        self.fragile = random.choice([True, False])

        # Nuevos atributos para compatibilidad con el inventario
        self.priority = priority
        self.deadline = deadline
        self.release_time = release_time
        self.payout = payment  # Alias para payment para compatibilidad

    @property
    def pickup_location(self):
        return list(self.pickup_pos)
    
    @property
    def dropoff_location(self):
        return list(self.dropoff_pos)

    def to_dict(self) -> Dict[str, Any]:
        """Serializar orden para guardado"""
        return {
            "id": self.id,
            "pickup_pos": list(self.pickup_pos),
            "dropoff_pos": list(self.dropoff_pos),
            "payment": self.payment,
            "time_limit": self.time_limit,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "picked_up_at": self.picked_up_at.isoformat() if self.picked_up_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "description": self.description,
            "weight": self.weight,
            "fragile": self.fragile,
            "priority": self.priority,
            "deadline": self.deadline,
            "release_time": self.release_time
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Deserializar orden desde datos guardados"""
        order = cls(
            data["id"],
            tuple(data["pickup_pos"]),
            tuple(data["dropoff_pos"]),
            data["payment"],
            data["time_limit"],
            weight=data.get("weight"),
            priority=data.get("priority", 0),
            deadline=data.get("deadline", ""),
            release_time=data.get("release_time", 0)
        )

        order.status = data["status"]
        order.created_at = datetime.fromisoformat(data["created_at"])
        order.expires_at = datetime.fromisoformat(data["expires_at"])

        if data.get("picked_up_at"):
            order.picked_up_at = datetime.fromisoformat(data["picked_up_at"])
        if data.get("delivered_at"):
            order.delivered_at = datetime.fromisoformat(data["delivered_at"])

        order.description = data.get("description", "Entrega urgente")
        order.fragile = data.get("fragile", False)

        return order

    def is_expired(self) -> bool:
        """Verificar si la orden ha expirado"""
        return datetime.now() > self.expires_at and self.status == OrderStatus.PENDING

    def get_remaining_time(self) -> float:
        """Obtener tiempo restante en segundos"""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, remaining)

    def pickup(self):
        """Marcar orden como recogida"""
        if self.status == OrderStatus.IN_PROGRESS:
            self.status = OrderStatus.PICKED_UP
            self.picked_up_at = datetime.now()

    def deliver(self):
        """Marcar orden como entregada"""
        if self.status == OrderStatus.PICKED_UP:
            self.status = OrderStatus.DELIVERED
            self.delivered_at = datetime.now()

    def cancel(self):
        """Cancelar orden"""
        if self.status in [OrderStatus.PENDING, OrderStatus.PICKED_UP]:
            self.status = OrderStatus.CANCELLED


class OrderManager:
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.active_orders: List[str] = []
        self.player_inventory: List[str] = []  # IDs de órdenes en inventario
        self.completed_orders: List[str] = []
        self.order_counter = 0

    def create_order(self, pickup_pos: Tuple[int, int], dropoff_pos: Tuple[int, int],
                     payment: float = None, time_limit: float = 600.0) -> Order:
        """Crear nueva orden"""
        self.order_counter += 1
        order_id = f"ORD_{self.order_counter:04d}"

        if payment is None:
            # Calcular pago basado en distancia
            distance = ((dropoff_pos[0] - pickup_pos[0]) ** 2 +
                        (dropoff_pos[1] - pickup_pos[1]) ** 2) ** 0.5
            base_payment = 50.0
            distance_bonus = distance * 5.0
            payment = base_payment + distance_bonus + random.uniform(-10, 20)

        order = Order(order_id, pickup_pos, dropoff_pos, payment, time_limit)
        self.orders[order_id] = order
        self.active_orders.append(order_id)

        return order

    def get_active_orders(self) -> List[Order]:
        """Obtener órdenes activas"""
        return [self.orders[order_id] for order_id in self.active_orders
                if order_id in self.orders]

    def get_player_orders(self) -> List[Order]:
        """Obtener órdenes en inventario del jugador"""
        return [self.orders[order_id] for order_id in self.player_inventory
                if order_id in self.orders]

    def pickup_order(self, order_id: str, player_pos: Tuple[float, float],
                     pickup_radius: float = 1.5) -> bool:
        """Intentar recoger una orden"""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.status != OrderStatus.PENDING:
            return False

        # Verificar distancia
        distance = ((player_pos[0] - order.pickup_pos[0]) ** 2 +
                    (player_pos[1] - order.pickup_pos[1]) ** 2) ** 0.5

        if distance > pickup_radius:
            return False

        # Recoger orden
        order.pickup()
        self.player_inventory.append(order_id)
        if order_id in self.active_orders:
            self.active_orders.remove(order_id)

        return True

    def deliver_order(self, order_id: str, player_pos: Tuple[float, float],
                      delivery_radius: float = 1.5) -> bool:
        """Intentar entregar una orden"""
        if order_id not in self.orders or order_id not in self.player_inventory:
            return False

        order = self.orders[order_id]
        if order.status != OrderStatus.PICKED_UP:
            return False

        # Verificar distancia
        distance = ((player_pos[0] - order.dropoff_pos[0]) ** 2 +
                    (player_pos[1] - order.dropoff_pos[1]) ** 2) ** 0.5

        if distance > delivery_radius:
            return False

        # Entregar orden
        order.deliver()
        self.player_inventory.remove(order_id)
        self.completed_orders.append(order_id)

        return True

    def update(self, delta_time: float):
        """Actualizar estado de órdenes"""
        expired_orders = []

        for order_id in self.active_orders.copy():
            if order_id in self.orders:
                order = self.orders[order_id]
                if order.is_expired():
                    order.status = OrderStatus.EXPIRED
                    expired_orders.append(order_id)
                    self.active_orders.remove(order_id)

        return expired_orders

    def get_inventory_weight(self) -> float:
        """Calcular peso total del inventario"""
        total_weight = 0.0
        for order_id in self.player_inventory:
            if order_id in self.orders:
                total_weight += self.orders[order_id].weight
        return total_weight

    def to_dict(self) -> Dict[str, Any]:
        """Serializar para guardado"""
        return {
            "orders": {oid: order.to_dict() for oid, order in self.orders.items()},
            "active_orders": self.active_orders.copy(),
            "player_inventory": self.player_inventory.copy(),
            "completed_orders": self.completed_orders.copy(),
            "order_counter": self.order_counter
        }

    def from_dict(self, data: Dict[str, Any]):
        """Deserializar desde datos guardados"""
        self.orders = {oid: Order.from_dict(order_data)
                       for oid, order_data in data.get("orders", {}).items()}
        self.active_orders = data.get("active_orders", [])
        self.player_inventory = data.get("player_inventory", [])
        self.completed_orders = data.get("completed_orders", [])
        self.order_counter = data.get("order_counter", 0)

    def clear(self):
        """Limpiar todos los datos"""
        self.orders.clear()
        self.active_orders.clear()
        self.player_inventory.clear()
        self.completed_orders.clear()
        self.order_counter = 0

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de órdenes"""
        total_orders = len(self.orders)
        completed = len(self.completed_orders)
        active = len(self.active_orders)
        in_progress = len(self.player_inventory)

        total_earnings = sum(order.payment for order_id, order in self.orders.items()
                             if order.status == OrderStatus.DELIVERED)

        return {
            "total_orders": total_orders,
            "completed": completed,
            "active": active,
            "in_progress": in_progress,
            "total_earnings": total_earnings,
            "success_rate": (completed / max(1, total_orders)) * 100
        }