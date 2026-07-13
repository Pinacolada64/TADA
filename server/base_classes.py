import json
import logging
import random
import re
from dataclasses import dataclass, field
from enum import Enum, StrEnum, IntEnum, auto
from typing import Dict, NamedTuple, Optional
import datetime
from enum import StrEnum, IntEnum, auto, Enum

from items import BaseItem
from network_context import GameContext


class Guild(StrEnum):
    """Guild name strings"""
    CIVILIAN = "Civilian"
    FIST = "The Iron Fist"
    SWORD = "Mark of the Sword"
    CLAW = "Mark of the Claw"
    OUTLAW = "Outlaw"


class Size(IntEnum):
    """
    Monster and Player sizes. These can be compared in combat to see if a taller monster misses over a shorter
    player's head, or vice versa
    """
    SWIFT = 0
    TINY = 1
    SHORT = 2
    SMALL = 3
    MEDIUM_SIZED = 4
    MAN_SIZED = 5
    BIG = 6
    LARGE = 7
    HUGE = 8


class Alignment(StrEnum):
    """Player and Monster alignments"""
    GOOD = "Good"
    NEUTRAL = "Neutral"
    EVIL = "Evil"


@dataclass
class BaseCharacterRace:
    """Base class for all Races; subclass for e.g., Pixie"""
    name: str = None
    """
    'can_fly' can be set to True if mounted on a Pegasus, also if the SPACE SUIT is fixed;
    this lets you navigate over bodies of water without the use of a DINGHY.
    Also the HOT AIR BALLOON in 'The Land of Oz' level could allow flight.
    If CharacterRace.PIXIE, 'can_fly' is also True.
    """
    can_fly: bool = False
    size: Size = Size.MAN_SIZED
    carrying_capacity: int = 10
    natural_alignment: Alignment = Alignment.NEUTRAL  # (depends on race)
    honor: int = 1_000  # TODO: look this up, I think that equates to Saintly for a Knight
    # current_alignment is based on Honor score (the lower it is, the more evil the character is)


class CombinationTypes(StrEnum):
    CASTLE = "Castle"
    ELEVATOR = "Elevator"  # Get this from the SCRAP OF PAPER item in the dungeon
    LOCKER = "Locker"


class Combination:
    """
    Represents a three-digit combination where each digit is between 1 and 99.
    """

    def __init__(self, name: CombinationTypes):
        """
        Initializes a combination with a given name and random numbers.
        """
        self.name = name
        self.combination = tuple(random.randrange(1, 100) for _ in range(3))  # Changed to 100 to include 99
        logging.debug("%s: %s" % (self.name, self.combination))

    def __str__(self):
        """
        Returns a formatted string for the combination, e.g., "Castle: 08-72-49".
        """
        return f"{self.name.rjust(8)}: {self.combination[0]:02}-{self.combination[1]:02}-{self.combination[2]:02}"

    @property
    def has_single_digit(self) -> bool:
        """
        A property that checks if any number in the combination is less than 10.
        Returns True if a single-digit number is found, otherwise False.
        """
        # any() is a clean way to check if any item in a sequence is True.
        # The (num < 10 for num in self.combination) part is a generator expression,
        # which is a memory-efficient way to perform this check.
        return any(num < 10 for num in self.combination)

    @classmethod
    def from_string(cls, ans, combination_type: CombinationTypes = CombinationTypes.CASTLE):
        import re
        """
        take the input string and split it into three digits separated by delimiters between digits
        (so "11-11-11", "11.11.11", "11 11 11", "11 / 11 / 11", etc. are all valid).
        Delimiter could be ".", "-", " ", etc.

        :param ans: combination type we're parsing
        :param combination_type: Type of combination (default is CASTLE)
        :return: Combination instance or None if invalid format
        """
        re.compile('\d+')
        parts = re.split(r'[\s\-.]+', ans.strip())
        if len(parts) != 3:
            return None
        try:
            numbers = tuple(int(part) for part in parts)
            if all(1 <= num <= 99 for num in numbers):
                combination = cls(name=combination_type)
                combination.combination = numbers
                return combination
            else:
                return None
        except ValueError:
            return None

    def valid_combination(self, ans):
        """
        Check if the provided answer matches the combination.
        :param ans: A tuple of three integers to check against the combination.
        :return: True if the answer matches the combination, False otherwise.
        """
        return ans == self.combination

class PlayerMoneyTypes(StrEnum):
    # this is the dict element to reference money amounts
    IN_HAND = "IN_HAND"
    IN_BANK = "IN_BANK"
    IN_BAR = "IN_BAR"


class PlayerMoneyCategory(StrEnum):
    # this refers to Player.silver{PlayerMoneyTypes.Enum} printable names
    IN_HAND = "In hand"
    IN_BANK = "In bank"
    IN_BAR = "In bar"


class WeaponClass(StrEnum):
    ENERGY = "Energy"  # 1
    BASH_SLASH = "Bash/Slash"  # 2
    POKE_JAB = "Poke/Jab"  # 3
    CLASS_4 = "X"  # class 4 was unassigned in the original code
    POLE_RANGED = "Pole/Ranged"  # 5
    CLASS_6 = "X"  # class 6 was unassigned in the original code
    CLASS_7 = "X"  # class 7 was unassigned in the original code
    PROJECTILE = "Projectile"  # 8
    PROXIMITY = "Proximity"  # 9


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"


class PronounType(Enum):
    """Defines the grammatical type of pronoun needed for Pronoun."""
    SUBJECTIVE = auto()           # e.g., "HE went to the store."
    OBJECTIVE = auto()            # e.g., "I gave the book to HIM."
    POSSESSIVE_ADJECTIVE = auto() # e.g., "That is HIS book."
    POSSESSIVE_PRONOUN = auto()   # e.g., "The book is HIS."
    REFLEXIVE = auto()            # e.g., "He did it HIMSELF."


class PlayerClass(StrEnum):
    """
    In the original Apple code, this was the variable 'pc' which could range from 1-9.
    The class number is in a comment.
    """
    # this player class will be referred to as PlayerClass.MAGIC_USER even if the player's gender is female, making her a witch:
    # FIXME: how do I do that? Python Player class can't be... inherited? from that i can see?
    #  TODO: "Wizard" if player.gender == Gender.MALE else 'Witch'
    WIZARD = "Wizard"  # 1
    DRUID = "Druid"  # 2
    FIGHTER = "Fighter"  # 3
    PALADIN = "Paladin"  # 4
    RANGER = "Ranger"  # 5
    THIEF = "Thief"  # 6
    ARCHER = "Archer"  # 7
    ASSASSIN = "Assassin"  # 8
    KNIGHT = "Knight"  # 9


class PlayerClassText(StrEnum):
    WIZARD = ("Masters of arcane magic, wizards and witches study ancient texts and theories to cast "
              "powerful spells. They often specialize in destructive elemental magic, illusions, or mind control. While "
              "formidable in spellcasting, they're typically physically frail.")
    DRUID = ("Guardians of nature, druids draw their power from the natural world. They can heal, shapeshift "
             "into animals, and wield primal magic that controls plants, weather, or the earth. They're often found in "
             "wild, untamed lands.")
    FIGHTER = ("The quintessential warrior, fighters excel in combat with various weapons and armor.They're "
               "resilient, skilled in tactical maneuvers, and can adapt to many fighting styles. They form the "
               "backbone of most adventuring parties.")
    PALADIN = ("Holy warriors, paladins are bound by sacred oaths to uphold justice and protect the innocent. "
               "They combine martial prowess with divine magic, capable of healing, smiting evil, and inspiring allies.")
    RANGER = ("Skilled survivalists and trackers, rangers are at home in the wilderness. They often specialize "
              "in archery and can commune with nature or animal companions. They excel at hunting, scouting, and "
              "ranged combat.")
    THIEF = ("Nimble and cunning, thieves operate in the shadows, specializing in stealth, lock-picking, "
             "disarming traps, and sleight of hand. They're excellent at reconnaissance and finding hidden treasures, "
             "and can be surprisingly deadly in a quick strike.")
    ARCHER = ("A specialist in ranged combat, the archer focuses entirely on mastery of the bow or crossbow. "
              "They are precise, agile, and can unleash a barrage of arrows, often finding weak points in an enemy's "
              "defense.")
    ASSASSIN = ("A darker counterpart to the thief, assassins are highly trained killers focused on "
                "eliminating specific targets. They excel at stealth, disguise, and delivering devastating surprise "
                "attacks, often utilizing poisons.")
    KNIGHT = ("A disciplined and honorable warrior, often serving a lord, kingdom, or an ideal. Knights are "
              "typically heavily armored and skilled in mounted combat, prioritizing defense and protecting their "
              "allies on the battlefield.")


class PlayerRace(StrEnum):
    """
    In the original Apple code, this was the variable 'pr' which could range from 1-9.
    The race number is in a comment.
    """
    """
    branch master/spur-code/LOGON.S:
    1) Human    4) Elf        7) Dwarf
    2) Ogre     5) Hobbit     8) Orc
    3) Pixie    6) Gnome      9) Half-Elf

    branch Skip/spur-code/SPUR.NEW.S:
    new4
     print \'Please Choose a Race:

    1) Human    4) Elf        7) Dwarf
    2) Ogre     5) Hobbit     8) Orc
    3) Pixie    6) Gnome      9) Half-Elf
    """
    HUMAN = "Human"  # 1
    OGRE = "Ogre"  # 2
    PIXIE = "Pixie"  # 3
    ELF = "Elf"  # 4
    HOBBIT = "Hobbit"  # 5
    # Apparently Halfling is the same as a Hobbit
    # HALFLING = "Halfling"  # 5
    GNOME = "Gnome"  # 6
    DWARF = 'Dwarf'  # 7
    ORC = 'Orc'  # 8
    HALF_ELF = 'Half-Elf'  # 9


class PlayerRaceText(StrEnum):
    HUMAN = ("The most adaptable and widespread race, humans are known for their diversity, ambition, and resilience. "
             "They can be found in almost any profession or land, often driven by innovation and a desire to explore.")
    OGRE = ("Large, powerful, and often fearsome, ogres are known for their immense strength and raw brute force. "
            "While sometimes depicted as simple-minded, they are capable of incredible feats of power.")
    PIXIE = ("Pixies are tiny, humanoid creatures of the Fae folk, renowned for their small size, delicate insect-like "
             "wings, and notoriously mischievous nature. They are often described as being no taller than a human hand, "
             "with slender limbs, pointed ears, and bright, sparkling eyes that reflect their lively personalities. "
             "Their wings shimmer with iridescent colors, often resembling those of a dragonfly or butterfly, allowing "
             "them to flit through the air with incredible speed and agility.")
    ELF = ("Graceful and long-lived, elves are often associated with magic, nature, and the arts. They possess keen "
           "senses and a natural affinity for archery and arcane knowledge, though they can sometimes seem aloof to "
           "shorter-lived races.")
    HOBBIT = ("Small and good-natured, hobbits are known for their love of comfort, good food, and simple lives. They "
              "are surprisingly agile and lucky, often making excellent thieves or unassuming adventurers.")
    GNOME = ("Small, inventive, and curious, gnomes are often fascinated by technology, illusions, and intricate "
             "mechanisms. They are known for their quick wit, practical jokes, and a love for discovery.")
    DWARF = ("Stout and resilient, dwarves are master artisans, miners, and warriors, with a strong connection to "
             "mountains and stone. They are known for their stubbornness, honor, and exceptional craftsmanship in "
             "metalwork and engineering.")
    ORC = ("Often depicted as fierce and warlike, orcs are strong and formidable in battle. They value strength and "
           "tribal loyalty, typically preferring direct confrontation over subtle tactics.")
    HALF_ELVES = ("Half-elves are the offspring of a human and an elf. This union creates individuals who embody "
                  "traits from both lineages. Like elves, half-elves often inherit a resistance to magical sleep and "
                  "charm effects, a subtle nod to their fey bloodline.")
    """
    "Darkvision: Many half-elves inherit the ability to see in dim light and darkness, though usually not as far as a "
    "full elf. "
    ""
    "Skill Versatility: In many game systems, half-elves are known for their broad skill set, able to pick up various "
    "proficiencies with relative ease. This further enhances their adaptable nature. "
    ""
    "Archetypes: Half-elves make fine bards, rogues, rangers, or diplomats. Their unique perspective also makes them "
    "compelling heroes or anti-heroes who grapple with their identity. "
    ""
    "In essence, a half-elf embodies the strengths and challenges of a blended heritage, often navigating a world "
    "where they are both familiar and foreign, and constantly seeking their place within it.")
    """

def class_and_race_combinations(ctx: GameContext):
    """

    :param ctx:
    :return: True: indicates a valid class/race combination
    """
    # if either ctx.player.char_class or ctx.player.char_race are None, character setup
    # is incomplete, and this should silently return True to allow char creation/editing
    # to continue until both char_class and char_race contain something to evaluate:

    if ctx.player.char_class is None or ctx.player.char_race is None:
        return True

    # list of bad class & race combinations:
    # TODO: use in Annex to change class/race?

    #       player class        disallowed player races
    test = {PlayerClass.WIZARD: [PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC],
            PlayerClass.DRUID: [PlayerRace.OGRE, PlayerRace.ORC],
            PlayerClass.THIEF: [PlayerRace.ELF],
            PlayerClass.ARCHER: [PlayerRace.OGRE, PlayerRace.GNOME, PlayerRace.HOBBIT],
            PlayerClass.ASSASSIN: [PlayerRace.GNOME, PlayerRace.ELF, PlayerRace.HOBBIT],
            PlayerClass.KNIGHT: [PlayerRace.OGRE, PlayerRace.ORC]}

    """
    # find PlayerClass key in test dict:
    for class, races in test.items():
        if ctx.player.char_class in test:

    if ctx.player.char_class == PlayerClass.WIZARD:
        logging.info("-=> Wizard")
        if ctx.player.char_race in [PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC]:
            logging.info("-=> %s: bad" % ctx.player.char_race)
            good_combination = False

    elif ctx.player.char_class == PlayerClass.DRUID:
        if ctx.player.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            good_combination = False

    elif ctx.player.char_class == PlayerClass.THIEF:
        if ctx.player.char_race == PlayerRace.ELF:
            good_combination = False

    elif ctx.player.char_class == PlayerClass.ARCHER:
        if ctx.player.char_race in [PlayerRace.OGRE, PlayerRace.GNOME, PlayerRace.HOBBIT]:
            good_combination = False

    elif ctx.player.char_class == PlayerClass.ASSASSIN:
        if ctx.player.char_race in [PlayerRace.GNOME, PlayerRace.ELF, PlayerRace.HOBBIT]:
            good_combination = False

    elif ctx.player.char_class == PlayerClass.KNIGHT:
        if ctx.player.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            good_combination = False
    """

class PlayerStat(StrEnum):
    CHR = "Charisma"
    CON = "Constitution"
    DEX = "Dexterity"
    INT = "Intelligence"
    STR = "Strength"
    WIS = "Wisdom"
    EGY = "Energy"


class PlayerRaceBonuses(Enum):
    # applied upon character creation, maybe elsewhere in future
    HUMAN = {PlayerStat.CON: 1, PlayerStat.DEX: 2, PlayerStat.INT: 2, PlayerStat.STR: -1},
    OGRE = {PlayerStat.CON: 2, PlayerStat.DEX: -1, PlayerStat.INT: -2, PlayerStat.STR: 3, PlayerStat.WIS: -1},
    PIXIE = {PlayerStat.DEX: -1, PlayerStat.STR: 1, PlayerStat.WIS: 1},
    ELF = {PlayerStat.DEX: 2, PlayerStat.INT: 1, PlayerStat.CON: -1, PlayerStat.WIS: 2},
    HOBBIT = {PlayerStat.DEX: 1, PlayerStat.INT: 2, PlayerStat.STR: -1, PlayerStat.EGY: 1},
    # FIXME: Gnome bonuses same as Human?:
    GNOME = {PlayerStat.CON: 1, PlayerStat.DEX: 2, PlayerStat.INT: 2, PlayerStat.STR: -1},
    DWARF = {PlayerStat.CON: 1, PlayerStat.DEX: -1, PlayerStat.CHR: 2},
    ORC = {PlayerStat.DEX: 1, PlayerStat.INT: -1, PlayerStat.STR: 2, PlayerStat.WIS: -1, PlayerStat.EGY: 2},
    HALF_ELF = {PlayerStat.DEX: 1, PlayerStat.WIS: 1}


class PlayerClassBonuses(Enum):
    # applied upon character creation, maybe elsewhere in future
    WIZARD ={PlayerStat.CON: -1, PlayerStat.INT: 2},
    DRUID ={PlayerStat.INT: 2, PlayerStat.STR: -1, PlayerStat.WIS: 2},
    FIGHTER ={PlayerStat.CON: 2, PlayerStat.DEX: -1, PlayerStat.INT: -2, PlayerStat.STR: 2, PlayerStat.EGY: 2},
    PALADIN ={PlayerStat.DEX: 1, PlayerStat.INT: 1, PlayerStat.STR: 1, PlayerStat.WIS: 1},
    RANGER ={PlayerStat.INT: -1, PlayerStat.STR: 1, PlayerStat.WIS: -1},
    THIEF ={PlayerStat.DEX: 1, PlayerStat.EGY: 2},
    ARCHER ={PlayerStat.DEX: 2, PlayerStat.EGY: -2},
    ASSASSIN ={PlayerStat.DEX: -1, PlayerStat.STR: 2},
    KNIGHT ={PlayerStat.CON: 1, PlayerStat.INT: 1, PlayerStat.EGY: -1}



class RoomAlignment(StrEnum):
    """Territorial affiliation of a *room* -- distinct from Guild, which is a
    *player/NPC's* own guild membership. SPUR never stores this as a discrete
    field: guild-territory checks are live substring tests on the room name
    (e.g. instr("=[]",ww$) for Fist, instr("\\|/",ww$) for Claw -- see
    SPUR.MAIN.S:589-592, SPUR.GUILD.S:12-15, SPUR.DUEL2.S:21/94/102/202/297/377),
    with no explicit "else" branch when nothing matches. NEUTRAL is this
    port's name for that fall-through case, not a state SPUR itself sets.
    """
    NEUTRAL   = "neutral"    # no marker -- open to all, no special rules
    FREE_FIRE = "free_fire"  # '+' suffix -- combat allowed regardless of guild
    FIST      = "fist"       # '=[]' suffix -- Fist guild territory
    CLAW      = "claw"       # '\|/' suffix -- Claw guild territory
    SWORD     = "sword"      # '-}----' suffix -- Sword guild territory
    HQ        = "hq"         # 'HQ' marker -- headquarters of whichever guild owns the room


# Human-readable labels for displaying a room's alignment to players (e.g.
# simple_server.py's _describe_room()). Kept separate from the enum's own
# .value strings, which _parse_room_alignment() matches directly against
# lowercase JSON tokens ('free_fire', 'fist', ...) -- renaming the .value
# strings themselves would break that parsing.
_ROOM_ALIGNMENT_LABELS: Dict["RoomAlignment", str] = {
    RoomAlignment.FREE_FIRE: "Free-Fire",
    RoomAlignment.FIST:      "Fist Territory",
    RoomAlignment.CLAW:      "Claw Territory",
    RoomAlignment.SWORD:     "Sword Territory",
    RoomAlignment.HQ:        "HQ",
}


def room_alignment_label(alignment: Optional["RoomAlignment"]) -> Optional[str]:
    """Human-readable label for *alignment*, or None if it shouldn't be shown.

    NEUTRAL means "no marker" (see RoomAlignment's docstring) and is never
    displayed -- every ordinary room defaults to NEUTRAL, so showing it would
    tag nearly every room in the game for no reason.
    """
    return _ROOM_ALIGNMENT_LABELS.get(alignment)


# level_1.json (the earliest, GBBS-tool-converted data) bakes SPUR's own
# ASCII sigil directly into some room names, e.g. 'CAVERN LEDGE -]----' or
# 'SECLUDED ROOM ==[] HQ'. Later, hand-authored levels (2-7) never do this
# -- their free_fire rooms are just plain names ('Tiny Town', 'The Foyer',
# ...). Display code renders its own colorized, terminal-appropriate sigil
# from room.alignment (see formatting.guild_sigil_for()) instead, so this
# legacy text needs stripping first to avoid showing the sigil twice.
_LEGACY_ALIGNMENT_SUFFIX_RE = re.compile(
    r'\s*(?:\+|-\]-+|-\}-+|==\[\]|//>|\\\|/)(\s+HQ)?\s*$'
)


def strip_legacy_alignment_suffix(name: str) -> tuple[str, bool]:
    """Strip a baked-in legacy SPUR sigil suffix from *name*, if present.

    Returns (clean_name, is_hq) -- is_hq is True if the suffix included a
    trailing 'HQ' marker (e.g. 'CAVERN PEAK -]---- HQ'), since that fact
    isn't tracked anywhere else (no room's `alignment` field is ever
    actually RoomAlignment.HQ in practice; HQ only ever appears as this
    bit of trailing name text alongside a guild alignment).
    """
    match = _LEGACY_ALIGNMENT_SUFFIX_RE.search(name)
    if not match:
        return name, False
    return _LEGACY_ALIGNMENT_SUFFIX_RE.sub('', name).rstrip(), bool(match.group(1))


# Room.exits is keyed by full words (north/south/east/west/up/down), but
# typed movement commands resolve to short forms (n/s/e/w/u/d) -- see
# Room.get_exit() and commands/movement.py's _DIR_ALIASES.
_SHORT_TO_FULL_DIRECTION = {'n': 'north', 's': 'south', 'e': 'east',
                            'w': 'west', 'u': 'up', 'd': 'down'}


class HiddenExitTarget(NamedTuple):
    """A confirmed hidden-exit destination -- see Room.hidden_exit()."""
    level: int
    room: int
    message_number: Optional[int] = None


@dataclass
class Room(object):
    number: int
    name: str
    desc: str
    exits: dict = field(default_factory=lambda: {})  # {n e s w rc rt}
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    # Territorial alignment of this room (Fist/Claw/Sword turf, free-fire
    # zone, guild HQ, or neutral). Not to be confused with Guild, which is a
    # player/NPC's own guild membership -- see RoomAlignment's docstring.
    alignment: RoomAlignment = RoomAlignment.NEUTRAL
    # List of RoomFlag values (as strings) parsed from SPUR room data.
    # e.g. ["water"], ["snow"], ["no_flee"], ["block_north", "block_east"]
    #
    # "grassy" is the one exception: in SPUR, checks like the sugar-cube/
    # wild-horse mechanics (SPUR.MISC.S d.sugar, SPUR.MAIN.S's `horse`
    # subroutine) test `instr("GRASSY", ww$)`, where ww$ is just the room's
    # own NAME text -- not a real structured flag. No room in the ported
    # data is actually named with "GRASSY" (the original room may not have
    # survived conversion), so this port retrofits the flag onto level 5
    # room 204 "Tiny Meadow" (ravine + "rich grass" in its description) as
    # the closest existing match, rather than reproducing a name-substring
    # check against nonexistent data.
    flags: list = field(default_factory=list)
    # Confirmed hidden-exit destinations (SPUR.MISC.S:419 "->"/"<-" markers --
    # the marker itself only says an exit exists, not where it goes, so this
    # is filled in per-room only once the real destination has been traced
    # against the SPUR source). Either a bare room number (same level) or
    # {"room": n, "level": n, "message_number": n} for a cross-level
    # destination like level 1 room 89's hardcoded teleport (SPUR.MISC.S:448)
    # -- "message_number" is optional, a server/messages.json key (see
    # messages.py) printed before the move. None if unconfirmed -- see
    # Server._hidden_exit_target()'s +/-1 guess fallback for rooms that only
    # carry the legacy hidden_exit_east/west flag string.
    hidden_exit_east: Optional[object] = None
    hidden_exit_west: Optional[object] = None

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

    def hidden_exit(self, direction: str, current_level: int) -> Optional['HiddenExitTarget']:
        """Return a HiddenExitTarget for a *confirmed* hidden exit, or None.

        Accepts short ('e'/'w') or full ('east'/'west') direction forms.
        """
        attr = {'e': 'hidden_exit_east', 'east': 'hidden_exit_east',
                'w': 'hidden_exit_west', 'west': 'hidden_exit_west'}.get(direction)
        value = getattr(self, attr, None) if attr else None
        if value is None:
            return None
        if isinstance(value, dict):
            msg_num = value.get('message_number')
            return HiddenExitTarget(
                level=int(value.get('level', current_level)),
                room=int(value['room']),
                message_number=int(msg_num) if msg_num is not None else None,
            )
        return HiddenExitTarget(level=current_level, room=int(value))

    def get_exit(self, direction: str) -> Optional[int]:
        """Look up an exit room number by direction, short or full form.

        Room data stores exits under full-word keys (north/south/east/west),
        but typed movement commands resolve to short forms (n/s/e/w/u/d)
        before reaching here -- see commands/movement.py's _DIR_ALIASES.
        Without normalizing, exits.get(direction) always missed and every
        real exit silently behaved like a dead end.
        """
        full = _SHORT_TO_FULL_DIRECTION.get(direction, direction)
        dest = self.exits.get(direction)
        if dest is None:
            dest = self.exits.get(full)
        return int(dest) if dest else None

    def exits_txt(self, ctx) -> str:
        """Return exits as a comma-delimited string.

        Takes a ctx (anything with a .player exposing is_debug), matching
        the calling convention used everywhere else in the codebase,
        rather than a bare debug bool -- so callers just pass the ctx they
        already have. When ctx.player.is_debug is set, each exit is
        annotated with its destination room number, e.g. "Up [to #47]".

        rc/rt semantics (historical TADA map format):
          rc == 1: Up connection   rt == 0: Shoppe   rt > 0: room number
          rc == 2: Down connection
        String values from JSON are coerced to int defensively.

        Room data stores exits under full-word keys (north/south/east/west --
        convert_from_gbbs_tool.py's EXIT_KEYS, used by every level including
        level_1.json since its reconciliation onto the modern schema), but
        compass_txts is keyed by the short forms used for typed movement
        commands (n/s/e/w). Without normalizing here, this always produced an
        empty exit list -- "Ye may travel:" silently never printed anything.
        """
        debug = bool(getattr(getattr(ctx, 'player', None), 'is_debug', False))
        _full_to_short = {v: k for k, v in _SHORT_TO_FULL_DIRECTION.items()}
        exit_txts = []
        for k in self.exits:
            short = _full_to_short.get(k, k)
            if short not in compass_txts:
                continue
            label = compass_txts[short]
            if debug:
                dest = self.exits.get(k)
                if dest:
                    label = f'{label} [to #{dest}]'
            exit_txts.append(label)
        try:
            rc = int(self.exits.get('rc', 0) or 0)
        except (ValueError, TypeError):
            rc = 0
        try:
            rt = int(self.exits.get('rt', 0) or 0)
        except (ValueError, TypeError):
            rt = 0
        if rc == 1:
            if rt == 0:
                exit_txts.append('Up to Shoppe')
            elif debug:
                exit_txts.append(f'Up [to #{rt}]')
            else:
                exit_txts.append('Up')
        elif rc == 2:
            if rt == 0:
                exit_txts.append('Down to Shoppe')
            elif debug:
                exit_txts.append(f'Down [to #{rt}]')
            else:
                exit_txts.append('Down')
        from tada_utilities import oxford_comma_list
        return oxford_comma_list(exit_txts, conjunction='or')


def _parse_room_alignment(value) -> RoomAlignment:
    """Coerce a JSON alignment value to a RoomAlignment, defaulting to NEUTRAL.

    Two JSON shapes exist in the wild:
      - level_1.json (hand/earlier-tooled): bare lowercase strings like
        'fist'/'claw'/'sword', keyed 'alignment'.
      - convert_from_gbbs_tool.py output: the same value set plus
        'free_fire'/'hq', keyed 'room_alignment'.
    Both use RoomAlignment's own string values, so a direct lookup covers both.
    """
    try:
        return RoomAlignment(str(value).lower())
    except ValueError:
        return RoomAlignment.NEUTRAL


class Map(object):
    def __init__(self):
        """
        Define the level map layout
        """
        self.rooms = {}    # backward-compat alias: same dict as self.levels[1]
        self.levels = {}   # {map_level (1-7): {room_number: Room}}

    def read_map(self, filename: str, level: int = 1):
        """
        Data format on C64:
        * Room number        (rm)
        * Location name      (lo$)
        * items: monster, item, weapon, food
        * exits: north, east, south, west,
          RC (room command: 1=move up,
                            2=move down),
          RT (Room exit transports you to:
                 <>0: room #, or 0=Shoppe)
        https://github.com/Pinacolada64/TADA/blob/master/text/s_t_level-1-data.txt

        *level* selects which dungeon floor (SPUR's cl, 1-7) this file's rooms
        belong to; room numbers are only unique within a single level.  Pass
        level=1 (the default) for the original single-level JSON shape.
        """
        try:
            with open(filename) as jsonF:
                map_data = json.load(jsonF)
                logging.debug("read_map: JSON data read")
                rooms = {}
                for room_data in map_data['rooms']:
                    room_kwargs = dict(room_data)
                    # convert_from_gbbs_tool.py keys this 'room_alignment';
                    # level_1.json keys it plain 'alignment' -- normalize both
                    # to a real RoomAlignment enum member.
                    raw_alignment = room_kwargs.pop('room_alignment', None)
                    if raw_alignment is None:
                        raw_alignment = room_kwargs.get('alignment')
                    room_kwargs['alignment'] = _parse_room_alignment(raw_alignment)
                    room = Room(**room_kwargs)
                    rooms[room.number] = room
                    logging.debug('%i: %s' % (room.number, room.name))
                self.levels[level] = rooms
                if level == 1:
                    self.rooms = rooms
        except FileNotFoundError:
            logging.error(">>> read_map: File not found: '%s'" % filename)

    def get_room(self, level: int, room_number: int) -> Optional['Room']:
        """Look up a room on a specific dungeon level, or None if not loaded."""
        return self.levels.get(level, {}).get(room_number)


class VinneyLoan(object):
    def __init__(self, due_date: datetime.date, amount_due: int):
        self.due_date = due_date
        self.amount_due = amount_due


compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West', 'u': 'Up', 'd': 'Down'}


class InventoryItem:
    """Base class for all inventory items, such as weapons, armor, etc.
     It holds Item object and the quantity of the item.
    """
    def __init__(self, item: BaseItem, quantity: int = 1):
        """
        Initialize the InventoryItem with an item and a quantity.
        :param item: The item object (e.g., Weapon, Armor, etc.)
        :param quantity: The number of this item in the inventory
        """
        self.item = item
        self.quantity = quantity

    def find_item(self, item_name: "InventoryItem") -> bool:
        """
        Check if the item string matches the given name.
        :param item_name: The name of the item to check
        :return: True if the item matches, False otherwise
        """
        return self.item.name.lower() == item_name.lower()

    def __increment_quantity(self, amount: int = 1):
        """
        Increment the quantity of the item by a specified amount.
        :param amount: The amount to increment the quantity by (default is 1)
        """
        if amount < 1:
            raise ValueError("Amount must be at least 1")
        self.quantity += amount

    def __decrement_quantity(self, amount: int = 1):
        """
        Decrement the quantity of the item by a specified amount.
        :param amount: The amount to decrement the quantity by (default is 1)
        """
        if amount < 1:
            raise ValueError("Amount must be at least 1")
        if self.quantity - amount < 0:
            raise ValueError("Cannot decrement quantity below zero")
        if self.quantity - amount == 0:
            logging.debug(f"Removing {self.item.name} from inventory")
            self.remove_item(self.item)
            return None
        self.quantity -= amount
        return None

    def __str__(self):
        if self.quantity == 1:
            return f"{self.item.name}"
        elif self.quantity > 1:
            return f"{self.item.name} (x{self.quantity})"
        return None

    def remove_item(self, item):
        self.inventory.remove(item)

