import arcade
import os
from typing import Optional

class AudioManager:
    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio", {})
        self.debug = bool(config.get("debug", False))

        self.music_volume = float(self.audio_config.get("music_volume", 1.0)) # 0.0 to 1.0

        self.current_music: Optional[arcade.Sound] = None
        self.music_player = None
        self.music_cache = {}

        if self.debug:
            print(f"AudioManager inicializado - Volumen: {self.music_volume * 100:.0f}%")

    def set_music_volume(self, volume_percent: float):
        self.music_volume = max(0.0, min(1.0, volume_percent / 100.0))

        if self.music_player:
            try:
                self.music_player.volume = self.music_volume
            except:
                pass

        self.config.setdefault("audio", {})["music_volume"] = self.music_volume
        if self.debug:
            print(f"Volumen de música: {self.music_volume * 100:.0f}%")

    def get_music_volume_percent(self) -> float:
        return self.music_volume * 100.0

    def play_music(self, music_path: str, loop: bool = True):
        """Soporta OGG y MP3"""
        try:
            if not os.path.exists(music_path):
                if self.debug:
                    print(f" Archivo de música no encontrado: {music_path}")
                return

            self.stop_music()

            if music_path not in self.music_cache:
                if self.debug:
                    print(f"Cargando música: {music_path}")
                self.music_cache[music_path] = arcade.load_sound(music_path)

            self.current_music = self.music_cache[music_path]

            self.music_player = self.current_music.play(
                volume=self.music_volume,
                loop=loop
            )

            if self.debug:
                print(f"Reproduciendo: {os.path.basename(music_path)} (vol: {self.music_volume * 100:.0f}%)")

        except Exception as e:
            if self.debug:
                print(f" Error al reproducir música {music_path}: {e}")

    def stop_music(self):
        if self.music_player:
            try:
                self.music_player.pause()
                self.music_player = None
            except:
                pass

    def pause_music(self):
        if self.music_player:
            try:
                self.music_player.pause()
            except:
                pass

    def resume_music(self):
        if self.music_player:
            try:
                self.music_player.play()
            except:
                pass

    def cleanup(self):
        self.stop_music()
        self.music_cache.clear()