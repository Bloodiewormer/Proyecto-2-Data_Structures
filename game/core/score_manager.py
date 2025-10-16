from __future__ import annotations
import os
import json
from typing import Any, List, Dict


class ScoreManager:
    def __init__(self, files_conf: Dict[str, Any], filename: str = "scores.json"):
        self.save_dir = files_conf.get("save_directory", "saves")
        os.makedirs(self.save_dir, exist_ok=True)
        self.filepath = os.path.join(self.save_dir, filename)

    def calculate_score(
            self,
            player,
            time_remaining: float,
            time_limit: float,
            victory: bool,
            play_time_sec: float,
    ) -> Dict[str, Any]:
        from datetime import datetime
        earnings = float(getattr(player, "earnings", 0.0))
        reputation = float(getattr(player, "reputation", 0.0))
        cancels = int(getattr(player, "orders_cancelled", 0))
        deliveries = int(getattr(player, "deliveries_completed", 0))

        # Multiplicador por reputación
        if reputation >= 90:
            pay_mult = 1.10
        elif reputation >= 80:
            pay_mult = 1.05
        else:
            pay_mult = 1.00

        score_base = int(round(earnings * pay_mult))

        time_ratio = (time_remaining / time_limit) if time_limit > 0 else 0.0
        if victory and time_ratio >= 0.20:
            # Bonus = 15% del score_base
            bonus_time = int(round(score_base * 0.15))
        else:
            bonus_time = 0

        # Penalización por cancelaciones (simple)
        penalty_per_cancel = 25
        penalties = cancels * penalty_per_cancel

        final_score = max(0, score_base + bonus_time - penalties)

        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "victory": bool(victory),
            "score": int(final_score),
            "score_base": int(score_base),
            "pay_mult": float(pay_mult),
            "bonus_time": int(bonus_time),
            "penalties": int(penalties),
            "earnings": int(round(earnings)),
            "reputation": int(round(reputation)),
            "orders_cancelled": cancels,
            "deliveries_completed": deliveries,
            "time_remaining": int(round(time_remaining)),
            "time_limit": int(round(time_limit)),
            "play_time_sec": int(round(play_time_sec)),
        }
        return entry

    def load_leaderboard(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.filepath):
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return sorted(data, key=lambda x: int(x.get("score", 0)), reverse=True)
        except Exception:
            pass
        return []

    def save_leaderboard(self, entries: List[Dict[str, Any]]) -> None:
        entries_sorted = sorted(entries, key=lambda x: int(x.get("score", 0)), reverse=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(entries_sorted, f, ensure_ascii=False, indent=2)

    def add_score(self, entry: Dict[str, Any], keep_top: int = 50) -> List[Dict[str, Any]]:
        leaderboard = self.load_leaderboard()
        leaderboard.append(entry)
        leaderboard.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
        if keep_top and keep_top > 0:
            leaderboard = leaderboard[:keep_top]
        self.save_leaderboard(leaderboard)
        return leaderboard