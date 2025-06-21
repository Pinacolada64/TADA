import logging
from dataclasses import dataclass, field
from typing import Optional
import doctest

# TADA-specific imports:
from base_classes import Size, PlayerMoneyTypes, PlayerMoneyCategory, PlayerStat
# from server import server_lock, room_players, compass_txts, players
from tada_utilities import make_random_id

# from server.user_settings import ClientSettingsNames, ClientValues

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


class BaseCharacter:
    """
    Base class for all Characters, whether a Player, Monster or NPC, to hold common attributes.
    Override the class to display a different id_prefix.

    :param id_prefix: default 'C". Subclass and set to 'M' for a Monster, 'P' for a Player, etc.
    :param id_number: item number from JSON file
    :param name: Character name
    :param max_inventory: max number of items in inventory
    :param inventory: Items in inventory
    """
    def __init__(self, **kwargs) -> None:
        self.id_prefix = kwargs.get('id_prefix', "C")
        self.id_number = kwargs.get('id_number', make_random_id())
        self.name = kwargs.get('name')
        self.max_inventory = kwargs.get('max_inventory', 5)
        self.inventory = kwargs.get('inventory')

    def __str__(self):
        """
        P = Player
        M = Monster
        etc.
        """
        return f'{self.name} [{self.id_prefix}#{self.id_number}]'


@dataclass
class Pixie(BaseCharacter):
    can_fly: bool = True
    size: Size = Size.TINY
    max_inventory: int = 4


@dataclass
class Ally(BaseCharacter):
    inventory: list[str] = field(default_factory=list)  # TODO: list[Item]
    abilities: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


class Horse(BaseCharacter):
    armor: list = field(default_factory=list)
    # if Horse.has_saddlebags is True, Horse can carry additional things (via GIVE?):
    has_saddlebags: bool
    in_saddlebags: list[str] = field(default_factory=list)  # TODO: list[Item]
    has_saddle: bool
    has_lasso: bool
    """
    TODO: additional things to be implemented later:
    training: bool (I think)
    lasso: bool
    # allowed foods: mash, hay, oats, apples, sugar_cubes
    flags: 'can_fly': pegasus (male), maybe?
    """


@dataclass
class Monster(BaseCharacter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = kwargs.get('status', 1)  # 1=alive, 0=dead?
        size: Optional[Size]
        self.strength = kwargs.get('strength', 0)
        self.to_hit = kwargs.get('to_hit', 0)
        self.special_weapon = kwargs.get('special_weapon')
        self.flags = kwargs.get('flags')
        # TODO: max_inventory: int, inventory: list, description: str, owner: Optional[None] = None
        # NOTE: alignment is in "flags": "evil", "good"
        self.id_prefix = "M"
        # TODO: the Owner is set only if the Monster joins the Player's party
        # FIXME: 'owner = Player' is unresolved reference
        self.owner = None

    def load(self, json_filename: str):
        pass


if __name__ == '__main__':
    from .player import Player
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    doctest.testmod(verbose=True)

    rulan = Player()

    print("- Adjust & show DEX score:")
    print("- Current DEX score:")
    print(rulan.show_stat(PlayerStat.DEX))
    add = 15
    print(f"- Adjust DEX to {add}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=add)
    print(rulan.show_stat(PlayerStat.DEX))

    subtract = -9
    verify = add + subtract
    print(f"- Adjust DEX by {subtract}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=subtract)
    print(rulan.show_stat(PlayerStat.DEX))
    # test = 5
    # print(f'{test.bit_count()}') # 2 bits set: bit 4 + bit 1

    if verify == add + subtract:
        print("* Math checks out!")
    else:
        print("* Somethin' ain't right.")

    wealth = 50_000
    print(f"\n- Set silver in hand to {wealth:,}")
    rulan.silver[PlayerMoneyTypes.IN_HAND] = wealth

    rulan.adj_silver_relative(PlayerMoneyTypes.IN_HAND, 100)
    rulan.adj_silver_relative(PlayerMoneyTypes.IN_BANK, 385)

    print(f"\n- Show money categories and values:")
    for k, category in enumerate(PlayerMoneyTypes, start=1):
        name = PlayerMoneyCategory[category].value
        amount = rulan.silver[name]  # Directly access the value using the enum member
        """
        >>> rulan.silver[PlayerMoneyTypes.IN_BAR]
        1000

        >>> PlayerMoneyCategory.IN_HAND.value, rulan.silver[PlayerMoneyTypes.IN_HAND]
        ('In hand', 50000)
        """
        print(f"{k:2>}. {name:.<10}: {amount:>9,}")

    print("\n- Show random combinations:")
    for combination_name, combination_tuple in rulan.combinations.items():
        print(f"{combination_name.value:>15}: {'-'.join(str(digit) for digit in combination_tuple)}")

    """
    # FIXME: doesn't work yet
    print("\n- Show client settings:")
    for i, client_setting in enumerate(ClientSettingsNames):
        value = ClientSettingsNames[client_setting]
        setting_name = client_setting.name.replace("_", " ").title()  # Improve readability
        print(f"{i + 1}. {setting_name}: {value}")
    """
