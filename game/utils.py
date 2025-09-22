import json
import math
import os
from pathlib import Path
from typing import Dict, Any, Tuple, List
from datetime import datetime

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return get_default_config()
    except json.JSONDecodeError as e:
        print(f"Error al leer configuración: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    return {
        "display": {"width": 800, "height": 600, "title": "Courier Quest"},
        "game": {"tile_size": 32, "time_limit_minutes": 12},
        "player": {"base_speed": 3.0, "max_inventory_weight": 10},
        "colors": {
            "street": [105, 105, 105],
            "building": [0, 0, 0],
            "park": [144, 238, 144]
        }
    }


def ensure_directories(directories: List[str]):
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def calculate_distance(pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    return math.sqrt(dx * dx + dy * dy)


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

"""clamp: encerrar un valor dentro de un rango"""
def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))


"""lerp: Es Jerga tecnica en dev de videojuegos y shaders (significa Linear intERPolation)"""
def lerp(initial_value: float, final_value: float, param: float) -> float:
    return initial_value + param * (final_value - initial_value)

def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def save_json(data: Dict[str, Any], filepath: str) -> bool:
    try:
        # Crear directorio si no existe
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error al guardar JSON {filepath}: {e}")
        return False


def load_json(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error al leer JSON {filepath}: {e}")
        return {}

def get_timestamp() -> str:
    return datetime.now().isoformat()



class Vector2D:
    def __init__(self, x: float = 0, y: float = 0):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float):
        return Vector2D(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self):
        length = self.length()
        if length > 0:
            self.x /= length
            self.y /= length
        return self

    def to_tuple(self) -> Tuple[float, float]:
        return self.x, self.y