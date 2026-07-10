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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CommandSettings':
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
