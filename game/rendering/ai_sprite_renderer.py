import math
import arcade
from typing import List, Tuple, Optional, Any
from pathlib import Path


class AISpriteRenderer:
    """
    Renderiza sprites de AI Players en el mundo 3D de forma optimizada.
    Corrige orientación, tamaño, colores y rendimiento.
    """

    def __init__(self, app_config: dict):
        self.debug = bool(app_config.get("debug", False))

        # Configuración
        self.max_render_distance = 15.0
        self.sprite_scale_base = 200.0
        self.min_sprite_size = 30

        # Cargar texturas con SpriteList
        self.sprite_pool = self._create_sprite_pool()

        # Cache de direcciones calculadas para evitar cambios bruscos
        self.ai_direction_cache = {}
        self.direction_smoothing = 0.3  # Segundos antes de cambiar dirección
        self.last_direction_update = {}

    def _create_sprite_pool(self) -> dict:
        """Crea pool de sprites con texturas cargadas correctamente"""
        pool = {}

        sprite_paths = {
            "down": "assets/images/ai_cyclist_down.png",
            "up": "assets/images/ai_cyclist_up.png",
            "left": "assets/images/ai_cyclist_left.png",
            "right": "assets/images/ai_cyclist_right.png"
        }

        for direction, path in sprite_paths.items():
            try:
                if Path(path).exists():
                    # Crear sprite list para esta dirección
                    sprite_list = arcade.SpriteList()

                    # Crear pool de sprites (máximo 10 AIs simultáneos)
                    sprites = []
                    for _ in range(10):
                        sprite = arcade.Sprite(path)
                        sprites.append(sprite)

                    pool[direction] = {
                        'sprites': sprites,
                        'list': sprite_list,
                        'index': 0
                    }

                    if self.debug:
                        test_sprite = arcade.Sprite(path)
                        print(f"[AISpriteRenderer] ✅ {direction}: {test_sprite.width}x{test_sprite.height}px")
                else:
                    if self.debug:
                        print(f"[AISpriteRenderer] ❌ No encontrado: {path}")
                    pool[direction] = None

            except Exception as e:
                if self.debug:
                    print(f"[AISpriteRenderer] ❌ Error cargando {direction}: {e}")
                pool[direction] = None

        return pool

    def render_ai_in_world(self,
                           ai_players: List[Any],
                           player_x: float,
                           player_y: float,
                           player_angle: float,
                           screen_width: int,
                           screen_height: int,
                           fov: float,
                           delta_time: float = 0.016):
        """
        Renderiza todos los AI players visibles
        """
        # Limpiar sprite lists y resetear índices
        for direction_data in self.sprite_pool.values():
            if direction_data:
                direction_data['list'].clear()
                direction_data['index'] = 0

        if not ai_players:
            return

        # Calcular AIs visibles con distancias
        visible_ais = []

        for ai in ai_players:
            dx = ai.x - player_x
            dy = ai.y - player_y
            distance = math.sqrt(dx * dx + dy * dy)

            # Filtrar por distancia
            if distance > self.max_render_distance or distance < 0.1:
                continue

            # Calcular ángulo relativo al jugador
            angle_to_ai = math.atan2(dy, dx)
            relative_angle = self._normalize_angle(angle_to_ai - player_angle)

            # Verificar si está dentro del FOV (con margen)
            half_fov = fov / 2.0
            if abs(relative_angle) <= half_fov + 0.4:
                visible_ais.append((distance, ai, relative_angle, angle_to_ai))

        # Ordenar por distancia (más lejano primero para correcta superposición)
        visible_ais.sort(key=lambda x: x[0], reverse=True)



        # Configurar cada AI sprite
        for distance, ai, relative_angle, angle_to_ai in visible_ais:
            self._setup_ai_sprite(
                ai, distance, relative_angle, angle_to_ai,
                screen_width, screen_height, fov, delta_time
            )

        # Dibujar todos los sprite lists
        for direction_data in self.sprite_pool.values():
            if direction_data and direction_data['list']:
                direction_data['list'].draw()

    def _setup_ai_sprite(self, ai: Any, distance: float, relative_angle: float,
                         angle_to_ai: float, screen_width: int, screen_height: int,
                         fov: float, delta_time: float):
        """Configura un sprite para renderizar un AI"""

        # Calcular dirección del sprite basada en el ángulo HACIA el AI desde el jugador
        # Esto hace que el sprite mire correctamente según la perspectiva del jugador
        direction = self._calculate_sprite_direction(ai, angle_to_ai, delta_time)

        # Verificar que tenemos pool para esta dirección
        direction_data = self.sprite_pool.get(direction)
        if not direction_data:
            if self.debug:
                print(f"[AISpriteRenderer] ⚠️ No hay sprites para dirección: {direction}")
            return

        # Obtener sprite del pool
        pool = direction_data['sprites']
        idx = direction_data['index']

        if idx >= len(pool):
            if self.debug:
                print(f"[AISpriteRenderer] ⚠️ Pool agotado para {direction}")
            return

        sprite = pool[idx]
        direction_data['index'] = idx + 1

        # Calcular posición en pantalla (X)
        normalized_angle = relative_angle / fov
        screen_x = (normalized_angle + 0.5) * screen_width

        # Calcular tamaño con perspectiva
        # Aumentar el tamaño base ya que los sprites son 30x30
        perspective_height = self.sprite_scale_base / max(distance, 0.5)
        sprite_height = max(self.min_sprite_size, int(perspective_height))

        # Limitar tamaño máximo
        sprite_height = min(sprite_height, screen_height // 3)

        # Calcular escala
        original_height = sprite.texture.height if sprite.texture else 30
        scale = sprite_height / original_height if original_height > 0 else 1.0

        # Posición Y: El sprite debe estar en el horizonte (centro vertical)
        horizon = screen_height // 2
        screen_y = horizon  # Centrado en el horizonte

        # Configurar sprite
        sprite.center_x = screen_x
        sprite.center_y = screen_y
        sprite.scale = scale

        # NO aplicar tint de color, usar color blanco para mantener colores originales
        sprite.color = (255, 255, 255)

        # Alpha basado en distancia
        distance_factor = max(0.5, 1.0 - (distance / self.max_render_distance))
        sprite.alpha = int(255 * distance_factor)

        # Agregar a la lista de renderizado
        direction_data['list'].append(sprite)

        # Debug: mostrar info del AI
        if self.debug:
            difficulty = getattr(ai, 'difficulty', 'easy')

            # Color de debug según dificultad
            if difficulty == 'easy':
                debug_color = arcade.color.GREEN
            elif difficulty == 'medium':
                debug_color = arcade.color.ORANGE
            else:
                debug_color = arcade.color.RED

            # Texto de debug sobre el sprite
            arcade.draw_text(
                f"{difficulty[0].upper()}\n{distance:.1f}m\n{direction}",
                screen_x, screen_y + sprite_height // 2 + 5,
                debug_color, 9,
                anchor_x="center", bold=True
            )

            # Borde para visualizar hitbox
            half_w = (sprite.width * scale) / 2
            half_h = (sprite.height * scale) / 2
            arcade.draw_lrbt_rectangle_outline(
                screen_x - half_w, screen_x + half_w,
                screen_y - half_h, screen_y + half_h,
                debug_color, 1
            )

    def _calculate_sprite_direction(self, ai: Any, angle_to_ai: float,
                                    delta_time: float) -> str:
        """
        Calcula qué sprite usar basado en el ángulo hacia el AI.
        Incluye suavizado para evitar cambios bruscos.

        El ángulo representa desde dónde el jugador ve al AI:
        - 0° (derecha): AI está a la derecha del jugador
        - 90° (arriba): AI está arriba del jugador
        - 180° (izquierda): AI está a la izquierda
        - 270° (abajo): AI está abajo del jugador
        """

        ai_id = id(ai)
        current_time = getattr(ai, '_last_update_time', 0)

        # Convertir ángulo a grados
        angle_deg = math.degrees(angle_to_ai)

        # Normalizar a 0-360
        while angle_deg < 0:
            angle_deg += 360
        while angle_deg >= 360:
            angle_deg -= 360

        # Determinar dirección del sprite basado en desde dónde se ve el AI
        # Si el AI está arriba del jugador (90°), mostramos sprite "up"
        # Si está abajo (270°), mostramos "down"
        # Si está a la derecha (0°), mostramos "right"
        # Si está a la izquierda (180°), mostramos "left"

        if 45 <= angle_deg < 135:
            new_direction = "up"  # AI está arriba
        elif 135 <= angle_deg < 225:
            new_direction = "left"  # AI está a la izquierda
        elif 225 <= angle_deg < 315:
            new_direction = "down"  # AI está abajo
        else:
            new_direction = "right"  # AI está a la derecha

        # Suavizado: solo cambiar si ha pasado suficiente tiempo
        if ai_id in self.ai_direction_cache:
            cached_direction = self.ai_direction_cache[ai_id]
            last_change = self.last_direction_update.get(ai_id, 0)

            # Si la dirección cambió, verificar tiempo
            if new_direction != cached_direction:
                time_since_change = current_time - last_change

                # Solo cambiar si ha pasado suficiente tiempo
                if time_since_change >= self.direction_smoothing:
                    self.ai_direction_cache[ai_id] = new_direction
                    self.last_direction_update[ai_id] = current_time
                else:
                    # Mantener dirección anterior
                    new_direction = cached_direction
            else:
                # Misma dirección, actualizar tiempo
                self.last_direction_update[ai_id] = current_time
        else:
            # Primera vez que vemos este AI
            self.ai_direction_cache[ai_id] = new_direction
            self.last_direction_update[ai_id] = current_time

        return new_direction

    def _normalize_angle(self, angle: float) -> float:
        """Normaliza ángulo a rango -π a π"""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle