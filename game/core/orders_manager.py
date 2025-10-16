import os
import json
import random
from datetime import datetime, timezone
from typing import Optional

from game.core import utils
from game.core.orders import Order


class OrdersManager:
    """
    Administra la cola programada y los pedidos activos del jugador.
    También realiza el set-up inicial desde API o archivo local.
    """
    def __init__(self):
        self.pending_orders: list[Order] = []
        self._orders_queue: list[tuple[float, Order]] = []
        self._orders_window = None
        self.order_release_interval: float = 120.0
        self.debug: bool = False
        self.canceled_orders: set[str] = set()  # <-- nuevo

    def attach_window(self, orders_window):
        self._orders_window = orders_window
        if self._orders_window:
            self._orders_window.set_pending_orders(self.pending_orders)

    def mark_canceled(self, order_id: str):
        self.canceled_orders.add(str(order_id))

    def setup_orders(self, api_client, files_conf: dict, app_config: dict, city, renderer, debug: bool = False, skip_ids: set[str] | None = None):
        """
        Carga pedidos de API o backup y prepara la cola de liberación.
        Genera puertas (renderer.generate_door_at) cuando corresponde.
        """
        self.debug = bool(debug)
        self.order_release_interval = float(app_config.get("game", {}).get("order_release_seconds", 120))
        self.pending_orders = []
        self._orders_queue = []
        skip_ids = set(skip_ids or ())

        # 1) cargar lista cruda
        orders_list = self._load_orders_list(api_client, files_conf)

        if self.debug:
            print(f"Total de pedidos cargados: {len(orders_list)}")

        # 2) helpers locales
        def _in_bounds(x, y):
            return 0 <= x < city.width and 0 <= y < city.height

        def _is_street(x, y):
            try:
                return city.tiles[y][x] == "C"
            except Exception:
                return False

        def _parse_xy(v):
            if isinstance(v, (list, tuple)) and len(v) == 2:
                return int(v[0]), int(v[1])
            return None

        def _time_limit_from_deadline(deadline_str: str, default_sec: float = 600.0) -> float:
            if not deadline_str:
                return default_sec
            try:
                s = str(deadline_str)
                if s.endswith("Z"):
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                else:
                    dt = datetime.fromisoformat(s)
                    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                return max(60.0, (dt - now).total_seconds())
            except Exception:
                return default_sec

        def _nearest_street_from(x0, y0, max_radius=64):
            if _in_bounds(x0, y0) and _is_street(x0, y0):
                return (x0, y0)
            best = None
            best_d2 = float("inf")
            for r in range(1, max_radius + 1):
                for dx in range(-r, r + 1):
                    for dy in (-r, r):
                        x, y = x0 + dx, y0 + dy
                        if _in_bounds(x, y) and _is_street(x, y):
                            d2 = (x - x0) * (x - x0) + (y - y0) * (y - y0)
                            if d2 < best_d2:
                                best, best_d2 = (x, y), d2
                for dy in range(-r + 1, r):
                    for dx in (-r, r):
                        x, y = x0 + dx, y0 + dy
                        if _in_bounds(x, y) and _is_street(x, y):
                            d2 = (x - x0) * (x - x0) + (y - y0) * (y - y0)
                            if d2 < best_d2:
                                best, best_d2 = (x, y), d2
                if best is not None:
                    return best
            return None

        def _snap_to_accessible_or_force(pos):
            if not pos:
                return None
            px, py = pos
            if _in_bounds(px, py) and _is_street(px, py):
                nb = utils.find_nearest_building(city, px, py)
                return (px, py), nb

            nb = utils.find_nearest_building(city, px, py)
            bx, by = nb if nb else (px, py)

            for nx, ny in ((bx + 1, by), (bx - 1, by), (bx, by + 1), (bx, by - 1)):
                if _in_bounds(nx, ny) and _is_street(nx, ny):
                    return (nx, ny), nb

            for nx in (bx - 1, bx, bx + 1):
                for ny in (by - 1, by, by + 1):
                    if (nx, ny) != (bx, by) and _in_bounds(nx, ny) and _is_street(nx, ny):
                        return (nx, ny), nb

            near_street = _nearest_street_from(bx, by, max_radius=96)
            if near_street:
                return near_street, nb
            near_street = _nearest_street_from(px, py, max_radius=96)
            if near_street:
                nn_b = utils.find_nearest_building(city, near_street[0], near_street[1])
                return near_street, nn_b
            return None

        # 3) parsear y construir Orders
        orders_objs = []
        for it in orders_list:
            try:
                oid = str(it.get("id") or f"ORD-{random.randint(1000, 9999)}")
                if oid in skip_ids or oid in self.canceled_orders:
                    continue

                pickup_raw = _parse_xy(it.get("pickup"))
                dropoff_raw = _parse_xy(it.get("dropoff"))
                if not pickup_raw or not dropoff_raw:
                    if self.debug:
                        print(f"Saltando pedido {oid}: pickup/dropoff inválidos")
                    continue

                snap_p = _snap_to_accessible_or_force(pickup_raw)
                snap_d = _snap_to_accessible_or_force(dropoff_raw)
                if not snap_p or not snap_d:
                    if self.debug:
                        print(f"Forzado fallido para {oid}: no hay calles en el mapa")
                    continue

                (pickup_pos, p_building) = snap_p
                (dropoff_pos, d_building) = snap_d

                payout = float(it.get("payout", it.get("payment", 0)))
                deadline = str(it.get("deadline", ""))
                time_limit = _time_limit_from_deadline(deadline, 600.0)

                order = Order(
                    order_id=oid,
                    pickup_pos=pickup_pos,
                    dropoff_pos=dropoff_pos,
                    payment=payout,
                    time_limit=time_limit,
                    weight=it.get("weight"),
                    priority=int(it.get("priority", 0)),
                    deadline=deadline,
                    release_time=int(it.get("release_time", 0)),
                )
                orders_objs.append(order)

                # Generar puertas si corresponde
                if renderer and city:
                    if p_building:
                        pbx, pby = p_building
                        if _in_bounds(pbx, pby) and city.tiles[pby][pbx] == "B":
                            renderer.generate_door_at(pbx, pby)
                    if d_building:
                        dbx, dby = d_building
                        if _in_bounds(dbx, dby) and city.tiles[dby][dbx] == "B":
                            renderer.generate_door_at(dbx, dby)

            except Exception as e:
                if self.debug:
                    print(f"Saltando pedido inválido: {e}")

        # 4) preparar cola según tiempo jugado
        self.pending_orders = []
        self._orders_queue = []
        elapsed = 0.0
        for i, order in enumerate(orders_objs):
            unlock_at = i * float(self.order_release_interval)
            if unlock_at <= elapsed:
                self.pending_orders.append(order)
            else:
                self._orders_queue.append((unlock_at, order))
        self._orders_queue.sort(key=lambda x: x[0])

        if self._orders_window:
            self._orders_window.set_pending_orders(self.pending_orders)
        if self.debug:
            print(f"{len(self.pending_orders)} active orders ready")

    def release_orders(self, total_play_time: float, notify):
        released = 0
        while self._orders_queue and self._orders_queue[0][0] <= float(total_play_time):
            _, order = self._orders_queue.pop(0)
            # No reinsertar cancelados por seguridad
            if order.id in self.canceled_orders:
                continue
            self.pending_orders.append(order)
            released += 1
            notify(f"Nuevo pedido disponible: {order.id}")

        if released and self._orders_window:
            self._orders_window.set_pending_orders(self.pending_orders)

    # --------- helpers privados ---------
    def _load_orders_list(self, api_client, files_conf: dict):
        data = None
        try:
            data = api_client.get_orders() if api_client else None
        except Exception as e:
            if self.debug:
                print(f"Error al cargar pedidos desde API: {e}")

        orders_list = []
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            orders_list = data["data"]
        elif isinstance(data, list):
            orders_list = data

        if not orders_list:
            try:
                backup_file = os.path.join(files_conf.get("data_directory", "data"), "pedidos.json")
                if os.path.exists(backup_file):
                    with open(backup_file, "r", encoding="utf-8") as f:
                        local = json.load(f)
                    if isinstance(local, dict):
                        if isinstance(local.get("data"), list):
                            orders_list = local["data"]
                        elif isinstance(local.get("orders"), list):
                            orders_list = local["orders"]
                    elif isinstance(local, list):
                        orders_list = local
                    if orders_list and self.debug:
                        print(f"Pedidos cargados desde backup: {backup_file} ({len(orders_list)})")
            except Exception as e:
                if self.debug:
                    print(f"Error al cargar pedidos desde backup: {e}")
        return orders_list