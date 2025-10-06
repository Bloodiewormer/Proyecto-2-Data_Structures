# Proyecto-1-Data_Structures

---------------------------------------PROYECTO DE ESTRUCTURAS DE DATOS-----------------------------------------------
JUEGO: COURIER QUEST


----------------------------------------------------------------------------------------------------------------------
iNTEGRANTES:
*BRANDON BRENES UMAÑA
*DAVID GONZÁLEZ CÓRDOBA
*FELIPE UGALDE VALLEJOS

----------------------------------------------------------------------------------------------------------------------

INSTRUCCIONES DE USO:


CONTROLES BÁSICOS
Movimiento

W o Flecha Arriba: Avanzar hacia adelante
S o Flecha Abajo: Retroceder
A o Flecha Izquierda: Girar a la izquierda
D o Flecha Derecha: Girar a la derecha

Gestión de Pedidos

O: Abrir/cerrar ventana de pedidos disponibles
Flecha Arriba/Abajo: Navegar entre pedidos
A: Aceptar pedido seleccionado
C: Cancelar pedido seleccionado

Inventario

I: Abrir/cerrar inventario
Q: Seleccionar siguiente pedido en inventario
Shift + Q: Seleccionar pedido anterior en inventario
Tab: Cambiar orden de inventario (prioridad/fecha límite)

Sistema

ESC: Pausar juego / Volver al menú anterior
F5: Guardar partida


OBJETIVO DEL JUEGO
Ganar $500 antes de que se agote el tiempo (15 minutos)



----------------------------------------------------------------------------------------------------------------------
ESTRUCTURAS DE DATOS UTILIZADAS
1. HEAPS 
Ubicación: Sistema de gestión de pedidos
Propósito: Gestión de pedidos con liberación escalonada basada en tiempo de juego
Operaciones:

Inserción: O(n log n)
Extracción del mínimo: O(1)

Uso: Liberar pedidos automáticamente según tiempo transcurrido

2. COLAS
Ubicación: Sistema de inventario del jugador
Propósito: Gestión de pedidos activos con capacidad limitada por peso
Operaciones:

Enqueue: O(1) + ordenamiento O(n log n)
Dequeue: O(n)

Uso: Almacenar y gestionar pedidos aceptados durante entregas

3. SET 
Ubicación: Sistema de renderizado
Propósito: Registro de posiciones de puertas en edificios
Operaciones:

Inserción: O(1)
Búsqueda: O(1)

Uso: Verificación rápida de puertas durante renderizado de paredes

4. Diccionarios
4.1 Caché de Minimap
Ubicación: Sistema de renderizado de minimap
Propósito: Evitar reconstrucción del minimap en cada frame
Complejidad: O(1) para búsqueda y acceso
4.2 Matriz de Transición de Markov
Ubicación: Sistema climático
Propósito: Probabilidades de cambio entre 9 condiciones climáticas
Complejidad: O(1) para acceso a probabilidades
4.3 Caché de Música
Ubicación: Sistema de audio
Propósito: Almacenar archivos de audio cargados
Complejidad: O(1) para búsqueda y recuperación
4.4 Leyenda de Tiles
Ubicación: Sistema de mapa de ciudad
Propósito: Mapear tipos de casillas a propiedades de superficie
Complejidad: O(1) para consultas de propiedades

5. LISTAS 
5.1 Frame Times
Ubicación: Sistema de métricas de rendimiento
Propósito: Registro de tiempos de frame para cálculo de FPS
Operaciones: Append O(1), pop(0) O(n)
Tamaño: Últimos 240 frames
5.2 Tiles del Mapa
Ubicación: Sistema de mapa de ciudad
Propósito: Matriz 2D representando el mapa
Acceso: O(1) usando índices [y][x]
5.3 Direcciones de Rayos
Ubicación: Sistema de ray casting
Propósito: Cache de vectores de dirección
Complejidad: O(n) inicialización, O(1) acceso
5.4 Filas de Muestreo del Piso
Ubicación: Sistema de renderizado de piso
Propósito: Optimización por muestreo espaciado
Complejidad: O(n/step)
----------------------------------------------------------------------------------------------------------------------

FÓRMULAS MATEMÁTICAS


1. Velocidad Efectiva del Jugador
Dónde se usa: Cálculo de movimiento del jugador
Cuándo se usa: Cada vez que el jugador se mueve

2. Multiplicador de Peso
Dónde se usa: Cálculo de velocidad efectiva
Cuándo se usa: Cuando el jugador carga más de 3 kg

3. DDA Ray Casting - Delta Distance
Dónde se usa: Algoritmo de ray casting para paredes
Cuándo se usa: Cada frame para detectar colisiones con paredes

4. DDA Ray Casting - Side Distance
Dónde se usa: Algoritmo de ray casting para paredes
Cuándo se usa: Inicialización de cada rayo

5. Distancia Perpendicular a Pared
Dónde se usa: Cálculo de altura de paredes en pantalla
Cuándo se usa: Después de detectar intersección con pared

6. Altura de Línea de Pared
Dónde se usa: Proyección de paredes en pantalla
Cuándo se usa: Renderizado de cada columna de pared

7. Límites de Dibujo de Pared
Dónde se usa: Proyección de paredes en pantalla
Cuándo se usa: Determinación de píxeles a dibujar para cada pared

8. Distancia de Fila de Piso
Dónde se usa: Renderizado de texturas de piso
Cuándo se usa: Cada frame para cada fila visible del piso

9. Coordenadas Mundiales de Piso
Dónde se usa: Mapeado de texturas en el piso
Cuándo se usa: Para cada píxel del piso renderizado

10. Score Base
Dónde se usa: Sistema de puntuación al finalizar partida
Cuándo se usa: Al terminar el juego por victoria o derrota

11. Multiplicador de Pago por Reputación
Dónde se usa: Sistema de puntuación
Cuándo se usa: Cálculo de score base

12. Bonus por Tiempo
Dónde se usa: Sistema de puntuación
Cuándo se usa: Al ganar con más del 20% del tiempo restante

13. Penalizaciones
Dónde se usa: Sistema de puntuación
Cuándo se usa: Cálculo de score final

14. Score Final
Dónde se usa: Sistema de puntuación
Cuándo se usa: Resultado final del juego

15. Interpolación Lineal (LERP)
Dónde se usa: Transiciones suaves de clima y colores
Cuándo se usa: Durante cambios graduales de estado climático

16. Normalización de Ángulo
Dónde se usa: Control de rotación del jugador
Cuándo se usa: Mantener ángulos en rango [-π, π]

17. Distancia Euclidiana
Dónde se usa: Detección de proximidad para pedidos
Cuándo se usa: Verificar si jugador está cerca de punto de recogida/entrega

18. Clamp (Restricción de Rango)
Dónde se usa: Limitación de valores de stamina y reputación
Cuándo se usa: Actualización de estadísticas del jugador
----------------------------------------------------------------------------------------------------------------------

COMPLEJIDADES ALGORÍTMICAS


Ray Casting DDA
Complejidad: O(w + h)
Contexto: Detección de paredes

Renderizado de Paredes
Complejidad: O(n)
Contexto: n = número de rayos

Renderizado de Piso
Complejidad: O(n × m)
Contexto: n = rayos, m = filas

Ordenamiento de Inventario
Complejidad: O(k log k)
Contexto: k = pedidos

Liberación de Pedidos
Complejidad: O(p)
Contexto: p = pedidos pendientes

Búsqueda de Edificio Cercano
Complejidad: O(w × h)
Contexto: w×h = tamaño del mapa

Selección Markov de Clima
Complejidad: O(c)
Contexto: c = 9 condiciones
----------------------------------------------------------------------------------------------------------------------


JUSTIFICACIÓN DE ESTRUCTURAS
Heap: Liberación ordenada de pedidos por tiempo sin mantener lista completa ordenada continuamente
Set: Búsqueda O(1) de puertas durante ray casting, crítico para rendimiento a 60 FPS
Diccionarios: Acceso constante a configuraciones, caché de recursos y matriz de transición climática
Listas: Representación natural de vectores 2D y matrices para el mapa
Cola: Inventario FIFO con priorización dinámica mediante ordenamiento secundario

----------------------------------------------------------------------------------------------------------------------
