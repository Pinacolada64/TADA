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
class NewsSettings:
    """news.py / logon_events/news.py's login-time news display preferences.

    last_read: ISO datetime string of this player's own news-read cursor,
    replacing player.last_connection as the 'since' argument to
    news.is_new_since() -- last_connection is a general-purpose timestamp
    other login-sequence code also reads/writes (e.g. connect.py's
    _maybe_reset_once_per_day()), so a bug there could desync news
    display too. None means never set -- is_new_since() treats that as
    "everything currently visible is new" (matches a brand-new player).

    show_all: False (default) shows only news posted since last_read;
    True shows the full directory of currently-active news items every
    login ('prefs' command toggle N). Formerly the flat
    command_settings.news_show_all field.
    """
    last_read: Optional[str] = None
    show_all: bool = False


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
class SaySettings:
    """commands/say.py preferences.

    split: False (default) shows the whole line as one quote. True: a
    ',,' in the text splits it into a mid-sentence attribution, e.g.
    'say This is something,,up with which I will not put!' becomes
    '"This is something," you exclaim, "up with which I will not put!"'

    verb: None (default) picks the verb from trailing punctuation (says/
    asks/exclaims/mutters). Set via 'say #verb=<word>' to always use that
    word instead (e.g. verb='grumble' -> 'Rulan grumbles, "..."');
    'say #verb=off' (or '#verb=' / '#verb=none') clears it back to
    punctuation-based selection. 'say #verb' (bare) previews the current
    verb without broadcasting anything.
    """
    split: bool = False
    verb: Optional[str] = None


@dataclass
class PageSettings:
    """commands/page.py preferences, namespaced as command_settings.page.

    haven: True blocks ALL incoming pages ('page #haven' / 'page #unhaven').

    ignored_pagers: names blocked from paging this player ('page #ignore
    <name>' / 'page #unignore <name>'); stored with original casing,
    compared case-insensitively.

    last_paged: the other party in your most recent page exchange, for the
    'page #reply' / 'page #r' target token -- set both when you send a page
    and when you receive one. Original casing; None until the first page
    either way.

    history: 'page #last' recent-recipient log -- a list of
    {'name': str, 'at': isoformat-str} dicts, most recent first, de-duped
    by name, capped at 10 (commands/messaging.py's record_message_target()
    / render_last_history()).

    last_limit: how many lines 'page #last' shows, 1..10 ('page #last N'
    sets it).
    """
    haven: bool = False
    ignored_pagers: list = field(default_factory=list)
    last_paged: Optional[str] = None
    history: list = field(default_factory=list)
    last_limit: int = 5


@dataclass
class WhisperSettings:
    """commands/whisper.py preferences, namespaced as command_settings.whisper.

    last_whispered: the other party in your most recent whisper exchange,
    for the 'whisper #reply' / 'whisper #r' target token -- set both when
    you send a whisper and when you receive one. Original casing; None
    until the first whisper either way.

    history / last_limit: as PageSettings, but for 'whisper #last'.
    """
    last_whispered: Optional[str] = None
    history: list = field(default_factory=list)
    last_limit: int = 5


@dataclass
class CommandSettings:
    """Player-controlled command preferences."""
    whereat_hidden: bool = False
    # Named groups for whisper/page: group_name (lower) → list of player names
    groups: dict = field(default_factory=dict)
    # PAGE command preferences: haven, ignored_pagers, #reply target,
    # #last history/limit (commands/page.py). Was a set of flat
    # CommandSettings fields (haven, ignored_pagers) -- from_dict() still
    # reads those from older save files.
    page: PageSettings = field(default_factory=PageSettings)
    # WHISPER command preferences: #reply target, #last history/limit
    # (commands/whisper.py).
    whisper: WhisperSettings = field(default_factory=WhisperSettings)
    # Tip-of-the-day cycling/display preference (commands/tips.py, tips.py)
    tips: TipsSettings = field(default_factory=TipsSettings)
    # Threaded message board preferences (board.py, commands/board.py)
    board: BoardSettings = field(default_factory=BoardSettings)
    # Login-time news display cursor (news.py, commands/connect.py)
    news: NewsSettings = field(default_factory=NewsSettings)
    # Saved teleport destinations (commands/teleport.py)
    teleport: TeleportSettings = field(default_factory=TeleportSettings)
    # False (default): bare movement letters are n/s/e/w (compass).
    # True: w/a/s/d instead, mapped to north/west/south/east (commands/movement.py).
    wasd_movement: bool = False
    # 'say' preferences: comma-split dialogue attribution, custom verb
    # override (commands/say.py)
    say: SaySettings = field(default_factory=SaySettings)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CommandSettings':
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        tips_data = known.pop('tips', None)
        board_data = known.pop('board', None)
        news_data = known.pop('news', None)
        teleport_data = known.pop('teleport', None)
        say_data = known.pop('say', None)
        page_data = known.pop('page', None)
        whisper_data = known.pop('whisper', None)
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
        if isinstance(news_data, dict):
            instance.news = NewsSettings(**{
                k: v for k, v in news_data.items()
                if k in NewsSettings.__dataclass_fields__
            })
        if isinstance(teleport_data, dict):
            # JSON round-trips tuples as lists -- convert (level, room)
            # pairs back to tuples so callers get consistent types.
            destinations = teleport_data.get('destinations') or {}
            instance.teleport = TeleportSettings(
                destinations={k: tuple(v) for k, v in destinations.items()}
            )
        if isinstance(say_data, dict):
            instance.say = SaySettings(**{
                k: v for k, v in say_data.items()
                if k in SaySettings.__dataclass_fields__
            })
        if isinstance(page_data, dict):
            instance.page = PageSettings(**{
                k: v for k, v in page_data.items()
                if k in PageSettings.__dataclass_fields__
            })
        else:
            # Back-compat: 'haven' and 'ignored_pagers' used to be flat
            # CommandSettings fields before the command_settings.page
            # namespace existed -- fold an older save file's values in.
            legacy = {}
            if 'haven' in data:
                legacy['haven'] = data['haven']
            if 'ignored_pagers' in data:
                legacy['ignored_pagers'] = list(data['ignored_pagers'] or [])
            if legacy:
                instance.page = PageSettings(**legacy)
        if isinstance(whisper_data, dict):
            instance.whisper = WhisperSettings(**{
                k: v for k, v in whisper_data.items()
                if k in WhisperSettings.__dataclass_fields__
            })
        return instance
