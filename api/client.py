import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from .cache import APICache

class APIClient:
    def __init__(self, config: Dict[str, Any]):

        self.base_url = config.get("base_url", "")
        self.timeout = config.get("timeout", 10)
        self.cache_enabled = config.get("cache_enabled", True)

        # Inicializar caché si está habilitado
        if self.cache_enabled:
            cache_dir = config.get("cache_directory", "api_cache")
            self.cache = APICache(cache_dir)
        else:
            self.cache = None

        # Session para reutilizar conexiones
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CourierQuest/1.0',
            'Accept': 'application/json'
        })

        # Estado de conexión
        self.is_online = True
        self.last_connection_check = None
        self.connection_check_interval = timedelta(minutes=5)

    def get_map(self) -> Optional[Dict[str, Any]]:
        return self._make_request("/city/map", "map")

    def get_orders(self) -> Optional[Dict[str, Any]]:
        return self._make_request("/city/jobs", "orders")

    def get_weather(self) -> Optional[Dict[str, Any]]:
        return self._make_request("/city/weather", "weather")

    def _make_request(self, endpoint: str, cache_key: str) -> Optional[Dict[str, Any]]:
        url = self.base_url + endpoint

        try:
            if not self._check_connection():
                return self._get_from_cache_or_backup(cache_key)

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Guardar en caché
            if self.cache:
                self.cache.save(cache_key, data)

            # NUEVO: Guardar como backup offline
            self._save_backup(cache_key, data)

            self.is_online = True
            print(f"Datos obtenidos desde API: {endpoint}")
            return data

        except requests.exceptions.RequestException as e:
            print(f"Error en petición API {endpoint}: {e}")
            self.is_online = False
            return self._get_from_cache_or_backup(cache_key)

        except json.JSONDecodeError as e:
            print(f"Error al decodificar JSON desde {endpoint}: {e}")
            return self._get_from_cache_or_backup(cache_key)

    def _save_backup(self, cache_key: str, data: Dict[str, Any]):
        """Guardar backup offline en data/"""
        backup_files = {
            "map": "data/ciudad.json",
            "orders": "data/pedidos.json",
            "weather": "data/weather.json"
        }

        backup_file = backup_files.get(cache_key)
        if backup_file:
            try:
                Path(backup_file).parent.mkdir(parents=True, exist_ok=True)
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error al guardar backup {backup_file}: {e}")

    def _check_connection(self) -> bool:
        now = datetime.now()

        # Verificar si es necesario comprobar conexión
        if (self.last_connection_check and
                now - self.last_connection_check < self.connection_check_interval):
            return self.is_online

        self.last_connection_check = now

        try:
            # Hacer un ping simple al servidor
            response = self.session.get(
                f"{self.base_url}/docs",
                timeout=5
            )
            self.is_online = response.status_code < 500

        except requests.exceptions.RequestException:
            self.is_online = False

        return self.is_online

    def _get_from_cache_or_backup(self, cache_key: str) -> Optional[Dict[str, Any]]:
        # Intentar obtener desde caché
        if self.cache:
            cached_data = self.cache.load(cache_key)
            if cached_data:
                print(f"Datos obtenidos desde caché: {cache_key}")
                return cached_data

        # Intentar cargar desde archivos de respaldo locales
        backup_files = {
            "map": "data/ciudad.json",
            "orders": "data/pedidos.json",
            "weather": "data/weather.json"
        }

        backup_file = backup_files.get(cache_key)
        if backup_file:
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"Datos obtenidos desde archivo de respaldo: {backup_file}")
                return data
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error al cargar archivo de respaldo {backup_file}: {e}")

        print(f"No se pudieron obtener datos para {cache_key}")
        return None

    def test_connection(self) -> bool:
        try:
            response = self.session.get(
                f"{self.base_url}/docs",
                timeout=self.timeout
            )
            return response.status_code < 500

        except requests.exceptions.RequestException:
            return False

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "is_online": self.is_online,
            "base_url": self.base_url,
            "last_check": self.last_connection_check.isoformat() if self.last_connection_check else None,
            "cache_enabled": self.cache_enabled,
            "timeout": self.timeout
        }

    def clear_cache(self):
        """Limpia el caché de la API"""
        if self.cache:
            self.cache.clear()
            print("Caché de API limpiado")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cierra la session"""
        if self.session:
            self.session.close()
