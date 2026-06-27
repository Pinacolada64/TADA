from dataclasses import dataclass, field
from server.base_classes import PlayerStat, Gender

@dataclass
class Player:
    name: str = None
    stats: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    silver: int = 0
    gender: Gender = Gender.MALE

def set_up_flags():
    return {}

def set_up_silver():
    return 0

__all__ = ['Player', 'set_up_flags', 'set_up_silver']

