import collections
import logging
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

from base_classes import Gender, Alignment


class AllyFlags(Enum):
    GOD = auto()
    GODDESS = auto()
    ELITE = auto()
    MECHANICAL = auto()
    # Can track other characters:
    TRACKING = auto()
    FIND_THINGS = auto()
    MOUNT = auto()
    BODY_BUILD = auto()

class AllyPosition(Enum):
    """Tactical position"""
    EMPTY = auto()
    LURKING = auto()
    POINT = auto()
    FLANK = auto()
    REAR = auto()


class AllyStatus(Enum):
    FREE = auto()
    SERVANT = auto()
    IN_PARTY = auto()
    UNCONSCIOUS = auto()
    DEAD = auto()


# 1. Define a clear and robust data structure
@dataclass
class Ally:
    """
    :param name: name
    :param gender: gender
    :param strength: strength
    :param to_hit: to-hit probability (x10, so 4 x10 = 40)
    :param flags: AllyFlags class [optional]
    """
    from base_classes import Alignment

    # 1. Define fields in the order your data provides them, e.g.:
    # Ally("ALAN OF YOR", "m", 9, 4),
    name: str
    gender: str  # Accept the raw string 'm' or 'f' first
    strength: int
    to_hit: int
    flags: Optional[List[AllyFlags]] = field(default_factory=list)

    def __post_init__(self):
        """
        This special method runs after the object is created.
        It's the perfect place to transform input data.
        """
        from base_classes import Alignment, Gender
        self.status = self.AllyStatus = AllyStatus.FREE  # Enum
        # # in TLoS: '(' good, ')' evil
        self.alignment: Alignment = Alignment.NEUTRAL
        self.position: AllyPosition = AllyPosition.EMPTY

        # 2. Convert the gender string to the correct Gender enum
        if self.gender == 'm':
            self.gender = Gender.MALE
        elif self.gender == 'f':
            self.gender = Gender.FEMALE

        self.hit_points: int = 0
        # 'ayf': int  # ally has a 1-ayf% chance of randomly finding sack of gold/diamond/etc.
        self.find_percentage: int = 0
        # TODO: look at Skip's branch on GitHub, it has more TRACKing stuff:
        """
        # https://github.com/Pinacolada64/TADA-old/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.MISC9.S
        # number of rooms away an ally can detect a target
        # TLOS: distance between tracker and target determined track strength.
        # target's last play date delta compared to date.today determines
        # "strength" of tracks: 1-3 days: very fresh, >3 days: weak (?)
        # https://docs.python.org/3/library/datetime.html
        """
        self.tracking_range: int = 0
        self.body_build: int = 0
        # 3. Use an f-string for safer and more readable logging
        #    Using .name on enums provides a clean string like "MALE"
        logging.debug(
            f"ALLY CREATED: name={self.name}, gender={self.gender.name}, "
            f"str={self.strength}, to_hit={self.to_hit}, flags={self.flags}, "
            f"status={self.status.name}, hp={self.hit_points}"
        )


def find_duplicate_allies(ally_list: List[Ally]) -> List[str]:
    """
    Checks for Allies with duplicate names in a list and prints a warning.

    Args:
        ally_list: The list of Ally objects to check.

    Returns:
        A list of names that were found to be duplicates.
    """
    # Create a list of all ally names
    names = [ally.name for ally in ally_list]

    # Count the occurrences of each name
    name_counts = collections.Counter(names)

    # Filter for names that appear more than once
    duplicates = [name for name, count in name_counts.items() if count > 1]

    if duplicates:
        print("⚠️ WARNING: Duplicate allies found!")
        for name in duplicates:
            print(f"  - '{name}' appears {name_counts[name]} times.")
    else:
        print("✅ No duplicate allies found.")

    return duplicates


def load_allies() -> list:
    # server_dir = Path(pathlib.Path.cwd())
    # ally_file = Path(server_dir / "allies.json")
    # with json.load(ally_file) as af:
    #     json.load()
    # https://github.com/Pinacolada64/TADA/blob/skip/SPUR-code/SPUR.BAR.S
    """Loads ally information from a structured list."""

    # Name, gender, strength, to-hit % (x10), flags
    # 3. Refactor the loop to use named attributes
    ally_data = [
        # name, gender, strength, to-hit % (x10), flags
        # alan-a-dale? I can't find info on him:
        Ally("ALAN OF YOR", "m", 9, 4),
        # Egyptian god of funerary rites:
        Ally("ANUBIS", "m", 5, 8, [AllyFlags.GOD]),
        # greek god of oracles, healing, archery, music and arts, light, knowledge,
        # herds and flocks, and protection of the young
        Ally("APOLLO", "m", 15, 7, [AllyFlags.GOD]),
        # greek god of war:
        Ally("ARES", "m", 15, 9, [AllyFlags.GOD]),
        # main protagonist of "Hitchhiker's Guide to the Galaxy":
        Ally("ARTHUR DENT", "m", 4, 4),
        # Greek goddess of wisdom, warfare, and handicraft:
        Ally("ATHENA", "f", 15, 6, [AllyFlags.GODDESS]),
        Ally("ATILLA THE HUN", "m", 15, 7),
        # from Batman comic:
        Ally("BATMAN", "m", 14, 5, [AllyFlags.ELITE]),
        Ally("BEAVER CLEAVER", "m", 9, 6),
        Ally("BETTY BOOP", "f", 7, 6),
        # from Monty Python and the Holy Grail?:
        Ally("BLACK KNIGHT", "m", 12, 7, [AllyFlags.ELITE]),
        Ally("BLUE DEMON", "m", 19, 9),
        Ally("BUCK ROGERS", "m", 12, 5),
        # singer:
        Ally("CARLY SIMON", "f", 8, 9),
        # from Batman comic:
        Ally("CATWOMAN", "f", 17, 5),
        Ally("CENTURIAN ROCK", "m", 20, 9, [AllyFlags.ELITE]),
        # American football player & coach (coached the Seahawks):
        Ally("CHUCK KNOX", "m", 12, 5),
        # Superman's alter ego:
        Ally("CLARK KENT", "m", 20, 9),
        # from the TV show "Hogan's Heroes":
        Ally("COLONEL KLINK", "m", 10, 2),
        Ally("CONAN", "m", 15, 6, [AllyFlags.ELITE]),
        Ally("DARK WARRIOR", "m", 12, 5),
        # from Star Wars:
        Ally("DARTH VADER", "m", 12, 6),
        # American politician, militia officer and frontiersman:
        Ally("DAVY CROCKETT", "m", 15, 7, [AllyFlags.ELITE]),
        # Greek goddess of food & fertility, wife of Zeus:
        Ally("DEMETER", "f", 12, 5, [AllyFlags.GODDESS]),
        Ally("DIRTY HARRY", "m", 18, 7),
        # From the movie "Back to the Future":
        Ally("DOC BROWN", "m", 4, 3),
        Ally("DRAGONSLAYER", "m", 19, 8),
        Ally("DUKE OF EARL", "m", 12, 8),
        # noblewoman of Rohan in "Lord of the Rings," defeats the Nazgul:
        Ally("EOWYN", "f", 16, 9),
        # https://en.wikipedia.org/wiki/Finieous_Fingers
        Ally("FINIEOUS FINGERS", "m", 12, 5),
        # From "Hitchhiker's Guide to the Galaxy":
        Ally("FORD PREFECT", "m", 3, 6),
        # Finieous Fingers' henchmen:
        Ally("FRED AND CHARLY", "m", 15, 9),
        Ally("FRED THE TERRIBLE", "m", 10, 7),
        # from "The Hobbit":
        Ally("FRODO", "m", 8, 6),
        # same:
        Ally("GANDALF THE GREY", "m", 7, 7, [AllyFlags.ELITE]),
        Ally("HAMMER", "m", 20, 9),
        Ally("IRIS", "f", 12, 5),
        Ally("IRON MAIDEN", "m", 14, 6),
        # writer of "The Hobbit," et al.:
        Ally("J.R.R. TOLKIEN", "m", 4, 3),
        # 3 singers:
        Ally("JANIS JOPLIN", "f", 15, 5),
        Ally("JIM MORRISON", "m", 4, 5),
        Ally("JUDAS PRIEST", "m", 8, 6),
        Ally("JULIA FELIX", "f", 10, 5),
        Ally("JULIAS CAESAR", "m", 12, 6, [AllyFlags.ELITE]),
        # Pulled the Sword from the Stone to become ruler of England:
        Ally("KING ARTHUR", "m", 16, 6, [AllyFlags.ELITE]),
        Ally("LAZY LARRY", "m", 7, 3),
        # from "Star Wars":
        Ally("LUKE SKYWALKER", "m", 15, 5),
        # singer:
        Ally("MARIAH CAREY", "f", 10, 5),
        # King Arthur's court wizard:
        Ally("MERLIN", "m", 10, 3, [AllyFlags.ELITE]),
        Ally("MINICIUS ITALUS", "m", 15, 6, [AllyFlags.ELITE]),
        # early childhood educator:
        Ally("MISTER ROGERS", "m", 10, 5),
        # alien from "Mork & Mindy" played by Robin Williams:
        Ally("MORK FROM ORK", "m", 15, 7),
        # Vulcan science officer aboard the Enterprise in Star Trek:
        Ally("MR. SPOCK", "m", 16, 6),
        Ally("MYSTIC MORGANNA", "f", 6, 4),
        # pizza-loving mutant turtles who live in the sewers:
        Ally("NINJA TURTLE", "m", 12, 5),
        # Greek god of the wild, shepherds and flocks:
        Ally("PAN", "m", 13, 6),
        # Francisco "Pancho" Villa, Mexican revolutionary, later president:
        Ally("PANCHO VILLA", "m", 10, 5),
        # singer:
        Ally("PAULA ABDUL", "f", 9, 8),
        # Greek goddess of spring, queen of the underworld after Hades abducted her::
        Ally("PERSEPHONE", "f", 9, 6, [AllyFlags.GODDESS]),
        # American news reporter:
        Ally("PETER JENNINGS", "m", 13, 6),
        # Queen of the British Iceni tribe:
        Ally("QUEEN BOUDICA", "f", 12, 5, [AllyFlags.ELITE]),
        # astromech droid from "Star Wars":
        Ally("R2-D2", "m", 9, 6, [AllyFlags.MECHANICAL]),
        # action movie hero:
        Ally("RAMBO", "m", 18, 7, [AllyFlags.ELITE]),
        # partner of Conan the Barbarian:
        Ally("RED SONJA", "f", 16, 6, [AllyFlags.ELITE]),
        Ally("RIKER THE STRIKER", "m", 12, 7),
        # character from the movie "Aliens":
        Ally("RIPLEY", "f", 18, 9),
        Ally("ROBIN HOOD", "m", 14, 8, [AllyFlags.ELITE]),
        # Yeah, not sure about this guy:
        # Ally("SADDAM HUSSEIN", "m", 5, 3),
        Ally("SAMWISE", "m", 14, 6),
        # character in "Terminator" movie:
        Ally("SARAH CONNOR", "f", 16, 5),
        # evil wizard in "Lord of the Rings":
        Ally("SARUMAN", "m", 20, 9),
        # engineer aboard the Enterprise in "Star Trek":
        Ally("SCOTTY", "m", 6, 4),
        # one of the Knights of King Arthur's Round Table:
        Ally("SIR GALAHAD", "m", 15, 4),
        Ally("SLAVE VERUS", "m", 20, 1),
        Ally("STEELY DAN", "m", 15, 7),
        # General in the Gulf War:
        Ally("STORMIN' NORMAN", "m", 20, 9),
        # FIXME: Typo? can't find "TAARNA"
        # Tarana Burke is an activist, started the "MeToo" movement
        Ally("TAARNA", "f", 12, 5),
        # American singer:
        Ally("TAYLOR DAYNE", "f", 6, 3),
        Ally("THE BISHOP", "m", 10, 7),
        Ally("THE BOGIEMAN", "m", 15, 5),
        Ally("THE IRON LADY", "f", 18, 9),
        # Character in, well, the movie of the same name:
        Ally("THE TERMINATOR", "m", 20, 5),
        Ally("TIMMY", "m", 7, 6),
        # Bob Cratchit's son from "A Christmas Carol":
        Ally("TINY TIM", "m", 6, 5),
        Ally("TRAJAN OF DURA", "m", 15, 8),
        # character from "Hitchhiker's Guide to the Galaxy":
        Ally("TRICIA MCMILLAN", "f", 4, 5),
        # communications officer aboard the Enterprise in "Star Trek":
        Ally("UHURA", "f", 7, 4),
        Ally("VERUS' BROTHER", "m", 15, 6),
        # American songwriter and rock star, wrote "Werewolves in London"
        Ally("WARREN ZEVON", "m", 15, 6),
        Ally("WEREWOLF OF LONDON", "m", 10, 5),
        # superheroine:
        Ally("WONDER WOMAN", "f", 18, 5, [AllyFlags.ELITE]),
        Ally("XEVIOUS", "m", 12, 4),
        # wise critter from Star Wars:
        Ally("YODA", "m", 15, 8),
        # President of the Galaxy in "Hitchhiker's Guide to the Galaxy":
        Ally("ZAPHOD BEEBLEBROX", "m", 5, 5),
        Ally("ZORBA THE GREEK", "m", 14, 6),
    ]
    logging.debug("servants: %i" % len(ally_data))
    return ally_data


def assign_random_statuses(ally_data: List[Ally]) -> List[Ally]:
    """Iterates through a list of allies and assigns a random status."""
    status_options = list(AllyStatus)  # Convert Enum to a list once
    for ally in ally_data:
        ally.status = random.choice(status_options)
    # count how many SERVANT status allies there are:
    servant_status = len([ally for ally in ally_data if ally.status == AllyStatus.SERVANT])
    logging.debug("Servant status: %s" % servant_status)
    return ally_data


def print_allies(ally_data: list) -> None:
    """Prints a formatted list of allies, including their status."""
    # The header correctly includes "Status"
    print(
        f"## {'Name'.ljust(20)} {'Gender'.ljust(8)} {'Strength'.ljust(8)} {'To-hit %'.ljust(10)} {'Status'.ljust(12)} Flags")
    print(f"-- {'-' * 20} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 10} {'-' * 20}")

    for i, ally in enumerate(ally_data):
        name = ally.name
        gender = "Male" if ally.gender == 'm' else "Female"
        strength = ally.strength
        # Get the status's name (e.g., "FREE", "DEAD") for clean printing
        status = ally.status.name
        to_hit_str = f"{ally.to_hit * 10}%"

        if ally.flags:
            flag_str = ", ".join(f.name for f in ally.flags)
        else:
            flag_str = "None"

        # FIXED: Added the 'status' variable to the print statement
        print(
            f"{i + 1: >2} {name.ljust(20)} {gender.ljust(8)} {str(strength).rjust(8)} "
            f"{to_hit_str.rjust(8)} {status.ljust(12)} {flag_str}"
        )


if __name__ == '__main__':
    ally_list = load_allies()
    assign_random_statuses(ally_list)
    print_allies(ally_list)
    find_duplicate_allies(ally_list)
