from __future__ import annotations
import random
from typing import Tuple
from game.IA.interfaces import StepPolicy


def _cardinal_neighbors():
    return [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _is_walkable(world, x: float, y: float) -> bool:
    city = world.city
    if x < 0 or y < 0 or x >= city.width or y >= city.height:
        return False
    return not city.is_wall(x, y)


class RandomChoicePolicy(StepPolicy):
    """
    Random choice con sesgo bajo hacia el target.
    IA Fácil: errática y torpe, pero NO camina hacia atrás.
    """

    def __init__(self, world, bias: float = 0.55):
        self.world = world
        self.bias = float(bias)
        self.debug = getattr(world, 'debug', False)
        self._decision_counter = 0

    def decide_step(self, ai: "AIPlayer") -> Tuple[int, int]:
        self._decision_counter += 1

        # 1. Obtener todos los movimientos válidos
        candidates = []
        for dx, dy in _cardinal_neighbors():
            nx, ny = ai.x + dx, ai.y + dy
            if _is_walkable(self.world, nx, ny):
                candidates.append((dx, dy))

        if not candidates:
            if self.debug:
                print(f"[Random-EASY] AI en ({ai.x:.1f},{ai.y:.1f}) sin movimientos válidos")
            return (0, 0)

        # 2. CRÍTICO: Eliminar retroceso ANTES de tomar decisiones
        last_step = getattr(ai, "_current_step", (0, 0))
        if last_step != (0, 0) and len(candidates) > 1:
            reverse = (-last_step[0], -last_step[1])
            candidates_no_reverse = [c for c in candidates if c != reverse]
            if candidates_no_reverse:
                candidates = candidates_no_reverse
                if self.debug and self._decision_counter % 30 == 0:
                    print(f"[Random-EASY] Eliminó retroceso {reverse}, quedan {len(candidates)} opciones")

        # 3. Debug cada 30 decisiones
        show_debug = self.debug and (self._decision_counter % 30 == 0)

        # 4. Intentar ir hacia el target según bias
        will_try_target = ai.current_target and random.random() < self.bias

        if will_try_target:
            tx, ty = ai.current_target

            def after_dist(step):
                dx, dy = step
                return abs((ai.x + dx) - tx) + abs((ai.y + dy) - ty)

            best_move = min(candidates, key=after_dist)

            # 70% de acierto cuando intenta
            if random.random() < 0.7:
                if show_debug:
                    dist = abs(ai.x - tx) + abs(ai.y - ty)
                    print(f"[Random-EASY] ✓ Intentó target {ai.current_target} y acertó (dist={dist:.1f})")
                return best_move
            else:
                if show_debug:
                    print(f"[Random-EASY] ❌ Intentó target pero falló")

        # 5. Movimiento aleatorio
        choice = random.choice(candidates)

        if show_debug and not will_try_target:
            print(f"[Random-EASY] 🎲 Movimiento aleatorio: {choice}")

        return choice