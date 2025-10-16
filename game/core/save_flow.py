from game.core.save_manager import SaveManager
from game.core.gamestate import GameState
from game.core.orders import Order
from game.core.utils import find_nearest_building
from typing import Optional, Tuple


class SaveFlow:
    def __init__(self, app_config: dict, debug: bool = False):
        self.app_config = app_config
        self.debug = bool(debug)
        self.save_manager = SaveManager(app_config)

    def save_game(self, game) -> bool:
        try:
            player_data = self.save_manager.serialize_player(game.player)
            city_data = self.save_manager.serialize_city(game.city)

            accepted_orders_payload = [order.to_dict() for order in game.player.inventory.orders]
            pending_orders_payload = [order.to_dict() for order in game.orders_manager.pending_orders]
            canceled_orders_payload = list(getattr(game.orders_manager, "canceled_orders", []))

            # persistir timer para evitar game over al cargar
            timer_payload = {
                "total_play_time": float(getattr(game, "total_play_time", 0.0)),
                "time_remaining": float(
                    getattr(game, "time_remaining", float(getattr(game, "time_limit", 0.0)))
                ),
            }

            save_data = {
                "player": player_data,
                "city": city_data,
                "orders": {
                    "accepted_orders": accepted_orders_payload,
                    "pending_orders": pending_orders_payload,
                    "canceled_orders": canceled_orders_payload,
                },
                "game_stats": getattr(game, "game_stats", {}),
                "timer": timer_payload,
            }
            return self.save_manager.save_to_file(save_data)
        except Exception as e:
            print(f"Error al guardar partida: {e}")
            import traceback; traceback.print_exc()
            return False

    def load_game(self, game) -> bool:
        try:
            save_data = self.save_manager.load_game()
            if not save_data:
                game.show_notification("Error al cargar partida")
                return False

            game._initialize_game_systems()

            # restaurar entidades base
            if "player" in save_data and getattr(game, "player", None):
                self.save_manager.restore_player(game.player, save_data["player"])
            if "city" in save_data and getattr(game, "city", None):
                self.save_manager.restore_city(game.city, save_data["city"])
            if "game_stats" in save_data:
                try:
                    game.game_stats = save_data["game_stats"]
                except Exception:
                    pass

            # restaurar timer primero
            timer_blob = save_data.get("timer") or {}
            try:
                tp = float(timer_blob.get("total_play_time", 0.0))
                tr = float(timer_blob.get("time_remaining", float(getattr(game, "time_limit", 0.0))))
                if tr <= 0 and getattr(game, "time_limit", 0.0) > 0:
                    tr = float(game.time_limit)
                game.total_play_time = tp
                game.time_remaining = tr
                if getattr(game, "timer", None) and hasattr(game.timer, "restore"):
                    game.timer.restore(play_time=tp, time_remaining=tr)
            except Exception:
                if getattr(game, "time_limit", 0.0) > 0:
                    game.total_play_time = 0.0
                    game.time_remaining = float(game.time_limit)
                    if getattr(game, "timer", None) and hasattr(game.timer, "restore"):
                        game.timer.restore(play_time=0.0, time_remaining=float(game.time_limit))

            # restaurar pedidos
            orders_blob = save_data.get("orders", {}) or {}
            accepted_orders = orders_blob.get("accepted_orders", [])
            pending_orders = orders_blob.get("pending_orders", [])
            canceled_ids = {str(i) for i in orders_blob.get("canceled_orders", [])}

            # accepted
            try:
                game.player.inventory.orders = []
                for it in accepted_orders:
                    try:
                        order = Order.from_dict(it)
                        game.player.inventory.orders.append(order)
                    except Exception as e:
                        print(f"Pedido inválido en accepted_orders: {it}. Error: {e}")
            except Exception:
                pass

            # pending (omitir cancelados)
            try:
                game.orders_manager.pending_orders = []
                for it in pending_orders:
                    try:
                        oid = str(it.get("id")) if isinstance(it, dict) else None
                        if oid and oid not in canceled_ids:
                            order = Order.from_dict(it)
                            game.orders_manager.pending_orders.append(order)
                    except Exception as e:
                        print(f"Pedido inválido en pending_orders: {it}. Error: {e}")
            except Exception:
                pass

            # reconstruir puertas usando la misma regla que orders_manager:
            # puerta en el tile de edificio "B" más cercano a pickup/dropoff
            try:
                self._rebuild_doors_for_orders(game)
            except Exception:
                pass

            game.state_manager.change_state(GameState.PLAYING)
            game.show_notification("Partida cargada")
            return True

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            import traceback; traceback.print_exc()
            game.show_notification("Error al cargar partida")
            game.state_manager.change_state(GameState.MAIN_MENU)
            return False

    @staticmethod
    def _place_door_for_world_pos(pos: Tuple[int, int], renderer, city):
        """elige el edificio más cercano con utils.find_nearest_building y genera la puerta ahí."""
        if not renderer or not city or not pos:
            return
        try:
            tx, ty = int(pos[0]), int(pos[1])
        except Exception:
            return

        b = find_nearest_building(city, tx, ty)
        if not b:
            return

        bx, by = int(b[0]), int(b[1])
        if 0 <= bx < int(city.width) and 0 <= by < int(city.height):
            try:
                if city.tiles[by][bx] == "B":
                    renderer.generate_door_at(bx, by)
            except Exception:
                pass

    def _rebuild_doors_for_orders(self, game):
        """regenera puertas para todos los pedidos conocidos (pending, en cola, inventario)."""
        renderer = getattr(game, "renderer", None)
        city = getattr(game, "city", None)
        if not renderer or not city:
            return

        # limpiar marcadores actuales (los volveremos a crear desde los pedidos)
        try:
            if hasattr(renderer, "door_positions") and renderer.door_positions is not None:
                renderer.door_positions.clear()
        except Exception:
            pass

        seen = set()

        def add_for_order(order):
            for pos in (getattr(order, "pickup_pos", None), getattr(order, "dropoff_pos", None)):
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    key = (int(pos[0]), int(pos[1]))
                    if key not in seen:
                        seen.add(key)
                        self._place_door_for_world_pos(key, renderer, city)

        om = getattr(game, "orders_manager", None)
        if om:
            for o in getattr(om, "pending_orders", []) or []:
                add_for_order(o)
            for item in getattr(om, "_orders_queue", []) or []:
                try:
                    _, o = item
                    add_for_order(o)
                except Exception:
                    pass

        player = getattr(game, "player", None)
        inv = getattr(player, "inventory", None) if player else None
        if inv:
            for o in getattr(inv, "orders", []) or []:
                add_for_order(o)