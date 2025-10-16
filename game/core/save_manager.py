import pickle
import shutil
from pathlib import Path
from typing import Dict, Any


class SaveManager:
    def __init__(self, config: dict):
        self.save_directory = Path(config.get("files", {}).get("save_directory", "saves"))
        self.save_directory.mkdir(parents=True, exist_ok=True)

        self.save_file = self.save_directory / "savegame.sav"
        self.backup_file = self.save_directory / "savegame_backup.sav"
        self.autosave_file = self.save_directory / "autosave.sav"

        # Configuración
        self.max_backups = 3
        self.compress_saves = False

    def _serialize_player(self, player):
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

    def _serialize_city(self, city):
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

    def _write_binary_save_file(self, save_data: Dict[str, Any], file_path: Path) -> bool:
        """Guardar los datos en un archivo binario"""
        try:
            with open(file_path, "wb") as f:
                pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Partida guardada exitosamente en {file_path}")
            return True
        except Exception as e:
            print(f"Error al guardar archivo: {e}")
            return False

    def _create_backup(self):
        """Crear una copia de seguridad de la partida guardada"""
        try:
            if self.save_file.exists():
                shutil.copy2(self.save_file, self.backup_file)
                print(f"Copia de seguridad creada en {self.backup_file}")
        except Exception as e:
            print(f"Error al crear copia de seguridad: {e}")

    # ---- API de compatibilidad solicitada ----
    def serialize_player(self, player) -> Dict[str, Any]:
        return self._serialize_player(player)

    def serialize_city(self, city) -> Dict[str, Any]:
        return self._serialize_city(city)

    def save_to_file(self, save_data: Dict[str, Any]) -> bool:
        try:
            self._create_backup()
        except Exception:
            pass
        return self._write_binary_save_file(save_data, self.save_file)

    def load_game(self):
        """Cargar partida desde archivo"""
        try:
            with open(self.save_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error al cargar partida: {e}")
            return None

    def restore_player(self, player, data: Dict[str, Any]) -> None:
        pos = data.get("position", {}) or {}
        stats = data.get("stats", {}) or {}
        counters = data.get("counters", {}) or {}
        try:
            player.x = float(pos.get("x", getattr(player, "x", 0.0)))
            player.y = float(pos.get("y", getattr(player, "y", 0.0)))
            player.angle = float(pos.get("angle", getattr(player, "angle", 0.0)))
        except Exception:
            pass
        try:
            player.stamina = float(stats.get("stamina", getattr(player, "stamina", 100.0)))
            player.reputation = float(stats.get("reputation", getattr(player, "reputation", 70.0)))
            player.earnings = float(stats.get("earnings", getattr(player, "earnings", 0.0)))
            total_w = float(stats.get("total_weight", getattr(player, "total_weight", 0.0)))
            if hasattr(player, "set_inventory_weight"):
                player.set_inventory_weight(total_w)
            else:
                player.total_weight = total_w
            player.state = str(stats.get("state", getattr(player, "state", "normal")))
        except Exception:
            pass
        try:
            player.deliveries_completed = int(counters.get("deliveries_completed", getattr(player, "deliveries_completed", 0)))
            player.orders_cancelled = int(counters.get("orders_cancelled", getattr(player, "orders_cancelled", 0)))
            player.consecutive_on_time = int(counters.get("consecutive_on_time", getattr(player, "consecutive_on_time", 0)))
        except Exception:
            pass

    def restore_city(self, city, data: Dict[str, Any]) -> None:
        dims = (data.get("dimensions", {}) or {})
        info = (data.get("info", {}) or {})
        try:
            city.width = int(dims.get("width", getattr(city, "width", 0)))
            city.height = int(dims.get("height", getattr(city, "height", 0)))
        except Exception:
            pass
        try:
            city.version = str(info.get("version", getattr(city, "version", "1.0")))
            city.goal = float(info.get("goal", getattr(city, "goal", 0)))
        except Exception:
            pass
        try:
            tiles = data.get("tiles")
            if tiles:
                city.tiles = tiles
        except Exception:
            pass
        try:
            legend = data.get("legend")
            if legend:
                city.legend = legend
        except Exception:
            pass
