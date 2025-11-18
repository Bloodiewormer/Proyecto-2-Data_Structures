# COURIER QUEST - Proyecto de Estructuras de Datos

![img.png](assets/images/MenuPrincipal.png)

---

## Integrantes del Equipo

- **Brandon Brenes Umaña**
- **David González Córdoba**
- **Felipe Ugalde Vallejos**

**Curso:** EIF-207 Estructuras de Datos  
**Institución:** UNA - Universidad Nacional de Costa Rica
**Período:** II Ciclo 2025

---

## Tabla de Contenidos

1. [Descripcion del Proyecto](#descripcion-del-proyecto)
2. [Instalacion y Requisitos](#instalacion-y-requisitos)
3. [Controles del Juego](#controles-del-juego)
4. [Objetivo del Juego](#objetivo-del-juego)
5. [Mecanicas de Juego](#mecanicas-de-juego)
6. [Sistema de Inteligencia Artificial](#sistema-de-inteligencia-artificial)
7. [Estructuras de Datos Utilizadas](#estructuras-de-datos-utilizadas)
8. [Algoritmos y Complejidad](#algoritmos-y-complejidad)
9. [Formulas Matematicas](#formulas-matematicas)
10. [API y Sistema de Cache](#api-y-sistema-de-cache)
11. [Sistema de Guardado](#sistema-de-guardado)
12. [Limitaciones y Trabajo Futuro](#limitaciones-y-trabajo-futuro)
13. [Creditos y Licencia](#creditos-y-licencia)

---

## Descripción del Proyecto

**Courier Quest** es un videojuego desarrollado en Python utilizando la librería **Arcade 3.3.2**. El jugador controla a un repartidor en bicicleta que debe completar pedidos en una ciudad simulada, gestionando factores como tiempo de entrega, clima dinámico, resistencia física y reputación.

El proyecto implementa diversos conceptos de estructuras de datos lineales y no lineales, algoritmos de ordenamiento y búsqueda, gestión de archivos (JSON y binarios), integración con API REST, sistema de ray-casting para renderizado 3D estilo Wolfenstein, y jugadores controlados por IA con tres niveles de dificultad.

![img.png](assets/images/Gameplay.png)

---

## Instalación y Requisitos

### Requisitos del Sistema

- **Python:** 3.8 o superior
- **Sistema Operativo:** Windows, macOS o Linux
- **Librerías necesarias:**
  - arcade==3.3.2
  - requests

### Instalación
```bash
# Clonar el repositorio
git clone https://github.com/usuario/courier-quest.git
cd courier-quest

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el juego
python main.py
```

### Estructura de Directorios
```
courier-quest/
├── api/                  # Cliente API y sistema de caché
├── assets/              # Recursos multimedia (música, imágenes)
├── data/                # Archivos de respaldo offline
├── game/                # Lógica del juego
│   ├── IA/             # Sistema de inteligencia artificial
│   │   ├── policies/   # Políticas de decisión (Easy, Medium)
│   │   ├── planner/    # Planificadores de rutas (A*)
│   │   └── strategies/ # Estrategias completas por dificultad
│   ├── entities/       # Jugador y AIPlayer
│   └── ...
├── saves/               # Partidas guardadas
├── api_cache/           # Caché de peticiones API
├── config.json          # Configuración del juego
└── main.py             # Punto de entrada
```

---

## Controles del Juego

### Movimiento

- **W** o **Flecha Arriba:** Avanzar hacia adelante
- **S** o **Flecha Abajo:** Retroceder
- **A** o **Flecha Izquierda:** Girar a la izquierda
- **D** o **Flecha Derecha:** Girar a la derecha

### Gestión de Pedidos

- **O:** Abrir/cerrar ventana de pedidos disponibles
- **Flecha Arriba/Abajo:** Navegar entre pedidos (en ventana de pedidos)
- **A:** Aceptar pedido seleccionado (en ventana de pedidos)
- **C:** Cancelar pedido seleccionado (en ventana de pedidos)

### Inventario

- **I:** Abrir/cerrar inventario del jugador
- **Q:** Seleccionar siguiente pedido en inventario
- **Shift + Q:** Seleccionar pedido anterior en inventario
- **Tab:** Cambiar orden de inventario (prioridad/fecha límite)

### Sistema de Deshacer

- **U:** Deshacer último movimiento/acción
- **Ctrl + Z:** Deshacer último movimiento/acción (alternativo)

### Debug (Solo con debug=true en config.json)

- **F1:** Toggle visualización de paths de IA
- **F2:** Toggle visualización de targets de IA
- **F3:** Toggle visualización de stamina de IA
- **F4:** Pausar/reanudar IA (jugador sigue activo)
- **1-7:** Forzar condiciones climáticas

### Sistema

- **ESC:** Pausar juego / Volver al menú anterior
- **F5:** Guardar partida rápida

---

## Objetivo del Juego

### Condiciones de Victoria

- Alcanzar **$550 en ganancias** (configurable) antes de que se agote el tiempo límite (6 minutos de juego real por defecto).
- Evitar que la IA alcance la meta antes que tú.

### Condiciones de Derrota

- **Reputación menor a 20:** El jugador pierde credibilidad y no puede continuar.
- **Tiempo agotado:** No se alcanzó la meta de ingresos en el tiempo límite.
- La IA alcanza la meta de ganancias antes que el jugador.

![img.png](assets/images/Victoria.png)

---

## Mecánicas de Juego

### Sistema de Pedidos

Los pedidos se liberan de forma escalonada cada 40 segundos (configurable). Cada pedido tiene:

- **ID único:** Identificador del pedido
- **Punto de recogida (pickup):** Coordenadas donde recoger el paquete (Se muestra en el minimap)
- **Punto de entrega (dropoff):** Coordenadas donde entregar el paquete (Se muestra en el minimap)
- **Pago:** Cantidad de dinero que se recibe al completar
- **Peso:** Afecta la velocidad del jugador
- **Prioridad:** Nivel de importancia (0 = normal, n = alta prioridad)
- **Tiempo límite:** Deadline para completar la entrega

![img.png](assets/images/Pedidos.png)

### Sistema de Resistencia (Stamina)

La resistencia del jugador varía entre **0-100**:

- **Normal (>30):** Velocidad completa
- **Cansado (10-30):** Velocidad reducida al 80%
- **Exhausto (≤0):** No puede moverse hasta recuperarse al 30%

**Consumo de resistencia:**
- Movimiento base: -0.5 por celda
- Peso extra (>3kg): -0.2 adicional por celda por cada unidad sobre 3kg
- Clima adverso:
  - Lluvia/Viento: -0.1 por celda
  - Tormenta: -0.3 por celda
  - Calor: -0.2 por celda

**Recuperación:**
- Parado: +5 puntos/segundo
- En punto de descanso: +10 puntos/segundo


### Sistema de Reputación

La reputación comienza en **70/100** y varía según las acciones del jugador:

**Cambios positivos:**
- Entrega a tiempo: +3
- Entrega temprana (≥20% antes del límite): +5
- Racha de 3 entregas sin penalización: +2 (bonus único)

**Cambios negativos:**
- Tarde ≤30s: -2
- Tarde 31-120s: -5
- Tarde >120s: -10
- Cancelar pedido aceptado: -4
- Perder/expirar paquete: -6

**Efectos de reputación:**
- **Reputación ≥90:** +5% en todos los pagos
- **Reputación <20:** Derrota inmediata


### Sistema Climático (Cadena de Markov)

El clima cambia automáticamente cada 45-60 segundos usando una matriz de transición de Markov de 9 estados:

**Condiciones disponibles:**
- **clear:** Despejado (velocidad ×1.00)
- **clouds:** Nublado (velocidad ×0.98)
- **rain_light:** Llovizna (velocidad ×0.90)
- **rain:** Lluvia (velocidad ×0.85)
- **storm:** Tormenta (velocidad ×0.75)
- **fog:** Niebla (velocidad ×0.88)
- **wind:** Viento (velocidad ×0.92)
- **heat:** Calor (velocidad ×0.90)
- **cold:** Frío (velocidad ×0.92)

Las transiciones entre climas son progresivas (3-5 segundos) para que los cambios se sientan naturales mediante interpolación lineal.

![img.png](assets/images/Climas.png)

### Sistema de Deshacer (Undo)

El jugador puede deshacer hasta **50 pasos** anteriores:

- El sistema guarda estados cada 0.5 segundos
- Cooldown de 0.3 segundos entre undos para evitar spam
- Se guarda: posición, ángulo, stats, inventario, contadores

---

## Sistema de Inteligencia Artificial

### Descripción General

El juego incluye un sistema completo de jugadores controlados por IA que compiten contra el jugador humano por los mismos pedidos. La IA tiene acceso a la misma información del mapa, clima y pedidos, y debe gestionar su propia stamina, reputación e inventario.

### Niveles de Dificultad

#### Fácil (Easy) - Random Choice Policy

**Comportamiento:**
- Toma decisiones probabilísticas con 35% de sesgo hacia el objetivo
- Elige direcciones aleatorias válidas evitando retroceder
- 70% de acierto cuando intenta moverse hacia el objetivo
- Gestión imprudente de stamina (ignora niveles bajos ocasionalmente)

**Implementación:**
- **Estructura:** Cola simple para gestión de movimientos válidos
- **Algoritmo:** Random Walk con sesgo direccional
- **Complejidad:** O(1) por decisión

Archivo: `game/IA/policies/random_choice.py`
```python
def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
    # Obtener movimientos válidos (elimina retroceso)
    candidates = self._get_valid_moves(ai)
    
    # 35% de intentar ir hacia target
    if ai.current_target and random.random() < 0.35:
        # 70% de acierto
        if random.random() < 0.7:
            return self._best_move_to_target(candidates, ai.current_target)
    
    # Movimiento aleatorio
    return random.choice(candidates)
```

#### **Media (Medium) - Greedy Policy con BFS**

**Comportamiento:**
- Evalúa movimientos usando función heurística (distancia + clima + peso)
- Usa BFS (Breadth-First Search) como respaldo cuando queda atascada
- Considera el clima y peso del inventario en decisiones
- Gestión conservadora de stamina

**Implementación:**
- **Estructura:** Cola FIFO para BFS, lista para evaluación greedy
- **Algoritmo:** Greedy best-first con pathfinding BFS
- **Complejidad:**
  - Greedy: O(n) donde n = vecinos válidos (4 máximo)
  - BFS: O(V + E) donde V = celdas del mapa, E = conexiones

Archivo: `game/IA/policies/greedy.py`
```python
def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
    # Detectar atascamiento (3+ frames sin movimiento)
    if self._detect_stuck():
        # Usar BFS para encontrar ruta alternativa
        self._bfs_path = self._find_bfs_path(current_pos, target)
    
    # Seguir path BFS si existe
    if self._bfs_path:
        return self._follow_path()
    
    # Evaluación greedy normal
    best_move = None
    best_score = float('inf')
    
    for dx, dy in cardinal_directions:
        score = (
            manhattan_distance(new_pos, target) +
            climate_penalty * 0.3 +
            weight_penalty * 0.2
        )
        if score < best_score:
            best_score = score
            best_move = (dx, dy)
    
    return best_move
```

#### Difícil (Hard) - A* Strategy

Comportamiento:
- Usa A* para calcular rutas óptimas considerando costos de superficie
- Planifica secuencias de múltiples pedidos para maximizar ganancias
- Replanifica dinámicamente cuando el clima empeora
- Gestión inteligente de stamina con descansos estratégicos

Implementación:
- Estructura: Cola de prioridad (heap) para A*, grafo ponderado del mapa
- Algoritmo: A* con heurística Manhattan
- Complejidad: O((V + E) log V) donde V = nodos, E = aristas

Archivos: 
- `game/IA/planner/astar.py`
- `game/IA/strategies/strategies.py` (HardStrategy)
```python
def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
    """A* pathfinding con validación de esquinas"""
    open_heap = []
    heapq.heappush(open_heap, (0.0, start))
    came_from = {}
    g_score = {start: 0.0}
    closed_set = set()
    
    while open_heap:
        _, current = heapq.heappop(open_heap)
        
        if current in closed_set:
            continue
        closed_set.add(current)
        
        if current == goal:
            break
        
        for neighbor in self._get_walkable_neighbors(current):
            # Costo: distancia + peso de superficie
            tentative_g = (g_score[current] + 
                          self._step_cost(neighbor[0], neighbor[1]))
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                f_score = tentative_g + self.heuristic(neighbor, goal)
                heapq.heappush(open_heap, (f_score, neighbor))
                came_from[neighbor] = current
    
    # Reconstruir path
    self._path = self._reconstruct_path(came_from, start, goal)
```

**Evaluación de secuencias de pedidos:**
```python
def _evaluate_sequence(self, ai: "AIPlayer", orders, game) -> float:
    total_payout = sum(order.payout for order in orders)
    total_distance = 0.0
    
    current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))
    
    for order in orders:
        # Calcular ruta con A*
        self.planner.replan(current_pos, order.pickup_pos)
        path_len_pickup = len(self.planner._path)
        
        self.planner.replan(order.pickup_pos, order.dropoff_pos)
        path_len_delivery = len(self.planner._path)
        
        total_distance += path_len_pickup + path_len_delivery
        current_pos = order.dropoff_pos
    
    predicted_stamina_cost = self._predict_stamina_cost(ai, total_distance)
    
    # Calcular valor final
    value = (
        total_payout +
        sum(o.priority * 50 for o in orders) -  # Bonus por prioridad
        (total_distance * 0.5) -                 # Penalización por distancia
        (predicted_stamina_cost * 2)             # Penalización por stamina
    )
    
    return value
```

### Arquitectura de la IA

```
AIPlayer (hereda de Player)
    ├── Strategy (decide qué hacer)
    │   ├── EasyStrategy (random)
    │   ├── MediumStrategy (greedy + BFS)
    │   └── HardStrategy (A* + planificación)
    │
    ├── Policy (decide cómo moverse)
    │   ├── RandomChoicePolicy
    │   └── GreedyPolicy
    │
    └── Planner (calcula rutas)
        └── AStarPlanner
```

### Sistema Anti-Atascamiento

Todas las dificultades incluyen detección y recuperación de atascamiento:
```python
def _detect_stuck(self) -> bool:
    """Detecta si la IA no se ha movido en los últimos 10 frames"""
    if len(self.position_history) < 10:
        return False
    
    total_distance = sum(
        math.sqrt((curr[0] - prev[0])**2 + (curr[1] - prev[1])**2)
        for prev, curr in zip(self.position_history[:-1], 
                             self.position_history[1:])
    )
    
    return total_distance < 0.2  # Umbral de movimiento mínimo

def _unstuck_maneuver(self, city) -> Tuple[float, float]:
    """Maniobra de escape: retroceder, perpendicular o teleport"""
    # 1. Intentar retroceder
    back_angle = self.angle + math.pi
    if self._is_valid_move(back_angle):
        return (math.cos(back_angle), math.sin(back_angle))
    
    # 2. Intentar perpendicular (90° a cada lado)
    for perp_angle in [self.angle + π/2, self.angle - π/2]:
        if self._is_valid_move(perp_angle):
            return (math.cos(perp_angle), math.sin(perp_angle))
    
    # 3. Teleport a última posición válida
    self.x, self.y = self.last_valid_position
    return (0.0, 0.0)
```

### Gestión de Stamina por IA

La IA maneja stamina de forma diferente según dificultad:

- **Easy:** Imprudente (20-60% awareness, descansa en 10-30)
- **Medium:** Conservadora (descansa en 0, objetivo 40)
- **Hard:** Predictiva (calcula costo de tarea, descansa estratégicamente)
```python
# Hard Strategy - Predicción de costo de stamina
def _predict_stamina_cost(self, ai: "AIPlayer", distance: float) -> float:
    base_cost = distance * 1.2
    
    # Penalización por peso
    if ai.total_weight > 3:
        base_cost *= (1.0 + (ai.total_weight - 3) * 0.1)
    
    # Penalización por clima
    if self.world.weather_system:
        speed_mult = self.world.weather_system.get_speed_multiplier()
        if speed_mult < 1.0:
            base_cost *= (1.5 - speed_mult * 0.5)
    
    return base_cost
```

### Renderizado de IA

Los jugadores IA se renderizan en el mundo 3D usando sprites direccionales:

**Archivo:** `game/rendering/ai_sprite_renderer.py`

- 8 direcciones de sprites (up, down, left, right, diagonales)
- Escala basada en distancia (perspectiva)
- Fade con distancia
- Fallback a 4 direcciones si faltan assets

```python
def render_ai_in_world(self, ai_players, player_x, player_y, 
                       player_angle, screen_width, screen_height, fov):
    """Renderiza AIs visibles desde perspectiva del jugador"""
    for ai in ai_players:
        # Calcular distancia y ángulo relativo
        dx = ai.x - player_x
        dy = ai.y - player_y
        dist = math.sqrt(dx*dx + dy*dy)
        
        # Culling por distancia
        if dist > self.max_render_distance:
            continue
        
        # Culling por FOV
        angle_to_ai = math.atan2(dy, dx)
        rel_angle = normalize_angle(angle_to_ai - player_angle)
        if abs(rel_angle) > fov / 2 + 0.4:
            continue
        
        # Calcular dirección del sprite relativa al jugador
        direction = self._calculate_sprite_direction(ai, angle_to_ai, player_angle)

        # Renderizar sprite con perspectiva
        self._render_sprite(ai, direction, dist, rel_angle, screen_width, screen_height)
```

### Configuración de IA

En `config.json`:
```json
"ai": {
    "enabled": true,
    "difficulty": "medium",
    "sprite_scale": 100,
    "max_render_distance": 15,
    "order_accept_cooldown": {
        "easy": 15.0,
        "medium": 7.0,
        "hard": 2.5
    }
}
```

### Teclas de Debug para IA

Con `debug: true` en config.json:

- **F1:** Visualizar paths (líneas cyan en minimap)
- **F2:** Visualizar targets (círculos rojos + líneas)
- **F3:** Mostrar stamina sobre cada IA
- **F4:** Pausar/reanudar solo IA (jugador sigue activo)

[[ImagenDebugIA]]

---

## Estructuras de Datos Utilizadas

### 1. Cola de Prioridad (Heap)

**Ubicación:** `game/game.py` - Sistema de gestión de pedidos  
**Propósito:** Gestión de pedidos con liberación escalonada basada en tiempo de juego

```python
self._orders_queue: list[tuple[float, Order]] = []  # (unlock_time_sec, Order)
```

**Operaciones:**
- Inserción: O(n log n)
- Extracción del mínimo: O(1)

**Justificación:** Permite liberar pedidos automáticamente según tiempo transcurrido sin mantener lista completa ordenada continuamente.

### 2. Cola (Queue - Lista)

**Ubicación:** `game/inventory.py` - Sistema de inventario del jugador  
**Propósito:** Gestión de pedidos activos con capacidad limitada por peso

```python
self.orders: List[Order] = []
```

**Operaciones:**
- Enqueue (agregar): O(1) + ordenamiento O(n log n)
- Dequeue (remover): O(n)

**Justificación:** Inventario FIFO con priorización dinámica mediante ordenamiento secundario por prioridad o deadline.

### 3. Conjunto (Set)

**Ubicación:** `game/renderer.py` - Sistema de renderizado  
**Propósito:** Registro de posiciones de puertas en edificios

```python
self.door_positions = set()
```

**Operaciones:**
- Inserción: O(1)
- Búsqueda: O(1)

**Justificación:** Verificación rápida de puertas durante ray casting, crítico para rendimiento a 60 FPS.

### 4. Diccionarios (Hash Maps)

#### 4.1 Caché de Minimap
**Ubicación:** `game/renderer.py`  
**Propósito:** Evitar reconstrucción del minimap en cada frame

```python
self._minimap_cache_key = None
self._minimap_shapes = None
```

**Complejidad:** O(1) para búsqueda y acceso

#### 4.2 Matriz de Transición de Markov
**Ubicación:** `game/weather.py`  
**Propósito:** Probabilidades de cambio entre 9 condiciones climáticas

```python
self.transition_matrix = {
    WeatherCondition.CLEAR: {
        WeatherCondition.CLEAR: 0.4,
        WeatherCondition.CLOUDS: 0.3,
        # ...
    }
}
```

**Complejidad:** O(1) para acceso a probabilidades

#### 4.3 Caché de Música
**Ubicación:** `game/audio.py`  
**Propósito:** Almacenar archivos de audio cargados

```python
self.music_cache = {}
```

**Complejidad:** O(1) para búsqueda y recuperación

#### 4.4 Leyenda de Tiles
**Ubicación:** `game/city.py`  
**Propósito:** Mapear tipos de casillas a propiedades de superficie

```python
self.legend = {
    "C": {"name": "calle", "surface_weight": 1.00},
    "B": {"name": "edificio", "blocked": True},
    "P": {"name": "parque", "surface_weight": 0.95}
}
```

**Complejidad:** O(1) para consultas de propiedades

### 5. Listas

#### 5.1 Frame Times
**Ubicación:** `game/game.py` - Métricas de rendimiento  
**Propósito:** Registro de tiempos de frame para cálculo de FPS

```python
self.frame_times = []  # Últimos 240 frames
```

**Operaciones:** Append O(1), pop(0) O(n)

#### 5.2 Tiles del Mapa
**Ubicación:** `game/city.py`  
**Propósito:** Matriz 2D representando el mapa

```python
self.tiles: List[List[str]] = []
```

**Acceso:** O(1) usando índices [y][x]

#### 5.3 Direcciones de Rayos (Ray Casting)
**Ubicación:** `game/renderer.py`  
**Propósito:** Cache de vectores de dirección para ray casting

```python
self._ray_dirs: List[Tuple[float, float]] = []
```

**Complejidad:** O(n) inicialización, O(1) acceso

#### 5.4 Pila de Undo (Deque)
**Ubicación:** `game/player.py`  
**Propósito:** Almacenar estados anteriores del jugador

```python
from collections import deque
self.undo_stack: deque = deque(maxlen=self.max_undo_steps)
```

**Operaciones:**
- Append: O(1)
- Pop: O(1)

**Justificación:** Deque es más eficiente que lista para operaciones en ambos extremos.

### 6. Grafo Ponderado (Implícito)

**Ubicación:** `game/IA/planner/astar.py` - A* Planner  
**Propósito:** Representación implícita del mapa como grafo para pathfinding

```python
# El grafo no se almacena explícitamente, se construye on-the-fly
# Nodos: celdas caminables del mapa (C, P)
# Aristas: conexiones entre celdas adyacentes
# Pesos: surface_weight de la celda destino
```

**Operaciones:**
- Generar vecinos: O(1) - máximo 4 vecinos cardinales
- Calcular costo: O(1) - lookup en legend del mapa

**Justificación:** Representación implícita ahorra memoria (no almacena todas las conexiones) y permite actualización dinámica cuando cambia el clima (modifica pesos sin reconstruir grafo).

### 7. Cola de Prioridad para A*

**Ubicación:** `game/IA/planner/astar.py`  
**Propósito:** Open set para algoritmo A*

```python
import heapq
open_heap = []
heapq.heappush(open_heap, (f_score, node))
```

**Operaciones:**
- Push: O(log n)
- Pop mínimo: O(log n)

**Justificación:** Heap binario permite extraer eficientemente el nodo con menor f_score en cada iteración de A*.

### 8. Historial de Posiciones (Lista Circular)

**Ubicación:** `game/entities/ai_player.py`  
**Propósito:** Detectar atascamiento de IA

```python
self.position_history = []
self.max_position_history = 10
```

**Operaciones:**
- Append + pop(0): O(n) pero n es pequeño (10)

**Justificación:** Mantiene ventana deslizante de posiciones recientes para calcular distancia total movida.

---

## Algoritmos y Complejidad

### 1. Ray Casting DDA (Digital Differential Analyzer)

**Archivo:** `game/renderer.py`  
**Complejidad:** O(w + h) donde w = ancho del mapa, h = alto del mapa  
**Contexto:** Detección de paredes para renderizado 3D

El algoritmo DDA recorre el grid del mapa de forma eficiente hasta encontrar una pared, evitando comprobar cada celda del mapa.

### 2. Renderizado de Paredes

**Complejidad:** O(n) donde n = número de rayos  
**Contexto:** Proyección de columnas de pared en pantalla

Cada rayo genera una columna vertical en pantalla, con merge horizontal de slices contiguos para reducir draw calls.

### 3. Renderizado de Piso

**Complejidad:** O(n × m) donde n = rayos, m = filas de muestreo  
**Contexto:** Texturizado del suelo con sampling espaciado

Optimización: solo se procesan filas cada `floor_row_step` píxeles para reducir cálculos.

### 4. Ordenamiento de Inventario

**Complejidad:** O(k log k) donde k = número de pedidos  
**Contexto:** Ordenar pedidos por prioridad o deadline

```python
self.orders.sort(key=lambda x: x.priority, reverse=True)  # Por prioridad
self.orders.sort(key=lambda x: x.deadline)  # Por deadline
```

### 5. Liberación Escalonada de Pedidos

**Complejidad:** O(p) donde p = pedidos pendientes de liberar  
**Contexto:** Desbloquear pedidos según tiempo transcurrido

```python
while self._orders_queue and self._orders_queue[0][0] <= elapsed:
    _, order = self._orders_queue.pop(0)
    self.pending_orders.append(order)
```

### 6. Búsqueda de Edificio Cercano

**Complejidad:** O(w × h) donde w×h = tamaño del mapa  
**Contexto:** Encontrar edificio más cercano para posicionar puertas

Búsqueda exhaustiva con optimización de distancia Manhattan para early termination.

### 7. Selección Markov de Clima

**Complejidad:** O(c) donde c = 9 condiciones climáticas  
**Contexto:** Elegir siguiente estado climático usando probabilidades

```python
def _select_next_condition(self) -> str:
    probabilities = self.transition_matrix.get(self.current_condition, {})
    # Acumulación de probabilidades y selección aleatoria
```

8. A* PathfindingArchivo: game/IA/planner/astar.py
Complejidad: O((V + E) log V) donde V = nodos visitados, E = aristas exploradas
Contexto: Calcular ruta óptima para IA difícil

```python
def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
    open_heap = []
    heapq.heappush(open_heap, (0.0, start))
    came_from = {}
    g_score = {start: 0.0}
    closed_set = set()
    
    while open_heap:
        _, current = heapq.heappop(open_heap)  # O(log V)
        
        if current in closed_set:
            continue
        closed_set.add(current)
        
        if current == goal:
            break
        
        # Explorar vecinos (máximo 4)
        for neighbor in self._get_walkable_neighbors(current):  # O(1)
            tentative_g = g_score[current] + self._step_cost(neighbor)
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                f_score = tentative_g + self.heuristic(neighbor, goal)  # O(1)
                heapq.heappush(open_heap, (f_score, neighbor))  # O(log V)
                came_from[neighbor] = current
```

Optimizaciones implementadas:

Conjunto cerrado para evitar revisar nodos ya explorados
Heurística Manhattan (admisible y consistente)
Early termination al alcanzar la meta
Límite de iteraciones para evitar loops infinitos


9.  BFS (Breadth-First Search)Archivo: game/IA/policies/greedy.py
**Complejidad**: O(V + E) donde V = celdas del mapa, E = conexiones entre celdas
**Contexto**: Pathfinding de respaldo para IA media cuando queda atascada
```python
def _find_bfs_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> list:
    from collections import deque
    
    queue = deque([(start, [start])])
    visited = {start}
    max_iterations = 500
    iterations = 0
    
    while queue and iterations < max_iterations:
        iterations += 1
        current, path = queue.popleft()  # O(1)
        
        if current == goal:
            return path[1:]
        
        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            neighbor = (current[0] + dx, current[1] + dy)
            
            if neighbor in visited:
                continue
            
            if not self._is_walkable(neighbor):
                continue
            
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    
    return []
```

Características:

Encuentra la ruta más corta en número de pasos (no considera pesos)
Más simple que A* pero menos eficiente
Usado como fallback cuando greedy falla

10. Evaluación Greedy con Heurística
Archivo: game/IA/policies/greedy.py
Complejidad: O(n) donde n = vecinos válidos (máximo 4)
Contexto: Decisión de movimiento para IA media


```python
def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
    candidates = []
    
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:  # O(4) = O(1)
        nx, ny = ai.x + dx, ai.y + dy
        
        if not self._is_walkable(nx, ny):
            continue
        
        # Calcular score heurístico
        score = (
            self._manhattan_distance((nx, ny), target) +
            self.climate_weight * self._climate_risk() +
            self._weight_penalty(ai)
        )
        
        candidates.append((score, dx, dy))
    
    # Ordenar y seleccionar mejor
    candidates.sort(key=lambda x: x[0])  # O(n log n) pero n ≤ 4
    return candidates[0][1:] if candidates else (0, 0)
```

11. Evaluación de Secuencias de Pedidos
Archivo: game/IA/strategies/strategies.py (HardStrategy)
Complejidad: O(k² × P) donde k = pedidos candidatos (≤8), P = complejidad de A*
Contexto: IA difícil planifica múltiples pedidos a la vez
```python
def _plan_order_sequence(self, ai: "AIPlayer", game):
    candidates = sorted(game.pending_orders[:8], 
                       key=lambda o: manhattan(ai.pos, o.pickup_pos))[:5]
    
    best_sequence = []
    best_value = float("-inf")
    
    # Evaluar secuencias de 1 pedido
    for o1 in candidates:  # O(k)
        if not self._is_order_viable(ai, o1):
            continue
        value = self._evaluate_sequence(ai, [o1], game)  # O(P) por A*
        if value > best_value:
            best_sequence = [o1.id]
            best_value = value
    
    # Evaluar secuencias de 2 pedidos
    for i, o1 in enumerate(candidates):  # O(k)
        for o2 in candidates[i+1:]:  # O(k)
            if not self._can_carry_both(ai, o1, o2):
                continue
            
            value = self._evaluate_sequence(ai, [o1, o2], game)  # O(P)
            if value > best_value:
                best_sequence = [o1.id, o2.id]
                best_value = value
    
    self.planned_sequence = best_sequence
```

Optimizaciones:

Limita candidatos a 5 más cercanos
Solo evalúa combinaciones de hasta 2 pedidos
Cache de rutas calculadas por A*

12. Detección de Atascamiento
Archivo: game/entities/ai_player.py
Complejidad: O(h) donde h = tamaño del historial (10)
Contexto: Prevenir que IA quede bloqueada

```python
def _detect_stuck(self) -> bool:
    if len(self.position_history) < self.max_position_history:
        return False
    
    # Calcular distancia total recorrida
    total_distance = 0.0
    for i in range(1, len(self.position_history)):  # O(10) = O(1)
        prev = self.position_history[i - 1]
        curr = self.position_history[i]
        dx = curr[0] - prev[0]
        dy = curr[1] - prev[1]
        total_distance += math.sqrt(dx * dx + dy * dy)
    
    # Umbral: menos de 0.2 unidades en 10 frames = atascado
    return total_distance < 0.2
```

13. Predicción de Costo de Stamina
Archivo: game/IA/strategies/strategies.py (HardStrategy)
Complejidad: O(1)
Contexto: IA difícil predice si puede completar un pedido

---

## Fórmulas Matemáticas

### 1. Velocidad Efectiva del Jugador

**Archivo:** `game/player.py` - Método `_calculate_effective_speed()`

![Formula Velocidad](https://latex.codecogs.com/svg.image?v_{eff}=v_0\times%20M_{clima}\times%20M_{peso}\times%20M_{rep}\times%20M_{resist}\times%20w_{superficie})

Donde:
- `v₀`: Velocidad base del jugador (3.0 celdas/seg)
- `M_clima`: Multiplicador climático (0.75 - 1.00)
- `M_peso`: Multiplicador por peso del inventario
- `M_rep`: Multiplicador por reputación (1.03 si rep ≥90)
- `M_resist`: Multiplicador por estado de resistencia
- `w_superficie`: Peso de la superficie (parque = 0.95, calle = 1.0)

### 2. Multiplicador de Peso

**Archivo:** `game/player.py`

![Formula Peso](https://latex.codecogs.com/svg.image?M_{peso}=\max(0.8,1-0.03\times%20peso_{total}))

Aplicado cuando `peso_total > 3 kg`

### 3. DDA Ray Casting - Delta Distance

**Archivo:** `game/renderer.py` - Método `_cast_wall_dda()`

![Formula Delta X](https://latex.codecogs.com/svg.image?\Delta%20d_x=\begin{cases}+\infty&\text{si%20}dir_x=0\\\left|\frac{1}{dir_x}\right|&\text{en%20otro%20caso}\end{cases})

![Formula Delta Y](https://latex.codecogs.com/svg.image?\Delta%20d_y=\begin{cases}+\infty&\text{si%20}dir_y=0\\\left|\frac{1}{dir_y}\right|&\text{en%20otro%20caso}\end{cases})

### 4. DDA Ray Casting - Side Distance (Inicialización)

**Archivo:** `game/renderer.py`

![Formula Side X](https://latex.codecogs.com/svg.image?s_x=\begin{cases}(pos_x-map_x)\times\Delta%20d_x&\text{si%20}dir_x<0\\(map_x+1-pos_x)\times\Delta%20d_x&\text{si%20}dir_x\geq%200\end{cases})

![Formula Side Y](https://latex.codecogs.com/svg.image?s_y=\begin{cases}(pos_y-map_y)\times\Delta%20d_y&\text{si%20}dir_y<0\\(map_y+1-pos_y)\times\Delta%20d_y&\text{si%20}dir_y\geq%200\end{cases})

### 5. Distancia Perpendicular a Pared

**Archivo:** `game/renderer.py`

![Formula Dist Perp](https://latex.codecogs.com/svg.image?d_{perp}=\begin{cases}\left|\frac{map_x-pos_x+(1-step_x)/2}{dir_x}\right|&\text{si%20side}=0\\\left|\frac{map_y-pos_y+(1-step_y)/2}{dir_y}\right|&\text{si%20side}=1\end{cases})

### 6. Altura de Línea de Pared

**Archivo:** `game/renderer.py`

![Formula Altura Pared](https://latex.codecogs.com/svg.image?h_{linea}=\left\lfloor\frac{altura_{pantalla}}{\max(0.0001,d_{perp})}\right\rfloor)

### 7. Límites de Dibujo de Pared

**Archivo:** `game/renderer.py`

![Formula Limites](https://latex.codecogs.com/svg.image?%5Cbegin%7Barray%7D%7Bl%7D%0Atop%20%3D%20%5Cmin(altura_%7Bpantalla%7D%2C%20horizonte%20%2B%20%5Cfrac%7Bh_%7Blinea%7D%7D%7B2%7D)%20%5C%5C%0Abottom%20%3D%20%5Cmax(0%2C%20horizonte%20-%20%5Cfrac%7Bh_%7Blinea%7D%7D%7B2%7D)%0A%5Cend%7Barray%7D)

### 8. Distancia de Fila de Piso

**Archivo:** `game/renderer.py` - Método `_prepare_floor_rows()`

![Formula Dist Piso](https://latex.codecogs.com/svg.image?d_{fila}=\frac{posZ}{horizonte-(y+0.5)})

Donde:
- `posZ = altura_pantalla × 0.5`
- `y`: coordenada y de la fila en pantalla

### 9. Coordenadas Mundiales de Piso

**Archivo:** `game/renderer.py` - Método `_render_floor()`

![Formula Coord Piso](https://latex.codecogs.com/svg.image?%5Cbegin%7Barray%7D%7Bl%7D%0Aw_x%20%3D%20pos_x%20%2B%20dir_x%20%5Ctimes%20d_%7Bfila%7D%20%5C%5C%0Aw_y%20%3D%20pos_y%20%2B%20dir_y%20%5Ctimes%20d_%7Bfila%7D%0A%5Cend%7Barray%7D)

### 10. Score Base

**Archivo:** `game/score.py` - Método `calculate_score()`

![Formula Score Base](https://latex.codecogs.com/svg.image?score_{base}=\left\lfloor%20ganancias\times%20M_{pago}\right\rfloor)

### 11. Multiplicador de Pago por Reputación

**Archivo:** `game/score.py`

![Formula Mult Pago](https://latex.codecogs.com/svg.image?M_{pago}=\begin{cases}1.10&\text{si%20rep}\geq%2090\\1.05&\text{si%20rep}\geq%2080\\1.00&\text{en%20otro%20caso}\end{cases})

### 12. Bonus por Tiempo

**Archivo:** `game/score.py`

![Formula Bonus](https://latex.codecogs.com/svg.image?bonus_{tiempo}=\begin{cases}\left\lfloor%20score_{base}\times%200.15\right\rfloor&\text{si%20victoria%20y%20}\frac{tiempo_{restante}}{tiempo_{limite}}\geq%200.20\\0&\text{en%20otro%20caso}\end{cases})

### 13. Penalizaciones

**Archivo:** `game/score.py`

![Formula Penalizacion](https://latex.codecogs.com/svg.image?penalizaciones=cancelaciones\times%2025)

### 14. Score Final

**Archivo:** `game/score.py`

![Formula Score Final](https://latex.codecogs.com/svg.image?score_{final}=\max(0,score_{base}+bonus_{tiempo}-penalizaciones))

### 15. Interpolación Lineal (LERP)

**Archivo:** `game/utils.py` - Función `lerp()`

![Formula LERP](https://latex.codecogs.com/svg.image?lerp(a,b,t)=a+t\times(b-a))

Usado para transiciones suaves de clima y colores.

### 16. Normalización de Ángulo

**Archivo:** `game/utils.py` - Función `normalize_angle()`

![Formula Norm Angulo](https://latex.codecogs.com/svg.image?\theta_{norm}=\theta\bmod%202\pi\in[-\pi,\pi])

### 17. Distancia Euclidiana

**Archivo:** `game/game.py` - Método `_distance_player_to()`

![Formula Distancia](https://latex.codecogs.com/svg.image?d=\sqrt{(x_2-x_1)^2+(y_2-y_1)^2})

Usada para verificar proximidad entre jugador y puntos de recogida/entrega.

### 18. Clamp (Restricción de Rango)

**Archivo:** `game/utils.py` - Función `clamp()`

![Formula Clamp](https://latex.codecogs.com/svg.image?clamp(x,min,max)=\begin{cases}min&\text{si%20}x<min\\max&\text{si%20}x>max\\x&\text{en%20otro%20caso}\end{cases})

Usada para limitar valores de stamina y reputación entre 0-100.

---

## API y Sistema de Caché

### Endpoints Utilizados

**Base URL:** `https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io`

- **GET /city/map:** Obtener datos del mapa de la ciudad
- **GET /city/jobs:** Obtener lista de pedidos disponibles
- **GET /city/weather:** Obtener información de ráfagas climáticas

### Sistema de Caché

**Archivo:** `api/cache.py`

El sistema implementa un caché inteligente con:

- **TTL (Time To Live) configurable por recurso:**
  - Mapa: 24 horas (datos estáticos)
  - Pedidos: 30 minutos (actualizaciones frecuentes)
  - Clima: 15 minutos (cambios dinámicos)

- **Backup automático offline:** Todos los datos de la API se guardan en `/data/` para modo sin conexión.

- **Limpieza automática:** El caché se limpia cuando excede 100MB o contiene entradas expiradas.

**Flujo de peticiones:**

1. Verificar conexión a Internet
2. Si online: Petición a API → Guardar en caché → Guardar backup offline
3. Si offline: Cargar desde caché → Si no existe, cargar desde backup


---

## Sistema de Guardado

### Guardado Binario

**Archivo:** `game/SaveManager.py`

El juego utiliza **formato binario (pickle)** para guardar partidas:

- **Archivo principal:** `saves/savegame.sav`
- **Backup automático:** `saves/savegame_backup.sav`
- **Autosave:** `saves/autosave.sav`

### Datos Guardados

- **Jugador:** Posición, ángulo, stamina, reputación, ganancias
- **Ciudad:** Dimensiones, tiles del mapa, meta de ingresos
- **Pedidos:** Estado de todos los pedidos (activos, completados, cancelados)
- **Estadísticas:** Tiempo jugado, entregas completadas, tiempo restante
- **Inventario:** Lista de pedidos aceptados con todos sus atributos

### Funcionalidades

- **Guardado rápido (F5):** Guarda en cualquier momento durante el juego
- **Guardado desde menú de pausa:** Opción "Guardar Partida"
- **Carga desde menú principal:** Detecta automáticamente si existe partida guardada
- **Sistema de respaldo:** Tres niveles de seguridad (principal, backup, autosave)

---

## Sistema de Puntuación (Leaderboard)

### Cálculo de Puntaje

El puntaje final se calcula al terminar una partida (victoria o derrota):

```
score_base = ganancias × multiplicador_reputación
bonus_tiempo = score_base × 0.15 (si victoria y tiempo_restante ≥ 20%)
penalizaciones = cancelaciones × 25
score_final = max(0, score_base + bonus_tiempo - penalizaciones)
```

### Leaderboard

**Archivo:** `saves/scores.json`

- Guarda las **50 mejores puntuaciones**
- Ordenadas de mayor a menor
- Incluye: timestamp, score, victorias/derrotas, estadísticas


---

## Estructura del Código

### Módulo `api/`

- **client.py:** Cliente HTTP para consumir API REST
- **cache.py:** Sistema de caché con TTL y limpieza automática

### Módulo `game/`

- **game.py:** Bucle principal del juego, estados, lógica de victoria/derrota
- **player.py:** Lógica del jugador, movimiento, stats, sistema de undo
- **city.py:** Representación del mapa, validación de posiciones
- **renderer.py:** Ray casting, renderizado 3D, minimap
- **weather.py:** Sistema climático con cadena de Markov
- **inventory.py:** Gestión de inventario del jugador
- **orders.py:** Clases Order y OrderManager
- **ordersWindow.py:** Interfaz de ventana de pedidos disponibles
- **audio.py:** Administrador de música y efectos de sonido
- **gamestate.py:** Máquina de estados (menús, pausa, jugando)
- **SaveManager.py:** Guardado/carga de partidas en formato binario
- **score.py:** Sistema de puntuación y leaderboard
- **settings.py:** Menú de configuración
- **utils.py:** Funciones auxiliares (lerp, clamp, distancias)

---

## Configuración

El archivo `config.json` permite modificar:

- **Resolución de pantalla**
- **Número de rayos (calidad gráfica)**
- **Volumen de música**
- **Velocidad del jugador**
- **Tiempo límite de partida**
- **Mecánicas de reputación**
- **Parámetros del sistema de deshacer**
- **Intervalos de liberación de pedidos**

>FOTOMENUCONFIG<

---

## Tecnologías y Librerías

- **Python 3.8+:** Lenguaje de programación
- **Arcade 3.3.2:** Motor de juego 2D/3D
- **Requests:** Cliente HTTP para API REST
- **JSON:** Formato de datos para configuración y caché
- **Pickle:** Serialización binaria para guardados

---

## Licencia

Este proyecto está bajo la **Licencia MIT**.

```
MIT License

Copyright (c) 2025 David González Córdoba

Permission is hereby granted, free of charge, to any person obtaining a copy
of this


