# file: game/savemanager.py
import pickle
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


class saveManager:
    """Administrador de guardado y carga de partidas (formato binario)"""

    def __init__(self, config: Dict[str, Any]):
        # Configuración de directorios
        self.save_directory = Path(config.get("files", {}).get("save_directory", "saves"))
        self.save_directory.mkdir(parents=True, exist_ok=True)

        # Archivos principales (ahora con extensión .sav)
        self.save_file = self.save_directory / "savegame.sav"
        self.backup_file = self.save_directory / "savegame_backup.sav"
        self.autosave_file = self.save_directory / "autosave.sav"

        # Configuración
        self.max_backups = 3
        self.compress_saves = False

    def save_game(self, player, city, orders_data=None, game_stats=None) -> bool:
        """Guardar el estado completo del juego en formato binario"""
        try:
            print("Iniciando guardado de partida (binario)...")

            # Crear backup del save anterior si existe
            self._create_backup()

            # Recopilar todos los datos del juego
            save_data = self._collect_game_data(player, city, orders_data, game_stats)

            # Guardar archivo principal en binario
            success = self._write_binary_save_file(save_data, self.save_file)

            if success:
                print(f"✓ Partida guardada exitosamente en {self.save_file}")
                # Guardar copia de autosave
                self._write_binary_save_file(save_data, self.autosave_file)
            else:
                print("✗ Error al guardar la partida")

            return success

        except Exception as e:
            print(f"Error crítico al guardar partida: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_game(self) -> Optional[Dict[str, Any]]:
        """Cargar el estado del juego desde archivo binario"""
        try:
            print("Intentando cargar partida (binario)...")

            # Intentar cargar desde archivo principal
            save_data = self._load_binary_save_file(self.save_file)

            if save_data:
                print(f"✓ Partida cargada desde {self.save_file}")
                self._print_save_info(save_data)
                return save_data

            # Si falla, intentar desde backup
            print("Archivo principal no disponible, intentando backup...")
            save_data = self._load_binary_save_file(self.backup_file)

            if save_data:
                print(f"✓ Partida cargada desde backup {self.backup_file}")
                self._print_save_info(save_data)
                return save_data

            # Si falla, intentar desde autosave
            print("Backup no disponible, intentando autosave...")
            save_data = self._load_binary_save_file(self.autosave_file)

            if save_data:
                print(f"✓ Partida cargada desde autosave {self.autosave_file}")
                self._print_save_info(save_data)
                return save_data

            print("✗ No se encontraron archivos de guardado válidos")
            return None

        except Exception as e:
            print(f"Error crítico al cargar partida: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _collect_game_data(self, player, city, orders_data, game_stats) -> Dict[str, Any]:
        """Recopilar todos los datos del juego para guardar"""
        # Datos del jugador
        player_data = self._serialize_player(player)

        # Datos de la ciudad/mapa
        city_data = self._serialize_city(city)

        # Datos de pedidos/órdenes
        orders_data = orders_data or {}

        # Estadísticas del juego
        game_stats = game_stats or {}

        # Metadatos adicionales
        metadata = {
            "play_time": game_stats.get("play_time", 0),
            "level": game_stats.get("level", 1),
            "difficulty": "normal",
            "version": "1.0",
            "game_version": "1.0.0"
        }

        return {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "player": player_data,
            "city": city_data,
            "orders": orders_data,
            "game_stats": game_stats,
            "metadata": metadata
        }

    def _serialize_player(self, player) -> Dict[str, Any]:
        """Serializar datos del jugador"""
        try:
            return {
                "position": {
                    "x": float(getattr(player, "x", 0.0)),
                    "y": float(getattr(player, "y", 0.0)),
                    "angle": float(getattr(player, "angle", 0.0))
                },
                "stats": {
                    "stamina": float(getattr(player, "stamina", 100.0)),
                    "reputation": float(getattr(player, "reputation", 70.0)),
                    "earnings": float(getattr(player, "earnings", 0.0)),
                    "total_weight": float(getattr(player, "total_weight", 0.0)),
                    "state": str(getattr(player, "state", "normal"))
                },
                "counters": {
                    "deliveries_completed": int(getattr(player, "deliveries_completed", 0)),
                    "orders_cancelled": int(getattr(player, "orders_cancelled", 0)),
                    "consecutive_on_time": int(getattr(player, "consecutive_on_time", 0))
                },
                "effects": {
                    "weather_speed_multiplier": float(getattr(player, "weather_speed_multiplier", 1.0)),
                    "weather_stamina_drain": float(getattr(player, "weather_stamina_drain", 0.0))
                },
                "config": {
                    "base_speed": float(getattr(player, "base_speed", 3.0)),
                    "turn_speed": float(getattr(player, "turn_speed", 1.5)),
                    "move_speed": float(getattr(player, "move_speed", 3.0))
                },
                "undo": {
                    "stack": list(getattr(player, "undo_stack", [])),
                    "last_undo_time": float(getattr(player, "last_undo_time", 0.0)),
                    "last_undo_save_time": float(getattr(player, "last_undo_save_time", 0.0))
                }
            }
        except Exception as e:
            print(f"Error al serializar jugador: {e}")
            return {}

    def _serialize_city(self, city) -> Dict[str, Any]:
        """Serializar datos de la ciudad"""
        try:
            return {
                "dimensions": {
                    "width": int(getattr(city, "width", 30)),
                    "height": int(getattr(city, "height", 30))
                },
                "info": {
                    "version": str(getattr(city, "version", "1.0")),
                    "goal": float(getattr(city, "goal", 3000.0))
                },
                "tiles": getattr(city, "tiles", []),
                "legend": getattr(city, "legend", {})
            }
        except Exception as e:
            print(f"Error al serializar ciudad: {e}")
            return {}

    def _write_binary_save_file(self, data: Dict[str, Any], filepath: Path) -> bool:
        """Escribir datos de guardado a archivo binario"""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception as e:
            print(f"Error al escribir archivo binario {filepath}: {e}")
            return False

    def _load_binary_save_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Cargar datos de guardado desde archivo binario"""
        try:
            if not filepath.exists():
                return None

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            if not data:
                return None

            # Validar estructura básica
            if not self._validate_save_data(data):
                print(f"Archivo de guardado inválido: {filepath}")
                return None

            return data

        except Exception as e:
            print(f"Error al cargar archivo binario {filepath}: {e}")
            return None

    def _validate_save_data(self, data: Dict[str, Any]) -> bool:
        """Validar que los datos de guardado tengan la estructura correcta"""
        required_keys = ["player", "city"]

        if not all(key in data for key in required_keys):
            return False

        # Validar estructura del jugador
        player_data = data.get("player", {})
        if not isinstance(player_data.get("position"), dict):
            return False

        # Validar estructura de la ciudad
        city_data = data.get("city", {})
        if not isinstance(city_data.get("tiles"), list):
            return False

        return True

    def _create_backup(self):
        """Crear backup del archivo de guardado actual"""
        try:
            if self.save_file.exists():
                shutil.copy2(self.save_file, self.backup_file)
                print(f"Backup creado: {self.backup_file}")
        except Exception as e:
            print(f"Error al crear backup: {e}")

    def _print_save_info(self, save_data: Dict[str, Any]):
        """Imprimir información del archivo cargado"""
        timestamp = save_data.get("timestamp", "Fecha desconocida")
        player_stats = save_data.get("player", {}).get("stats", {})
        earnings = player_stats.get("earnings", 0)
        reputation = player_stats.get("reputation", 0)

        print(f"Guardado el: {timestamp}")
        print(f"Dinero: ${earnings:.0f}")
        print(f"Reputación: {reputation:.0f}")

    def restore_player(self, player, player_data: Dict[str, Any]) -> bool:
        """Restaurar el estado del jugador desde datos guardados"""
        try:
            print("Restaurando estado del jugador...")

            # Posición
            pos = player_data.get("position", {})
            player.x = float(pos.get("x", getattr(player, "x", 0.0)))
            player.y = float(pos.get("y", getattr(player, "y", 0.0)))
            player.angle = float(pos.get("angle", getattr(player, "angle", 0.0)))

            # Estadísticas
            stats = player_data.get("stats", {})
            player.stamina = float(stats.get("stamina", getattr(player, "stamina", 100.0)))
            player.reputation = float(stats.get("reputation", getattr(player, "reputation", 70.0)))
            player.earnings = float(stats.get("earnings", getattr(player, "earnings", 0.0)))
            player.total_weight = float(stats.get("total_weight", getattr(player, "total_weight", 0.0)))
            player.state = stats.get("state", getattr(player, "state", "normal"))

            # Contadores
            counters = player_data.get("counters", {})
            player.deliveries_completed = int(counters.get("deliveries_completed", 0))
            player.orders_cancelled = int(counters.get("orders_cancelled", 0))
            player.consecutive_on_time = int(counters.get("consecutive_on_time", 0))

            # Efectos de clima
            effects = player_data.get("effects", {})
            player.weather_speed_multiplier = float(effects.get("weather_speed_multiplier", 1.0))
            player.weather_stamina_drain = float(effects.get("weather_stamina_drain", 0.0))

            if "undo" in player_data:
                undo_data = player_data["undo"]

                # restaurar stack (convertir lista a deque)
                from collections import deque
                saved_stack = undo_data.get("stack", [])
                player.undo_stack = deque(
                    saved_stack,
                    maxlen=getattr(player, 'max_undo_steps', 50)
                )

                # restaurar timestamps
                player.last_undo_time = float(undo_data.get("last_undo_time", 0.0))
                player.last_undo_save_time = float(undo_data.get("last_undo_save_time", 0.0))

                print(f"stack de undo restaurado ({len(player.undo_stack)} estados)")
            print(f"Jugador restaurado en posición ({player.x:.1f}, {player.y:.1f})")
            print(f"Estadísticas: ${player.earnings:.0f}, Rep: {player.reputation:.0f}")

            return True

        except Exception as e:
            print(f"Error al restaurar jugador: {e}")
            import traceback
            traceback.print_exc()
            return False

    def restore_city(self, city, city_data: Dict[str, Any]) -> bool:
        """Restaurar el estado de la ciudad desde datos guardados"""
        try:
            print("Restaurando estado de la ciudad...")

            # Dimensiones
            dims = city_data.get("dimensions", {})
            city.width = int(dims.get("width", getattr(city, "width", 30)))
            city.height = int(dims.get("height", getattr(city, "height", 30)))

            # Información general
            info = city_data.get("info", {})
            city.version = str(info.get("version", getattr(city, "version", "1.0")))
            city.goal = float(info.get("goal", getattr(city, "goal", 3000.0)))

            # Tiles del mapa
            if "tiles" in city_data and city_data["tiles"]:
                city.tiles = city_data["tiles"]

            # Leyenda de tipos de tiles
            if "legend" in city_data and city_data["legend"]:
                city.legend = city_data["legend"]

            print(f"✓ Ciudad restaurada: {city.width}x{city.height}, Meta: ${city.goal:.0f}")

            return True

        except Exception as e:
            print(f"Error al restaurar ciudad: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_save_info(self) -> Optional[Dict[str, Any]]:
        """Obtener información básica del archivo de guardado"""
        try:
            if not self.save_file.exists():
                return None

            # Cargar datos binarios
            with open(self.save_file, 'rb') as f:
                save_data = pickle.load(f)

            if not save_data:
                return None

            metadata = save_data.get("metadata", {})
            player_stats = save_data.get("player", {}).get("stats", {})
            player_counters = save_data.get("player", {}).get("counters", {})

            return {
                "timestamp": save_data.get("timestamp", "Desconocido"),
                "play_time": metadata.get("play_time", 0),
                "level": metadata.get("level", 1),
                "player_earnings": player_stats.get("earnings", 0),
                "player_reputation": player_stats.get("reputation", 0),
                "deliveries_completed": player_counters.get("deliveries_completed", 0),
                "file_size": self.save_file.stat().st_size
            }

        except Exception as e:
            print(f"Error al obtener información de guardado: {e}")
            return None

    def delete_save(self) -> bool:
        """Eliminar archivo de guardado"""
        try:
            deleted = False

            if self.save_file.exists():
                self.save_file.unlink()
                deleted = True
                print(f"Archivo principal eliminado: {self.save_file}")

            if self.backup_file.exists():
                self.backup_file.unlink()
                deleted = True
                print(f"Backup eliminado: {self.backup_file}")

            if self.autosave_file.exists():
                self.autosave_file.unlink()
                deleted = True
                print(f"Autosave eliminado: {self.autosave_file}")

            return deleted

        except Exception as e:
            print(f"Error al eliminar archivos de guardado: {e}")
            return False

    def has_save(self) -> bool:
        """Verificar si existe un archivo de guardado válido"""
        return (self.save_file.exists() and self.save_file.stat().st_size > 0)

    def autosave(self, player, city, orders_data=None, game_stats=None) -> bool:
        """Realizar guardado automático"""
        try:
            save_data = self._collect_game_data(player, city, orders_data, game_stats)
            success = self._write_binary_save_file(save_data, self.autosave_file)

            if success:
                print("✓ Autosave completado")
            else:
                print("✗ Error en autosave")

            return success

        except Exception as e:
            print(f"Error en autosave: {e}")
            return False

    def get_all_saves(self) -> List[Dict[str, Any]]:
        """Obtener lista de todos los archivos de guardado disponibles"""
        saves = []

        # Archivo principal
        if self.save_file.exists():
            info = self.get_save_info()
            if info:
                saves.append({
                    "type": "main",
                    "file": self.save_file,
                    "info": info
                })

        # Backup
        if self.backup_file.exists():
            try:
                with open(self.backup_file, 'rb') as f:
                    backup_data = pickle.load(f)
                if backup_data:
                    saves.append({
                        "type": "backup",
                        "file": self.backup_file,
                        "timestamp": backup_data.get("timestamp", "Desconocido")
                    })
            except:
                pass

        # Autosave
        if self.autosave_file.exists():
            try:
                with open(self.autosave_file, 'rb') as f:
                    autosave_data = pickle.load(f)
                if autosave_data:
                    saves.append({
                        "type": "autosave",
                        "file": self.autosave_file,
                        "timestamp": autosave_data.get("timestamp", "Desconocido")
                    })
            except:
                pass

        return saves

    def clean_old_saves(self, keep_count: int = 5):
        """Limpiar archivos de guardado antiguos"""
        try:
            # Esta función podría expandirse para manejar múltiples saves
            # Por ahora solo mantenemos los archivos principales
            print(f"Manteniendo {keep_count} archivos de guardado más recientes")

        except Exception as e:
            print(f"Error al limpiar saves antiguos: {e}")

    def export_save(self, export_path: str) -> bool:
        """Exportar archivo de guardado a ubicación específica"""
        try:
            if not self.save_file.exists():
                print("No hay archivo de guardado para exportar")
                return False

            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(self.save_file, export_file)
            print(f"✓ Guardado exportado a: {export_file}")
            return True

        except Exception as e:
            print(f"Error al exportar guardado: {e}")
            return False

    def import_save(self, import_path: str) -> bool:
        """Importar archivo de guardado desde ubicación específica"""
        try:
            import_file = Path(import_path)

            if not import_file.exists():
                print(f"Archivo no encontrado: {import_file}")
                return False

            # Validar el archivo antes de importar
            with open(import_file, 'rb') as f:
                test_data = pickle.load(f)

            if not test_data or not self._validate_save_data(test_data):
                print("Archivo de guardado inválido")
                return False

            # Crear backup del save actual si existe
            self._create_backup()

            # Copiar archivo importado
            shutil.copy2(import_file, self.save_file)
            print(f"✓ Guardado importado desde: {import_file}")
            return True

        except Exception as e:
            print(f"Error al importar guardado: {e}")
            return False

    def get_save_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de los archivos de guardado"""
        stats = {
            "has_main_save": self.save_file.exists(),
            "has_backup": self.backup_file.exists(),
            "has_autosave": self.autosave_file.exists(),
            "total_files": 0,
            "total_size_mb": 0.0
        }

        try:
            files_to_check = [self.save_file, self.backup_file, self.autosave_file]

            for file_path in files_to_check:
                if file_path.exists():
                    stats["total_files"] += 1
                    stats["total_size_mb"] += file_path.stat().st_size / (1024 * 1024)

            stats["total_size_mb"] = round(stats["total_size_mb"], 2)

        except Exception as e:
            print(f"Error al obtener estadísticas: {e}")

        return stats