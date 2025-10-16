# python
from game.core.save_manager import SaveManager
from game.core.gamestate import GameState
from game.core.orders import Order
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

            # Persist timer to avoid game over on load
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

            # Restore core entities
            if "player" in save_data and getattr(game, "player", None):
                self.save_manager.restore_player(game.player, save_data["player"])
            if "city" in save_data and getattr(game, "city", None):
                self.save_manager.restore_city(game.city, save_data["city"])
            if "game_stats" in save_data:
                try:
                    game.game_stats = save_data["game_stats"]
                except Exception:
                    pass

            # Restore timer first to avoid instant game over
            timer_blob = save_data.get("timer") or {}
            try:
                tp = float(timer_blob.get("total_play_time", 0.0))
                tr = float(timer_blob.get("time_remaining", float(getattr(game, "time_limit", 0.0))))
                # Safety floor: if something bad was saved, clamp to time_limit
                if tr <= 0 and getattr(game, "time_limit", 0.0) > 0:
                    tr = float(game.time_limit)
                game.total_play_time = tp
                game.time_remaining = tr
                if getattr(game, "timer", None) and hasattr(game.timer, "restore"):
                    game.timer.restore(play_time=tp, time_remaining=tr)
            except Exception:
                # Fallback: reset to full time
                if getattr(game, "time_limit", 0.0) > 0:
                    game.total_play_time = 0.0
                    game.time_remaining = float(game.time_limit)
                    if getattr(game, "timer", None) and hasattr(game.timer, "restore"):
                        game.timer.restore(play_time=0.0, time_remaining=float(game.time_limit))

            # Restore orders
            orders_blob = save_data.get("orders", {}) or {}
            accepted_orders = orders_blob.get("accepted_orders", [])
            pending_orders = orders_blob.get("pending_orders", [])
            canceled_ids = {str(i) for i in orders_blob.get("canceled_orders", [])}

            # Accepted: append directly to avoid status/timer overrides
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

            # Pending: skip canceled
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

            # Rebuild doors near pickup/dropoff positions using adjacent building facade
            try:
                SaveFlow.rebuild_doors_for_orders(game)
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
    def _find_adjacent_building(tile_x: int, tile_y: int, city) -> Optional[Tuple[int, int]]:
        """Return first adjacent 'B' building tile around (tile_x, tile_y); if none, nearest within small radius."""
        if not city:
            return None
        w, h = int(city.width), int(city.height)
        # Immediate 4-neighbors first
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            bx, by = tile_x + dx, tile_y + dy
            if 0 <= bx < w and 0 <= by < h:
                try:
                    if city.tiles[by][bx] == "B":
                        return bx, by
                except Exception:
                    pass
        # Fallback: search a small radius for nearest building
        best = None
        best_dist = 999999
        max_r = 4
        for ry in range(max(tile_y - max_r, 0), min(tile_y + max_r + 1, h)):
            for rx in range(max(tile_x - max_r, 0), min(tile_x + max_r + 1, w)):
                try:
                    if city.tiles[ry][rx] == "B":
                        d = abs(rx - tile_x) + abs(ry - tile_y)
                        if d < best_dist:
                            best_dist = d
                            best = (rx, ry)
                except Exception:
                    pass
        return best

    @staticmethod
    def _ensure_door_near(pos: Tuple[int, int], renderer, city):
        """Given a street or building pos, place a door on the building facade.
        If pos is a building tile itself, use it directly; otherwise, find an adjacent building.
        """
        if not renderer or not city or not pos:
            return
        try:
            tx, ty = int(pos[0]), int(pos[1])
        except Exception:
            return
        # If the pos itself is a building, place the door there
        try:
            if 0 <= tx < city.width and 0 <= ty < city.height and city.tiles[ty][tx] == "B":
                renderer.generate_door_at(tx, ty)
                return
        except Exception:
            pass
        # Otherwise, find an adjacent building tile
        building = SaveFlow._find_adjacent_building(tx, ty, city)
        if building:
            bx, by = building
            renderer.generate_door_at(bx, by)

    @staticmethod
    def rebuild_doors_for_orders(game):
        """
        Rebuild doors for all known orders (pending, queued, inventory) using pickup/dropoff positions.
        Call this after loading a save or after restoring orders from API/backup.
        """
        renderer = getattr(game, "renderer", None)
        city = getattr(game, "city", None)
        if not renderer or not city:
            return

        # Clear existing door markers safely
        try:
            if hasattr(renderer, "door_positions") and renderer.door_positions is not None:
                renderer.door_positions.clear()
        except Exception:
            pass

        seen_positions = set()

        def add_from_order(order):
            for pos in (getattr(order, "pickup_pos", None), getattr(order, "dropoff_pos", None)):
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    key = (int(pos[0]), int(pos[1]))
                    if key not in seen_positions:
                        seen_positions.add(key)
                        SaveFlow._ensure_door_near(key, renderer, city)

        # Pending and queued orders (from orders manager)
        om = getattr(game, "orders_manager", None)
        if om:
            for o in getattr(om, "pending_orders", []) or []:
                add_from_order(o)
            for item in getattr(om, "_orders_queue", []) or []:
                try:
                    _, o = item
                    add_from_order(o)
                except Exception:
                    pass

        # Orders currently in player's inventory
        player = getattr(game, "player", None)
        inv = getattr(player, "inventory", None) if player else None
        if inv:
            for o in getattr(inv, "orders", []) or []:
                add_from_order(o)
