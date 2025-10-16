import time
import arcade
from game.core.gamestate import GameState


class InputHandler:
    """
    Maneja la entrada de teclado durante el juego y delega acciones.
    """
    def __init__(self, game):
        self.game = game

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        game = self.game
        state = game.state_manager.current_state

        if state != GameState.PLAYING:
            return False

        # Ventana de pedidos (si está abierta consume teclas)
        if game.orders_window and game.orders_window.is_open:
            if symbol == arcade.key.UP:
                game.orders_window.previous_order()
                return True
            elif symbol == arcade.key.DOWN:
                game.orders_window.next_order()
                return True
            elif symbol == arcade.key.A:
                if not game.orders_window.accept_order():
                    game.show_notification("No hay capacidad para este pedido")
                return True
            elif symbol == arcade.key.C:
                game.orders_window.cancel_order()
                return True

        # Movimiento
        if symbol in (arcade.key.W, arcade.key.UP):
            game._move_forward = True
            return True
        elif symbol in (arcade.key.S, arcade.key.DOWN):
            game._move_backward = True
            return True
        elif symbol in (arcade.key.A, arcade.key.LEFT):
            game._turn_left = True
            return True
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            game._turn_right = True
            return True

        # Acciones
        if symbol == arcade.key.F5:
            game.save_game()
            return True
        elif symbol == arcade.key.Q:
            self._cycle_inventory_order(reverse=bool(modifiers & arcade.key.MOD_SHIFT))
            return True
        elif symbol == arcade.key.TAB:
            self._toggle_inventory_sort()
            return True
        elif symbol == arcade.key.I:
            # AHORA: panel desde el HUD (no el modelo)
            if getattr(game, "hud", None) and hasattr(game.hud, "toggle_inventory"):
                game.hud.toggle_inventory()
                game.show_notification("Inventario abierto" if game.hud.is_inventory_open() else "Inventario cerrado")
            return True
        elif symbol == arcade.key.O:
            if game.orders_window:
                game.orders_window.ensure_initial_position(game.width, game.height)
                if game.orders_window.toggle_open():
                    if game.orders_window.is_open:
                        window_x = (game.width - game.orders_window.panel_width) // 2
                        window_y = (game.height - game.orders_window.panel_height) // 2
                        game.orders_window.set_target_position(window_x, window_y)
                        game.show_notification("Ventana de pedidos abierta")
                    else:
                        game.show_notification("Ventana de pedidos cerrada")
            return True

        # Undo (Z+CTRL o U)
        elif symbol == arcade.key.Z and (modifiers & arcade.key.MOD_CTRL):
            if game.player:
                current_time = time.time()
                if game.player.undo(current_time):

                    undo_stats = game.player.get_undo_stats()
                    remaining = undo_stats['available_undos']
                    game.show_notification(f"paso deshecho ({remaining} disponibles)", 1.5)
                else:
                    game.show_notification("no hay más pasos para deshacer", 1.5)
            return True
        elif symbol == arcade.key.U:
            if game.player:
                current_time = time.time()
                if game.player.undo(current_time):

                    undo_stats = game.player.get_undo_stats()
                    remaining = undo_stats['available_undos']
                    game.show_notification(f" paso deshecho ({remaining} restantes)", 1.5)
                else:
                    if len(game.player.undo_stack) < 2:
                        game.show_notification("no hay estados anteriores", 1.5)
                    else:
                        game.show_notification("espera antes de deshacer de nuevo", 1.0)
            return True

        # Teclas de debug
        if game.debug and game.weather_system:
            if symbol == arcade.key.KEY_1:
                game.weather_system.force_weather_change("clear")
                game.show_notification("Clima forzado: Despejado")
                return True
            elif symbol == arcade.key.KEY_2:
                game.weather_system.force_weather_change("rain")
                game.show_notification("Clima forzado: Lluvia")
                return True
            elif symbol == arcade.key.KEY_3:
                game.weather_system.force_weather_change("storm")
                game.show_notification("Clima forzado: Tormenta")
                return True
            elif symbol == arcade.key.KEY_4:
                game.weather_system.force_weather_change("fog")
                game.show_notification("Clima forzado: Niebla")
                return True
            elif symbol == arcade.key.KEY_5:
                game.weather_system.force_weather_change("wind")
                game.show_notification("Clima forzado: Viento")
                return True
            elif symbol == arcade.key.KEY_6:
                game.weather_system.force_weather_change("heat")
                game.show_notification("Clima forzado: Calor")
                return True
            elif symbol == arcade.key.KEY_7:
                game.weather_system.force_weather_change("cold")
                game.show_notification("Clima forzado: Frío")
                return True

        return False

    def on_key_release(self, symbol: int, modifiers: int) -> bool:
        game = self.game
        if game.state_manager.current_state != GameState.PLAYING:
            return False

        if symbol in (arcade.key.W, arcade.key.UP):
            game._move_forward = False
            return True
        elif symbol in (arcade.key.S, arcade.key.DOWN):
            game._move_backward = False
            return True
        elif symbol in (arcade.key.A, arcade.key.LEFT):
            game._turn_left = False
            return True
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            game._turn_right = False
            return True
        return False

    # ---------- helpers ----------
    def _cycle_inventory_order(self, reverse: bool = False):
        game = self.game
        if not game.player or not getattr(game.player, "inventory", None):
            return
        inv = game.player.inventory
        if not inv.orders:
            game.show_notification("Sin pedidos", 1.0)
            return
        if reverse:
            inv.previous_order()
        else:
            inv.next_order()
        cur = inv.get_current_order()
        if cur:
            game.show_notification(f"Pedido: {cur.id[:8]}  $ {cur.payout:.0f}", 1.2)

    def _toggle_inventory_sort(self):
        game = self.game
        if not game.player or not getattr(game.player, "inventory", None):
            return
        inv = game.player.inventory
        if inv.sort_mode == "priority":
            inv.sort_by_deadline()
        else:
            inv.sort_by_priority()
        game.show_notification(f"Orden: {inv.sort_mode}", 1.2)