# file: main.py
import arcade
import sys
from pathlib import Path

# Añadir el directorio raíz al path para imports
sys.path.append(str(Path(__file__).parent))

from game.game import CourierGame
from game.utils import load_config, ensure_directories


def main():
    try:
        # Cargar configuración
        config = load_config()

        # Crear directorios necesarios
        files_config = config.get("files", {})
        directories = [
            files_config.get("save_directory", "saves"),
            files_config.get("data_directory", "data"),
            files_config.get("cache_directory", "api_cache")
        ]
        ensure_directories(directories)

        # Crear e iniciar el juego
        game = CourierGame(config)
        game.setup()

        print("=== COURIER QUEST ===")
        print("Controles del juego:")
        print("- WASD o flechas: Movimiento")
        print("- ESC: Pausa/Menú")
        print("- F5: Guardado rápido")
        print("- ↑/↓ en menús: Navegar")
        print("- ENTER en menús: Seleccionar")
        print("====================")

        arcade.run()

    except Exception as e:
        print(f"Error al inicializar el juego: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())