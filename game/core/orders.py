from typing import Dict, Any, Optional, Tuple, List
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
    accepted_at: float = -1.0
    time_remaining: float = -1.0

    def __init__(
        self,
        order_id: str,
        pickup_pos: Tuple[int, int],
        dropoff_pos: Tuple[int, int],
        payment: float,
        time_limit: float,
        weight: float = 0.0,
        priority: int = 0,
        deadline: Optional[str] = None,
        release_time: int = 0,
        status: str = OrderStatus.PENDING,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        picked_up_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
        description: str = "",
        fragile: bool = False,
    ) -> None:
        self.id = order_id
        self.pickup_pos = pickup_pos
        self.dropoff_pos = dropoff_pos
        self.payment = float(payment)
        self.time_limit = float(time_limit)

        self.status = status

        self.created_at = created_at or datetime.now()
        self.expires_at = expires_at or (self.created_at + timedelta(seconds=self.time_limit))
        self.picked_up_at = picked_up_at
        self.delivered_at = delivered_at

        self.weight = float(weight)
        self.fragile = bool(fragile)
        self.description = description
        self.priority = int(priority)
        self.deadline = deadline
        self.release_time = int(release_time)
        self.payout = self.payment

        self.accepted_at = -1.0
        self.time_remaining = -1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pickup_pos": list(self.pickup_pos),
            "dropoff_pos": list(self.dropoff_pos),
            "payment": self.payment,
            "time_limit": self.time_limit,
            "weight": self.weight,
            "priority": self.priority,
            "deadline": self.deadline,
            "release_time": self.release_time,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "picked_up_at": self.picked_up_at.isoformat() if self.picked_up_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "description": self.description,
            "fragile": self.fragile,
            # Persist per\-order timer state
            "accepted_at": self.accepted_at,
            "time_remaining": self.time_remaining,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        obj = cls(
            order_id=data["id"],
            pickup_pos=tuple(data["pickup_pos"]),
            dropoff_pos=tuple(data["dropoff_pos"]),
            payment=float(data["payment"]),
            time_limit=float(data["time_limit"]),
            weight=float(data.get("weight", 0.0)),
            priority=int(data.get("priority", 0)),
            deadline=data.get("deadline"),
            release_time=int(data.get("release_time", 0)),
            status=str(data.get("status", OrderStatus.PENDING)),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            picked_up_at=datetime.fromisoformat(data["picked_up_at"]) if data.get("picked_up_at") else None,
            delivered_at=datetime.fromisoformat(data["delivered_at"]) if data.get("delivered_at") else None,
            description=str(data.get("description", "")),
            fragile=bool(data.get("fragile", False)),
        )
        # Restore per\-order timer state
        obj.accepted_at = float(data.get("accepted_at", -1.0))
        obj.time_remaining = float(data.get("time_remaining", -1.0))
        return obj


    def is_expired(self) -> bool:
        try:
            if self.accepted_at >= 0:
                return self.time_remaining == 0.0
            return (datetime.now() > self.expires_at) and (self.status in (OrderStatus.PENDING, OrderStatus.IN_PROGRESS))
        except Exception:
            return False

    def get_remaining_time(self) -> float:
        try:
            remaining = (self.expires_at - datetime.now()).total_seconds()
            return max(0.0, float(remaining))
        except Exception:
            return 0.0

    def pickup(self):
        if self.status in (OrderStatus.IN_PROGRESS, OrderStatus.PENDING):
            self.status = OrderStatus.PICKED_UP
            self.picked_up_at = datetime.now()

    def deliver(self):
        if self.status == OrderStatus.PICKED_UP:
            self.status = OrderStatus.DELIVERED
            self.delivered_at = datetime.now()

    def cancel(self):
        if self.status in [OrderStatus.PENDING, OrderStatus.PICKED_UP, OrderStatus.IN_PROGRESS]:
            self.status = OrderStatus.CANCELLED

    def start_timer(self, current_play_time: float):
        self.accepted_at = float(current_play_time)
        self.time_remaining = float(getattr(self, "time_limit", 0.0))

    def update_time_remaining(self, elapsed_since_accept: float):
        if self.accepted_at < 0 or self.time_remaining < 0:
            return
        self.time_remaining = max(0.0, float(getattr(self, "time_limit", 0.0)) - elapsed_since_accept)


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
                o = self.orders[order_id]
                if getattr(o, "status", "") == "picked_up":
                    total_weight += float(getattr(o, "weight", 0.0))
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
