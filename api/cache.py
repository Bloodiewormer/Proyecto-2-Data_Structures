import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class APICache:
    def __init__(self, cache_directory: str = "api_cache"):
        self.cache_dir = Path(cache_directory)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.default_ttl = timedelta(hours=1)  # Tiempo de vida por defecto
        self.max_cache_size = 100 * 1024 * 1024  # 100MB máximo

        self.ttl_config = {
            "map": timedelta(hours=24),  # Datos de mapa cambian raramente
            "orders": timedelta(minutes=30), # Pedidos pueden cambiar cada 30 minutos
            "weather": timedelta(minutes=15)   # Clima puede cambiar cada 15 minutos
        }

        self.index_file = self.cache_dir / "cache_index.json"
        self.index = self._load_index()

    def save(self, key: str, data: Dict[str, Any], ttl: Optional[timedelta] = None) -> bool:
        try:
            # Usar TTL específico o por defecto
            if ttl is None:
                ttl = self.ttl_config.get(key, self.default_ttl)

            # Crear metadata
            timestamp = datetime.now()
            expires_at = timestamp + ttl

            cache_entry = {
                "data": data,
                "timestamp": timestamp.isoformat(),
                "expires_at": expires_at.isoformat(),
                "key": key
            }

            # Guardar archivo de datos
            cache_file = self.cache_dir / f"{key}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, indent=2, ensure_ascii=False)

            # Actualizar índice
            self.index[key] = {
                "file": str(cache_file),
                "timestamp": timestamp.isoformat(),
                "expires_at": expires_at.isoformat(),
                "size": cache_file.stat().st_size
            }

            self._save_index()

            # Limpiar caché si es necesario
            self._cleanup_if_needed()

            return True

        except Exception as e:
            print(f"Error al guardar en caché {key}: {e}")
            return False

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            # Verificar si existe en el índice
            if key not in self.index:
                return None

            entry_info = self.index[key]

            # Verificar si ha expirado
            expires_at = datetime.fromisoformat(entry_info["expires_at"])
            if datetime.now() > expires_at:
                self._remove_expired_entry(key)
                return None

            # Cargar archivo
            cache_file = Path(entry_info["file"])
            if not cache_file.exists():
                # Archivo no existe, limpiar del índice
                del self.index[key]
                self._save_index()
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_entry = json.load(f)

            return cache_entry["data"]

        except Exception as e:
            print(f"Error al cargar desde caché {key}: {e}")
            return None

    def is_cached(self, key: str) -> bool:
        if key not in self.index:
            return False

        try:
            entry_info = self.index[key]
            expires_at = datetime.fromisoformat(entry_info["expires_at"])
            return datetime.now() <= expires_at

        except Exception:
            return False

    def remove(self, key: str) -> bool:
        try:
            if key in self.index:
                entry_info = self.index[key]
                cache_file = Path(entry_info["file"])

                # Eliminar archivo si existe
                if cache_file.exists():
                    cache_file.unlink()

                # Eliminar del índice
                del self.index[key]
                self._save_index()

                return True

        except Exception as e:
            print(f"Error al remover entrada de caché {key}: {e}")

        return False

    def clear(self) -> bool:
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "cache_index.json":
                    cache_file.unlink()

            self.index.clear()
            self._save_index()

            print("Caché limpiado completamente")
            return True

        except Exception as e:
            print(f"Error al limpiar caché: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        total_size = 0
        valid_entries = 0
        expired_entries = 0

        now = datetime.now()

        for key, entry_info in self.index.items():
            total_size += entry_info.get("size", 0)

            try:
                expires_at = datetime.fromisoformat(entry_info["expires_at"])
                if now <= expires_at:
                    valid_entries += 1
                else:
                    expired_entries += 1
            except Exception:
                expired_entries += 1

        return {
            "total_entries": len(self.index),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "total_size_bytes": total_size,
            "cache_directory": str(self.cache_dir),
            "max_size_bytes": self.max_cache_size
        }

    def cleanup_expired(self) -> int:
        removed_count = 0
        now = datetime.now()
        expired_keys = []

        # Encontrar claves expiradas
        for key, entry_info in self.index.items():
            try:
                expires_at = datetime.fromisoformat(entry_info["expires_at"])
                if now > expires_at:
                    expired_keys.append(key)
            except Exception:
                expired_keys.append(key)  # Entrada corrupta

        # Eliminar entradas expiradas
        for key in expired_keys:
            if self.remove(key):
                removed_count += 1

        if removed_count > 0:
            print(f"Eliminadas {removed_count} entradas expiradas del caché")

        return removed_count

    def _load_index(self) -> Dict[str, Any]:
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error al cargar índice de caché: {e}")

        return {}

    def _save_index(self) -> bool:
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error al guardar índice de caché: {e}")
            return False

    def _remove_expired_entry(self, key: str):
        try:
            if key in self.index:
                entry_info = self.index[key]
                cache_file = Path(entry_info["file"])

                if cache_file.exists():
                    cache_file.unlink()

                del self.index[key]
                self._save_index()

        except Exception as e:
            print(f"Error al remover entrada expirada {key}: {e}")

    def _cleanup_if_needed(self):
        try:
            stats = self.get_cache_stats()

            if stats["total_size_bytes"] > self.max_cache_size:
                # Primero limpiar entradas expiradas
                self.cleanup_expired()

                # Si aún excede el tamaño, eliminar entradas más antiguas
                if self.get_cache_stats()["total_size_bytes"] > self.max_cache_size:
                    self._cleanup_oldest_entries()

        except Exception as e:
            print(f"Error en limpieza automática de caché: {e}")

    def _cleanup_oldest_entries(self):
        try:
            # Ordenar entradas por timestamp (más antiguas primero)
            sorted_entries = sorted(
                self.index.items(),
                key=lambda x: x[1]["timestamp"]
            )

            for key, _ in sorted_entries:
                self.remove(key)

                # Verificar si ya estamos por debajo del límite
                stats = self.get_cache_stats()
                if stats["total_size_bytes"] <= self.max_cache_size * 0.8:  # 80% del límite
                    break

        except Exception as e:
            print(f"Error al limpiar entradas antiguas: {e}")