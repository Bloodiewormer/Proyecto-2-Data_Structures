from game.core.save_manager import SaveManager
from game.core.gamestate import GameState
from game.core.orders import Order


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
            # Recopilar datos del jugador
            player_data = self.save_manager.serialize_player(game.player)

            # Recopilar datos de la ciudad
            city_data = self.save_manager.serialize_city(game.city)

            # Guardar pedidos aceptados
            accepted_orders_payload = [
                order.to_dict() for order in game.player.inventory.orders
            ]

            # Guardar pedidos pendientes
            pending_orders_payload = [
                order.to_dict() for order in game.orders_manager.pending_orders
            ]

            # Guardar pedidos cancelados
            canceled_orders_payload = list(game.orders_manager.canceled_orders)

            # Crear estructura de guardado
            save_data = {
                "player": player_data,
                "city": city_data,
                "orders": {
                    "accepted_orders": accepted_orders_payload,
                    "pending_orders": pending_orders_payload,
                    "canceled_orders": canceled_orders_payload,
                },
                "game_stats": game.game_stats,
            }

            # Guardar datos
            return self.save_manager.save_to_file(save_data)

        except Exception as e:
            print(f"Error al guardar partida: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_game(self, game) -> bool:
        try:
            save_data = self.save_manager.load_game()
            if not save_data:
                game.show_notification("Error al cargar partida")
                return False

            # Inicializa sistemas
            game._initialize_game_systems()

            # Restaurar player y city
            if "player" in save_data and getattr(game, "player", None):
                self.save_manager.restore_player(game.player, save_data["player"])
            if "city" in save_data and getattr(game, "city", None):
                self.save_manager.restore_city(game.city, save_data["city"])

            # Procesar pedidos guardados
            orders_blob = save_data.get("orders", {})
            accepted_orders = orders_blob.get("accepted_orders", [])
            pending_orders = orders_blob.get("pending_orders", [])
            canceled_ids = set(orders_blob.get("canceled_orders", []))

            # Restaurar pedidos aceptados
            game.player.inventory.orders = []
            for it in accepted_orders:
                try:
                    order = Order.from_dict(it)
                    game.player.inventory.add_order(order)
                except KeyError as e:
                    print(f"Pedido inválido en accepted_orders: {it}. Error: {e}")

            # Restaurar pedidos pendientes
            game.orders_manager.pending_orders = []
            for it in pending_orders:
                try:
                    if it["id"] not in canceled_ids:
                        order = Order.from_dict(it)
                        game.orders_manager.pending_orders.append(order)
                except KeyError as e:
                    print(f"Pedido inválido en pending_orders: {it}. Error: {e}")

            # Generar puertas para pedidos activos y pendientes
            for order in game.player.inventory.orders + game.orders_manager.pending_orders:
                try:
                    if order.pickup_pos:
                        game.renderer.generate_door_at(*order.pickup_pos)
                    if order.dropoff_pos:
                        game.renderer.generate_door_at(*order.dropoff_pos)
                except Exception as e:
                    print(f"Error al generar puertas para el pedido: {order.id}. Error: {e}")

            # Cambiar estado del juego a "Jugando"
            game.state_manager.change_state(GameState.PLAYING)
            game.show_notification("Partida cargada")
            return True

        except Exception as e:
            print(f"Error al cargar partida: {e}")
            import traceback
            traceback.print_exc()
            game.show_notification("Error al cargar partida")
            game.state_manager.change_state(GameState.MAIN_MENU)
            return False