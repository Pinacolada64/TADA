"""command_settings.py — Per-player command preference settings.

Stored on the player as player.command_settings and persisted with the save file.
Commands read and write fields here instead of using PlayerFlags for preferences
that are player-controlled options rather than game state.

Usage::

    from command_settings import CommandSettings

    # In Player.__init__:
    self.command_settings = CommandSettings()

    # In a command:
    ctx.player.command_settings.whereat_hidden = True
"""
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class TipsSettings:
    """commands/tips.py preferences -- see tips.py's next_tip().

    enabled: whether a tip is shown automatically at login
    (commands/connect.py's _login_tip_lines()); 'tips #on'/'tips #off'
    toggle this. tip_number: 1-based index of the last tip shown,
    persisted so 'tips' (bare) and the login display both advance the
    same cursor instead of repeating.
    """
    enabled: bool = True
    tip_number: int = 0


@dataclass
class BoardSettings:
    """board.py / commands/board.py preferences.

    last_date: ISO date string ('YYYY-MM-DD') marking the player's own
    "read new messages" threshold -- only 'board ld' moves this forward,
    'board rn' just reads against whatever's currently set and never
    advances it on its own. None means never set -- board.is_new_since()
    treats that as "everything is new".
    """
    last_date: Optional[str] = None


@dataclass
class TeleportSettings:
    """commands/teleport.py preferences.

    destinations: name (as typed with '#learn') -> (level, room) tuple.
    'teleport #learn <name>' saves the player's current location under
    that name; bare 'teleport' lists saved destinations; 'teleport <name>'
    (exact match, case-insensitive) jumps straight there, ahead of the
    numeric-room and room-name-substring-search fallbacks.
    """
    destinations: dict = field(default_factory=dict)


@dataclass
class CommandSettings:
    """Player-controlled command preferences."""
    whereat_hidden: bool = False
    # Named groups for whisper/page: group_name (lower) → list of player names
    groups: dict = field(default_factory=dict)
    # False (default): show only news posted since the player's last login.
    # True: show the full directory of currently-active news items every login.
    news_show_all: bool = False
    # PAGE command preferences (commands/page.py)
    # True: block ALL incoming pages ('page #haven' / 'page #unhaven').
    haven: bool = False
    # Names blocked from paging this player ('page #ignore <name>' /
    # 'page #unignore <name>'); stored with original casing, compared
    # case-insensitively.
    ignored_pagers: list = field(default_factory=list)
    # Tip-of-the-day cycling/display preference (commands/tips.py, tips.py)
    tips: TipsSettings = field(default_factory=TipsSettings)
    # Threaded message board preferences (board.py, commands/board.py)
    board: BoardSettings = field(default_factory=BoardSettings)
    # Saved teleport destinations (commands/teleport.py)
    teleport: TeleportSettings = field(default_factory=TeleportSettings)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CommandSettings':
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        tips_data = known.pop('tips', None)
        board_data = known.pop('board', None)
        teleport_data = known.pop('teleport', None)
        instance = cls(**known)
        if isinstance(tips_data, dict):
            instance.tips = TipsSettings(**{
                k: v for k, v in tips_data.items()
                if k in TipsSettings.__dataclass_fields__
            })
        if isinstance(board_data, dict):
            instance.board = BoardSettings(**{
                k: v for k, v in board_data.items()
                if k in BoardSettings.__dataclass_fields__
            })
        if isinstance(teleport_data, dict):
            # JSON round-trips tuples as lists -- convert (level, room)
            # pairs back to tuples so callers get consistent types.
            destinations = teleport_data.get('destinations') or {}
            instance.teleport = TeleportSettings(
                destinations={k: tuple(v) for k, v in destinations.items()}
            )
        return instance
