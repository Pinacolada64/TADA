"""
Server configuration module.
"""
import json
from pathlib import Path
from typing import Any, Dict, NamedTuple


class SettingInfo(NamedTuple):
    """One SETTINGS_METADATA entry: value type, admin-facing description,
    and a human-readable display label (Ryan: map the raw snake_case key
    to a proper string for display -- 'victory_item_number' shows as
    'Victory Item', not the bare key)."""
    type: type
    description: str
    label: str


# key -> SettingInfo. Shared metadata so any editor -- the live in-game
# admin command (commands/config.py) or the offline setup script
# (setup/server_setup.py) -- lists/validates/labels the exact same
# settings instead of each hardcoding its own subset. Order here is
# display order. The key itself is still what's actually typed (e.g.
# `config victory_item_number 6`) -- .label is display-only.
SETTINGS_METADATA: Dict[str, SettingInfo] = {
    'game_name': SettingInfo(str, "This game's display name (SPUR.CONTROL.S config2).", 'Game Name'),
    'session_time_limit_minutes': SettingInfo(
        int, 'Per-session time limit in minutes, 0-90, 0=unlimited '
             '(SPUR.CONTROL.S time.set). Same budget the Dusk warning '
             'counts down -- setting this alone does not yet enforce a cutoff.',
        'Session Time Limit',
    ),
    'victory_type': SettingInfo(
        str, "What escaping via the level 6 ladder up (room 117, "
             "\"Shimmering Portal\") requires to win: 'gold', 'item', or "
             "'both' (SPUR.CONTROL.S object label). See victory.py for the "
             "full win check.",
        'Victory Type',
    ),
    'victory_gold_amount': SettingInfo(
        int, "Silver required in hand to win, when victory_type is 'gold' or 'both'.",
        'Victory Gold Amount',
    ),
    'victory_item_number': SettingInfo(
        int, "objects.json Treasure item number required to win, when victory_type is 'item' or 'both'; 0 = none set.",
        'Victory Item',
    ),
    'dwarf_silver': SettingInfo(
        int, 'Silver The Dwarf (tips.txt) has stolen so far, server-wide. Awarded in full to whoever kills him.',
        "Dwarf's Silver",
    ),
    'dwarf_move_interval_minutes': SettingInfo(
        int, 'Minutes between the Dwarf relocating to a new random level-1 room '
             '(encounters/dwarf.py). Not part of original SPUR -- there he never '
             'moves once placed -- added so he\'s a moving target, not a campable fix.',
        'Dwarf Move Interval',
    ),
    'require_invites': SettingInfo(bool, 'Whether invites are required for new-player registration.', 'Require Invites'),
    'invite_expiry_days': SettingInfo(int, 'Days until an issued invite expires.', 'Invite Expiry Days'),
    'max_players': SettingInfo(int, 'Maximum simultaneous connected players.', 'Max Players'),
    'ansi_port': SettingInfo(
        int, 'Listen port for the JSON/ANSI wire protocol (Python client, telnet-style terminals). Changing this has no effect until the server restarts.',
        'ANSI Port',
    ),
    'petscii_port': SettingInfo(
        int, 'Listen port for raw PETSCII byte connections (Commodore 64/128 clients). Changing this has no effect until the server restarts.',
        'PETSCII Port',
    ),
    'host': SettingInfo(
        str, 'Server listen host/interface, shared by both ports. Changing this has no effect until the server restarts.',
        'Host',
    ),
    'server_timezone': SettingInfo(
        str, "IANA zone name (e.g. 'America/New_York') the server's own "
             "timestamps (player.last_connection, etc. -- stored as naive "
             "datetime.now()) are considered to be in. Blank means "
             "\"whatever timezone the server process's OS is set to\" -- "
             "the same behavior as before this setting existed. This is "
             "what PREFS 'Z' Timezone's 'Server Local' option actually "
             "means for each player; see formatting.format_player_datetime().",
        'Server Timezone',
    ),
}


def setting_label(key: str) -> str:
    """Display label for *key*, falling back to a Title Case guess
    (underscores -> spaces) for anything missing from SETTINGS_METADATA
    -- shouldn't normally happen, but keeps callers crash-free."""
    info = SETTINGS_METADATA.get(key)
    if info is not None:
        return info.label
    return key.replace('_', ' ').title()


def format_value(value: Any) -> str:
    """Render a config value for display (On/Off for bools, str() otherwise)."""
    if isinstance(value, bool):
        return 'On' if value else 'Off'
    return str(value)


def parse_value(key: str, raw: str) -> Any:
    """Parse a raw string into the type SETTINGS_METADATA declares for
    *key*. Raises ValueError with a player/sysop-facing message on a bad
    value; callers don't need to add their own type-error text."""
    value_type = SETTINGS_METADATA[key].type
    if value_type is bool:
        if raw.lower() in ('on', 'true', 'yes', '1'):
            return True
        if raw.lower() in ('off', 'false', 'no', '0'):
            return False
        raise ValueError(f"'{key}' expects on/off, not '{raw}'")
    if value_type is int:
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"'{key}' expects a whole number, not '{raw}'")
    return raw


def resolve_key(partial: str) -> tuple:
    """Resolve a (possibly abbreviated) setting name against
    SETTINGS_METADATA.

    Returns (matched_key, candidates):
      - Exact match: (key, [key]).
      - Unique prefix match (case-insensitive): (key, [key]) -- e.g.
        'victory' expands to 'victory_type' only if that's the sole
        setting starting with 'victory'.
      - Ambiguous prefix (multiple settings share it, e.g. 'victory_'
        alone would match all three victory_* keys): (None, candidates)
        so the caller can list them and ask the admin to be more specific.
      - No match at all: (None, []).
    """
    if partial in SETTINGS_METADATA:
        return partial, [partial]
    partial_lower = partial.lower()
    candidates = [k for k in SETTINGS_METADATA if k.lower().startswith(partial_lower)]
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


class ServerConfig:
    """
    Manages server configuration including optional features like invites.
    """
    _instance = None
    # Anchored to config.py's own location, not the process's cwd -- a
    # bare relative Path('server_config.json') writes wherever the
    # process happened to be launched from, which for setup/
    # server_setup.py (runnable from server/, the repo root, or anywhere
    # else -- see that script's own sys.path fix) meant a stray
    # server_config.json could land somewhere other than server/. Found
    # live via a test launched with cwd=repo root.
    _config_file = Path(__file__).resolve().parent / 'server_config.json'
    _default_config = {
        'require_invites': True,  # Whether invites are required for registration
        'invite_expiry_days': 7,  # Number of days until an invite expires
        'max_players': 100,       # Maximum number of players
        # Two separate listeners, matching simple_server.py's Server class
        # (DEFAULT_PORT/PETSCII_PORT): ANSI/JSON (Python client, telnet-
        # style terminals) and raw PETSCII bytes (Commodore 64/128) are
        # genuinely different wire protocols on different ports, not one
        # generic "port" -- the previous single 'port' key (defaulting to
        # 5001, which didn't even match simple_server.py's real 34083
        # default) was never actually wired to the running server at all.
        'ansi_port': 34083,
        'petscii_port': 34064,
        'host': 'localhost',      # Server host, shared by both listeners
        # The Dwarf (tips.txt / MECHANICS.md "The Dwarf" -- a single,
        # server-wide NPC on a fixed level-1 room who steals silver from
        # every player until killed; killing him awards ALL of it at once).
        # Server-wide, not per-player, so it belongs here rather than on
        # any one Player -- commands/stats.py reads it via this config
        # instead of a (per-player, and thus wrong) PlayerMoneyTypes slot.
        'dwarf_silver': 0,
        'dwarf_move_interval_minutes': 15,

        # --- SPUR.CONTROL.S game configuration (SysOp "config"/"object"/
        # "time.set" labels) -- the handful of settings there that are
        # genuinely simple server-wide config, as opposed to the bulk of
        # that file (monster/weapon/item/room/level editors), which are
        # separate full admin tools, not config.py's concern.
        'game_name': 'The Land of Spur',  # config2's "Enter the name of your game"
        # time.set: per-session time limit in minutes, 0-90, 0=unlimited.
        # Same "ticks" budget the already-implemented Dusk warning counts
        # down to zero (SPUR.COMBAT.S:11, MECHANICS.md's "Dusk warning") --
        # this is the admin-configurable length of that budget. Storing the
        # setting here doesn't by itself enforce a cutoff; see
        # session_time_limit_minutes' docstring.
        'session_time_limit_minutes': 0,
        # object label: what "winning" requires when a player escapes via
        # the level 6 ladder up (room 117, "Shimmering Portal" -- see
        # victory.py). SPUR's go=1/2/3 -- victory_type is one of
        # "gold", "item", "both". victory_item_number is an objects.json
        # Treasure item number (0 = none set); SPUR's chk.obj refused to
        # let the SysOp pick anything literally named JEWEL/DIAMOND/GOLD/
        # SILVER/COIN (too generic/ambiguous with ordinary loot) -- worth
        # enforcing the same rule wherever an admin command ends up setting
        # this, not just here.
        'victory_type': 'gold',
        'victory_gold_amount': 5000,
        'victory_item_number': 0,

        # Blank = "whatever timezone the server process's OS is set to"
        # (unchanged behavior). See SETTINGS_METADATA's entry above and
        # formatting.format_player_datetime().
        'server_timezone': '',
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServerConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from file or create with defaults."""
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r') as f:
                    self._config = {**self._default_config, **json.load(f)}
            except (json.JSONDecodeError, OSError):
                self._config = self._default_config.copy()
                self._save_config()
        else:
            self._config = self._default_config.copy()
            self._save_config()

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._config, f, indent=4)
        except OSError as e:
            print(f"Warning: Could not save server config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save to file."""
        if key in self._default_config:
            self._config[key] = value
            self._save_config()
        else:
            raise KeyError(f"Invalid config key: {key}")

    def set_validated(self, key: str, value: Any) -> None:
        """Set a value by SETTINGS_METADATA key, going through this
        class's own @property setter when one exists (e.g. victory_type's
        validation, session_time_limit_minutes' clamping) and falling back
        to set() otherwise.

        A plain setattr(config, key, value) is NOT safe for keys without a
        dedicated @property (port, host, max_players, invite_expiry_days)
        -- Python allows arbitrary attribute assignment on any object, so
        it would silently create a stray instance attribute instead of
        updating self._config / server_config.json at all. Found live via
        commands/config.py's 'config port 9999' reporting success while
        the value never actually changed.
        """
        if isinstance(getattr(type(self), key, None), property):
            setattr(self, key, value)
        else:
            self.set(key, value)

    @property
    def require_invites(self) -> bool:
        """Whether invites are required for registration."""
        return self.get('require_invites', True)

    @require_invites.setter
    def require_invites(self, value: bool) -> None:
        """Set whether invites are required for registration."""
        self.set('require_invites', bool(value))

    @property
    def dwarf_silver(self) -> int:
        """Silver The Dwarf has stolen so far, server-wide (see
        _default_config's comment). Awarded in full to whoever kills him."""
        return int(self.get('dwarf_silver', 0))

    @dwarf_silver.setter
    def dwarf_silver(self, value: int) -> None:
        self.set('dwarf_silver', int(value))

    @property
    def dwarf_move_interval_minutes(self) -> int:
        """Minutes between the Dwarf relocating to a new level-1 room
        (encounters/dwarf.py's maybe_relocate())."""
        return int(self.get('dwarf_move_interval_minutes', 15))

    @dwarf_move_interval_minutes.setter
    def dwarf_move_interval_minutes(self, value: int) -> None:
        self.set('dwarf_move_interval_minutes', max(1, int(value)))

    @property
    def game_name(self) -> str:
        """Display name for this game instance (SPUR.CONTROL.S config2)."""
        return str(self.get('game_name', 'The Land of Spur'))

    @game_name.setter
    def game_name(self, value: str) -> None:
        self.set('game_name', str(value))

    @property
    def session_time_limit_minutes(self) -> int:
        """Per-session time limit in minutes (SPUR.CONTROL.S time.set),
        0-90, 0 meaning unlimited. Same budget the Dusk warning counts down
        (MECHANICS.md's "Dusk warning", SPUR.COMBAT.S:11) -- this is only
        the configured length of it; nothing currently reads this value to
        actually disconnect or restrict a player at the limit."""
        return int(self.get('session_time_limit_minutes', 0))

    @session_time_limit_minutes.setter
    def session_time_limit_minutes(self, value: int) -> None:
        value = max(0, min(90, int(value)))
        self.set('session_time_limit_minutes', value)

    @property
    def victory_type(self) -> str:
        """What escaping via the level 6 ladder up (room 117, "Shimmering
        Portal") requires to count as a win: 'gold' (victory_gold_amount
        in hand), 'item' (carrying victory_item_number), or 'both'
        (SPUR.CONTROL.S's object label, go=1/2/3). See victory.py for the
        full win check."""
        return str(self.get('victory_type', 'gold'))

    @victory_type.setter
    def victory_type(self, value: str) -> None:
        if value not in ('gold', 'item', 'both'):
            raise ValueError("victory_type must be 'gold', 'item', or 'both'")
        self.set('victory_type', value)

    @property
    def victory_gold_amount(self) -> int:
        """Silver required in hand to win, when victory_type is 'gold' or
        'both' (SPUR's oh/ol, here as a single amount)."""
        return int(self.get('victory_gold_amount', 5000))

    @victory_gold_amount.setter
    def victory_gold_amount(self, value: int) -> None:
        self.set('victory_gold_amount', max(0, int(value)))

    @property
    def victory_item_number(self) -> int:
        """objects.json Treasure item number required to win, when
        victory_type is 'item' or 'both' (SPUR's og); 0 = none set."""
        return int(self.get('victory_item_number', 0))

    @victory_item_number.setter
    def victory_item_number(self, value: int) -> None:
        self.set('victory_item_number', max(0, int(value)))

    @property
    def ansi_port(self) -> int:
        """Listen port for the JSON/ANSI wire protocol (simple_server.py's
        DEFAULT_PORT). Changing this has no effect until the server
        restarts."""
        return int(self.get('ansi_port', 34083))

    @ansi_port.setter
    def ansi_port(self, value: int) -> None:
        self.set('ansi_port', int(value))

    @property
    def petscii_port(self) -> int:
        """Listen port for raw PETSCII byte connections (simple_server.py's
        PETSCII_PORT). Changing this has no effect until the server
        restarts."""
        return int(self.get('petscii_port', 34064))

    @petscii_port.setter
    def petscii_port(self, value: int) -> None:
        self.set('petscii_port', int(value))

    @property
    def server_timezone(self) -> str:
        """IANA zone name the server's own naive timestamps are considered
        to be in, or '' for "whatever the OS is set to" (see
        SETTINGS_METADATA's entry and formatting.format_player_datetime())."""
        return str(self.get('server_timezone', '') or '')

    @server_timezone.setter
    def server_timezone(self, value: str) -> None:
        value = (value or '').strip()
        if value:
            import zoneinfo
            if value not in zoneinfo.available_timezones():
                raise ValueError(f"'{value}' isn't a recognized IANA timezone name.")
        self.set('server_timezone', value)

# Global instance
config = ServerConfig()
