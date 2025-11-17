import math
import arcade
from typing import List, Tuple, Optional, Any
from pathlib import Path


class AISpriteRenderer:
    """
    Renderiza sprites de AI considerando la perspectiva del jugador.
    """

    def __init__(self, app_config: dict):
        self.debug = bool(app_config.get("debug", False))

        self.max_render_distance = 15.0
        self.sprite_scale_base = 200.0
        self.min_sprite_size = 30

        self.sprite_pool = self._create_sprite_pool()

    def _create_sprite_pool(self) -> dict:
        """Carga sprites con fallback a 4 direcciones"""
        pool = {}

        directions_8 = ["down", "down_right", "right", "up_right",
                        "up", "up_left", "left", "down_left"]

        fallback_map = {
            "down_right": "right",
            "up_right": "right",
            "up_left": "left",
            "down_left": "left"
        }

        for direction in directions_8:
            path = f"assets/images/ai_cyclist_{direction}.png"

            if Path(path).exists():
                pool[direction] = self._load_sprite_data(path, direction)
            elif direction in fallback_map:
                fallback_dir = fallback_map[direction]
                fallback_path = f"assets/images/ai_cyclist_{fallback_dir}.png"
                if Path(fallback_path).exists():
                    pool[direction] = self._load_sprite_data(fallback_path, direction)
                else:
                    pool[direction] = None
            else:
                pool[direction] = None

        loaded = sum(1 for v in pool.values() if v is not None)
        if self.debug:
            print(f"[AI Sprites] Cargados: {loaded}/8 direcciones")

        return pool

    def _load_sprite_data(self, path: str, direction: str) -> dict:
        """Carga sprite"""
        try:
            sprite_list = arcade.SpriteList()
            sprites = [arcade.Sprite(path) for _ in range(10)]

            if self.debug:
                test = arcade.Sprite(path)
                print(f"[AI Sprites] ✅ {direction}: {test.width}x{test.height}px")

            return {'sprites': sprites, 'list': sprite_list, 'index': 0}
        except Exception as e:
            if self.debug:
                print(f"[AI Sprites] ❌ {direction}: {e}")
            return None

    def render_ai_in_world(self,
                           ai_players: List[Any],
                           player_x: float,
                           player_y: float,
                           player_angle: float,
                           screen_width: int,
                           screen_height: int,
                           fov: float,
                           delta_time: float = 0.016):
        """Renderiza AIs visibles desde perspectiva del jugador"""

        # Reset
        for data in self.sprite_pool.values():
            if data:
                data['list'].clear()
                data['index'] = 0

        if not ai_players:
            return

        # Calcular visibles
        visible = []
        for ai in ai_players:
            dx = ai.x - player_x
            dy = ai.y - player_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > self.max_render_distance or dist < 0.1:
                continue

            angle_to_ai = math.atan2(dy, dx)
            rel_angle = self._normalize_angle(angle_to_ai - player_angle)

            if abs(rel_angle) <= fov / 2 + 0.4:
                visible.append((dist, ai, rel_angle, angle_to_ai))

        # Ordenar por distancia
        visible.sort(key=lambda x: x[0], reverse=True)

        # Configurar sprites
        for dist, ai, rel_angle, angle_to_ai in visible:
            self._setup_sprite(ai, dist, rel_angle, angle_to_ai, player_angle,
                               screen_width, screen_height, fov)

        # Dibujar
        for data in self.sprite_pool.values():
            if data and data['list']:
                data['list'].draw()

    def _setup_sprite(self, ai: Any, distance: float, relative_angle: float,
                      angle_to_ai: float, player_angle: float,
                      screen_width: int, screen_height: int, fov: float):
        """Configura sprite con dirección relativa al jugador"""

        # Calcular qué dirección del sprite mostrar basado en:
        # 1. Dirección de movimiento del AI
        # 2. Desde dónde lo ve el jugador
        direction = self._calculate_sprite_direction_relative_to_player(
            ai, angle_to_ai, player_angle
        )

        data = self.sprite_pool.get(direction)
        if not data:
            return

        idx = data['index']
        if idx >= len(data['sprites']):
            return

        sprite = data['sprites'][idx]
        data['index'] = idx + 1

        # Posición X
        norm_angle = relative_angle / fov
        screen_x = (norm_angle + 0.5) * screen_width

        # Tamaño con perspectiva
        height = self.sprite_scale_base / max(distance, 0.5)
        height = max(self.min_sprite_size, min(int(height), screen_height // 3))

        # Escala
        scale = height / sprite.texture.height if sprite.texture else 1.0

        # Posición Y (horizonte)
        screen_y = screen_height // 2

        # Configurar
        sprite.center_x = screen_x
        sprite.center_y = screen_y
        sprite.scale = scale
        sprite.color = (255, 255, 255)
        sprite.alpha = int(255 * max(0.5, 1.0 - distance / self.max_render_distance))

        data['list'].append(sprite)

        # Debug
        if self.debug:
            colors = {'easy': arcade.color.GREEN, 'medium': arcade.color.ORANGE, 'hard': arcade.color.RED}
            diff = getattr(ai, 'difficulty', 'easy')
            arcade.draw_circle_filled(screen_x, screen_y + height // 2 + 5, 3, colors.get(diff, arcade.color.WHITE))

    def _calculate_sprite_direction_relative_to_player(self, ai: Any,
                                                       angle_to_ai: float,
                                                       player_angle: float) -> str:
        """
        Calcula qué sprite mostrar basado en:
        - La dirección de movimiento del AI
        - Desde qué ángulo el jugador ve al AI

        Esto hace que el sprite se vea natural desde la perspectiva del jugador.
        """

        # Obtener ángulo de movimiento del AI
        ai_movement_angle = getattr(ai, 'angle', 0.0)

        # Calcular la diferencia entre:
        # - Hacia dónde se mueve el AI (ai_movement_angle)
        # - Desde dónde lo ve el jugador (angle_to_ai + 180°)

        # El jugador ve al AI desde angle_to_ai
        # Pero queremos saber en qué dirección relativa se mueve el AI
        view_angle = angle_to_ai + math.pi  # Invertir para perspectiva del jugador

        # Diferencia entre movimiento del AI y vista del jugador
        relative_movement = self._normalize_angle(ai_movement_angle - view_angle)

        # Convertir a grados
        angle_deg = math.degrees(relative_movement)
        while angle_deg < 0:
            angle_deg += 360

        # Mapear a 8 direcciones (o 4 con fallback)
        if 337.5 <= angle_deg or angle_deg < 22.5:
            return "up"  # Alejándose del jugador
        elif 22.5 <= angle_deg < 67.5:
            return "up_right"
        elif 67.5 <= angle_deg < 112.5:
            return "right"  # Moviéndose a la derecha
        elif 112.5 <= angle_deg < 157.5:
            return "down_right"
        elif 157.5 <= angle_deg < 202.5:
            return "down"  # Acercándose al jugador
        elif 202.5 <= angle_deg < 247.5:
            return "down_left"
        elif 247.5 <= angle_deg < 292.5:
            return "left"  # Moviéndose a la izquierda
        else:
            return "up_left"

    def _normalize_angle(self, angle: float) -> float:
        """Normaliza ángulo a -π a π"""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle