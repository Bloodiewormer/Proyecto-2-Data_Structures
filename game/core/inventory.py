from typing import List, Optional, Dict, Any
from game.core.orders import Order


class Inventory:
    """
    Modelo de inventario (dominio). Sin responsabilidades de UI.
    """
    def __init__(self, max_weight: float = 10.0):
        self.max_weight = max_weight
        self.orders: List[Order] = []
        self.current_index = 0
        self.sort_mode = "priority"  # 'priority' | 'deadline'

    @property
    def current_weight(self) -> float:
        # SOLO cuenta el peso de pedidos recogidos
        return sum(float(getattr(order, "weight", 0.0)) for order in self.orders
                   if getattr(order, "status", "") == "picked_up")

    @property
    def can_add_more(self) -> bool:
        return self.current_weight < self.max_weight

    def add_order(self, order: Order) -> bool:
        try:
            # Nota: el peso de in_progress NO debe contar, current_weight ya filtra.
            if self.current_weight + float(getattr(order, "weight", 0.0)) <= self.max_weight:
                order.status = "in_progress"
                self.orders.append(order)
                self.sort_orders()
                return True
            else:
                return False
        except Exception:
            return False

    def remove_order(self, order_id: str) -> Optional[Order]:
        try:
            for i, order in enumerate(self.orders):
                if order.id == order_id:
                    return self.orders.pop(i)
            return None
        except Exception:
            return None

    def get_current_order(self) -> Optional[Order]:
        if not self.orders:
            return None
        return self.orders[self.current_index]

    def next_order(self):
        if not self.orders:
            return
        self.current_index = (self.current_index + 1) % len(self.orders)

    def previous_order(self):
        if not self.orders:
            return
        self.current_index = (self.current_index - 1) % len(self.orders)

    def sort_by_priority(self):
        try:
            self.orders.sort(key=lambda x: x.priority, reverse=True)
            self.sort_mode = "priority"
            self.current_index = 0
        except Exception:
            pass

    def sort_by_deadline(self):
        try:
            self.orders.sort(key=lambda x: x.deadline)
            self.sort_mode = "deadline"
            self.current_index = 0
        except Exception:
            pass

    def sort_orders(self):
        try:
            if self.sort_mode == "priority":
                self.sort_by_priority()
            elif self.sort_mode == "deadline":
                self.sort_by_deadline()
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_orders": len(self.orders),
            "current_weight": self.current_weight,
            "max_weight": self.max_weight,
            "sort_mode": self.sort_mode,
            "current_index": self.current_index,
        }