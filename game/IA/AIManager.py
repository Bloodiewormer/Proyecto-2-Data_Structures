# game/ai/ai_manager.py
from typing import List, Optional
from game.entities.ai_player import AIPlayer


class AIManager:
    """
    Gestiona múltiples jugadores IA.
    Se integra con CourierGame para actualizar y renderizar.
    """

    def __init__(self, game):
        self.game = game
        self.ai_players: List[AIPlayer] = []

    def add_ai_player(self, difficulty: str = "easy") -> Optional[AIPlayer]:
        """Agregar nuevo jugador IA"""
        if not self.game.city:
            return None

        # Spawn en posición inicial del mapa
        spawn_x, spawn_y = self.game.city.get_spawn_position()

        # Configuración del jugador (misma que humano)
        player_config = self.game.app_config.get("player", {})

        ai = AIPlayer(spawn_x, spawn_y, player_config, difficulty)
        self.ai_players.append(ai)

        return ai

    def update(self, delta_time: float):
        """Actualizar todos los jugadores IA"""
        for ai in self.ai_players:
            ai.update_ai(delta_time, self.game)

            # Procesar pickups y deliveries
            if hasattr(self.game, 'delivery_system'):
                self.game.delivery_system.process(
                    ai,
                    self.game.pickup_radius,
                    lambda msg: None  # IA no muestra notificaciones
                )

    def remove_ai_player(self, ai: AIPlayer):
        """Remover jugador IA"""
        if ai in self.ai_players:
            self.ai_players.remove(ai)

    def clear_all(self):
        """Remover todos los jugadores IA"""
        self.ai_players.clear()

    def get_stats(self) -> dict:
        """Estadísticas de todos los jugadores IA"""
        return {
            "count": len(self.ai_players),
            "players": [
                {
                    "difficulty": ai.difficulty,
                    "earnings": ai.earnings,
                    "reputation": ai.reputation,
                    "deliveries": ai.deliveries_completed
                }
                for ai in self.ai_players
            ]
        }


# ============ INTEGRACIÓN CON GAME.PY ============
"""
Para integrar en game/game.py:

1. Importar en la parte superior:
   from game.ai.ai_manager import AIManager

2. En __init__ de CourierGame, agregar:
   self.ai_manager = AIManager(self)

3. En start_new_game(), después de inicializar sistemas:
   # Agregar IA según configuración
   ai_config = self.app_config.get("ai", {})
   if ai_config.get("enabled", False):
       difficulty = ai_config.get("difficulty", "easy")
       self.ai_manager.add_ai_player(difficulty)

4. En on_update(), después de actualizar jugador humano:
   if self.ai_manager:
       self.ai_manager.update(delta_time)

5. Para renderizar IA en el minimapa (game/ui/minimap.py), 
   agregar después de dibujar jugador humano:

   # Dibujar jugadores IA
   if hasattr(game, 'ai_manager') and game.ai_manager:
       for ai in game.ai_manager.ai_players:
           ai_x = x + (ai.x + 0.5) * scale_x
           ai_y = y + (ai.y + 0.5) * scale_y
           arcade.draw_circle_filled(ai_x, ai_y, 2, arcade.color.RED)

6. Agregar en config.json:
   "ai": {
       "enabled": true,
       "difficulty": "medium"
   }

7. Para cambiar dificultad en runtime desde menú:
   self.game.ai_manager.clear_all()
   self.game.ai_manager.add_ai_player("hard")
"""