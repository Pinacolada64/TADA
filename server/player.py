import json
import logging
import os
import random
import textwrap
import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import threading

import net_common as nc
from flags import PlayerFlags
from party import Party

# Provide fallbacks for server-level globals. These modules may differ between
# server implementations; prefer `simple_server` if available, otherwise `net_server`.
try:
    import simple_server as _ss
except Exception:
    _ss = None
try:
    import net_server as _ns
except Exception:
    _ns = None

if _ss is not None:
    server_lock = getattr(_ss, 'server_lock', threading.Lock())
    room_players = getattr(_ss, 'room_players', {})
    players = getattr(_ss, 'players', {})
elif _ns is not None:
    server_lock = getattr(_ns, 'server_lock', threading.Lock())
    room_players = getattr(_ns, 'room_players', {})
    players = getattr(_ns, 'players', {})
else:
    server_lock = threading.Lock()
    room_players = {}
    players = {}

def _get_server_module():
    """Return an available server module that exposes server_lock, room_players, players.
    Prefer simple_server, then net_server, then old_server.
    """
    if _ss is not None:
        return _ss
    if _ns is not None:
        return _ns
    return None

if TYPE_CHECKING:
    import terminal
    from base_classes import (CombinationTypes, PlayerMoneyTypes, PlayerStat, Gender, compass_txts, Guild, Alignment,
    InventoryItem)
    from base_variables import STAT_DATA
    from players import Ally
    from flags import Flag, new_player_default_flags, PlayerFlags, FlagDisplayTypes
    from net_common import Message
    # from simple_server  import server_lock, room_players, players
    from tada_utilities import make_random_id
    from network_context import GameContext


def set_up_flags():
    from flags import Flag, new_player_default_flags
    # make a dict of Flag() objects
    flags = {flag_elements[0]: Flag(*flag_elements) for flag_elements in new_player_default_flags}
    return flags


def make_random_id():
    random_id = random.randint(1, 256 * 256)
    logging.debug("%i", random_id)
    return random_id


def make_random_stat():
    random_number = random.randint(1, 18)
    logging.debug("%i", random_number)
    return random_number


def set_up_client_settings():
    from terminal import ClientSettings
    return ClientSettings()


def set_up_combinations():
    from base_classes import Combination, CombinationTypes
    # Returns a dict of CombinationTypes -> Combination, e.g. {CombinationTypes.CASTLE: <40-10-05>}.
    # ELEVATOR and LOCKER are deliberately omitted here: unlike Castle, neither is known to
    # the player from the start. ELEVATOR is only generated when the SCRAP OF PAPER (item
    # #69) is READ (see commands/read.py), matching SPUR.MISC2.S's `elev` subroutine.
    # LOCKER is granted (and its combination handed over) by the locker attendant on a
    # player's first visit to the Shoppe's Private Locker -- see shoppe/locker.py.
    combinations = {combination_type: Combination(combination_type)
                     for combination_type in CombinationTypes
                     if combination_type not in (CombinationTypes.ELEVATOR, CombinationTypes.LOCKER)}
    logging.debug(combinations)
    return combinations


def set_up_rulan() -> dict:
    from base_classes import Guild
    birthday = datetime.datetime(1976, 6, 16)
    last_play_date = datetime.date.today()
    logging.info("Setting up Rulan.")
    return {'name': 'Rulan',
            'times_played': None,  # this marks a new player
            'guild': Guild.FIST,
            'birthday': birthday,
            'last_play_date': last_play_date,
            }


def set_up_silver() -> dict:
    from base_classes import PlayerMoneyTypes
    # numeric values can have underscores in them to separate thousands, trillions places in a localization-
    # agnostic way: 1_000 represents 1,000.00 or 1.000,00 depending on locale.
    # make a dict: {PlayerMoneyType.IN_BAR: 1_000, PlayerMoneyType.IN_BANK: 2_000, PlayerMoneyType.IN_HAND: 3_000}
    silver_types = {v: k * 1_000 for k, v in enumerate(PlayerMoneyTypes, start=1)}
    logging.info("%s" % silver_types)
    return silver_types


def set_up_stats() -> dict:
    from base_classes import PlayerStat
    stats = {k: make_random_stat() for k in PlayerStat}
    logging.debug("%s" % stats)
    return stats


def longest_flag_name() -> int:
    """
    Determine the length of the longest PlayerFlag string, so the calling routine
    can print the maximum number of ellipses to display (including some padding); e.g.:

    item_one......: foo
    item_two......: bar
    item_three....: baz
    """
    from flags import PlayerFlags
    return len(max([x for x in PlayerFlags], key=len)) + 4


class Player:
    """
    Attributes, flags, and other stuff about players.
    """
    """
    TODO: There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Player or Ally object if they hold it, or None if no-one holds it
    """

    def __init__(self, **kwargs):
        """this code is called when creating a new character"""
        from base_classes import Alignment, Guild, Gender, PlayerMoneyTypes
        import terminal
        """
        The point behind all this is that dataclasses can't account for unknown parameters, and I'll
        be adding attributes to the Player class definition for some time until the attributes stabilize.

        The .get() method avoids KeyErrors since it replaces missing parameters with the 2nd parameter,
        or None if not specified.
        """
        # FIXME: probably just forget this, net_server.py handles connected_users(set)
        """
        connection_id: list of CommodoreServer IDs: {'connection_id': id, 'name': 'name'}
        for k in len(connection_ids):
            if connection_id in connection_ids[1][k]:
                logging.info(f'Player.__init__: duplicate {connection_id['id']} assigned to '
                             f'{connection_ids[1][connection_id]}')
            return
        temp = {self.name, connection_id}
        connection_ids.append({'name': name, connection_id})
        logging.info(f'Player.__init__: Connections: {len(connection_ids)}, {connection_ids}')
        self.connection_id = connection_id  # 'id' shadows built-in name
        """
        self.connection_id = kwargs.get('connection_id', make_random_id())
        # keep this until I figure out where it is in net_server.py:
        self.name = kwargs.get('name', "Generic Name")

        # Personal one-line quote (60 char max) shown to other players who
        # see this player in a room (SPUR.MISC2.S:488-503's QUOTE command;
        # commands/quote.py). None/unset means "silent" -- no quote line
        # shown, matching SPUR's "is silent.." fallback rather than a
        # stored "blank" sentinel string.
        self.quote = kwargs.get('quote')

        self.gender = kwargs.get('gender', Gender.MALE)

        # creates a new stats dict for each Player, creates random stats:
        # TODO: set with Player.set_stat_absolute(PlayerStat.xyz, value)
        self.stats = kwargs.get("stats", set_up_stats())
        # flags:
        self.flags = kwargs.get('flags', set_up_flags())
        # dict of CombinationTypes -> Combination (ELEVATOR is added later, on-demand,
        # by reading the scrap of paper -- see set_up_combinations()):
        self.combinations = kwargs.get('combinations') or set_up_combinations()
        # client settings - set up some defaults
        self.client_settings = kwargs.get('client_settings', set_up_client_settings())
        # per-player command preferences (whereat visibility, etc.)
        from command_settings import CommandSettings
        _cs_raw = kwargs.get('command_settings', {})
        self.command_settings = (CommandSettings.from_dict(_cs_raw)
                                 if isinstance(_cs_raw, dict) else CommandSettings())

        self.natural_alignment = kwargs.get('natural_alignment', Alignment.NEUTRAL)
        self.current_alignment = kwargs.get('current_alignment', Alignment.NEUTRAL)

        # creates a new silver dict for each Player:
        # IN_BANK may be cleared on character death (TODO: look in TLOS source)
        # IN_BAR should be preserved after character's death (TODO: same)
        self.silver = kwargs.get('silver', set_up_silver())
        if self.silver:
            """
            >>> print(f"{PlayerMoneyTypes.IN_HAND}: {silver_types[PlayerMoneyTypes.IN_HAND]:,}")
            In hand: 1,000
            """
            silver_in_hand = self.get_silver(PlayerMoneyTypes.IN_HAND)
            logging.info("Silver in hand: %i" % silver_in_hand)

        self.times_played = kwargs.get('times_played', None)
        # last_connection helps determine whether once_per_day events should be reset, but we just care about the day
        # rolling over, not that 24 hours have passed.
        # TODO: Also in the LASTON command to show when a player was last online.
        # Player.connect() should set last_connection to datetime.now().
        # Player.disconnect() should also set last_connection to datetime.now().
        self.last_connection = kwargs.get('last_connection', datetime.datetime.now())
        """
        proposed stats:
        some (not all) other stats, still collecting them:

        special_items[
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT does not actually need to be carried around in inventory, I don't suppose, just a flag?
        """
        self.map_level = kwargs.get('map_level', 1)  # cl (current dungeon level, 1-7)
        self.xp_level = kwargs.get('xp_level', 1)  # SPUR's xp/yn (character level, from experience)
        self.map_room = kwargs.get('map_room', 1)  # cr (current room)
        self.moves_made = kwargs.get('moves_made')
        # tracks how many moves made during the game session to calculate experience points awarded at quit:
        self.moves_today = kwargs.get('moves_today', 0)
        self.birthday = kwargs.get('birthday')  # TODO: use datetime
        self.guild = kwargs.get('guild', Guild.CIVILIAN)  # [civilian | fist | sword | claw | outlaw]
        # 1       2        3       4      5       6       7         8       9
        self.char_class = kwargs.get('char_class')
        # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
        self.char_race = kwargs.get('char_race')
        # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

        from inventory import Inventory, class_inventory_limit
        _raw_inv = kwargs.get('inventory')
        _class_limit = class_inventory_limit(self.char_class)
        self.max_inventory_size: int = kwargs.get('max_inventory_size', _class_limit)
        if isinstance(_raw_inv, Inventory):
            self.inventory: Inventory = _raw_inv
        elif isinstance(_raw_inv, list):
            self.inventory = Inventory.from_json(_raw_inv, capacity=self.max_inventory_size)
        else:
            self.inventory = Inventory(capacity=self.max_inventory_size)

        # Private Shoppe locker (SPUR.MISC6.S "locker" subroutine; shoppe/locker.py).
        # None until the locker attendant sets one up on the player's first visit --
        # see set_up_combinations()'s comment on CombinationTypes.LOCKER.
        from inventory import LOCKER_CAPACITY
        _raw_locker = kwargs.get('locker')
        if isinstance(_raw_locker, Inventory):
            self.locker: Inventory = _raw_locker
        elif isinstance(_raw_locker, list):
            self.locker = Inventory.from_json(_raw_locker, capacity=LOCKER_CAPACITY)
        else:
            self.locker = None

        # combat stuff:
        self.hit_points = kwargs.get('hit_points', 10)
        # Survival: food (ps in SPUR) and drink (pe in SPUR), each 0-20.
        # Both deplete over time; starvation kills when both reach 0.
        self.food     = kwargs.get('food',     20)
        self.drink    = kwargs.get('drink',    20)
        self.poisoned = kwargs.get('poisoned', False)
        self.diseased = kwargs.get('diseased', False)
        # the lower the Honor score, the more evil the character has become.
        # TODO: look it up, but I think 1,000 honor points is equivalent to a Saintly Knight.
        self.honor = kwargs.get('honor', 1_000)

        # Vinny the Loan Shark debt tracking (t_bar_vinney.lbl / SPUR.BAR3.S)
        self.loan_amount: int = kwargs.get('loan_amount', 0)   # silver owed to Vinny
        self.loan_days:   int = kwargs.get('loan_days',   0)   # days remaining to repay

        self.shield = kwargs.get('shield')
        self.armor = kwargs.get('armor')
        # Loaded ammo state (set by USE command, consumed by combat).
        self.ammo_rounds: int = kwargs.get('ammo_rounds', 0)
        self.ammo_damage: int = kwargs.get('ammo_damage', 0)
        self.ammo_max:    int = kwargs.get('ammo_max', 0)    # vl: total rounds when loaded (recovery cap)
        self.ring_worn:  bool = kwargs.get('ring_worn', False)  # zu$[2]: ring of invisibility worn
        self.experience = kwargs.get('experience', 0)
        self.monsters_killed: list[int] = kwargs.get('monsters_killed', [])
        self.picked_up_items: list[int] = kwargs.get('picked_up_items', [])
        # Item numbers already granted their one-time +1 Wisdom bonus for
        # being read (SPUR.MISC2.S:316's `if pw<25 pw=pw+1` -- fires on
        # every consumed book there, scroll or not; this port keeps
        # non-scroll books re-readable instead of consuming them, so the
        # bonus is tracked per item instead to prevent farming it by
        # re-reading the same reference book). See commands/read.py.
        self.read_books: list[int] = kwargs.get('read_books', [])
        self.readied_weapon = None  # currently readied weapon (BaseItem or None)
        # Page messages queued while busy (currently: in combat -- see
        # commands/messaging.py's is_in_combat() and commands/page.py).
        # Flushed and shown by network_context.py's prompt() the next time
        # this player is prompted, instead of interrupting combat mid-round.
        self.pending_pages: list[str] = []
        # Battle experience per weapon type, keyed by str(id_number), value 0-99.
        # Persists independently of inventory so experience survives dropping/selling.
        self.weapon_experience: dict = kwargs.get('weapon_experience', {})
        """
        Things you can only do once per day (file_formats.txt):
        'pr'        has PRAYed once
        'pr2'       has PRAYed twice per day (only if char_class is Druid)
        'birthday'  Player's birthday is today and they've already got their birthday present
                    (prevents them from logging on multiple times per day and getting multiple presents)
        # TODO: make these Enums, finish this list
        """
        self.once_per_day = kwargs.get('once_per_day', [])
        self.last_play_date = kwargs.get('last_play_date', datetime.datetime.now())

        self.party = Party.from_json(kwargs.get('party', []))
        self.allies = kwargs.get('allies', [])

        self.guild = kwargs.get('guild', Guild.CIVILIAN)

        """
        TODO: MORE CLASSES
        combat:
            honor: int
        class Weapon:
            name: str
            percent_left: int
        class AmmoWeapon:
            ammunition_for: Weapon
            loaded_with: Ammunition
        class Ammunition:
            rounds_per_unit: int  # how many rounds

        bad_hombre_rating (BHR) is calculated from stats, not stored in player log
        """
        # using Dataclasses and updating attributes:
        # https://www.reddit.com/r/learnpython/comments/1gzmlqv/comment/lyxnpxc/

        # Wizard Glow stuff:
        # None if inactive, or non-magic user
        # != 0 is the number of rounds left, decrement at every turn
        self.wizard_glow = kwargs.get('wizard_glow')
        # Allow passing an explicit id via kwargs (e.g., player.Player(name=..., id=username)).
        self.id = kwargs.get('id', None)  # account id

        # command history:
        self.command = None
        self.previous_command = None

        # flag whether a save is required:
        self.unsaved_changes: bool = False

        # If an id was provided, attempt to load persisted player state from disk
        try:
            if self.id:
                self._load()
        except Exception:
            logging.debug('No saved player data loaded for %s' % (self.id or self.name))

        # hit_points defaulted to 0 since 62391c4 ("Updating old code - added
        # player.py"), causing _game_loop to quit the player after every command.
        # Revive anyone saved at 0 HP so they aren't permanently stuck.
        if self.hit_points <= 0:
            self.hit_points = 10

    def __str__(self):
        """print representation of Player object"""
        return f"{self.name} <Player>"

    def __repr__(self):
        return f"Player <{self.name}>"

    @property
    def is_expert(self) -> bool:
        """
        Check whether the player is in Expert Mode or not
        (more concise than "if player.query_flag(PlayerFlag.EXPERT_MODE)" all over the place)
        If so, extra prompts and information are displayed to help the player
        """
        return self.query_flag(PlayerFlags.EXPERT_MODE)

    @property
    def is_debug(self) -> bool:
        """
        Check whether the player is in Debug Mode or not:
        (same reasoning as above)
        If so, extra logging messages are displayed to help the programmer"""
        return self.query_flag(PlayerFlags.DEBUG_MODE)

    @property
    def return_key(self) -> str:
        """The player's negotiated Enter/Return key label (e.g. 'Enter' or
        'Return'), for prompts like "(Enter: Attack)" or "press X to cancel".
        Shortcut for client_settings.return_key so callers don't have to
        repeat that whole path (see the TODO this replaces in
        create_character.py:530)."""
        return getattr(self.client_settings, 'return_key', 'Enter')

    @property
    def is_future_expansion(self) -> None:
        """TODO: Another such shortcut, to be determined"""
        return None

    def set_stat(self, ctx: 'GameContext', stat: "PlayerStat", adj: int, verbose: bool = False):
        """
        Set stat <stat> to an absolute value. This has been provided for backwards compatibility
        with adj_stat_relative().

        :param ctx: GameContext
        :param stat: statistic in self.stats{} dict to adjust
        :param adj: relative adjustment (+x or -x)
        :param verbose: True: tell about it, False: don't
        :return: stat, TODO: maybe also 'success': True if 0 > stat > <limit>

        >>> rulan = Player(**set_up_rulan())

        >>> rulan.adj_stat_relative(PlayerStat.STR, -5, True)  # decrement Rulan's strength by 5, notify
        'You feel weaker.'
        """
        from base_variables import STAT_DATA
        if stat not in self.stats:
            logging.warning(f"Stat {stat} doesn't exist.")
            # raise ValueError?
            return
        # adjust stat by <adjustment>:
        before = self.stats[stat]
        after = before + adj
        logging.info("Before: %s %i" % (stat, after))
        # TODO: call adjust_stat_relative() instead?
        if not self.is_expert or not verbose:
            # STAT_DATA structure: STAT_DATA[PlayerStat.X]['phrases'] -> (less, more)
            phrase = STAT_DATA[stat]["phrases"][before < after]
            ctx.send(f"You feel {phrase}.")
            # TODO: jwhoag suggested adding 'confidence' -> 'brave' -- good idea,
            #  not sure where it can be added yet.
        logging.info("After: %s %i" % (stat, after))
        self.stats[stat] = after

    def has_item(self, item):
        """Check if player has item"""
        return item in self.inventory

    def look_at(self, item: Any):
        """
        Print a string that shows the name of the object. If the Player owns the item,
        or the Player's DEBUG or ADMIN flags are True, also show the ID prefix and number.
        Example:
            'Sword [Weapon #4]' if the Player owns the item, or the DEBUG or ADMIN flags are True
            'Sword' if the Player does not own the item, or the DEBUG or ADMIN flags are False
        """
        if item.owner is self or (self.query_flag(PlayerFlags.DEBUG_MODE) or self.query_flag(PlayerFlags.ADMIN)):
            print(f"{item.name} [{item.item_type} #{item.item_id}]")
        else:
            print(f"{item.name}")
        if item.description:
            print(item.description)

    def output(self, text_lines: str | list) -> "Message":
        """
        Print <text_lines> in client's Translation, word-wrapped to client's column width to Player.
        A null string outputs a blank line.

        :param text_lines: text to output (can be either a list of strings or a single string)
        :return: Message
        """
        """
        TODO: implement cbmcodec2 ASCII -> PETSCII translation

        TODO: implement different success messages for Player originating action vs. other Players in room
        use player.
        for cxn in all_players_in_room:
            if char.(something, idk what at this point) == Player.who_performed_action:
                output(f"You throw the snowball at {target}.")
            else:
                output(f"{actor} throws the snowball at {target}.")
        
        if self.client_settings.translation == Translation.PETSCII:
            codec = "petscii_c64en_lc"
            temp = string.encode(codec)
            logging.debug(repr(temp))  # don't print Commodore color codes to Linux terminal
        """
        from net_server import Message
        from tada_utilities import text_pager

        formatted_lines = []

        if isinstance(text_lines, str):
            # Process a single string, which might result in multiple wrapped lines
            processed_lines = self.process_single_line(text_lines)
            formatted_lines.extend(processed_lines)  # Use extend for multiple lines from one input
        elif isinstance(text_lines, list):
            # Process each string in the list
            collected_lines = []
            for line in text_lines:
                # if line == '':
                #     collected_lines.append("\n")
                processed_lines = self.process_single_line(line)
                formatted_lines.extend(processed_lines)  # Use extend here too

        # Use text_pager if lines > screen rows
        if len(formatted_lines) >= self.client_settings.screen_rows:
            # text_pager(player, text_lines)
            try:
                text_pager(self, formatted_lines)
            except Exception:
                logging.debug("Unable to run text_pager (async) synchronously; falling back to direct output")
                for ln in formatted_lines:
                    print(ln)
        # otherwise, print each line from the flattened list without paging:
        """
        for line in final_output_lines:
            if line == '':
                print()
            else:
                print(line)
        """
        # The Message object should receive a flat list of strings
        return Message(lines=formatted_lines)

    def process_single_line(self, raw_input: str) -> list[str]:
        """
        Apply text wrapping, bullet point formatting and highlighting to a single string,
        returning a list of wrapped lines.

        :param self: Player object (to infer line ending options)
        :param raw_input: string to process
        :return str: null string or text-wrapped strings
        """
        import colorama
        import re
        from tada_utilities import bulleted_list_format

        # turn empty string into newline (TODO: from player.client_settings.line_ending
        if raw_input == '':
            return [""]

        column_width = self.client_settings.screen_columns
        logging.debug("width: %i | raw_input: %s" % (column_width, raw_input))

        # Apply highlighting before wrapping to avoid breaking color codes
        # TODO: handle player's highlight / normal color preferences
        # This regex is correct for [text] -> RED text
        highlighted_line_content = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=raw_input)

        # textwrap.fill returns a single string, which might contain newline characters if the input
        # had them or if it needed to break lines itself.
        # To get a list of lines, use textwrap.wrap and then join or just handle it directly.
        # textwrap.fill already handles wrapping, but if you want lines as separate strings,
        # you might need to split it if it has internal newlines.
        # Assuming textwrap.fill always returns a single string *without* internal newlines
        # UNLESS the original raw_input had them, and we want to ensure each element in the
        # returned list is a single visual line.

        wrapped_text = textwrap.fill(text=highlighted_line_content, width=column_width)

        # process lines into bulleted text:
        if wrapped_text.startswith("* "):
            wrapped_text = bulleted_list_format(wrapped_text[2:], column_width)

        # textwrap.fill *might* introduce newlines. We want to return a list of distinct lines.
        # So, we split by newline to ensure each element is a single line.
        return wrapped_text.splitlines()

    def set_silver_absolute(self, kind: "PlayerMoneyTypes", amount: int):
        """
        Set amount of silver in PlayerMoneyType[kind] to an absolute value.
        To adjust by a relative amount, see adjust_silver_relative().
        :param kind: PlayerMoneyTypes key
        :param amount: amount to set
        :return: None
        """
        try:
            self.silver[kind] = amount
            logging.debug("kind: %s, amount: %i" % (kind, amount))
        except KeyError:
            logging.warning("kind: invalid type %s" % kind)

    def get_silver(self, kind: "PlayerMoneyTypes") -> int:
        """Return the silver amount for the given PlayerMoneyTypes key.

        This method is resilient: it handles enum keys, string keys, and falls
        back to 0 on any error.
        """
        try:
            # Direct lookup (typical case: enum key)
            val = self.silver.get(kind, 0)
            return int(val) if val is not None else 0
        except Exception:
            # Try to match by string name / value in case the keys are stored differently
            try:
                kstr = str(kind)
                for k, v in self.silver.items():
                    try:
                        if k == kind or str(k) == kstr or (hasattr(k, 'name') and k.name == kstr) or (hasattr(k, 'value') and str(k.value) == kstr):
                            return int(v)
                    except Exception:
                        continue
            except Exception:
                pass
        return 0

    def subtract_silver(self, kind: "PlayerMoneyTypes", amount: int) -> bool:
        """Deduct amount from the given silver pool if the player can afford it.

        Returns True and deducts if the player has enough; returns False otherwise.
        """
        current = self.get_silver(kind)
        if current < amount:
            return False
        self.set_silver_absolute(kind, current - amount)
        return True

    def gain_weapon_experience(self, weapon_id_number: int) -> int:
        """Increment battle experience for weapon_id_number by 1 (cap 99).

        Call this only when the weapon lands a killing blow (SPUR.MISC.S:384
        "p.a3" is the ONLY place SPUR's vp is ever incremented -- there's no
        per-swing accrual). See combat/engine.py's _monster_dies() for the
        one call site; general per-swing character XP is a separate counter
        (player.experience, combat/engine.py's _add_exp()).

        Returns the new value.  Marks unsaved_changes so it is persisted.
        """
        key = str(weapon_id_number)
        current = int(self.weapon_experience.get(key, 0))
        if current < 99:
            self.weapon_experience[key] = current + 1
            self.unsaved_changes = True
        return int(self.weapon_experience.get(key, current))

    def get_flag(self, flag_name: "PlayerFlags") -> Optional["Flag"]:
        """
        Given a PlayerFlag Enum, return the Flag object
        :param flag_name: name of flag
        :return: Flag object
        """
        current = self.flags.get(flag_name)
        if current:
            logging.debug("flag: %s" % current)
            return current
        else:
            logging.warning("no flag %s" % flag_name)
            return None

    def set_flag(self, flag: "PlayerFlags", verbose: bool = False) -> tuple[bool, str | None]:
        """Set a flag to True. Returns (True, message) if verbose, (True, None) otherwise."""
        try:
            import flags as _flags
            _flags.set_flag(self, flag)
            msg = f"{getattr(flag, 'value', flag)}: On." if verbose else None
            return True, msg
        except Exception:
            logging.exception('Failed to set flag')
            return False, None

    def clear_flag(self, flag: "PlayerFlags", verbose: bool = False) -> tuple[bool, str | None]:
        """Set a flag to False. Returns (False, message) if verbose, (False, None) otherwise."""
        try:
            import flags as _flags
            _flags.clear_flag(self, flag)
            msg = f"{getattr(flag, 'value', flag)}: Off." if verbose else None
            return False, msg
        except Exception:
            logging.exception('Failed to clear flag')
            return False, None

    def toggle_flag(self, flag, verbose: bool = False) -> tuple[bool, str | None]:
        """Toggle a flag. Returns (new_state, message) if verbose, (new_state, None) otherwise."""
        try:
            import flags as _flags
            new_state = _flags.toggle_flag(self, flag)
            msg = f"{getattr(flag, 'value', flag)}: {'On' if new_state else 'Off'}." if verbose else None
            return new_state, msg
        except Exception:
            logging.exception('Failed to toggle flag')
            return False, None

    def query_flag(self, flag) -> bool:
        """Return the boolean state of the named flag (delegates to flags.query_flag)."""
        try:
            import flags as _flags
            return bool(_flags.query_flag(self, flag))
        except Exception:
            logging.exception('Failed to query flag')
            return False


    def set_stat_absolute(self, stat: "PlayerStat", value: int):
        """
        Set a statistic to an absolute value: e.g., PlayerStat.CON = 10.
        To adjust a statistic +/- a certain number of points, use adj_stat_relative(PlayerStat.CON, -5) instead.

        :param stat: statistic in self.stat{} dict to adjust
        :param value: value to set PlayerStat to
        :return: stat
        """
        """
        TODO: maybe also return 'success': True if 0 > stat > limit)
        TODO: adj_stat_relative() to add/subtract value relative to its current value
            i.e., set_stat_absolute(PlayerStat.INT, 5)  # sets INT to 5
                  adj_stat_relative(PlayerStat.INT, 20)  # adds 20 to whatever INT is
        
        >>> set_stat_test = Player()

        >>> set_stat_test.set_stat_absolute(PlayerStat.INT, 15)

        >>> set_stat_test.print_stat(PlayerStat.INT, abbreviated=True)
        Int: 15

        >>> set_stat_test.set_stat_absolute(PlayerStat.WIS, 9)

        >>> set_stat_test.print_stat(PlayerStat.WIS, abbreviated=False))
        Wisdom: 9

        # test of Character.set_stat()
        >>> shaia = Player(name="Shaia",
        ...                connection_id=2,
        ...                client={'name': 'TADA', 'columns': 80, 'rows': 25},
        ...                gender=Gender.FEMALE)

        >>> shaia.set_stat_absolute(PlayerStat.INT, 18)

        >>> print(f"{shaia.name} ...... {shaia.print_stat([PlayerStat.INT])}")  # the longer method
        Shaia ...... Int: 18
        """

    def get_stat(self, stat: "PlayerStat") -> int | None:
        """
        if 'stat' is str: return value of single stat as str: 'stat'

        :return: value of single stat as int: 'stat', or None if stat doesn't exist
        TODO: if 'stat' is list: sum up contents of list: [PlayerStat.STR, PlayerStat.WIS, PlayerStat.INT]...
        TODO: refactor get_multiple_stats() to accept a list of PlayerStats, then for each stat, call get_stat()
            -- avoids multiple confusing function calls trying to do too much
        """
        try:
            return self.stats[stat]
        except KeyError:
            logging.warning("Stat '%s' doesn't exist." % stat)
            return None

    def get_one_stat(self, stat: "PlayerStat") -> str | None:
        """
        :param stat: PlayerStat to retrieve
        :return: statistic value, or None if stat_list empty, or IndexError is encountered
        """
        if not stat:
            logging.error("No stats provided")
            return None
        try:
            return self.stats[stat]
        except IndexError:
            logging.error("No stat %s" % stat)
            return None

    def print_stat(self, stat: "PlayerStat", abbreviated: bool):
        """
        Print player stat in title case: '<Stat>: <value>' on a single line.
        Cha: 10

        print_multiple_stats() uses this function as a helper:
        Cha: 10   Dex: 15   Int: 9

        :param stat: a single PlayerStat Enum(s) to report
        :param abbreviated: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        :return: None

        >>> test = Player()
        
        >>> test.set_stat_absolute(PlayerStat.CHR, 10)  # set Charisma to 10

        >>> test.print_stat(stat=PlayerStat.CHR, abbreviated=False)
        Charisma: 10
        """
        from base_variables import STAT_DATA
        try:
            print(f"{STAT_DATA['name'][abbreviated]}: {stat.value}")
        except IndexError:
            logging.warning("Stat '%s' doesn't exist." % stat)
            # TODO: raise ValueError?
            return None

    def print_multiple_stats(self, stat_list: list["PlayerStat"],
                             abbreviate: bool):
        """
        :param stat_list: list of PlayerStat(s) to report
        :param abbreviate: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        """
        for stat in stat_list:
            self.print_stat(stat, abbreviate)

    def get_birthday(self):
        """
        get a character's birthday
        :return: str: "month/day" ("month/day/year" if age known)
        >>> test = Player()  # birthday = datetime.now()
        
        >>> self.get_birthday(age=0, birthday=datetime.date(6, 16, 1976))
        6/16
        """
        # TODO: locale stuff where dates are in either month-day-year / year-month-day format?
        year = self.birthday.year
        month = self.birthday.month
        day = self.birthday.day
        return f"{month}/{day}/{year}"

    def get_age(self):
        # TODO: datetime.now() - self.birthday
        pass

    def connect(self):
        server = _get_server_module()
        if server is None:
            logging.error("connect: no server module available to register connection")
            return
        with getattr(server, 'server_lock'):
            # TODO: add last_connection as datetime.now()
            getattr(server, 'room_players')[self.map_room].add(self.id)
            self.last_connection = datetime.datetime.now()
            logging.info("%s connected at %s" % (self.name, self.last_connection))
            # TODO: notify other players in same room of connection ("%s wakes up.")
            # TODO: watchfor list: ("[Somewhere in the land, ]%s has woken up / fallen asleep.")
            #    ("Somewhere in the land, " printed if not in the same room.)

    def move(self, destination_room: int, direction=None):
        current_room = self.map_room
        server = _get_server_module()
        if server is None:
            logging.error("move: no server module available to update room_players")
            return
        with getattr(server, 'server_lock'):
            logging.debug("Player.move: Before remove: %s" % getattr(server, 'room_players')[current_room])
            getattr(server, 'room_players')[current_room].remove(self.id)
            logging.debug("Player.move: After remove: %s" % getattr(server, 'room_players')[current_room])

            self.map_room = destination_room
            logging.debug("Player.move: Before add: %s" % getattr(server, 'room_players')[self.map_room])
            getattr(server, 'room_players')[self.map_room].add(self.id)
            logging.debug("Player.move: After add: %s" % getattr(server, 'room_players')[self.map_room])
            logging.debug('Player.move: Moved %s from %s to %s' % (self.name, current_room, self.map_room))
            # Use net_common.Message via module import to avoid import-time circular issues
            if direction is None:
                return nc.Message(lines=[f'[{self.name} disappears in a flash of light.'])
            else:
                # compass_txts is in base_classes; import lazily
                from base_classes import compass_txts
                return nc.Message(lines=[f"{self.name} moves {compass_txts[direction]}."])

    @staticmethod
    def _json_path(user_id):
        # Resolve run directory at runtime from net_common (may be a Path or string)
        try:
            import net_common
            base = getattr(net_common, 'run_server_dir', None)
        except Exception:
            base = None
        if base is None:
            base = Path('./run/server')
        # Ensure string path
        base_path = str(base)
        return os.path.join(base_path, f"player-{user_id}.json")

    def save(self, force: bool = False) -> bool:
        """Persist player to disk. If force=True, ignore unsaved_changes."""
        try:
            if not force and not getattr(self, 'unsaved_changes', False):
                logging.debug("Player.save: no changes to save for %s" % getattr(self, 'name', '<unknown>'))
                return True
            if self.id is None:
                logging.error("Player.save: cannot save player without id: %s" % getattr(self, 'name', '<unknown>'))
                return False
            path = self._json_path(self.id)
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            # Build a dict representation but serialize flags minimally (name/status) to keep JSON compact.
            # Exclude session-only attributes that hold live objects and are not restored on load.
            _SESSION_ONLY = {'readied_weapon', 'storm_servant_bonus', 'compass_active', 'pending_pages'}
            data_out = {k: v for k, v in self.__dict__.items() if k not in _SESSION_ONLY}
            data_out['party'] = self.party.to_json()
            from inventory import Inventory
            if isinstance(self.inventory, Inventory):
                data_out['inventory'] = self.inventory.to_json()
            if isinstance(self.locker, Inventory):
                data_out['locker'] = self.locker.to_json()
            from command_settings import CommandSettings
            if isinstance(self.command_settings, CommandSettings):
                data_out['command_settings'] = self.command_settings.to_dict()
            try:
                import flags as _flags
                data_out['flags'] = _flags.serialize_flags_for_save(self)
            except Exception:
                # If flags module isn't available or fails, fall back to previous behavior
                try:
                    # If self.flags is present and looks like mapping, attempt to convert simple entries
                    if isinstance(self.flags, dict):
                        simple = {}
                        for kk, vv in list(self.flags.items()):
                            try:
                                name = vv.name if hasattr(vv, 'name') else (kk.value if hasattr(kk, 'value') else str(kk))
                                simple[name] = {'name': name, 'status': bool(getattr(vv, 'status', False))}
                            except Exception:
                                continue
                        data_out['flags'] = simple
                except Exception:
                    pass
            with open(path, 'w') as jsonF:
                json.dump(data_out, jsonF, default=lambda o: getattr(o, '__dict__', str(o)), indent=4)
            self.unsaved_changes = False
            logging.info("Player.save: Saved %s to %s" % (getattr(self, 'name', '<unknown>'), path))
            return True
        except Exception:
            logging.exception("Player.save: Failed to save player %s" % getattr(self, 'name', '<unknown>'))
            return False

    def _load(self) -> bool:
        """Attempt to load a saved player JSON file and merge values into this Player.

        Only a small, safe set of fields are merged to avoid overwriting runtime-only objects.
        Returns True if a file was successfully loaded, False otherwise.
        """
        try:
            path = self._json_path(self.id)
            if not os.path.exists(path):
                return False
            with open(path, 'r') as f:
                data = json.load(f)

            # Display name, as last saved -- e.g. after an EditPlayer rename
            # (commands/editplayer.py's _names_menu() edit_name()).  Without
            # this, connect.py's _authenticate() always reconstructs Player
            # with name=char_name, which falls back to the lowercased login
            # username (creds.get('char_name') is never actually written
            # anywhere), so any case-preserving rename was silently
            # discarded on the very next login.
            if 'name' in data and isinstance(data['name'], str) and data['name'].strip():
                self.name = data['name']

            # Merge simple scalar fields
            simple_keys = ('map_room', 'map_level', 'xp_level', 'times_played', 'moves_today', 'hit_points', 'quote')
            for k in simple_keys:
                if k in data:
                    try:
                        setattr(self, k, int(data[k]) if data[k] is not None else data[k])
                    except Exception:
                        setattr(self, k, data[k])

            # Migrate saves written before xp_level existed: map_level used to be
            # overloaded as both dungeon floor (SPUR's cl) and character level
            # (SPUR's xp/yn -- see combat/engine.py's old level-up code). Any
            # save missing xp_level was written under that conflation, so its
            # map_level value is really the character's xp_level; the dungeon
            # floor for such saves resets to 1 (no floor-travel history to trust).
            if 'xp_level' not in data and 'map_level' in data:
                try:
                    self.xp_level = int(data['map_level'])
                except Exception:
                    self.xp_level = 1
                self.map_level = 1

            # Inventory
            if 'inventory' in data and isinstance(data['inventory'], list):
                try:
                    from inventory import Inventory
                    self.inventory = Inventory.from_json(
                        data['inventory'], capacity=self.max_inventory_size
                    )
                except Exception:
                    logging.exception("Player._load: failed to restore inventory for %s", self.name)

            # Private Annex locker (only present once the attendant has set one up)
            if 'locker' in data and isinstance(data['locker'], list):
                try:
                    from inventory import Inventory, LOCKER_CAPACITY
                    self.locker = Inventory.from_json(data['locker'], capacity=LOCKER_CAPACITY)
                except Exception:
                    logging.exception("Player._load: failed to restore locker for %s", self.name)

            # Picked-up static room items — must survive logout so they don't reappear
            if 'picked_up_items' in data and isinstance(data['picked_up_items'], list):
                self.picked_up_items = [int(i) for i in data['picked_up_items'] if isinstance(i, (int, float))]

            # Books already granted their one-time reading Wisdom bonus
            if 'read_books' in data and isinstance(data['read_books'], list):
                self.read_books = [int(i) for i in data['read_books'] if isinstance(i, (int, float))]

            # Previous session's login time -- save() writes this via str(datetime),
            # which is also a valid fromisoformat() input (space instead of 'T').
            # Without this restore, self.last_connection stays at its __init__
            # default (datetime.now() at construction time), so it always reads
            # as "just now" and news.py's "since last login" comparison would
            # never find anything older to compare against.
            if 'last_connection' in data and isinstance(data['last_connection'], str):
                try:
                    self.last_connection = datetime.datetime.fromisoformat(data['last_connection'])
                except ValueError:
                    logging.exception("Player._load: failed to restore last_connection for %s", self.name)

            # Per-player kill list (each entry is a monster number)
            if 'monsters_killed' in data and isinstance(data['monsters_killed'], list):
                self.monsters_killed = [int(i) for i in data['monsters_killed'] if isinstance(i, (int, float))]

            # Combinations — accepts both the current dict shape ({name: {...}})
            # and the older list-of-dicts shape ([{'name': ..., 'combination': [...]}])
            # written before player.combinations became a dict keyed by CombinationTypes.
            if 'combinations' in data:
                try:
                    from base_classes import Combination, CombinationTypes
                    raw = data['combinations']
                    if isinstance(raw, dict):
                        entries = raw.values()
                    elif isinstance(raw, list):
                        entries = raw
                    else:
                        entries = []
                    restored = {}
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        saved_name = entry.get('name')
                        combo_type = next((ct for ct in CombinationTypes
                                           if ct.value == saved_name or ct.name == saved_name), None)
                        if combo_type is None:
                            continue
                        values = entry.get('combination')
                        if not (isinstance(values, (list, tuple)) and len(values) == 3):
                            continue
                        combo = Combination(combo_type)
                        combo.combination = tuple(int(v) for v in values)
                        restored[combo_type] = combo
                    self.combinations = restored
                except Exception:
                    logging.exception("Player._load: failed to restore combinations for %s", self.name)

            # Command settings
            if 'command_settings' in data and isinstance(data['command_settings'], dict):
                try:
                    from command_settings import CommandSettings
                    self.command_settings = CommandSettings.from_dict(data['command_settings'])
                except Exception:
                    logging.exception("Player._load: failed to restore command_settings for %s", self.name)

            # Guild — stored as the enum's string value; reverse-look up the member.
            if 'guild' in data:
                try:
                    from base_classes import Guild
                    saved = data['guild']
                    matched = next((g for g in Guild if g.value == saved), None)
                    if matched is not None:
                        self.guild = matched
                except Exception:
                    pass

            # char_class / char_race / gender -- stored as the enum's string
            # value, same as guild above. These were never restored at all:
            # every login silently reset them to defaults (char_class=None,
            # char_race=None, gender=Gender.MALE) regardless of what the
            # player actually chose at creation -- discovered by round-
            # tripping a real Player through Player(id=..., name=...) the
            # same way commands/connect.py's login flow does it.
            if 'char_class' in data and data['char_class'] is not None:
                try:
                    from base_classes import PlayerClass
                    saved = data['char_class']
                    matched = next((c for c in PlayerClass if c.value == saved), None)
                    if matched is not None:
                        self.char_class = matched
                except Exception:
                    pass
            if 'char_race' in data and data['char_race'] is not None:
                try:
                    from base_classes import PlayerRace
                    saved = data['char_race']
                    matched = next((r for r in PlayerRace if r.value == saved), None)
                    if matched is not None:
                        self.char_race = matched
                except Exception:
                    pass
            if 'gender' in data and data['gender'] is not None:
                try:
                    from base_classes import Gender
                    saved = data['gender']
                    matched = next((g for g in Gender if g.value == saved), None)
                    if matched is not None:
                        self.gender = matched
                except Exception:
                    pass

            # Merge stats and silver dicts where present
            if 'stats' in data and isinstance(data['stats'], dict):
                try:
                    self.stats.update(data['stats'])
                except Exception:
                    pass
            if 'silver' in data and isinstance(data['silver'], dict):
                try:
                    self.silver = data['silver']
                except Exception:
                    pass
            if 'weapon_experience' in data and isinstance(data['weapon_experience'], dict):
                try:
                    self.weapon_experience = {str(k): int(v) for k, v in data['weapon_experience'].items()}
                except Exception:
                    pass

            # Flags: convert saved name->status mapping back into player's flags mapping
            try:
                import flags as _flags
                if 'flags' in data and isinstance(data['flags'], dict):
                    # ensure mapping exists
                    _flags.ensure_player_flags(self)
                    restored_true: list[str] = []
                    for fname, entry in data['flags'].items():
                        try:
                            status = bool(entry.get('status', False)) if isinstance(entry, dict) else bool(entry)
                            # find enum by value
                            pf = next((pf for pf in _flags.PlayerFlags if pf.value == fname), None)
                            if pf is not None:
                                if status:
                                    _flags.set_flag(self, pf)
                                    restored_true.append(fname)
                                else:
                                    _flags.clear_flag(self, pf)
                            else:
                                # attach as legacy string entry
                                existing = getattr(self, 'flags', {})
                                existing[fname] = entry
                                try:
                                    self.flags = existing
                                except Exception:
                                    pass
                        except Exception:
                            logging.exception('Player._load: error restoring flag %r', fname)
                    logging.debug('Player._load: restored flags (True): %s', restored_true)
            except Exception:
                logging.exception('Player._load: flags block failed')

            return True
        except Exception:
            logging.exception('Failed to load player data for %s' % (self.id or '<unknown>'))
            return False

    def quit(self):
        """High-level quit helper: force-save the player and return.
        Note: actual disconnect mechanics are server-specific and not invoked here.
        """
        try:
            # If id is missing but name exists, use name as a fallback id and attempt to save.
            if getattr(self, 'id', None) is None:
                nm = getattr(self, 'name', None)
                if nm:
                    logging.info("Player.quit: id missing, using name as id fallback: %s" % nm)
                    try:
                        self.id = str(nm)
                    except Exception:
                        logging.exception("Failed to coerce player.name to id; skipping save")
                        return False
                else:
                    logging.info("Player.quit: skipping save because player has no id or name")
                    return False

            saved = self.save(force=True)
            if not saved:
                logging.warning("Player.quit: save returned False for %s (id=%s)" % (getattr(self, 'name', '<unknown>'), getattr(self, 'id', None)))
            return bool(saved)
        except Exception:
            logging.exception("Exception while forcing save on quit for %s" % getattr(self, 'name', '<unknown>'))
            return False
