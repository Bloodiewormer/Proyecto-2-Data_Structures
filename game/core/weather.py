# file: game/weather.py
import json
import random
from game.core.utils import  lerp
from typing import Dict, Any, Tuple
from pathlib import Path


class WeatherCondition:
    """Condiciones climáticas disponibles"""
    CLEAR = "clear"
    CLOUDS = "clouds"
    RAIN_LIGHT = "rain_light"
    RAIN = "rain"
    STORM = "storm"
    FOG = "fog"
    WIND = "wind"
    HEAT = "heat"
    COLD = "cold"


class WeatherSystem:

    def __init__(self, api_client, config: Dict[str, Any]):
        self.api_client = api_client
        self.config = config

        weather_conf = config.get("weather", {})

        self.burst_duration_min = float(weather_conf.get("burst_duration_min", 45))
        self.burst_duration_max = float(weather_conf.get("burst_duration_max", 90))
        if self.burst_duration_max < self.burst_duration_min:
            self.burst_duration_max = self.burst_duration_min

        # Estado actual del clima
        self.current_condition = WeatherCondition.CLEAR
        self.current_intensity = 0.2

        # Transición suave entre climas
        self.transitioning = False
        self.transition_duration = float(weather_conf.get("transition_duration", 4.0))
        self.transition_progress = 0.0
        self.previous_condition = WeatherCondition.CLEAR
        self.previous_intensity = 0.2

        # Configuración de multiplicadores de velocidad base
        self.speed_multipliers = {
            WeatherCondition.CLEAR: 1.00,
            WeatherCondition.CLOUDS: 0.98,
            WeatherCondition.RAIN_LIGHT: 0.90,
            WeatherCondition.RAIN: 0.85,
            WeatherCondition.STORM: 0.75,
            WeatherCondition.FOG: 0.88,
            WeatherCondition.WIND: 0.92,
            WeatherCondition.HEAT: 0.90,
            WeatherCondition.COLD: 0.92
        }

        # Configuración de drenaje de resistencia
        self.stamina_drains = {
            WeatherCondition.CLEAR: 0.0,
            WeatherCondition.CLOUDS: 0.0,
            WeatherCondition.RAIN_LIGHT: 0.1,
            WeatherCondition.RAIN: 0.1,
            WeatherCondition.STORM: 0.3,
            WeatherCondition.FOG: 0.0,
            WeatherCondition.WIND: 0.1,
            WeatherCondition.HEAT: 0.2,
            WeatherCondition.COLD: 0.05
        }

        # Colores para el cielo según el clima
        self.sky_colors = {
            WeatherCondition.CLEAR: (135, 206, 235),  # Azul cielo
            WeatherCondition.CLOUDS: (169, 169, 169),  # Gris claro
            WeatherCondition.RAIN_LIGHT: (119, 136, 153),  # Gris azulado
            WeatherCondition.RAIN: (105, 105, 105),  # Gris medio
            WeatherCondition.STORM: (47, 79, 79),  # Gris muy oscuro
            WeatherCondition.FOG: (220, 220, 220),  # Gris muy claro
            WeatherCondition.WIND: (176, 196, 222),  # Azul grisáceo
            WeatherCondition.HEAT: (255, 218, 185),  # Naranja pálido
            WeatherCondition.COLD: (175, 238, 238)  # Azul muy pálido
        }

        # Colores para las nubes según el clima
        self.cloud_colors = {
            WeatherCondition.CLEAR: (255, 255, 255),  # Blanco
            WeatherCondition.CLOUDS: (211, 211, 211),  # Gris claro
            WeatherCondition.RAIN_LIGHT: (169, 169, 169),  # Gris
            WeatherCondition.RAIN: (128, 128, 128),  # Gris medio
            WeatherCondition.STORM: (64, 64, 64),  # Gris muy oscuro
            WeatherCondition.FOG: (240, 248, 255),  # Blanco azulado
            WeatherCondition.WIND: (220, 220, 220),  # Gris muy claro
            WeatherCondition.HEAT: (255, 250, 240),  # Blanco cálido
            WeatherCondition.COLD: (240, 248, 255)  # Blanco frío
        }

        # Matriz de transición de Markov (9x9 para todas las condiciones)
        self.transition_matrix = {
            WeatherCondition.CLEAR: {
                WeatherCondition.CLEAR: 0.4,
                WeatherCondition.CLOUDS: 0.3,
                WeatherCondition.RAIN_LIGHT: 0.1,
                WeatherCondition.RAIN: 0.05,
                WeatherCondition.STORM: 0.02,
                WeatherCondition.FOG: 0.05,
                WeatherCondition.WIND: 0.05,
                WeatherCondition.HEAT: 0.02,
                WeatherCondition.COLD: 0.01
            },
            WeatherCondition.CLOUDS: {
                WeatherCondition.CLEAR: 0.2,
                WeatherCondition.CLOUDS: 0.3,
                WeatherCondition.RAIN_LIGHT: 0.2,
                WeatherCondition.RAIN: 0.15,
                WeatherCondition.STORM: 0.05,
                WeatherCondition.FOG: 0.05,
                WeatherCondition.WIND: 0.03,
                WeatherCondition.HEAT: 0.01,
                WeatherCondition.COLD: 0.01
            },
            WeatherCondition.RAIN_LIGHT: {
                WeatherCondition.CLEAR: 0.1,
                WeatherCondition.CLOUDS: 0.25,
                WeatherCondition.RAIN_LIGHT: 0.3,
                WeatherCondition.RAIN: 0.25,
                WeatherCondition.STORM: 0.08,
                WeatherCondition.FOG: 0.02,
                WeatherCondition.WIND: 0.0,
                WeatherCondition.HEAT: 0.0,
                WeatherCondition.COLD: 0.0
            },
            WeatherCondition.RAIN: {
                WeatherCondition.CLEAR: 0.05,
                WeatherCondition.CLOUDS: 0.2,
                WeatherCondition.RAIN_LIGHT: 0.3,
                WeatherCondition.RAIN: 0.25,
                WeatherCondition.STORM: 0.15,
                WeatherCondition.FOG: 0.05,
                WeatherCondition.WIND: 0.0,
                WeatherCondition.HEAT: 0.0,
                WeatherCondition.COLD: 0.0
            },
            WeatherCondition.STORM: {
                WeatherCondition.CLEAR: 0.05,
                WeatherCondition.CLOUDS: 0.15,
                WeatherCondition.RAIN_LIGHT: 0.2,
                WeatherCondition.RAIN: 0.4,
                WeatherCondition.STORM: 0.15,
                WeatherCondition.FOG: 0.05,
                WeatherCondition.WIND: 0.0,
                WeatherCondition.HEAT: 0.0,
                WeatherCondition.COLD: 0.0
            },
            WeatherCondition.FOG: {
                WeatherCondition.CLEAR: 0.3,
                WeatherCondition.CLOUDS: 0.3,
                WeatherCondition.RAIN_LIGHT: 0.1,
                WeatherCondition.RAIN: 0.05,
                WeatherCondition.STORM: 0.02,
                WeatherCondition.FOG: 0.2,
                WeatherCondition.WIND: 0.02,
                WeatherCondition.HEAT: 0.01,
                WeatherCondition.COLD: 0.0
            },
            WeatherCondition.WIND: {
                WeatherCondition.CLEAR: 0.3,
                WeatherCondition.CLOUDS: 0.3,
                WeatherCondition.RAIN_LIGHT: 0.1,
                WeatherCondition.RAIN: 0.05,
                WeatherCondition.STORM: 0.02,
                WeatherCondition.FOG: 0.03,
                WeatherCondition.WIND: 0.15,
                WeatherCondition.HEAT: 0.03,
                WeatherCondition.COLD: 0.02
            },
            WeatherCondition.HEAT: {
                WeatherCondition.CLEAR: 0.4,
                WeatherCondition.CLOUDS: 0.2,
                WeatherCondition.RAIN_LIGHT: 0.05,
                WeatherCondition.RAIN: 0.02,
                WeatherCondition.STORM: 0.01,
                WeatherCondition.FOG: 0.02,
                WeatherCondition.WIND: 0.1,
                WeatherCondition.HEAT: 0.15,
                WeatherCondition.COLD: 0.05
            },
            WeatherCondition.COLD: {
                WeatherCondition.CLEAR: 0.3,
                WeatherCondition.CLOUDS: 0.25,
                WeatherCondition.RAIN_LIGHT: 0.1,
                WeatherCondition.RAIN: 0.05,
                WeatherCondition.STORM: 0.02,
                WeatherCondition.FOG: 0.1,
                WeatherCondition.WIND: 0.08,
                WeatherCondition.HEAT: 0.05,
                WeatherCondition.COLD: 0.05
            }
        }

        # Archivos de respaldo
        self.weather_backup_file = Path(config["files"]["data_directory"]) / "weather.json"
        self.weather_bursts = []
        self.current_burst_index = 0
        self.debug = bool(config.get("debug", False))

        # Cargar datos iniciales
        self._load_weather_data()

    def _load_weather_data(self) -> bool:
        """Cargar datos del clima desde la API o backup"""
        try:
            if self.debug:
                print("Cargando datos del clima...")

            # Intentar desde API (ya guarda backup automáticamente)
            if self.api_client:
                weather_data = self.api_client.get_weather()
                if weather_data:
                    self._parse_weather_data(weather_data)
                    if self.debug:
                        print("Datos del clima cargados desde API")
                    return True

        except Exception as e:
            if self.debug:
                print(f"Error al cargar clima desde API: {e}")

        # Cargar desde backup offline
        try:
            backup_data = self._load_json(str(self.weather_backup_file))
            if backup_data:
                self._parse_weather_data(backup_data)
                if self.debug:
                    print("Datos del clima cargados desde backup offline")
                return True
        except Exception as e:
            if self.debug:
                print(f"Error al cargar clima desde backup: {e}")

        # Fallback: clima por defecto
        self._create_default_weather()
        if self.debug:
            print("Usando datos de clima por defecto")
        return True

    def _parse_weather_data(self, weather_data: Dict[str, Any]):
        """Parsear datos del clima desde la API"""
        if "bursts" in weather_data:
            self.weather_bursts = weather_data["bursts"]
        else:
            self._create_default_weather()

        # Inicializar con el primer burst si existe
        if self.weather_bursts:
            first_burst = self.weather_bursts[0]
            self.current_condition = first_burst.get("condition", WeatherCondition.CLEAR)
            self.current_intensity = first_burst.get("intensity", 0.2)
            self.burst_duration = first_burst.get("duration_sec", 90.0)

        if self.debug:
            print(f"Clima inicial: {self.current_condition} (intensidad: {self.current_intensity})")

    def _create_default_weather(self):
        """Crear datos de clima por defecto"""
        # Keep your default bursts/conditions if needed, but ensure durations come from config
        self.weather_bursts = []  # optional: keep empty and rely on Markov
        self.current_condition = WeatherCondition.CLEAR
        self.current_intensity = 0.2
        # Use configured range, not a fixed 90s
        self.burst_duration = random.uniform(self.burst_duration_min, self.burst_duration_max)
        self.time_in_current_burst = 0.0

    def update(self, delta_time: float, player):
        """Actualizar el sistema de clima"""
        # Actualizar transición si está activa
        if self.transitioning:
            self.transition_progress += delta_time / self.transition_duration
            if self.transition_progress >= 1.0:
                self.transition_progress = 1.0
                self.transitioning = False
                self.previous_condition = self.current_condition
                self.previous_intensity = self.current_intensity

        # Actualizar tiempo en burst actual
        self.time_in_current_burst += delta_time

        # Verificar si debe cambiar el clima
        if self.time_in_current_burst >= self.burst_duration:
            self._transition_to_next_weather()
            self.time_in_current_burst = 0.0

        # Aplicar efectos del clima al jugador
        if player:
            self._apply_weather_effects(player)

    def _transition_to_next_weather(self):
        """Transicionar al siguiente estado climático usando Markov"""
        # Save previous state
        self.previous_condition = self.current_condition
        self.previous_intensity = self.current_intensity

        # Pick next using Markov and config-driven duration
        next_condition = self._select_next_condition()
        next_intensity = random.uniform(0.1, 1.0)
        next_duration = random.uniform(self.burst_duration_min, self.burst_duration_max)

        self.current_condition = next_condition
        self.current_intensity = next_intensity
        self.burst_duration = next_duration

        # Reset timer for the new burst
        self.time_in_current_burst = 0.0

        # Start smooth transition
        self.transitioning = True
        self.transition_progress = 0.0

        if self.debug:
            print(f"[Weather] -> {self.current_condition} "
                  f"intensity={self.current_intensity:.2f} "
                  f"duration={self.burst_duration:.1f}s")


    def _select_next_condition(self) -> str:
        probabilities = self.transition_matrix.get(self.current_condition, {})

        if not probabilities:
            return WeatherCondition.CLEAR

        # Crear lista acumulativa de probabilidades
        conditions = list(probabilities.keys())
        cumulative_probs = []
        total = 0.0

        for condition in conditions:
            total += probabilities[condition]
            cumulative_probs.append(total)

        # Seleccionar usando número aleatorio
        rand = random.random() * total

        for i, cumulative_prob in enumerate(cumulative_probs):
            if rand <= cumulative_prob:
                return conditions[i]

        return conditions[-1]  # Fallback

    def _apply_weather_effects(self, player):
        # Obtener multiplicadores interpolados durante la transición
        speed_multiplier = self._get_interpolated_speed_multiplier()
        stamina_drain = self._get_interpolated_stamina_drain()

        # Aplicar efectos al jugador
        player.apply_weather_effects(speed_multiplier, stamina_drain)

    def _get_interpolated_speed_multiplier(self) -> float:
        current_mult = self.speed_multipliers.get(self.current_condition, 1.0)

        if not self.transitioning:
            return current_mult

        previous_mult = self.speed_multipliers.get(self.previous_condition, 1.0)
        return lerp(previous_mult, current_mult, self.transition_progress)

    def _get_interpolated_stamina_drain(self) -> float:
        current_drain = self.stamina_drains.get(self.current_condition, 0.0)

        if not self.transitioning:
            return current_drain

        previous_drain = self.stamina_drains.get(self.previous_condition, 0.0)
        return lerp(previous_drain, current_drain, self.transition_progress)


    @property
    def sky_color(self) -> Tuple[int, int, int]:
        current_color = self.sky_colors.get(self.current_condition, (135, 206, 235))

        if not self.transitioning:
            return current_color

        previous_color = self.sky_colors.get(self.previous_condition, (135, 206, 235))

        # Interpolar cada componente RGB
        r = int(lerp(previous_color[0], current_color[0], self.transition_progress))
        g = int(lerp(previous_color[1], current_color[1], self.transition_progress))
        b = int(lerp(previous_color[2], current_color[2], self.transition_progress))

        return (r, g, b)

    @property
    def cloud_color(self) -> Tuple[int, int, int]:
        current_color = self.cloud_colors.get(self.current_condition, (255, 255, 255))

        if not self.transitioning:
            return current_color

        previous_color = self.cloud_colors.get(self.previous_condition, (255, 255, 255))

        # Interpolar cada componente RGB
        r = int(lerp(previous_color[0], current_color[0], self.transition_progress))
        g = int(lerp(previous_color[1], current_color[1], self.transition_progress))
        b = int(lerp(previous_color[2], current_color[2], self.transition_progress))

        return (r, g, b)

    def get_weather_info(self) -> Dict[str, Any]:
        return {
            "condition": self.current_condition,
            "intensity": self.current_intensity,
            "speed_multiplier": self._get_interpolated_speed_multiplier(),
            "stamina_drain": self._get_interpolated_stamina_drain(),
            "time_remaining": self.burst_duration - self.time_in_current_burst,
            "transitioning": self.transitioning,
            "transition_progress": self.transition_progress if self.transitioning else 0.0,
            "sky_color": self.sky_color,
            "cloud_color": self.cloud_color
        }

    def get_weather_name(self) -> str:
        """Obtener nombre legible del clima actual"""
        names = {
            WeatherCondition.CLEAR: "Despejado",
            WeatherCondition.CLOUDS: "Nublado",
            WeatherCondition.RAIN_LIGHT: "Llovizna",
            WeatherCondition.RAIN: "Lluvia",
            WeatherCondition.STORM: "Tormenta",
            WeatherCondition.FOG: "Niebla",
            WeatherCondition.WIND: "Ventoso",
            WeatherCondition.HEAT: "Calor",
            WeatherCondition.COLD: "Frío"
        }
        return names.get(self.current_condition, "Desconocido")

    def force_weather_change(self, condition: str, intensity: float = None):
        if condition in self.speed_multipliers:
            self.previous_condition = self.current_condition
            self.previous_intensity = self.current_intensity

            self.current_condition = condition
            self.current_intensity = intensity if intensity is not None else random.uniform(0.1, 1.0)
            # Use configured range instead of hardcoded 45–90
            self.burst_duration = random.uniform(self.burst_duration_min, self.burst_duration_max)

            self.transitioning = True
            self.transition_progress = 0.0
            self.time_in_current_burst = 0.0

            if self.debug:
                print(f"Clima forzado a: {condition} (intensidad: {self.current_intensity})")


    def _load_json(self, filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}