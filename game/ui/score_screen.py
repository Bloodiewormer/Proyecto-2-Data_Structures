import arcade

class ScoreScreen:
    def __init__(self, game, entry, leaderboard):
        self.game = game
        self.entry = entry
        self.leaderboard = leaderboard[:10]  # top 10 visibles

    def handle_key_press(self, symbol: int, modifiers: int) -> bool:
        # Enter o Esc -> volver al menú principal
        if symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.ESCAPE):
            self.game.return_to_main_menu()
            return True
        # R -> Iniciar nueva partida de inmediato
        if symbol == arcade.key.R:
            # Limpia overlay y arranca
            self.game.game_over_active = False
            self.game.score_screen = None
            self.game.start_new_game()
            return True
        return False

    def draw(self):
        w = self.game.width
        h = self.game.height

        # Panel
        pw, ph = int(w * 0.75), int(h * 0.75)
        left = (w - pw) // 2
        right = left + pw
        bottom = (h - ph) // 2
        top = bottom + ph

        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, (0, 0, 0, 180))
        arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, arcade.color.WHITE, 2)

        # Title
        title = "¡Victoria!" if self.entry.get("victory") else "Derrota"
        title_color = arcade.color.GREEN if self.entry.get("victory") else arcade.color.RED
        arcade.draw_text(title, w // 2, top - 48, title_color, 28, anchor_x="center")

        # Leaderboard column (fixed position; do not move)
        lb_x = right - 260
        lb_y_start = top - 100

        # Results block constrained to the left of the leaderboard
        res_right = lb_x - 16  # right edge of results column

        y = top - 100
        line_h = 24
        lbl_color = arcade.color.LIGHT_GRAY
        val_color = arcade.color.WHITE

        def line(lbl: str, val: str):
            nonlocal y
            arcade.draw_text(lbl, left + 24, y, lbl_color, 14)
            arcade.draw_text(val, res_right, y, val_color, 14, anchor_x="right")
            y -= line_h

        earnings = self.entry.get("earnings", 0)
        pay_mult = self.entry.get("pay_mult", 1.0)
        score_base = self.entry.get("score_base", 0)
        bonus_time = self.entry.get("bonus_time", 0)
        penalties = self.entry.get("penalties", 0)
        final_score = self.entry.get("score", 0)
        reputation = self.entry.get("reputation", 0)
        cancels = self.entry.get("orders_cancelled", 0)
        delivered = self.entry.get("deliveries_completed", 0)

        line("Ganancias", f"${earnings:.0f}")
        line("Multiplicador reputación", f"x{pay_mult:.2f} (Rep {reputation})")
        line("Score base", f"{score_base}")
        line("Bonus tiempo", f"+{bonus_time}")
        line("Penalizaciones", f"-{penalties} (Cancelaciones: {cancels})")
        y -= 6
        arcade.draw_lrbt_rectangle_filled(left + 24, res_right, y + 6, y + 8, (255, 255, 255, 60))
        y -= 10
        line("Score final", f"{final_score}")
        line("Entregas completadas", f"{delivered}")

        # Top leaderboard (right, unchanged)
        lb_y = lb_y_start
        arcade.draw_text("Top Puntajes", lb_x, lb_y, arcade.color.YELLOW, 16)
        lb_y -= 28
        for i, e in enumerate(self.leaderboard, start=1):
            txt = f"{i:>2}. {int(e.get('score', 0)):>6}  {'OK' if e.get('victory') else 'KO'}  {e.get('timestamp')[:10]}"
            arcade.draw_text(txt, lb_x, lb_y, arcade.color.LIGHT_GRAY, 12)
            lb_y -= 18

        # Instructions
        info = "Enter: Menu Principal"
        arcade.draw_text(info, w // 2, bottom + 32, arcade.color.LIGHT_GRAY, 12, anchor_x="center")