import json
import logging
import os
import random
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
    from items import ItemCategory
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

    # Ring-buffer caps matching SPUR.MISC.S:333-334 (xo/xo$, rations) and
    # SPUR.MISC.S:321-322 (xt/xt$, items) -- see spur-variables.md. Unlike
    # SPUR's unconditional append, this port's record_ration_pickup()/
    # record_item_pickup() dedupe (Ryan's call): no reason to burn a ring
    # buffer slot on a repeated get/take of the same item.
    RATION_HISTORY_CAP = 20
    ITEM_HISTORY_CAP = 60
    COMMAND_HISTORY_CAP = 20

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
        # Cumulative points drained from stats by the Ring of Invisibility
        # curse (survival.py's RING_WORN tick), keyed by PlayerStat name.
        # The Fountain of Youth / Galadriel's Vial (survival.py's
        # full_restore()) undoes this debt -- SPUR has no separate
        # base-stat concept to restore toward, so this tracks the delta
        # instead.
        self.ring_drain = kwargs.get('ring_drain') or {}
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
        # Per-level "have you been here" bitfield (visited_rooms.py), keyed
        # by str(level), one bit per room number, hex-encoded -- same
        # MSB-first-per-byte packing GBBS's own message-store header uses
        # (Ryan's idea; see LEVEL_AUDIT.md's room-renumbering investigation
        # for that precedent). Must exist before map_room below, since
        # mark_visited() marks the player's starting/loaded room.
        self.visited_rooms: dict = kwargs.get('visited_rooms') or {}
        self.map_room = kwargs.get('map_room', 1)  # cr (current room)
        from visited_rooms import mark_visited
        mark_visited(self, self.map_level, self.map_room)
        self.moves_made = kwargs.get('moves_made')
        # tracks how many moves made during the game session to calculate experience points awarded at quit:
        self.moves_today = kwargs.get('moves_today', 0)
        # survival.py's survival_tick() command counter -- persisted (not
        # session-only) so a player can't reset their hunger/thirst
        # countdown by simply logging out and back in.
        self._survival_counter = kwargs.get('_survival_counter', 0)
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
        # Server's raw weapons.json list, passed in by the login path so a
        # carried weapon can be rebuilt as a real Weapon (not a lightweight
        # Item) on reload -- see items.resolve_weapon(). Session-only:
        # never persisted, see save()'s _SESSION_ONLY set.
        self._weapons_data = kwargs.get('weapons_data')
        if isinstance(_raw_inv, Inventory):
            self.inventory: Inventory = _raw_inv
        elif isinstance(_raw_inv, list):
            self.inventory = Inventory.from_json(_raw_inv, capacity=self.max_inventory_size,
                                                  weapons_data=self._weapons_data)
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
        # id_number of the shield item currently backing player.shield's
        # condition rating -- set by commands/new_player.py's starting
        # equipment step, shoppe/armory.py's shield purchase, and
        # commands/use.py's shield-boost consumable (even though that item
        # is removed on use and isn't "worn" in the WEAR sense, USE-ing a
        # shield is the normal way players equip one, so it updates this
        # too as of 2026-08-08). Needed so shield_proficiency below can be
        # tracked per physical shield, like weapon_experience.
        self.active_shield_id: Optional[int] = kwargs.get('active_shield_id')
        # id_number of the armor item currently backing player.armor's
        # condition rating -- mirrors active_shield_id above, but for armor.
        # Set by commands/wear.py whenever armor is worn (including the
        # #113/#115 flat-rating special cases); unlike active_shield_id it
        # has no purchase-time setter yet since shoppe/armory.py's armor
        # branch doesn't exist. Not consulted by combat -- armor has no
        # proficiency/block-exp system parallel to shield_proficiency --
        # this exists purely so STAT and the login banner can say *which*
        # armor piece is worn instead of just a bare percentage.
        self.active_armor_id: Optional[int] = kwargs.get('active_armor_id')
        # Loaded ammo state (set by USE command, consumed by combat).
        self.ammo_rounds: int = kwargs.get('ammo_rounds', 0)
        self.ammo_damage: int = kwargs.get('ammo_damage', 0)
        self.ammo_max:    int = kwargs.get('ammo_max', 0)    # vl: total rounds when loaded (recovery cap)
        # Ring of invisibility worn (zu$[2]) lives on PlayerFlags.RING_WORN
        # (query_flag/set_flag/clear_flag), not a plain attribute here --
        # encounters/little_girl.py and commands/stats.py already read it
        # that way.
        self.experience = kwargs.get('experience', 0)
        # Every monster number this player has killed, one entry per kill --
        # NOT deduplicated (Ryan's request: a monster killed 3 times over a
        # career should count 3 times). monsters_killed (the @property,
        # below __init__) is the derived kill count; anything that just
        # wants "have I fought monster #N before" should test
        # `N in player.dead_monsters` directly.
        self.dead_monsters: list[int] = kwargs.get('dead_monsters', [])
        # Lifetime kill log, one entry per kill, never cleared by
        # bar/zelda.py's Resurrect Monsters (that only clears dead_monsters,
        # the re-encounter/examine/teleport/charm gate above). monsters_killed
        # (the @property, below __init__) is derived from this, not from
        # dead_monsters -- monsters flagged re_animates append here on every
        # kill but are deliberately never added to dead_monsters (see
        # combat/engine.py's _record_kill), so they count toward the stat
        # forever while staying eligible to be fought again and again.
        self.kill_log: list[int] = kwargs.get('kill_log', [])
        # Monster numbers charmed and recruited into this player's party via
        # charm.py -- room.monster is shared/global map state (see
        # dead_monsters' own per-player "dead for this viewer" pattern
        # this mirrors), so a charmed-and-joined monster must be tracked
        # per player rather than removed from the room, or other players
        # would lose the monster too.
        self.charmed_monsters: list[int] = kwargs.get('charmed_monsters', [])
        # Monster numbers scared off by a loud weapon (SPUR.COMBAT.S scare
        # subroutine) that this player has personally frightened away --
        # SPUR's md==2 "tracks" state. Same per-player shape as
        # dead_monsters/charmed_monsters above: room.monster stays put for
        # other players, so "has fled for me" has to live here rather than
        # on the room.
        self.fled_monsters: list[int] = kwargs.get('fled_monsters', [])
        # Session history of rations/items already taken so they don't
        # respawn in a room description -- SPUR's xo/xo$ (rations, 20-entry
        # ring buffer) and xt/xt$ (items/weapons, 60-entry ring buffer).
        # Both are reset and (rations only) reseeded from currently-carried
        # rations once _load() has restored the saved inventory below --
        # see the login-reset block after _load().
        self.ration_history: list[int] = kwargs.get('ration_history', [])
        self.item_history: list[int] = kwargs.get('item_history', [])
        # Last COMMAND_HISTORY_CAP raw command lines typed by this player,
        # oldest first -- viewable with the 'history' command and re-run
        # with '^N' (N=1 is the most recent). Unlike ration_history/
        # item_history above, this persists across logins (no reset in the
        # login block below) and never dedupes -- repeating the same
        # command is a legitimate, expected use case (see command_processor
        # .py's '^N' handling).
        self.command_history: list[str] = kwargs.get('command_history', [])
        # Item numbers already granted their one-time +1 Wisdom bonus for
        # being read (SPUR.MISC2.S:316's `if pw<25 pw=pw+1` -- fires on
        # every consumed book there, scroll or not; this port keeps
        # non-scroll books re-readable instead of consuming them, so the
        # bonus is tracked per item instead to prevent farming it by
        # re-reading the same reference book). See commands/read.py.
        self.read_books: list[int] = kwargs.get('read_books', [])
        self.readied_weapon = None  # currently readied weapon (BaseItem or None)
        # Session-only: name of a player who has challenged this player to a
        # duel and is awaiting DUEL ACCEPT / DUEL DECLINE (see
        # combat/duel.py). Only one challenge can be pending at a time.
        self.pending_duel_challenge: Optional[str] = None
        # Personal duel win/loss record (SPUR.DUEL2.S's "personal" label,
        # spur.a1$'s g0/g9 fields) -- distinct from guild_standings.py's
        # per-guild tally, which only covers guild-vs-guild duels.
        # Persisted (not session-only): incremented by combat/duel.py's
        # DuelSession._end() on every decisive SPORT DUEL.
        self.duel_wins: int = kwargs.get('duel_wins', 0)
        self.duel_losses: int = kwargs.get('duel_losses', 0)
        # Who knocked this player unconscious (SPUR.DUEL2.S's "uncon"
        # subroutine) -- read by logon_events/unconscious_wake.py to name
        # the opponent in the wake-up line, then cleared alongside
        # PlayerFlags.UNCONSCIOUS. None when not unconscious.
        self.defeated_by: Optional[str] = kwargs.get('defeated_by', None)
        # Session-only: the shared combat.duel.DuelSession this player is
        # currently fighting in, if any (set on both duelists by
        # combat/duel.py's _resolve_challenge(), cleared by
        # DuelSession._end()). Not a real object graph to persist -- a duel
        # in progress is inherently a live-session-only concept.
        self.active_duel = None
        # Page messages queued while busy (currently: in combat -- see
        # commands/messaging.py's is_in_combat() and commands/page.py).
        # Flushed and shown by network_context.py's prompt() the next time
        # this player is prompted, instead of interrupting combat mid-round.
        self.pending_pages: list[str] = []
        # Battle experience per weapon type, keyed by str(id_number), value 0-99.
        # Persists independently of inventory so experience survives dropping/selling.
        self.weapon_experience: dict = kwargs.get('weapon_experience', {})
        # Shield-block proficiency per shield item, keyed by str(id_number),
        # value 0-99 -- not part of original SPUR (shield block chance there
        # comes purely from the shield's condition value). New mechanic:
        # increments by 1 for active_shield_id every time a shield block
        # actually succeeds in combat (see combat/engine.py's
        # _apply_monster_damage()), mirroring weapon_experience exactly.
        # Feeds a small bonus into the shield block-threshold roll
        # (combat/resolution.py's shield_exp_bonus()) once a player has
        # enough of it with the shield they currently have equipped.
        self.shield_proficiency: dict = kwargs.get('shield_proficiency', {})
        # Quest #16 (quests/README.md) -- item #86 "Tut's Treasure", level 2
        # room 158 "Secret Chamber". examined=True once EXAMINEd (disarms a
        # trap, +2 INT); taken=True once GET afterward awards the gold bonus.
        # See quests/tuts_treasure.py for the full mechanic.
        from flags import TutTreasure
        _raw_tt = kwargs.get('tuts_treasure')
        if isinstance(_raw_tt, TutTreasure):
            self.tuts_treasure = _raw_tt
        elif isinstance(_raw_tt, dict):
            self.tuts_treasure = TutTreasure(
                examined=bool(_raw_tt.get('examined', False)),
                taken=bool(_raw_tt.get('taken', False)),
            )
        else:
            self.tuts_treasure = TutTreasure()
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

        self.party = Party.from_json(kwargs.get('party', []), weapons_data=self._weapons_data)
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

        # New in TADA: mirrors SPUR.MISC3.S's xz$ -- "already examined"
        # item names used by EXAMINE's magic/cursed reveal to avoid
        # re-rolling the same item's status back-to-back. SPUR's xz$ is a
        # single-slot BASIC variable (SPUR only ever holds one item at a
        # time), but TADA's inventory is a list, so this is a list too --
        # a scalar here would forget item A's reveal the moment item B got
        # examined. Not persisted, same reasoning as SPUR's xz$ resetting
        # each session (see commands/examine.py's _examine_item()).
        self.last_examined = []

        # New in TADA: mirrors SPUR.MISC3.S's ys$ "loot" flag -- how many
        # times this player has used LOOT this session (once normally,
        # twice for Outlaws; see commands/loot.py). Not persisted, same
        # reasoning as last_examined above.
        self.loot_count = 0

        # New in TADA: mirrors SPUR.MISC2.S's ys$ "*pr1"/"*pr2"/"*prd"
        # flags -- how many times this player has PRAYed this session
        # (once normally, twice for Druids/Paladins) and whether they've
        # been warned off pestering the Spirit of the Dungeons (the next
        # PRAY after the warning is fatal; see commands/pray.py). Not
        # persisted, same reasoning as last_examined/loot_count above.
        self.prayed_count    = 0
        self.prayer_punished = False

        # Allow passing an explicit id via kwargs (e.g., player.Player(name=..., id=username)).
        self.id = kwargs.get('id', None)  # account id

        # command history:
        self.command = None
        self.previous_command = None

        # A monster charmed via charm.py, awaiting the "wants to join you"
        # decision on leaving its room -- {'level', 'room_no',
        # 'monster_number', 'name', 'strength', 'to_hit'} or None.
        # Deliberately NOT persisted (no simple_keys entry, no _load()
        # restoration) -- matches SPUR's zq, which was session-scoped too
        # (a fresh BBS-door session every login). Player.save() dumps the
        # full __dict__ regardless, so a pending charm sits harmlessly in
        # the save file as dead data rather than actually surviving a
        # reconnect.
        self.pending_charm = None

        # flag whether a save is required:
        self.unsaved_changes: bool = False

        # If an id was provided, attempt to load persisted player state from disk
        try:
            if self.id:
                self._load()
        except Exception:
            logging.debug('No saved player data loaded for %s' % (self.id or self.name))

        # Login-time reset (SPUR.LOGON.S:198 xo=xf:xo$=xf$;
        # SPUR.LOGON.S:208 xt$="":xt=0), run after _load() so self.inventory
        # reflects the restored save. Ration history is replaced with
        # whatever rations/drinks are currently carried (so a room's
        # ration stays suppressed while carried, even past the 20-entry
        # pickup ring buffer).
        try:
            from items import ItemCategory
            carried_rations = [
                int(getattr(entry.item, 'id_number', 0) or 0)
                for entry in self.inventory.entries(category=str(ItemCategory.FOOD))
                + self.inventory.entries(category=str(ItemCategory.DRINK))
            ]
            self.ration_history = [i for i in carried_rations if i]
        except Exception:
            logging.debug('Could not seed ration_history from inventory for %s', self.id or self.name)

        # Item history has no carried-inventory equivalent in master's
        # SPUR.LOGON.S and starts empty each session. Skip's branch of the
        # SPUR source (origin/skip -- a fuller LOGON.S revision master
        # lacks) additionally re-seeds xt$ at login from currently-worn
        # armor/shield item numbers (read from misc.data), so a worn piece
        # doesn't reappear as pickable in its room. Now that both halves
        # have an item id (active_shield_id, active_armor_id -- the latter
        # added 2026-08-08 alongside commands/wear.py setting it), seed
        # from both.
        worn_ids = [getattr(self, 'active_shield_id', None), getattr(self, 'active_armor_id', None)]
        self.item_history = [int(i) for i in worn_ids if i]

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

    @property
    def monsters_killed(self) -> int:
        """Total kill count (STATS display, etc.) -- derived from kill_log,
        the lifetime per-kill log. NOT dead_monsters, which is the separate
        re-encounter/examine/teleport/charm gate that bar/zelda.py's
        Resurrect Monsters clears -- that purchase restores the ability to
        refight monsters, it does not erase this stat. Read-only: to clear
        a player's kill count, reset kill_log itself, not this."""
        return len(self.kill_log)

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

    def has_item(self, *, name: str | None = None, item_id: int | None = None,
                 category: 'ItemCategory | str | None' = None) -> bool:
        """True if the player's inventory has an entry matching all given
        criteria (see Inventory.find(), which this mirrors)."""
        return bool(self.inventory.find(name=name, item_id=item_id, category=category))

    def record_ration_pickup(self, item_id: int) -> None:
        """Append to the ration ring buffer (SPUR xo/xo$), evicting the oldest
        entry once full. A no-op if item_id is already recorded -- unlike
        SPUR's unconditional append, a repeated get/take of the same ration
        shouldn't burn another slot."""
        if item_id in self.ration_history:
            return
        self.ration_history.append(item_id)
        if len(self.ration_history) > self.RATION_HISTORY_CAP:
            self.ration_history.pop(0)
        self.unsaved_changes = True

    def record_item_pickup(self, item_id: int) -> None:
        """Append to the item/weapon ring buffer (SPUR xt/xt$), evicting the
        oldest entry once full. A no-op if item_id is already recorded --
        unlike SPUR's unconditional append, a repeated get/take of the same
        item shouldn't burn another slot."""
        if item_id in self.item_history:
            return
        self.item_history.append(item_id)
        if len(self.item_history) > self.ITEM_HISTORY_CAP:
            self.item_history.pop(0)
        self.unsaved_changes = True

    def record_command(self, text: str) -> None:
        """Append a typed command line to the command ring buffer, evicting
        the oldest entry once full. Unlike record_ration_pickup()/
        record_item_pickup(), this always appends -- repeating the same
        command is expected, not wasted space."""
        if not text:
            return
        self.command_history.append(text)
        if len(self.command_history) > self.COMMAND_HISTORY_CAP:
            self.command_history.pop(0)
        self.unsaved_changes = True

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

    def gain_shield_proficiency(self, shield_id_number: Optional[int]) -> int:
        """Increment shield_proficiency for shield_id_number by 1 (cap 99).

        Call this every time a shield block actually succeeds in combat
        (combat/engine.py's _apply_monster_damage(), when result.shield_blocked
        is truthy) -- not part of original SPUR, a new tracked mechanic.
        Mirrors gain_weapon_experience()'s shape exactly.

        shield_id_number is normally player.active_shield_id -- if it's
        None (no identifiable shield item, e.g. very old saves from before
        this existed), this is a no-op and returns 0: there's nothing to
        credit the block to.

        Returns the new value.  Marks unsaved_changes so it is persisted.
        """
        if shield_id_number is None:
            return 0
        key = str(shield_id_number)
        current = int(self.shield_proficiency.get(key, 0))
        if current < 99:
            self.shield_proficiency[key] = current + 1
            self.unsaved_changes = True
        return int(self.shield_proficiency.get(key, current))

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
            _SESSION_ONLY = {'readied_weapon', 'storm_servant_bonus', 'skill_potion_bonus', 'compass_active', 'pending_pages',
                             'pending_duel_challenge', 'active_duel', '_weapons_data'}
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
            from terminal import ClientSettings
            if isinstance(self.client_settings, ClientSettings):
                data_out['client_settings'] = self.client_settings.to_dict()
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

            # Resumable character creation (commands/new_player.py's
            # main_flow()): creation_done=False plus creation_step marks a
            # paused, unfinished character -- commands/connect.py's
            # _authenticate() checks this and routes back into main_flow()
            # at the saved step instead of the normal game loop. Absent
            # entirely for every account created before this existed, or
            # once creation_done=True -- getattr(player, 'creation_done',
            # True) at every call site treats "no such attribute" the same
            # as "finished," which is correct for all of those.
            if 'creation_done' in data:
                self.creation_done = bool(data['creation_done'])
            if 'creation_step' in data:
                try:
                    self.creation_step = int(data['creation_step'])
                except (TypeError, ValueError):
                    pass
            if not getattr(self, 'creation_done', True):
                logging.info(
                    "Player._load: %s has an unfinished character creation "
                    "(creation_step=%r) -- will resume main_flow() instead "
                    "of the normal game loop",
                    self.name, getattr(self, 'creation_step', None),
                )

            # Merge simple scalar fields
            # shield/armor/active_shield_id added here because they were
            # previously written by save() (full __dict__ dump) but never
            # read back -- every login silently reset a player's shield and
            # armor condition to their __init__ defaults. Found while wiring
            # up the starting-equipment feature, which depends on these
            # actually persisting. shield_proficiency is a dict, merged
            # separately below alongside weapon_experience.
            # food/drink added here for the same reason -- found live while
            # testing spells/charm.py's CHARM POTION (a player's thirst
            # silently reset to "not thirsty" on every reconnect, making it
            # impossible to ever actually drink anything after logging back
            # in).
            # experience/honor/moves_made/wizard_glow added here for the same
            # reason as the block above: written by save() but never read
            # back. experience in particular is the counter driving
            # xp_level (combat/resolution.py's _add_exp()) -- every login
            # silently reset a character's experience to 0, even though
            # xp_level itself (already in this tuple) was restored fine.
            # Found by a systematic round-trip audit of every kwargs.get()
            # default in __init__ against what _load() actually restores.
            # ammo_rounds/ammo_max/ammo_damage added here for the same
            # reason -- unlike readied_weapon (genuinely session-only, see
            # _SESSION_ONLY below), these three are NOT session-only: they
            # get written by save()'s full __dict__ dump same as
            # shield/armor above, but were never read back, so ammo loaded
            # via USE (commands/use.py) silently reset to 0/0/0 on every
            # reconnect even though the file on disk still had the real
            # values. Found live: READY + USE bolts showed "CROSSBOW
            # 4/4 rounds", QUIT, reconnect, READY again showed "CROSSBOW
            # 0/0 rounds" with no USE in between.
            simple_keys = ('map_room', 'map_level', 'xp_level', 'times_played', 'moves_today', 'hit_points', 'quote',
                           'shield', 'armor', 'active_shield_id', 'active_armor_id', 'loan_amount', 'loan_days', 'food', 'drink',
                           '_survival_counter', 'experience', 'honor', 'moves_made', 'wizard_glow',
                           'duel_wins', 'duel_losses', 'ammo_rounds', 'ammo_max', 'ammo_damage', 'defeated_by')
            for k in simple_keys:
                if k in data:
                    try:
                        setattr(self, k, int(data[k]) if data[k] is not None else data[k])
                    except Exception:
                        setattr(self, k, data[k])

            # poisoned/diseased -- kept out of simple_keys above because that
            # loop's int(data[k]) cast would turn True/False into 1/0 rather
            # than a real bool. Same "written by save(), never read back" gap
            # as the rest of this audit: a poisoned or diseased player was
            # silently cured on every reconnect.
            if 'poisoned' in data:
                self.poisoned = bool(data['poisoned'])
            if 'diseased' in data:
                self.diseased = bool(data['diseased'])

            # once_per_day -- gates events like encounters/djinn_sighting.py,
            # encounters/galadriel.py, bar/skip.py, commands/use.py from
            # firing more than once per real-world day. Never restored, so
            # a reconnect let all of them fire again the same day.
            if 'once_per_day' in data and isinstance(data['once_per_day'], list):
                self.once_per_day = list(data['once_per_day'])

            # last_play_date -- same restore pattern as last_connection
            # above, for the "have we already shown today's X" family of
            # checks that compare against it.
            if 'last_play_date' in data and isinstance(data['last_play_date'], str):
                try:
                    self.last_play_date = datetime.datetime.fromisoformat(data['last_play_date'])
                except ValueError:
                    logging.exception("Player._load: failed to restore last_play_date for %s", self.name)

            # natural_alignment / current_alignment -- stored as the enum's
            # string value, same pattern as guild/char_class/char_race/gender
            # below. Never restored, so every login reset both to Neutral
            # regardless of what the player actually was.
            if 'natural_alignment' in data:
                try:
                    from base_classes import Alignment
                    saved = data['natural_alignment']
                    matched = next((a for a in Alignment if a.value == saved), None)
                    if matched is not None:
                        self.natural_alignment = matched
                except Exception:
                    pass
            if 'current_alignment' in data:
                try:
                    from base_classes import Alignment
                    saved = data['current_alignment']
                    matched = next((a for a in Alignment if a.value == saved), None)
                    if matched is not None:
                        self.current_alignment = matched
                except Exception:
                    pass

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
                logging.info(
                    "Player._load: %s's save predates xp_level -- migrating "
                    "old map_level=%r to xp_level=%d and resetting map_level to 1",
                    self.name, data['map_level'], self.xp_level,
                )

            # Inventory
            if 'inventory' in data and isinstance(data['inventory'], list):
                try:
                    from inventory import Inventory
                    self.inventory = Inventory.from_json(
                        data['inventory'], capacity=self.max_inventory_size,
                        weapons_data=getattr(self, '_weapons_data', None),
                    )
                except Exception:
                    logging.exception("Player._load: failed to restore inventory for %s", self.name)

            # Private Annex locker (only present once the attendant has set one up)
            if 'locker' in data and isinstance(data['locker'], list):
                try:
                    from inventory import Inventory, LOCKER_CAPACITY
                    self.locker = Inventory.from_json(
                        data['locker'], capacity=LOCKER_CAPACITY,
                        weapons_data=getattr(self, '_weapons_data', None),
                    )
                except Exception:
                    logging.exception("Player._load: failed to restore locker for %s", self.name)

            # Party members (Ally.to_json()/Party.to_json() -- see party.py).
            # Same gap as shield/armor/loan_amount above: save() writes
            # party via the full __dict__ dump, but _load() never read it
            # back, so every owned ally silently vanished on reconnect.
            # Found live while playtesting encounters/ally_gold_find.py and
            # encounters/ally_starvation.py.
            if 'party' in data and isinstance(data['party'], list):
                try:
                    from party import Party
                    self.party = Party.from_json(
                        data['party'], weapons_data=getattr(self, '_weapons_data', None),
                    )
                except Exception:
                    logging.exception("Player._load: failed to restore party for %s", self.name)

            # Session history of picked-up rations/items -- restored here so
            # save()'s full __dict__ dump round-trips, but both are reset
            # (and ration_history reseeded from carried rations) on every
            # login in __init__, matching SPUR.LOGON.S:198's xo=xf:xo$=xf$
            # and SPUR.LOGON.S:208's xt$="":xt=0.
            if 'ration_history' in data and isinstance(data['ration_history'], list):
                self.ration_history = [int(i) for i in data['ration_history'] if isinstance(i, (int, float))]
            if 'item_history' in data and isinstance(data['item_history'], list):
                self.item_history = [int(i) for i in data['item_history'] if isinstance(i, (int, float))]

            # Command history (see __init__) -- unlike ration_history/
            # item_history above, this is NOT reset on login.
            if 'command_history' in data and isinstance(data['command_history'], list):
                self.command_history = [str(c) for c in data['command_history'] if isinstance(c, str)]

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

            # Character's date of birth -- __init__ only sets this from a
            # 'birthday' kwarg, which commands/connect.py's _authenticate()
            # never passes on reconnect, so without this restore every
            # login silently reset it to None (and then wrote that None
            # back out on the next save, permanently erasing it). Found
            # via logon_events/birthday.py's greeting never firing for a
            # save file that had a real birthday on disk.
            if 'birthday' in data and isinstance(data['birthday'], str):
                try:
                    self.birthday = datetime.datetime.fromisoformat(data['birthday'])
                except ValueError:
                    logging.exception("Player._load: failed to restore birthday for %s", self.name)

            # Per-player kill log (each entry is a monster number, one per
            # kill -- not deduplicated). 'dead_monsters' is the current key;
            # 'monsters_killed' is the old (deduplicated-list) key from
            # before monsters_killed became a derived @property -- migrate
            # it once so older saves don't silently lose their kill history.
            if 'dead_monsters' in data and isinstance(data['dead_monsters'], list):
                self.dead_monsters = [int(i) for i in data['dead_monsters'] if isinstance(i, (int, float))]
            elif 'monsters_killed' in data and isinstance(data['monsters_killed'], list):
                logging.info("Player._load: %s's save predates dead_monsters -- migrating "
                             "its old monsters_killed list", self.name)
                self.dead_monsters = [int(i) for i in data['monsters_killed'] if isinstance(i, (int, float))]

            # Lifetime kill log (see __init__'s comment). 'kill_log' is the
            # current key; saves predating its introduction bootstrap from
            # dead_monsters (already loaded above) so existing kill counts
            # aren't reset to 0 -- from this point on the two lists diverge
            # only for re_animates kills.
            if 'kill_log' in data and isinstance(data['kill_log'], list):
                self.kill_log = [int(i) for i in data['kill_log'] if isinstance(i, (int, float))]
            else:
                logging.info("Player._load: %s's save predates kill_log -- bootstrapping "
                             "it from dead_monsters", self.name)
                self.kill_log = list(self.dead_monsters)

            # Per-player charmed-and-recruited list (each entry is a monster number)
            if 'charmed_monsters' in data and isinstance(data['charmed_monsters'], list):
                self.charmed_monsters = [int(i) for i in data['charmed_monsters'] if isinstance(i, (int, float))]

            # Per-player scared-off list (each entry is a monster number) --
            # SPUR's md==2 "tracks" state, see __init__'s comment.
            if 'fled_monsters' in data and isinstance(data['fled_monsters'], list):
                self.fled_monsters = [int(i) for i in data['fled_monsters'] if isinstance(i, (int, float))]

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

            # Client settings (PREFS: border style, colors, tab settings,
            # line ending, timezone/date format, ...) -- previously never
            # restored at all, so every preference silently reset to
            # ClientSettings' own __init__-time defaults on reconnect.
            if 'client_settings' in data and isinstance(data['client_settings'], dict):
                try:
                    from terminal import ClientSettings
                    self.client_settings = ClientSettings.from_dict(data['client_settings'])
                    logging.info("Player._load: restored client_settings for %s", self.name)
                except Exception:
                    logging.exception("Player._load: failed to restore client_settings for %s", self.name)

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
            if 'visited_rooms' in data and isinstance(data['visited_rooms'], dict):
                try:
                    self.visited_rooms = {str(k): str(v) for k, v in data['visited_rooms'].items()}
                except Exception:
                    pass
            if 'shield_proficiency' in data and isinstance(data['shield_proficiency'], dict):
                try:
                    self.shield_proficiency = {str(k): int(v) for k, v in data['shield_proficiency'].items()}
                except Exception:
                    pass
            if 'tuts_treasure' in data and isinstance(data['tuts_treasure'], dict):
                try:
                    from flags import TutTreasure
                    self.tuts_treasure = TutTreasure(
                        examined=bool(data['tuts_treasure'].get('examined', False)),
                        taken=bool(data['tuts_treasure'].get('taken', False)),
                    )
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
                                logging.info(
                                    "Player._load: %r is not a known PlayerFlags "
                                    "member for %s -- keeping it as a raw legacy "
                                    "flags entry (%r)",
                                    fname, self.name, entry,
                                )
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


# ---------------------------------------------------------------------------
# Per-item armor/shield durability (2026-08-08)
# ---------------------------------------------------------------------------
# Free functions, not Player methods -- deliberately, so commands/wear.py,
# commands/use.py, commands/unwear.py, combat/engine.py, combat/duel.py and
# commands/cast.py's ENCHANT ARMOR/SHIELD all call real code even when
# exercised in tests against a MagicMock() player fixture (this codebase's
# established test pattern -- see tests/commands/test_wear.py etc.). A
# MagicMock auto-vivifies any attribute access, so `player.refresh_
# equipped_rating(...)` as a *method* call would silently return an
# unconfigured Mock instead of running this logic and setting player.armor
# for real -- found live while wiring this up: two existing WEAR/USE tests
# kept asserting player.armor == 0 no matter what the real logic should
# have produced. A plain function taking `player` explicitly always runs
# for real, Mock or not, since it only reads/writes ordinary attributes.

def equipped_entry(player, slot: str):
    """Return the InventoryEntry backing the currently-equipped armor or
    shield (slot='armor'/'shield'), matched against active_armor_id/
    active_shield_id. None if that slot is empty or the id no longer
    matches anything actually carried (e.g. it was dropped/given away
    without going through commands/unwear.py).

    Source-of-truth lookup for the per-item durability model: player.armor/
    player.shield are a *derived* mirror of whatever this returns'
    item.condition is -- see refresh_equipped_rating() below. Every write
    site (WEAR/USE, UNWEAR, combat degradation, ENCHANT ARMOR/SHIELD) goes
    through this rather than trusting the flat mirror to already be right.
    """
    item_id = getattr(player, f'active_{slot}_id', None)
    if item_id is None:
        return None
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return None
    entries = inv.find(item_id=item_id)
    return entries[0] if entries else None


def refresh_equipped_rating(player, slot: str) -> int:
    """Recompute player.armor/player.shield from the equipped item's real
    condition, capped by class/race (commands/wear.py's _armor_cap() /
    commands/use.py's _shield_cap()). Call this after every equip, unequip,
    degrade, or ENCHANT so the flat mirror never drifts from the item
    actually backing it. Returns the new value.

    Zeroes the mirror (and returns 0) when the slot is empty --
    equipped_entry() returning None covers both "never equipped" and "the
    equipped item is gone" (dropped, given away, destroyed) the same way.
    """
    entry = equipped_entry(player, slot)
    if entry is None:
        setattr(player, slot, 0)
        return 0
    condition = int(getattr(entry.item, 'condition', 100) or 0)
    if slot == 'armor':
        from commands.wear import _armor_cap
        cap = _armor_cap(player)
    else:
        from commands.use import _shield_cap
        name_upper = (getattr(entry.item, 'name', '') or '').upper()
        cap_bonus  = 20 if ('BATTLE' in name_upper or 'LAZER' in name_upper) else 0
        cap = _shield_cap(player, cap_bonus)
    value = min(cap, condition)
    setattr(player, slot, value)
    return value


def unequip_if_worn(player, item) -> str | None:
    """Clear active_armor_id/active_shield_id (and refresh the mirrored
    rating) if *item* is the specific piece currently equipped in that
    slot. Returns 'armor'/'shield' when something was actually cleared,
    None otherwise -- callers use this to decide whether an informative
    message is owed (see unworn_if_given_away()).

    equipped_entry()'s own docstring already calls out "dropped/given away
    without going through commands/unwear.py" as a case it can't detect on
    its own -- this is that missing other half. Without it, GIVE/DROPping
    worn armor or a worn shield left player.armor/player.shield (and
    STATS' "(name)" display) still showing it as equipped indefinitely,
    even though it was no longer anywhere in the player's own pack.
    Matched by identity (entry.item is item), not id_number -- armor/
    shield never stack (see inventory.Inventory.add()), so two carried
    pieces can share an id_number while only one is actually the worn one.
    """
    from item_system import ItemType
    item_type = getattr(item, 'type', None)
    slot = {ItemType.ARMOR: 'armor', ItemType.SHIELD: 'shield'}.get(item_type)
    if slot is None:
        return None
    entry = equipped_entry(player, slot)
    if entry is not None and entry.item is item:
        setattr(player, f'active_{slot}_id', None)
        refresh_equipped_rating(player, slot)
        return slot
    return None


def unworn_if_given_away(player, item) -> str | None:
    """Clear whichever of player.readied_weapon / active_armor_id /
    active_shield_id currently points at *item*. Returns 'weapon',
    'armor', or 'shield' when something was actually cleared, None
    otherwise -- commands/give.py and commands/drop.py use this to tell a
    non-expert player what just happened to their equipped gear (mirrors
    commands/wear.py's existing `if not player.is_expert:` hint pattern),
    since losing a readied/worn item as an unadvertised side effect of an
    unrelated command is exactly the kind of thing a new player would
    otherwise be confused by.

    GIVE and DROP need to check all three equip slots regardless of the
    item's own type, so this wraps unequip_if_worn() (armor/shield) with
    the weapon-readied case commands/unready.py already handles on its
    own UNREADY path -- without it, giving away or dropping your
    currently readied weapon left player.readied_weapon (and STAT's
    "Weapon readied: ..." line) pointing at an item you no longer have,
    and worse, combat/resolution.py's player_attacks() takes `weapon` as
    a plain parameter with no inventory check of its own -- it would
    keep using that phantom weapon's stats for every swing until the
    player READY'd something else or UNREADY'd manually. Ryan's report,
    direct follow-up to the armor/shield version of this same bug.
    """
    if getattr(player, 'readied_weapon', None) is item:
        player.readied_weapon = None
        player.storm_servant_bonus = None
        player.skill_potion_bonus = None
        return 'weapon'
    return unequip_if_worn(player, item)


_UNWORN_VERB = {'weapon': 'wielding', 'armor': 'wearing', 'shield': 'carrying'}


def unworn_notice(slot: str | None, name: str) -> str | None:
    """Build the non-expert "(You are no longer ...)" hint for a slot
    unworn_if_given_away() just cleared, or None if nothing was cleared.
    Shared by commands/give.py and commands/drop.py so the wording can't
    drift between the two call sites."""
    if slot is None:
        return None
    return f'(You are no longer {_UNWORN_VERB[slot]} the {name}.)'


def apply_equipment_degradation(player, slot: str, degraded: int, destroyed: bool) -> None:
    """Apply combat degradation to the equipped armor/shield item's real
    .condition, and remove it from inventory entirely if destroyed.

    Shared by combat/engine.py's _apply_monster_damage() and
    combat/duel.py's _apply_degradation() -- both used to just zero or
    decrement player.armor/player.shield directly, leaving the actual
    item's condition (and its continued presence in the pack) untouched
    by the very hits that were supposed to wear it down or break it.
    Destroying an already-degraded item takes it out of inventory the
    same way commands/unwear.py takes off a healthy one -- clears
    active_armor_id/active_shield_id, item's gone either way.

    No-op (beyond a mirror refresh) if the slot turns out to be empty --
    e.g. degradation math ran against a stale flat player.armor/shield
    reading from before this redesign; nothing to charge it to.
    """
    entry = equipped_entry(player, slot)
    if entry is not None:
        if destroyed:
            inv = getattr(player, 'inventory', None)
            if inv is not None:
                inv.remove(entry.item, quantity=entry.quantity)
            setattr(player, f'active_{slot}_id', None)
        elif degraded:
            current = int(getattr(entry.item, 'condition', 100) or 0)
            entry.item.condition = max(0, current - degraded)
    refresh_equipped_rating(player, slot)
