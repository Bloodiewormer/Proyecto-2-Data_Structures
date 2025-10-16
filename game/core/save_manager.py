import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class SaveManager:
    def __init__(self, config: dict):
        self.save_directory = Path(config.get("files", {}).get("save_directory", "saves"))
        self.save_directory.mkdir(parents=True, exist_ok=True)

        self.save_file = self.save_directory / "savegame.sav"
        self.backup_file = self.save_directory / "savegame_backup.sav"
        self.autosave_file = self.save_directory / "autosave.sav"

    def serialize_player(self, player):
        """Serializar datos del jugador"""
        return {
            "position": {
                "x": float(player.x),
                "y": float(player.y),
                "angle": float(player.angle),
            },
            "stats": {
                "stamina": float(player.stamina),
                "reputation": float(player.reputation),
                "earnings": float(player.earnings),
                "total_weight": float(player.total_weight),
                "state": str(player.state),
            },
            "counters": {
                "deliveries_completed": int(player.deliveries_completed),
                "orders_cancelled": int(player.orders_cancelled),
                "consecutive_on_time": int(player.consecutive_on_time),
            },
        }

    def restore_player(self, player, player_data):
        """Restaurar datos al jugador desde el guardado"""
        try:
            # Restaurar posición
            player.x = player_data["position"]["x"]
            player.y = player_data["position"]["y"]
            player.angle = player_data["position"]["angle"]

            # Restaurar estadísticas
            player.stamina = player_data["stats"]["stamina"]
            player.reputation = player_data["stats"]["reputation"]
            player.earnings = player_data["stats"]["earnings"]
            player.total_weight = player_data["stats"]["total_weight"]
            player.state = player_data["stats"]["state"]

            # Restaurar contadores
            player.deliveries_completed = player_data["counters"]["deliveries_completed"]
            player.orders_cancelled = player_data["counters"]["orders_cancelled"]
            player.consecutive_on_time = player_data["counters"]["consecutive_on_time"]

        except KeyError as e:
            print(f"Faltan datos clave para restaurar al jugador: {e}")
            raise

    def serialize_city(self, city):
        """Serializar datos de la ciudad"""
        return {
            "dimensions": {
                "width": int(city.width),
                "height": int(city.height),
            },
            "info": {
                "version": str(city.version),
                "goal": float(city.goal),
            },
            "tiles": city.tiles,
            "legend": city.legend,
        }

    def restore_city(self, city, city_data):
        """Restaurar datos de la ciudad desde el guardado"""
        try:
            # Restaurar dimensiones
            city.width = city_data["dimensions"]["width"]
            city.height = city_data["dimensions"]["height"]

            # Restaurar información general
            city.version = city_data["info"]["version"]
            city.goal = city_data["info"]["goal"]

            # Restaurar tiles y leyenda
            city.tiles = city_data["tiles"]
            city.legend = city_data["legend"]

        except KeyError as e:
            print(f"Faltan datos clave para restaurar la ciudad: {e}")
            raise

    def save_to_file(self, save_data):
        """Guardar los datos en un archivo binario"""
        try:
            with open(self.save_file, "wb") as f:
                pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Partida guardada exitosamente en {self.save_file}")
            return True
        except Exception as e:
            print(f"Error al guardar archivo: {e}")
            return False

    def load_game(self):
        """Cargar partida desde archivo"""
        try:
            with open(self.save_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error al cargar partida: {e}")
            return None