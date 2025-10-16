from game.core.save_manager import SaveManager
from game.core.gamestate import GameState


class SaveFlow:
    """
    Encapsula guardar y cargar partida usando SaveManager y aplicando el estado al juego.
    Mantiene los mensajes y música, y coopera con GameTimer y OrdersManager si existen.
    """
    def __init__(self, app_config: dict, debug: bool = False):
        self.app_config = app_config
        self.debug = bool(debug)
        self.save_manager = SaveManager(app_config)

    def save_game(self, game) -> bool:
        try:
            if not getattr(game, "player", None) or not getattr(game, "city", None):
                return False

            # Si existe GameTimer, úsalo como fuente de verdad
            if getattr(game, "timer", None):
                snapshot = game.timer.snapshot_for_save()
                game.game_stats["play_time"] = snapshot["play_time"]
                game.game_stats["time_remaining"] = snapshot["time_remaining"]
            else:
                # Compatibilidad si aún se usa total_play_time/time_remaining
                game.game_stats["play_time"] = getattr(game, "total_play_time", 0.0)
                game.game_stats["time_remaining"] = getattr(game, "time_remaining", 0.0)

            # Construir lista de pedidos aceptados en inventario para guardar
            accepted_orders_payload = []
            try:
                if getattr(game, "player", None) and getattr(game.player, "inventory", None):
                    for o in game.player.inventory.orders:
                        accepted_orders_payload.append({
                            "id": o.id,
                            "pickup": list(o.pickup_pos),
                            "dropoff": list(o.dropoff_pos),
                            "payout": float(getattr(o, "payout", getattr(o, "payment", 0))),
                            "weight": float(getattr(o, "weight", 0.0)),
                            "priority": int(getattr(o, "priority", 0)),
                            "deadline": str(getattr(o, "deadline", "")),
                            "time_limit": float(getattr(o, "time_limit", 0.0)),
                            "status": str(getattr(o, "status", "")),
                        })
            except Exception:
                pass

            # Mezcla en orders_data lo que ya tengas con accepted_orders (sin romper formatos previos)
            orders_payload = dict(getattr(game, "orders_data", {}) or {})
            orders_payload["accepted_orders"] = accepted_orders_payload

            success = self.save_manager.save_game(
                game.player, game.city, orders_payload, game.game_stats
            )

            if success:
                game.show_notification("Partida guardada")
                if getattr(game, "debug", False):
                    print(f"Guardado - Tiempo restante: {game.game_stats['time_remaining']:.1f}s")
                    print(f"Total jugado: {game.game_stats['play_time']:.1f}s")
            else:
                game.show_notification("Error al guardar")

            return success

        except Exception as e:
            print(f"Error crítico al guardar: {e}")
            import traceback; traceback.print_exc()
            game.show_notification("Error al guardar")
            return False

    def load_game(self, game) -> bool:
        try:
            save_data = self.save_manager.load_game()
            if not save_data:
                game.show_notification("Error al cargar partida")
                return False

            # Inicializa sistemas (API/City/Player/Renderer/Weather/OrdersWindow)
            game._initialize_game_systems()

            # Restaurar player/city
            if "player" in save_data and getattr(game, "player", None):
                self.save_manager.restore_player(game.player, save_data["player"])
            if "city" in save_data and getattr(game, "city", None):
                self.save_manager.restore_city(game.city, save_data["city"])

            # Restaurar pedidos "data" crudo si lo usas en SaveManager
            if "orders" in save_data:
                game.orders_data = save_data["orders"]

                # Reconstruir y reinsertar órdenes aceptadas en el inventario
                from game.core.orders import Order
                accepted_ids = set()
                try:
                    orders_blob = save_data.get("orders", {}) or {}
                    for it in orders_blob.get("accepted_orders", []):
                        order = Order(
                            order_id=str(it.get("id")),
                            pickup_pos=tuple(it.get("pickup", (0, 0))),
                            dropoff_pos=tuple(it.get("dropoff", (0, 0))),
                            payment=float(it.get("payout", it.get("payment", 0.0))),
                            time_limit=float(it.get("time_limit", 0.0)),
                            weight=float(it.get("weight", 0.0)),
                            priority=int(it.get("priority", 0)),
                            deadline=str(it.get("deadline", "")),
                            release_time=0,
                        )
                        # Restaurar status exactamente como estaba
                        setattr(order, "status", str(it.get("status", "in_progress")))
                        if getattr(game.player, "add_order_to_inventory", None):
                            game.player.add_order_to_inventory(order)
                        elif getattr(game.player, "inventory", None):
                            # fallback directo al modelo
                            game.player.inventory.add_order(order)
                        accepted_ids.add(order.id)
                except Exception:
                    pass

            # Restaurar estadísticas y timer
            if "game_stats" in save_data:
                game.game_stats = save_data["game_stats"]
                game.total_play_time = float(game.game_stats.get("play_time", 0.0))
                game.time_remaining = float(game.game_stats.get("time_remaining", game.time_limit))

                if getattr(game, "timer", None):
                    game.timer.restore(
                        play_time=game.total_play_time,
                        time_remaining=game.time_remaining
                    )

            # Re-armar pedidos y puertas en el mapa
            if getattr(game, "orders_manager", None):
                # Intentar pasar skip_ids si el OrdersManager lo soporta
                try:
                    game.orders_manager.setup_orders(
                        api_client=game.api_client,
                        files_conf=game.files_conf,
                        app_config=game.app_config,
                        city=game.city,
                        renderer=game.renderer,
                        debug=getattr(game, "debug", False),
                        skip_ids=locals().get("accepted_ids", set()),
                    )
                except TypeError:
                    # Compatibilidad con firmas antiguas sin skip_ids
                    game.orders_manager.setup_orders(
                        api_client=game.api_client,
                        files_conf=game.files_conf,
                        app_config=game.app_config,
                        city=game.city,
                        renderer=game.renderer,
                        debug=getattr(game, "debug", False),
                    )
                # Compatibilidad con game.pending_orders si el juego lo usa
                game.pending_orders = game.orders_manager.pending_orders

            # Estado y música
            game.state_manager.change_state(GameState.PLAYING)
            game.show_notification("Partida cargada")

            game_music = game.app_config.get("audio", {}).get("game_music")
            if game_music and getattr(game, "audio_manager", None):
                game.audio_manager.play_music(game_music, loop=True)

            if getattr(game, "debug", False):
                print(f"Partida cargada - Tiempo restante: {game.time_remaining:.1f}s")
                print(f"Total jugado: {game.total_play_time:.1f}s")

            return True

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            import traceback; traceback.print_exc()
            game.show_notification("Error al cargar partida")
            game.state_manager.change_state(GameState.MAIN_MENU)
            return False