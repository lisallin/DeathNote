# game_state.py
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GameState:
    # Turn counter
    turn: int = 0

    # High-level location in the world
    # "intro" is only for the very first message, then we go to "home"
    location: str = "intro"

    # Suspicion meters (0–100) – all start at 0 now
    suspicion_L: int = 0
    suspicion_task_force: int = 0
    suspicion_public: int = 0

    # Notebook and investigation flags
    notebook_hidden: bool = True
    l_investigation_progress: int = 0

    # Surveillance at home
    cameras_at_home: bool = False              # L has installed cameras
    cameras_revealed_to_player: bool = False   # player has noticed them

    # Misc flags + history of messages
    flags: Dict[str, bool] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Return a JSON-friendly version of the state for the frontend."""
        return {
            "turn": self.turn,
            "location": self.location,
            "suspicion_L": self.suspicion_L,
            "suspicion_task_force": self.suspicion_task_force,
            "suspicion_public": self.suspicion_public,
            "notebook_hidden": self.notebook_hidden,
            "l_investigation_progress": self.l_investigation_progress,
            "cameras_at_home": self.cameras_at_home,
            "cameras_revealed_to_player": self.cameras_revealed_to_player,
        }
