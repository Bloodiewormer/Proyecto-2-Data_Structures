import arcade
import sys
from pathlib import Path

# Añadir el directorio raíz al path para imports
sys.path.append(str(Path(__file__).parent))

from game.game import CourierGame
from game.utils import load_config


def main():
    try:
        # Cargar configuración
        config = load_config()

        # Crear e iniciar el juego
        game = CourierGame(config)
        game.setup()
        arcade.run()

    except Exception as e:
        print(f"Error al inicializar el juego: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())