# python
# File: `player_flag.py`
from dataclasses import dataclass, field
from typing import Optional

# Lightweight fallback: avoid importing 'flags' here to prevent circular imports.
# This function simply returns a default display type; if you later need to
# resolve real metadata, call into flags module at runtime (not at import time).

def get_flag_display_type(name: str) -> str:
    """Return a default display type for a flag name without importing flags.

    Keeping this minimal avoids circular imports when `flags.py` imports
    `player_flag.get_flag_display_type` during module initialization.
    """
    return "ONOFF"


@dataclass
class PlayerFlag:
    name: str
    status: bool
    _display_type: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        if self._display_type is None:
            try:
                self._display_type = get_flag_display_type(self.name)
            except Exception:
                self._display_type = "ONOFF"

    def to_dict(self) -> dict:
        # Public serialization: only expose name + status
        return {"name": self.name, "status": bool(self.status)}

    def set(self, value: bool):
        self.status = bool(value)