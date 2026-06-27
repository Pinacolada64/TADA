# compatibility shim for old_server package at project root
from .group_management import Group
from .player import Player, set_up_flags, set_up_silver
from .base_classes import PlayerStat, Gender

# For compatibility with modules that import `from old_server import PlayerHandler`
# but expect the implementation from server/old_server.py, try to re-export it.
try:
    # server is the package folder under the repo (server/old_server.py)
    from server.old_server import PlayerHandler, server_lock, players_in_room, players
    __all__ = ['Group', 'Player', 'set_up_flags', 'set_up_silver', 'PlayerStat', 'Gender',
               'PlayerHandler', 'server_lock', 'players_in_room', 'players']
except Exception:
    # If server.old_server is not importable in this environment, fall back to the
    # original minimal exports and don't fail the import of this shim.
    __all__ = ['Group', 'Player', 'set_up_flags', 'set_up_silver', 'PlayerStat', 'Gender']
