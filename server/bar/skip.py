from bar.ally_data import Ally
from base_classes import PlayerMoneyTypes, Gender, PronounType
from flags import PlayerFlags
from menu_system import MenuItem, Menu, display_menu
from player import Player
from tada_utilities import input_string, input_yes_no, input_number_range, get_pronoun


def main(player: Player):
    """Order hash or coffee from Skip"""
    apostrophe = "'"
    print("Skip sweats over a hot grill, muttering under his breath...")

    # TODO: make handling once-daily events a general function
    add_item = "Skip"
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        add_skip = input_yes_no(f"Add '{add_item}' to once-per-day activities? ")
        if add_skip:
            if add_item not in player.once_per_day:
                player.once_per_day.append(add_item)
                player.output("Appended.")
    if add_item in player.once_per_day:
        player.output(f'Skip suddenly looks annoyed. "Hey, you{apostrophe}ve already [been] here once today!" '
                      "He points angrily towards the exit, and you decide to heed his advice. "
                      "(Never argue with a man who has hot grease at his disposal.)")
        return

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        menu(player)

    pay_9_grand = False
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        pay_9_grand = input_yes_no("Pay 9,000 for something to trigger failure cases")

    while True:
        player.output("")
        command = input_string(player, f'"What{apostrophe}ll ya have, {player.name}?"',
                               None, True, keep_msg=False)
        menu_item = command.lower()  # no problem doing this with a null string
        player.output("")

        if menu_item == 'h':
            player.add_to_party(player, Ally("Michelle", "f", 4, 5))
            player.add_to_party(player, Ally("King Brian", "m", 5, 6))
            party_count: int = len(player.party)
            if party_count == 0:
                # just the Player themselves, so "you decide":
                first_or_third_person = "you"
                pronoun = get_pronoun(player, PronounType.SUBJECTIVE)
                plural = ""
            else:
                hash_menu = Menu("Patrons")
                hash_menu.add_item(MenuItem(f"1. {player.name}"))
                patrons = [player]
                total = 1
                for i, v in enumerate(player.party, 2):
                    hash_menu.add_item(MenuItem(text=f"{i}. {v.name}"))
                    total += 1
                    patrons.append(v)
                display_menu(player, [hash_menu])
                selection = input_number_range("Choose who to feed", 1, total, player,
                                               "Try again.")
                patron = patrons[selection - 1]
                # "<name> decides..."
                pronoun, plural = "", ""
                if isinstance(patron, Player):
                    # TODO: determine first-person ("you") vs third-person ("he"/"she") pronouns
                    pronoun = get_pronoun(patron, PronounType.SUBJECTIVE).capitalize()
                    plural = ""
                    first_or_third_person = "you" if selection == 1 else get_pronoun(patron, PronounType.SUBJECTIVE)
                elif isinstance(patron, Ally):
                    first_or_third_person = get_pronoun(patron, PronounType.SUBJECTIVE)
                    plural = "s"
            # returns True if successful:
            if player.subtract_silver(PlayerMoneyTypes.IN_HAND, 9_000 if pay_9_grand else 1):
                player.output(f"Skip pushes a chipped plate with some hash sitting on it towards {patron.name}. "
                              f"Hesitantly, {first_or_third_person} decide{plural} to sample Skip's wares. "
                              f"The hash is greasy, but hot and nourishing.")
                current_hp = patron.hit_points
                adjusted_hp = current_hp + 5
                patron.hit_points = adjusted_hp
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    # TODO: again, first-person ("Your") vs. third-person ("her", "his", possessive adjective)
                    # selection == 1 will always be the main player character:
                    pronoun = "Your" if selection == 1 else get_pronoun(patron, PronounType.POSSESSIVE_ADJECTIVE)
                    player.output(f"({pronoun.capitalize()} hit points have gone up by 5, from {current_hp} to "
                                  f"{adjusted_hp}.)")
            else:
                player.output(f'"Sorry, pal," Skip mutters, "I{apostrophe}m not running a charity here."')

        elif menu_item == 'c':
            if player.subtract_silver(PlayerMoneyTypes.IN_HAND, 9_000 if pay_9_grand else 5):
                # can afford it:
                player.output("Skip sets a chipped mug filled with viscous black... something... "
                              "on the counter in front of you. "
                              "Oddly enough, the steaming mug of coffee is strangely satisfying.")
                if player.query_flag(PlayerFlags.TIRED):
                    player.clear_flag(PlayerFlags.TIRED)
                    if not player.query_flag(PlayerFlags.EXPERT_MODE):
                        print("(You feel more awake.)")
            else:
                # can't afford it:
                player.output('Skip wipes a nonexistent spot on the luncheon counter with a rag. '
                              '"I know, times are tough."')
            continue

        elif menu_item == '?':
            menu(player)
            continue

        elif menu_item in ['l', '']:
            player.output(f'"Yeah, well... take {apostrophe}er easy..." Skip mumbles.')
            return
        else:
            print(f'"That ain{apostrophe}t on the menu," Skip mutters.')


def menu(player: Player):
    player.output(["[H]ash   (1 silver),",
                   "[C]offee (5 silver)",
                   "[L]eave"])

if __name__ == '__main__':
    player = Player()
    player.clear_flag(PlayerFlags.EXPERT_MODE)
    player.set_flag(PlayerFlags.TIRED)
    main(player=player)
