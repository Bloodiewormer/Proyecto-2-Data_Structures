import math


class DeliverySystem:
    """
    Lógica de pickups y entregas basada en la posición del jugador.
    Mantiene el mismo comportamiento y mensajes que en game.py.
    """
    def __init__(self):
        pass

    def _distance(self, px: float, py: float, tx: float, ty: float) -> float:
        dx = px - tx
        dy = py - ty
        return math.hypot(dx, dy)

    def process(self, player, radius: float, notify):
        """
        Recorre los pedidos del inventario del jugador y procesa pickups/entregas.
        - notify: función callable(str) para mostrar notificaciones.
        """
        if not player or not getattr(player, "inventory", None):
            return

        inv = player.inventory
        for order in list(inv.orders):
            # Pickup
            if getattr(order, "status", "") == "in_progress":
                px, py = order.pickup_pos
                if self._distance(player.x, player.y, px, py) <= radius:
                    order.pickup()
                    notify(f"Recogido {order.id}")
                    # Actualizar peso del jugador para que afecte velocidad sólo con picked_up
                    try:
                        player.set_inventory_weight(player.inventory.current_weight)
                    except Exception:
                        pass
                    continue

            # Entrega
            if getattr(order, "status", "") == "picked_up":
                dx, dy = order.dropoff_pos
                if self._distance(player.x, player.y, dx, dy) <= radius:
                    order.deliver()
                    payout = float(getattr(order, "payout", getattr(order, "payment", 0.0)))
                    player.add_earnings(payout)
                    player.update_reputation_for_delivery(order)
                    player.remove_order_from_inventory(order.id)
                    notify(f"Entregado {order.id}  +${payout:.0f}")
                    # Actualizar peso del jugador después de entregar
                    try:
                        player.set_inventory_weight(player.inventory.current_weight)
                    except Exception:
                        pass
