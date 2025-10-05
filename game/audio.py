# file: game/audio.py
import arcade
import os
from typing import Optional


class AudioManager:
    """Administrador de audio del juego - Soporta OGG y MP3"""

    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio", {})

        # Volumen (0.0 a 1.0)
        self.music_volume = float(self.audio_config.get("music_volume", 1.0))

        # Música actual
        self.current_music: Optional[arcade.Sound] = None
        self.music_player = None

        # Cache de música
        self.music_cache = {}

        print(f"AudioManager inicializado - Volumen: {self.music_volume * 100:.0f}%")

    def set_music_volume(self, volume_percent: float):
        """Establecer volumen de música (0-100)"""
        self.music_volume = max(0.0, min(1.0, volume_percent / 100.0))

        # Aplicar al reproductor actual si existe
        if self.music_player:
            try:
                self.music_player.volume = self.music_volume
            except:
                pass

        # Actualizar configuración
        self.config["audio"]["music_volume"] = self.music_volume
        print(f"Volumen de música: {self.music_volume * 100:.0f}%")

    def get_music_volume_percent(self) -> float:
        """Obtener volumen actual de música en porcentaje"""
        return self.music_volume * 100.0

    def play_music(self, music_path: str, loop: bool = True):
        """Reproducir música - Soporta OGG y MP3"""
        try:
            # Verificar que el archivo existe
            if not os.path.exists(music_path):
                print(f" Archivo de música no encontrado: {music_path}")
                return

            # Detener música actual
            self.stop_music()

            # Cargar música desde cache o archivo
            if music_path not in self.music_cache:
                print(f"Cargando música: {music_path}")
                self.music_cache[music_path] = arcade.load_sound(music_path)

            self.current_music = self.music_cache[music_path]

            # Reproducir con volumen configurado
            self.music_player = self.current_music.play(
                volume=self.music_volume,
                loop=loop
            )

            print(f"🎵 Reproduciendo: {os.path.basename(music_path)} (vol: {self.music_volume * 100:.0f}%)")

        except Exception as e:
            print(f" Error al reproducir música {music_path}: {e}")

    def stop_music(self):
        """Detener música actual"""
        if self.music_player:
            try:
                self.music_player.pause()
                self.music_player = None
            except:
                pass

    def pause_music(self):
        """Pausar música"""
        if self.music_player:
            try:
                self.music_player.pause()
            except:
                pass

    def resume_music(self):
        """Reanudar música pausada"""
        if self.music_player:
            try:
                self.music_player.play()
            except:
                pass

    def cleanup(self):
        """Limpiar recursos de audio"""
        self.stop_music()
        self.music_cache.clear()