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

    # En la clase SaveFlow, modificar save_game():

    def save_game(self, game) -> bool:
        try:
            player_data = self.save_manager.serialize_player(game.player)
            city_data = self.save_manager.serialize_city(game.city)

            accepted_orders_payload = [order.to_dict() for order in game.player.inventory.orders]
            pending_orders_payload = [order.to_dict() for order in game.orders_manager.pending_orders]
            canceled_orders_payload = list(getattr(game.orders_manager, "canceled_orders", []))

            timer_payload = {
                "total_play_time": float(getattr(game, "total_play_time", 0.0)),
                "time_remaining": float(
                    getattr(game, "time_remaining", float(getattr(game, "time_limit", 0.0)))
                ),
            }

            # =====  Serializar IA =====
            ai_data = self._serialize_ai_players(game)
            # ================================

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
                "ai_players": ai_data,  # ← NUEVO
            }
            return self.save_manager.save_to_file(save_data)
        except Exception as e:
            print(f"Error al guardar partida: {e}")
            import traceback;
            traceback.print_exc()
            return False

    def _serialize_ai_players(self, game) -> dict:
        """
        Serializa SOLO los datos esenciales de la IA, sin tocar su estrategia/planner.
        """
        if not hasattr(game, 'ai_players') or not game.ai_players:
            return {"enabled": False, "players": []}

        players_data = []
        for ai in game.ai_players:
            # Serializar inventario de la IA
            ai_inventory = []
            if hasattr(ai, 'inventory') and ai.inventory.orders:
                for order in ai.inventory.orders:
                    ai_inventory.append(order.to_dict())

            # Datos básicos de la IA
            ai_data = {
                "x": float(ai.x),
                "y": float(ai.y),
                "angle": float(ai.angle),
                "difficulty": str(ai.difficulty),
                "stamina": float(ai.stamina),
                "reputation": float(ai.reputation),
                "earnings": float(ai.earnings),
                "total_weight": float(ai.total_weight),
                "deliveries_completed": int(ai.deliveries_completed),
                "orders_cancelled": int(ai.orders_cancelled),
                "inventory": ai_inventory,

            }
            players_data.append(ai_data)

        return {
            "enabled": True,
            "difficulty": game.ai_difficulty,
            "players": players_data
        }

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

            # restaurar timer
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

            # reconstruir puertas
            try:
                self._rebuild_doors_for_orders(game)
            except Exception:
                pass

            # ===== Restaurar IA =====
            self._restore_ai_players(game, save_data)
            # ================================

            game.state_manager.change_state(GameState.PLAYING)
            game.show_notification("Partida cargada")
            return True

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            import traceback;
            traceback.print_exc()
            game.show_notification("Error al cargar partida")
            game.state_manager.change_state(GameState.MAIN_MENU)
            return False

    def _restore_ai_players(self, game, save_data: dict):
        """
        Restaura jugadores IA de forma segura, RECREANDO sus estrategias desde cero.
        """
        ai_data = save_data.get("ai_players", {})

        if not ai_data or not ai_data.get("enabled", False):
            # Limpiar cualquier IA existente
            if hasattr(game, 'ai_players'):
                game.ai_players.clear()
            game.ai_enabled = False
            return

        # Limpiar IA existentes
        if hasattr(game, 'ai_players'):
            game.ai_players.clear()
        else:
            game.ai_players = []

        # Restaurar configuración global
        game.ai_enabled = True
        game.ai_difficulty = ai_data.get("difficulty", "easy")

        # Restaurar cada jugador IA
        from game.entities.ai_player import AIPlayer
        from game.IA.strategies.strategies import EasyStrategy, MediumStrategy, HardStrategy

        for ai_save in ai_data.get("players", []):
            try:
                difficulty = str(ai_save.get("difficulty", "easy"))

                # Crear nueva estrategia desde cero (CRÍTICO para evitar bugs)
                if difficulty == "easy":
                    strategy = EasyStrategy(game)
                elif difficulty == "medium":
                    strategy = MediumStrategy(game)
                elif difficulty == "hard":
                    strategy = HardStrategy(game)
                else:
                    strategy = EasyStrategy(game)

                # Crear nueva IA con estrategia fresca
                ai = AIPlayer(
                    start_x=float(ai_save.get("x", 1.0)),
                    start_y=float(ai_save.get("y", 1.0)),
                    config=game.app_config.get("player", {}),
                    difficulty=difficulty,
                    world=game,
                    strategy=strategy  # ← Estrategia nueva
                )

                # Restaurar solo datos de estado
                ai.angle = float(ai_save.get("angle", 0.0))
                ai.stamina = float(ai_save.get("stamina", 100.0))
                ai.reputation = float(ai_save.get("reputation", 70.0))
                ai.earnings = float(ai_save.get("earnings", 0.0))
                ai.total_weight = float(ai_save.get("total_weight", 0.0))
                ai.deliveries_completed = int(ai_save.get("deliveries_completed", 0))
                ai.orders_cancelled = int(ai_save.get("orders_cancelled", 0))

                # Restaurar inventario
                ai.inventory.orders = []
                for order_dict in ai_save.get("inventory", []):
                    try:
                        order = Order.from_dict(order_dict)
                        ai.inventory.orders.append(order)
                    except Exception as e:
                        print(f"Error restaurando pedido de IA: {e}")

                # Actualizar peso del inventario
                ai.set_inventory_weight(ai.inventory.current_weight)


                ai.current_target = None

                game.ai_players.append(ai)

                if game.debug:
                    print(f"[SaveFlow] IA restaurada: {difficulty} en ({ai.x:.1f},{ai.y:.1f}), "
                          f"${ai.earnings:.0f}, {len(ai.inventory.orders)} pedidos")

            except Exception as e:
                print(f"Error restaurando jugador IA: {e}")
                import traceback
                traceback.print_exc()

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