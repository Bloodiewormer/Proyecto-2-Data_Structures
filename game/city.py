import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

from .utils import load_json, save_json


class CityMap:

    def __init__(self, api_client, config: Dict[str, Any]):

        self.api_client = api_client
        self.config = config

        # Datos del mapa
        self.tiles: List[List[str]] = []
        self.width = 0
        self.height = 0
        self.version = "1.0"
        self.goal = 3000

        # Leyenda de tiles
        self.legend = {
            "C": {"name": "calle", "surface_weight": 1.00},
            "B": {"name": "edificio", "blocked": True},
            "P": {"name": "parque", "surface_weight": 0.95}
        }

        # Archivos de respaldo
        self.map_backup_file = Path(config["files"]["data_directory"]) / "ciudad.json"

    def load_map(self) -> bool:
        try:
            # Intentar cargar desde API
            if self.api_client:
                map_data = self.api_client.get_map()
                if map_data:
                    self._parse_map_data(map_data)
                    # Guardar copia de respaldo
                    save_json(map_data, str(self.map_backup_file))
                    print("Mapa cargado desde API")
                    return True

        except Exception as e:
            print(f"Error al cargar mapa desde API: {e}")

        # Cargar desde archivo de respaldo
        try:
            backup_data = load_json(str(self.map_backup_file))
            if backup_data:
                self._parse_map_data(backup_data)
                print("Mapa cargado desde archivo de respaldo")
                return True
        except Exception as e:
            print(f"Error al cargar mapa desde respaldo: {e}")

        # Si todo falla, usar mapa por defecto
        self._create_default_map()
        print("Usando mapa por defecto")
        return True



    def is_wall(self, x: float, y: float) -> bool:
        ix, iy = int(x), int(y)

        # Verificar límites del mapa
        if ix < 0 or iy < 0 or ix >= self.width or iy >= self.height:
            return True

        # Verificar si el tile es un edificio (pared)
        tile_type = self.tiles[iy][ix]
        return tile_type == "B"

    def get_surface_weight(self, x: float, y: float) -> float:
        ix, iy = int(x), int(y)

        # Verificar límites del mapa
        if ix < 0 or iy < 0 or ix >= self.width or iy >= self.height:
            return 1.0

        tile_type = self.tiles[iy][ix]
        tile_info = self.legend.get(tile_type, {"surface_weight": 1.0})

        return tile_info.get("surface_weight", 1.0)

    def get_spawn_position(self) -> Tuple[float, float]:

        # Buscar una posición de calle cerca del centro
        center_x, center_y = self.width / 2, self.height / 2

        for radius in range(1, max(self.width, self.height)):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x = center_x + dx
                    y = center_y + dy

                    if (0 <= x < self.width and 0 <= y < self.height and
                            not self.is_wall(x, y)):
                        return (float(x), float(y))

        # Fallback: esquina superior izquierda
        return (1.0, 1.0)



    def _parse_map_data(self, map_data: Dict[str, Any]):
        # Extraer datos
        if "data" in map_data:
            map_data = map_data["data"]

        self.version = map_data.get("version", "1.0")
        self.width = map_data.get("width", 0)
        self.height = map_data.get("height", 0)
        self.tiles = map_data.get("tiles", [])
        self.goal = map_data.get("goal", 3000)

        # Actualizar leyenda si está presente
        if "legend" in map_data:
            self.legend.update(map_data["legend"])

        # Validar datos
        if self.height != len(self.tiles):
            raise ValueError(f"Altura del mapa ({self.height}) no coincide con número de filas ({len(self.tiles)})")

        if self.tiles and self.width != len(self.tiles[0]):
            raise ValueError(f"Ancho del mapa ({self.width}) no coincide con número de columnas ({len(self.tiles[0])})")



    def _create_default_map(self):
        """Crea un mapa por defecto si no se puede cargar desde API o archivo"""
        self.width = 20
        self.height = 15
        self.version = "1.0"
        self.goal = 3000

        # Crear mapa simple con calles y algunos edificios
        self.tiles = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                # Bordes como edificios
                if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                    row.append("B")
                # Algunos edificios internos
                elif (x % 4 == 0 and y % 4 == 0) or (x % 6 == 3 and y % 5 == 2):
                    row.append("B")
                # Algunos parques
                elif x % 8 == 4 and y % 6 == 3:
                    row.append("P")
                # Resto son calles
                else:
                    row.append("C")
            self.tiles.append(row)



    def get_tile_at(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return "B"  # Fuera de límites se considera pared

    def is_valid_position(self, x: float, y: float) -> bool:
        return (0 <= x < self.width and
                0 <= y < self.height and
                not self.is_wall(x, y))

    def get_map_info(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "width": self.width,
            "height": self.height,
            "goal": self.goal,
            "total_orders": len(self.orders),
            "available_pickups": len(self.pickup_points),
            "available_dropoffs": len(self.dropoff_points)
        }