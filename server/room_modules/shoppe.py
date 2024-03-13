from net_server import UserHandler


def shoppe_menu():
    print("""
*^^^^^^^^^*                 *^^^^^^^^^*
[(^^^^^^^)]  ___  ___  ___  [(^^^^^^^)]
 |   o   |___| |__| |__| |___|   o   |
 |                                   |
 |   The Land of SPUR Shoppe Menu    |
 |:::::::::::::::::::::::::::::::::::|
 |     A: Adventure Log              |
 |     B: Ye Olde Banker             |
 |     C: Conquerors of the Land     |
 |     E: Enter The Land of SPUR     |
 |     G: General Store              |
 |     H: Help with Game             |
 |     I: Thy Inventory              |
 |     J: Join (or change) Guild     |
 |     L: List Opponents             |
 |     O: Olly's Ammo & Traps Shop   |
 |     P: Pawn Shoppe                |
 |     S: Thy Status                 |
 |     V: Visit the Wizard           |
 |     W: Ye Olde Armory/Weaponry    |
 |:::::::::::::::::::::::::::::::::::|
 |SChool: Character/class information|
 |ELevator: Ascend or descend levels |
 |  LOcker: Store/retrieve items     |
 [][][][][][][][][]*[][][][][][][][][]

""")


if __name__ == '__main__':
    print("You are in the Shoppe.")
    # from net_server import UserHandler

    option = ""
    while option != 'q':
        option = UserHandler.promptRequest(prompt="What is thy choice? ",
                                           choices={'a': 'Adventure Log',
                                                    'b': 'Bank',
                                                    '?': 'Help'},
                                           lines=["bla", "bla"],
                                           ).lower()
        print(option)
        if option == "?":
            shoppe_menu()
