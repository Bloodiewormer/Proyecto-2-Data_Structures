from dataclasses import dataclass


@dataclass
class GameTimer:
    """
    Maneja el tiempo total jugado y el tiempo restante del nivel.
    API simple para avanzar por delta y para guardar/cargar.
    """
    time_limit_seconds: float
    total_play_time: float = 0.0
    time_remaining: float = 0.0
    running: bool = False

    def start_new(self):
        self.total_play_time = 0.0
        self.time_remaining = float(self.time_limit_seconds)
        self.running = True

    def restore(self, play_time: float, time_remaining: float):
        self.total_play_time = float(play_time or 0.0)
        # Si no viene time_remaining, use el límite
        self.time_remaining = float(time_remaining if time_remaining is not None else self.time_limit_seconds)
        self.running = True

    def advance(self, delta_time: float):
        if not self.running:
            return
        dt = max(0.0, float(delta_time))
        self.total_play_time += dt
        self.time_remaining -= dt
        if self.time_remaining < 0:
            self.time_remaining = 0.0

    def snapshot_for_save(self) -> dict:
        return {
            "play_time": self.total_play_time,
            "time_remaining": self.time_remaining,
        }