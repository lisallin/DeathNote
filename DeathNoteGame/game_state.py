from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class GameState:
    """
    Symbolic state for the Death Note / Kira-style suspicion game.
    """

    # How many turns (user actions) have happened so far
    turn: int = 0

    # High-level story location / phase
    location: str = "intro"

    # Suspicion meters (0–100) for different groups
    suspicion_L: int = 20          # baseline suspicion from L-like detective
    suspicion_task_force: int = 10 # police task force suspicion
    suspicion_public: int = 0      # general public / media suspicion

    # Whether the Death Note is still hidden and safe
    notebook_hidden: bool = True

    # NEW: how far along you are in investigating L's identity (0–3)
    l_investigation_progress: int = 0

    # Free-form flags you might want later
    flags: Dict[str, Any] = field(default_factory=dict)

    # Conversation / narration history
    history: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a plain dict for JSON responses.
        """
        return {
            "turn": self.turn,
            "location": self.location,
            "suspicion_L": self.suspicion_L,
            "suspicion_task_force": self.suspicion_task_force,
            "suspicion_public": self.suspicion_public,
            "notebook_hidden": self.notebook_hidden,
            "l_investigation_progress": self.l_investigation_progress,
            "flags": self.flags,
            "history": self.history,
        }
