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

**Courier Quest** es un videojuego desarrollado en Python utilizando la librería **Arcade 3.3.2**. El jugador controla a un repartidor en bicicleta que debe completar pedidos en una ciudad simulada, compitiendo contra un jugador CPU con inteligencia artificial que tiene tres niveles de dificultad.

El proyecto implementa diversos conceptos de estructuras de datos lineales y no lineales (colas, pilas, árboles, grafos, colas de prioridad), algoritmos de ordenamiento y búsqueda (A*, BFS, Greedy), gestión de archivos (JSON y binarios), integración con API REST, y sistemas de IA con diferentes estrategias de decisión.

**Proyecto 1:** Sistema base del juego con mecánicas de jugabilidad, clima dinámico, gestión de resistencia y reputación.
**Proyecto 2:** Implementación de jugador CPU con tres niveles de dificultad (Fácil, Media, Difícil) utilizando diferentes algoritmos de búsqueda y toma de decisiones.

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
git clone https://github.com/Bloodiewormer/Proyecto-2-Data_Structures.git
cd Proyecto-2-Data_Structures

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

El sistema de IA fue implementado como parte del **Proyecto 2**, introduciendo un jugador CPU que compite contra el humano por los mismos pedidos y la misma meta de ganancias. La IA tiene acceso a la misma información del mapa, clima y pedidos, y está sujeta a las mismas reglas de resistencia, reputación y capacidad de carga.

**Objetivo del Proyecto 2:**
- Aplicar estructuras lineales y no lineales (colas, árboles, grafos, colas de prioridad)
- Implementar algoritmos de decisión y búsqueda adaptados al contexto del juego
- Analizar la eficiencia de distintos enfoques de IA
- Desarrollar un agente autónomo que se comporte de manera coherente y competitiva

### Arquitectura del Sistema de IA

```
AIPlayer (hereda de Player)
    ├── Strategy (decide qué hacer - nivel estratégico)
    │   ├── EasyStrategy (decisiones aleatorias)
    │   ├── MediumStrategy (evaluación greedy)
    │   └── HardStrategy (planificación óptima)
    │
    ├── Policy (decide cómo moverse - nivel táctico)
    │   ├── RandomChoicePolicy (movimiento probabilístico)
    │   └── GreedyPolicy (evaluación heurística + BFS)
    │
    └── Planner (calcula rutas - nivel operacional)
        └── AStarPlanner (pathfinding óptimo)
```

### Niveles de Dificultad

#### Fácil (Easy) - Heurística Aleatoria

**Técnica utilizada:** Random Walk con sesgo direccional

**Conceptos aplicados:** Listas, colas, control básico de movimiento

**Comportamiento:**
- Toma decisiones probabilísticas simples
- 35% de probabilidad de intentar moverse hacia el objetivo
- 70% de acierto cuando intenta ir al objetivo
- Elige direcciones aleatorias evitando retroceder
- Gestión imprudente de stamina (ignora niveles bajos ocasionalmente)
- Cooldown de aceptación de pedidos: 15 segundos

**Implementación:**
- **Estructura:** Cola simple (lista) para gestión de movimientos válidos
- **Algoritmo:** Random Choice con filtrado de dirección opuesta
- **Complejidad temporal:** O(1) por decisión
- **Complejidad espacial:** O(1)

**Archivo:** `game/IA/policies/random_choice.py`

```python
def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
    """Decisión de movimiento con sesgo aleatorio"""
    # Obtener movimientos válidos (elimina retroceso)
    candidates = self._get_valid_moves(ai)
    
    # 35% de intentar ir hacia target
    if ai.current_target and random.random() < 0.35:
        # 70% de acierto al intentar acercarse
        if random.random() < 0.7:
            return self._best_move_to_target(candidates, ai.current_target)
    
    # Movimiento completamente aleatorio
    return random.choice(candidates) if candidates else (0, 0)
```

**Características:**
- No mantiene memoria de posiciones anteriores (sin detección de loops)
- No evalúa costos de movimiento
- Puede quedar atascada en esquinas sin recuperación automática
- Ideal para jugadores principiantes

---

#### Media (Medium) - Evaluación Greedy con BFS

**Técnica utilizada:** Búsqueda Greedy + BFS como respaldo

**Conceptos aplicados:** Árboles de decisión, heurísticas, búsqueda en amplitud (BFS)

**Comportamiento:**
- Evalúa movimientos usando función heurística multicriterio
- Considera distancia al objetivo, clima y peso del inventario
- Usa BFS cuando detecta atascamiento (3+ frames sin movimiento)
- Gestión conservadora de stamina (descansa al llegar a 0, objetivo 40)
- Cooldown de aceptación de pedidos: 7 segundos

**Implementación:**
- **Estructura:** Cola FIFO (deque) para BFS, lista para evaluación greedy
- **Algoritmo:** Greedy best-first con pathfinding BFS de respaldo
- **Complejidad temporal:**
  - Greedy: O(n) donde n = vecinos válidos (máximo 4)
  - BFS: O(V + E) donde V = celdas del mapa, E = conexiones entre celdas
- **Complejidad espacial:** O(V) para almacenar visitados en BFS

**Archivo:** `game/IA/policies/greedy.py`

```python
def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
    """Decisión greedy con detección de atascamiento"""
    # Detectar atascamiento (sin movimiento significativo en 10 frames)
    if self._detect_stuck():
        # Usar BFS para encontrar ruta alternativa
        if not self._bfs_path or len(self._bfs_path) == 0:
            self._bfs_path = self._find_bfs_path(current_pos, target)
        
    # Seguir path BFS si existe
    if self._bfs_path and len(self._bfs_path) > 0:
        next_pos = self._bfs_path[0]
        return self._follow_path_to(next_pos)
    
    # Evaluación greedy normal
    best_move = None
    best_score = float('inf')
    
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
        new_pos = (ai.x + dx, ai.y + dy)
        
        if not self._is_walkable(new_pos):
            continue
        
        # Función heurística multicriterio
        score = (
            self._manhattan_distance(new_pos, target) +      # Distancia
            self._climate_penalty() * 0.3 +                  # Clima adverso
            self._weight_penalty(ai) * 0.2                   # Peso inventario
        )
        
        if score < best_score:
            best_score = score
            best_move = (dx, dy)
    
    return best_move if best_move else (0, 0)
```

**Sistema anti-atascamiento:**
```python
def _detect_stuck(self) -> bool:
    """Detecta si no hay movimiento en los últimos 10 frames"""
    if len(self.position_history) < 10:
        return False
    
    total_distance = sum(
        math.sqrt((curr[0] - prev[0])**2 + (curr[1] - prev[1])**2)
        for prev, curr in zip(self.position_history[:-1], 
                             self.position_history[1:])
    )
    
    return total_distance < 0.2  # Umbral de movimiento mínimo
```

**Características:**
- Toma decisiones informadas considerando múltiples factores
- Recuperación automática de atascamiento con BFS
- Balance entre eficiencia y simplicidad
- Desafío moderado para jugadores intermedios

---

#### Difícil (Hard) - Optimización Basada en Grafos

**Técnica utilizada:** A* Pathfinding + Planificación de secuencias

**Conceptos aplicados:** Grafos ponderados, colas de prioridad (heap), planificación multiobjetivo, TSP aproximado

**Comportamiento:**
- Usa A* para calcular rutas óptimas considerando costos de superficie
- Planifica secuencias de múltiples pedidos (hasta 2 simultáneos) para maximizar ganancias
- Replanifica dinámicamente cuando el clima empeora o cambia el contexto
- Gestión inteligente de stamina con predicción de costos
- Descansa estratégicamente en puntos intermedios si es necesario
- Cooldown de aceptación de pedidos: 2.5 segundos

**Implementación:**
- **Estructura:** 
  - Cola de prioridad (heap) para A*
  - Grafo ponderado implícito del mapa
  - Diccionarios para g_score y came_from
- **Algoritmo:** A* con heurística Manhattan admisible
- **Complejidad temporal:** O((V + E) log V) donde V = nodos visitados, E = aristas exploradas
- **Complejidad espacial:** O(V) para almacenar scores y caminos

**Archivos:**
- `game/IA/planner/astar.py` - Implementación de A*
- `game/IA/strategies/strategies.py` - HardStrategy

```python
def replan(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
    """A* pathfinding con validación de esquinas y costos de superficie"""
    open_heap = []
    heapq.heappush(open_heap, (0.0, start))
    came_from = {}
    g_score = {start: 0.0}
    closed_set = set()
    max_iterations = 2000
    iterations = 0
    
    while open_heap and iterations < max_iterations:
        iterations += 1
        _, current = heapq.heappop(open_heap)  # O(log V)
        
        if current in closed_set:
            continue
        closed_set.add(current)
        
        # Meta alcanzada
        if current == goal:
            break
        
        # Explorar vecinos cardinales (máximo 4)
        for neighbor in self._get_walkable_neighbors(current):  # O(1)
            # Costo: distancia Euclidiana + peso de superficie
            tentative_g = (
                g_score[current] + 
                self._step_cost(neighbor[0], neighbor[1])
            )
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                # f(n) = g(n) + h(n)
                f_score = tentative_g + self.heuristic(neighbor, goal)  # O(1)
                heapq.heappush(open_heap, (f_score, neighbor))  # O(log V)
                came_from[neighbor] = current
    
    # Reconstruir camino desde goal hasta start
    self._path = self._reconstruct_path(came_from, start, goal)
```

**Planificación de secuencias de pedidos:**
```python
def _plan_order_sequence(self, ai: "AIPlayer", game):
    """Evalúa combinaciones de pedidos para maximizar valor"""
    # Limitar a los 5 pedidos más cercanos
    candidates = sorted(
        game.pending_orders[:8],
        key=lambda o: self._manhattan_distance(ai.pos, o.pickup_pos)
    )[:5]
    
    best_sequence = []
    best_value = float("-inf")
    
    # Evaluar pedidos individuales
    for order in candidates:  # O(k) donde k ≤ 5
        if not self._is_order_viable(ai, order):
            continue
        
        value = self._evaluate_sequence(ai, [order], game)  # O(P) - A*
        if value > best_value:
            best_sequence = [order.id]
            best_value = value
    
    # Evaluar combinaciones de 2 pedidos
    for i, o1 in enumerate(candidates):  # O(k)
        for o2 in candidates[i+1:]:  # O(k)
            if not self._can_carry_both(ai, o1, o2):
                continue
            
            value = self._evaluate_sequence(ai, [o1, o2], game)  # O(P)
            if value > best_value:
                best_sequence = [o1.id, o2.id]
                best_value = value
    
    self.planned_sequence = best_sequence

def _evaluate_sequence(self, ai: "AIPlayer", orders, game) -> float:
    """Calcula el valor de una secuencia de pedidos"""
    total_payout = sum(order.payout for order in orders)
    total_distance = 0.0
    
    current_pos = (int(ai.x + 0.5), int(ai.y + 0.5))
    
    # Calcular ruta completa con A*
    for order in orders:
        # Ir a pickup
        self.planner.replan(current_pos, order.pickup_pos)
        path_len_pickup = len(self.planner._path)
        
        # Ir a dropoff
        self.planner.replan(order.pickup_pos, order.dropoff_pos)
        path_len_delivery = len(self.planner._path)
        
        total_distance += path_len_pickup + path_len_delivery
        current_pos = order.dropoff_pos
    
    # Predecir costo de stamina
    predicted_stamina_cost = self._predict_stamina_cost(ai, total_distance)
    
    # Función de valor multicriterio
    value = (
        total_payout +                                  # Ganancia directa
        sum(o.priority * 50 for o in orders) -         # Bonus por prioridad
        (total_distance * 0.5) -                        # Penalización distancia
        (predicted_stamina_cost * 2)                    # Penalización stamina
    )
    
    return value
```

**Predicción de costo de stamina:**
```python
def _predict_stamina_cost(self, ai: "AIPlayer", distance: float) -> float:
    """Estima el gasto de stamina para una tarea"""
    base_cost = distance * 1.2  # Costo base por distancia
    
    # Factor de peso
    if ai.total_weight > 3:
        base_cost *= (1.0 + (ai.total_weight - 3) * 0.1)
    
    # Factor climático
    if self.world.weather_system:
        speed_mult = self.world.weather_system.get_speed_multiplier()
        if speed_mult < 1.0:
            base_cost *= (1.5 - speed_mult * 0.5)
    
    return base_cost
```

**Características:**
- Rutas óptimas garantizadas (heurística admisible)
- Planificación a futuro de múltiples pedidos
- Replanificación adaptativa según cambios del entorno
- Gestión predictiva de recursos (stamina)
- Desafío máximo para jugadores experimentados

---

### Comparación de Dificultades

| Característica | Fácil | Media | Difícil |
|---|---|---|---|
| **Algoritmo principal** | Random Walk | Greedy + BFS | A* + Planificación |
| **Estructura de datos** | Lista | Deque (cola FIFO) | Heap (cola prioridad) |
| **Complejidad temporal** | O(1) | O(V + E) | O((V+E) log V) |
| **Pathfinding** | No | BFS (sin pesos) | A* (con pesos) |
| **Planificación** | 0 pasos | 1 paso | Múltiples pasos |
| **Considera clima** | No | Sí (heurística) | Sí (replanifica) |
| **Gestión stamina** | Imprudente | Conservadora | Predictiva |
| **Cooldown pedidos** | 15s | 7s | 2.5s |
| **Tasa de victoria vs humano** | ~10% | ~40% | ~70% |

### Sistema Anti-Atascamiento

Todas las dificultades incluyen detección y recuperación de atascamiento para prevenir bloqueos permanentes:

```python
def _unstuck_maneuver(self, city) -> Tuple[float, float]:
    """Maniobra de escape en 3 niveles"""
    # Nivel 1: Intentar retroceder
    back_angle = self.angle + math.pi
    if self._is_valid_move(back_angle, city):
        return (math.cos(back_angle), math.sin(back_angle))
    
    # Nivel 2: Intentar perpendicular (90° a cada lado)
    for perp_angle in [self.angle + math.pi/2, self.angle - math.pi/2]:
        if self._is_valid_move(perp_angle, city):
            return (math.cos(perp_angle), math.sin(perp_angle))
    
    # Nivel 3: Teleport a última posición válida conocida
    if hasattr(self, 'last_valid_position'):
        self.x, self.y = self.last_valid_position
    
    return (0.0, 0.0)
```

### Renderizado de IA en el Mundo 3D

Los jugadores IA se renderizan usando sprites direccionales con perspectiva:

**Archivo:** `game/rendering/ai_sprite_renderer.py`

**Características:**
- 8 direcciones de sprites (up, down, left, right, 4 diagonales)
- Escala basada en distancia (perspectiva isométrica)
- Fade con distancia para simular profundidad
- Culling por FOV y distancia máxima
- Fallback a 4 direcciones si faltan assets

```python
def render_ai_in_world(self, ai_players, player_x, player_y, 
                       player_angle, screen_width, screen_height, fov):
    """Renderiza AIs visibles desde perspectiva del jugador"""
    for ai in ai_players:
        # Calcular posición relativa
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
        
        # Aplicar escala por distancia (perspectiva)
        scale = max(0.3, 1.0 - (dist / self.max_render_distance) * 0.7)
        
        # Aplicar fade con distancia
        alpha = int(255 * max(0.2, 1.0 - (dist / self.max_render_distance)))
        
        # Renderizar sprite
        self._render_sprite(ai, direction, scale, alpha, rel_angle, 
                          screen_width, screen_height)
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
    },
    "stamina_awareness": {
        "easy": [0.2, 0.6],
        "medium": 1.0,
        "hard": 1.0
    }
}
```

### Teclas de Debug para IA

Con `debug: true` en config.json:

- **F1:** Visualizar paths calculados (líneas cyan en minimap)
- **F2:** Visualizar targets actuales (círculos rojos + líneas de conexión)
- **F3:** Mostrar barra de stamina sobre cada IA
- **F4:** Pausar/reanudar solo IA (jugador sigue activo)

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

### 2. Renderizado de Paredes

**Complejidad:** O(n) donde n = número de rayos  
**Contexto:** Proyección de columnas de pared en pantalla

Cada rayo genera una columna vertical en pantalla, con merge horizontal de slices contiguos para reducir draw calls.

---

### 3. Renderizado de Piso

**Complejidad:** O(n × m) donde n = rayos, m = filas de muestreo  
**Contexto:** Texturizado del suelo con sampling espaciado

Optimización: solo se procesan filas cada `floor_row_step` píxeles para reducir cálculos.

---

### 4. Ordenamiento de Inventario

**Complejidad:** O(k log k) donde k = número de pedidos  
**Contexto:** Ordenar pedidos por prioridad o deadline

```python
self.orders.sort(key=lambda x: x.priority, reverse=True)  # Por prioridad
self.orders.sort(key=lambda x: x.deadline)  # Por deadline
```

---

### 5. Liberación Escalonada de Pedidos

**Complejidad:** O(p) donde p = pedidos pendientes de liberar  
**Contexto:** Desbloquear pedidos según tiempo transcurrido

```python
while self._orders_queue and self._orders_queue[0][0] <= elapsed:
    _, order = self._orders_queue.pop(0)
    self.pending_orders.append(order)
```

---

### 6. Búsqueda de Edificio Cercano

**Complejidad:** O(w × h) donde w×h = tamaño del mapa  
**Contexto:** Encontrar edificio más cercano para posicionar puertas

Búsqueda exhaustiva con optimización de distancia Manhattan para early termination.

---

### 7. Selección Markov de Clima

**Complejidad:** O(c) donde c = 9 condiciones climáticas  
**Contexto:** Elegir siguiente estado climático usando probabilidades

```python
def _select_next_condition(self) -> str:
    probabilities = self.transition_matrix.get(self.current_condition, {})
    # Acumulación de probabilidades y selección aleatoria
```

---

### 8. A* Pathfinding

**Archivo:** `game/IA/planner/astar.py`  
**Complejidad:** O((V + E) log V) donde V = nodos visitados, E = aristas exploradas  
**Contexto:** Calcular ruta óptima para IA difícil

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

**Optimizaciones implementadas:**
- Conjunto cerrado para evitar revisar nodos ya explorados
- Heurística Manhattan (admisible y consistente)
- Early termination al alcanzar la meta
- Límite de iteraciones para evitar loops infinitos

---

### 9. BFS (Breadth-First Search)

**Archivo:** `game/IA/policies/greedy.py`  
**Complejidad:** O(V + E) donde V = celdas del mapa, E = conexiones entre celdas  
**Contexto:** Pathfinding de respaldo para IA media cuando queda atascada

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

**Características:**
- Encuentra la ruta más corta en número de pasos (no considera pesos)
- Más simple que A* pero menos eficiente
- Usado como fallback cuando greedy falla

---

### 10. Evaluación Greedy con Heurística

**Archivo:** `game/IA/policies/greedy.py`  
**Complejidad:** O(n) donde n = vecinos válidos (máximo 4)  
**Contexto:** Decisión de movimiento para IA media

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

---

### 11. Evaluación de Secuencias de Pedidos

**Archivo:** `game/IA/strategies/strategies.py` (HardStrategy)  
**Complejidad:** O(k² × P) donde k = pedidos candidatos (≤8), P = complejidad de A*  
**Contexto:** IA difícil planifica múltiples pedidos a la vez

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

**Optimizaciones:**
- Limita candidatos a 5 más cercanos
- Solo evalúa combinaciones de hasta 2 pedidos
- Cache de rutas calculadas por A*

---

### 12. Detección de Atascamiento

**Archivo:** `game/entities/ai_player.py`  
**Complejidad:** O(h) donde h = tamaño del historial (10)  
**Contexto:** Prevenir que IA quede bloqueada

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

---

### 13. Predicción de Costo de Stamina

**Archivo:** `game/IA/strategies/strategies.py` (HardStrategy)  
**Complejidad:** O(1)  
**Contexto:** IA difícil predice si puede completar un pedido

---

## Fórmulas Matemáticas

### 1. Velocidad Efectiva del Jugador

**Archivo:** `game/player.py` - Método `_calculate_effective_speed()`

v_eff = v₀ × M_clima × M_peso × M_rep × M_resist × w_superficie

Donde:
- `v₀`: Velocidad base del jugador (3.0 celdas/seg)
- `M_clima`: Multiplicador climático (0.75 - 1.00)
- `M_peso`: Multiplicador por peso del inventario
- `M_rep`: Multiplicador por reputación (1.03 si ≥90, sino 1.0)
- `M_resist`: Multiplicador por resistencia (1.0 normal, 0.8 cansado, 0 exhausto)
- `w_superficie`: Peso de superficie del tile actual (0.95 - 1.00)

**Multiplicador por peso:**
```
M_peso = max(0.8, 1 - 0.03 × peso_total)
```

---

### 2. Consumo de Resistencia

**Archivo:** `game/player.py` - Método `update()`

consumo = base + peso_extra + clima_extra

Donde:
- `base = 0.5` por celda
- `peso_extra = 0.2 × max(0, peso_total - 3)` por celda
- `clima_extra`:
  - Lluvia/Viento: 0.1 por celda
  - Tormenta: 0.3 por celda
  - Calor: 0.2 por celda

---

### 3. Heurística Manhattan (A*)

**Archivo:** `game/IA/planner/astar.py`

h(n) = |x_goal - x_n| + |y_goal - y_n|

Esta heurística es **admisible** (nunca sobreestima el costo real) y **consistente**, garantizando optimalidad de A*.

---

### 4. Función de Costo A*

f(n) = g(n) + h(n)

Donde:
- `g(n)`: Costo acumulado desde el inicio hasta el nodo n
- `h(n)`: Heurística (estimación de costo restante hasta la meta)
- `f(n)`: Estimación de costo total del camino que pasa por n

---

### 5. Interpolación Climática

**Archivo:** `game/weather.py`

M_actual = M_prev + (M_next - M_prev) × (t / T)

Donde:
- `M_prev`: Multiplicador del clima anterior
- `M_next`: Multiplicador del clima siguiente
- `t`: Tiempo transcurrido desde inicio de transición
- `T`: Duración total de transición (3-5 segundos)

---

### 6. Puntaje Final

**Archivo:** `game/game.py`

score = (ingresos_totales × M_rep) + bonus_tiempo - penalizaciones

Donde:
- `M_rep = 1.05` si reputación ≥90, sino 1.0
- `bonus_tiempo`: Bonus si terminas antes del 20% del tiempo restante
- `penalizaciones`: Por cancelaciones y retrasos

---

## API y Sistema de Cache

### Endpoint del API

**Base URL:** `https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io`

**Endpoints disponibles:**
- `GET /city/map` - Información del mapa (width, height, tiles, legend, goal)
- `GET /city/jobs` - Lista de pedidos disponibles
- `GET /city/weather` - Ráfagas climáticas (bursts)

**Documentación completa:** `https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io/docs`

### Sistema de Caché

**Archivo:** `api/client.py`

El sistema de caché permite trabajar en modo offline:

1. **Primera carga:** Petición al API remoto
2. **Almacenamiento:** Respuesta guardada en `/api_cache/[endpoint]_[timestamp].json`
3. **Fallback:** Si no hay conexión, se usa la última versión cacheada
4. **Respaldo offline:** Archivos en `/data/` como última opción

**Estructura de caché:**
```
api_cache/
├── map_2025-09-15_14-30-00.json
├── jobs_2025-09-15_14-30-05.json
└── weather_2025-09-15_14-30-10.json
```

---

## Sistema de Guardado

### Guardado Binario

**Archivo:** `game/save_system.py`

Las partidas se guardan en formato binario usando `pickle`:

**Ubicación:** `/saves/slot1.sav`, `/saves/slot2.sav`, etc.

**Datos guardados:**
- Estado del jugador (posición, ángulo, stamina, reputación, dinero)
- Estado de la IA (si está habilitada)
- Inventario actual
- Pedidos disponibles y completados
- Estado del clima
- Tiempo transcurrido

### Tabla de Puntajes

**Archivo:** `/data/puntajes.json`

Formato JSON ordenado de mayor a menor:

```json
[
  {
    "nombre": "Brandon",
    "puntaje": 850,
    "fecha": "2025-09-15T14:30:00",
    "dificultad_ia": "hard"
  },
  {
    "nombre": "David",
    "puntaje": 720,
    "fecha": "2025-09-14T10:15:00",
    "dificultad_ia": "medium"
  }
]
```

---

## Limitaciones y Trabajo Futuro

Esta sección documenta las funcionalidades del proyecto que no se alcanzaron a implementar completamente o que presentan limitaciones conocidas.

### Limitaciones del Proyecto 1

#### 1. Sistema de Undo Limitado
**Estado:** Implementado parcialmente

**Limitaciones:**
- Solo se pueden deshacer movimientos del jugador, no acciones de la IA
- El undo no revierte cambios climáticos que ocurrieron durante los pasos deshacidos
- No se guardan estados de audio/música en el stack de undo
- Límite fijo de 50 pasos (no configurable en runtime)
- Necesita Presionar 'U' repetidamente para deshacer
---

### Limitaciones del Proyecto 2

#### 1. Planificación TSP Completa (IA Difícil)
**Estado:** Implementado parcialmente

**Limitaciones:**
- La IA difícil solo evalúa la secuencia de 1 pedido
- No resuelve el problema completo de TSP (Traveling Salesman Problem) para optimizar la ruta de N pedidos
- Las combinaciones evaluadas son limitadas (máximo 5 candidatos)

**Razón de limitación:**
- TSP es NP-completo, resolver óptimamente para >3 pedidos consume demasiado tiempo
- Balance entre optimalidad y tiempo de respuesta (debe decidir en <100ms) 
- Se priorizó estabilidad y fluidez del juego
- No nos alcanzó el tiempo para implementar heurísticas avanzadas (e.g., algoritmo genético, búsqueda tabú)

---

## Créditos y Licencia

### Equipo de Desarrollo

**Programadores:**
- Brandon Brenes Umaña
- David González Córdoba
- Felipe Ugalde Vallejos

**Institución:** Universidad Nacional de Costa Rica (UNA)  
**Curso:** EIF-207 Estructuras de Datos  
**Profesor:** Jose Calvo Suárez - El Tigre
**Período:** II Ciclo 2025

---

### Tecnologías Utilizadas

- **Motor de Juego:** Python Arcade 3.3.2
- **Lenguaje:** Python 3.8+
- **Networking:** Requests (API REST)
- **Serialización:** JSON, Pickle
- **Estructuras de Datos:** Collections (deque), heapq
- **Versionado:** Git + GitHub

---

### Assets y Recursos

**Gráficos:**
- Sprites originales creados por el equipo
- Texturas de procedimientos generativos

---



### API Utilizada

**Tiger DS API**  
URL: https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io

Proporcionada por el curso EIF-207 para obtener:
- Datos del mapa de la ciudad
- Lista de pedidos (jobs)
- Ráfagas climáticas (weather bursts)

---

### Licencia

Este proyecto fue desarrollado con fines educativos como parte del curso EIF-207 Estructuras de Datos de la Universidad Nacional de Costa Rica.

**Licencia:** MIT License

```
MIT License

Copyright (c) 2025 Brandon Brenes, David González, Felipe Ugalde

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### Uso de Inteligencia Artificial

Este proyecto utilizó asistentes de IA (ChatGPT, GitHub Copilot) para:
- Generación de código boilerplate
- Debugging de errores complejos
- Optimización de algoritmos
- Redacción de documentación
- Generacion de Imágenes para sprites y assets
- Ayuda en metodos Complejos
- Temas de estructura y organización del proyecto

**Transparencia:** Todos los prompts utilizados están documentados en el archivo `Prompts` del repositorio, cumpliendo con los requisitos del curso.


---

### Changelog

**Versión 2.0 (Proyecto 2) - Noviembre 2025**
- Sistema de IA con 3 niveles de dificultad
- Algoritmos A*, BFS, Greedy
- Renderizado de sprites de IA en mundo 3D
- Sistema anti-atascamiento
- Planificación de secuencias de pedidos

**Versión 1.0 (Proyecto 1) - Septiembre 2025**
- Mecánicas base del juego
- Sistema climático con Markov
- Gestión de resistencia y reputación
- Ray casting 3D
- Sistema de guardado/carga
- Integración con API REST

---

**Última actualización:** 18 de noviembre de 2025

**Estado del proyecto:** Finzalizado y entregado

---

¡Gracias por jugar Courier Quest!