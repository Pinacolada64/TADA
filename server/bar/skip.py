from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from player import Player
from tada_utilities import input_string, input_yes_no


def main(player: Player):
    """Order hash or coffee from Skip"""
    from bar.main import prompt
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
        player.output(f'Skip suddenly looks annoyed. "Hey, you{apostrophe} already [been] here once today!" '
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
                               None, False, keep_msg=False)
        player.output("")

        if command == 'h':
            # returns True if successful:
            if player.subtract_silver(PlayerMoneyTypes.IN_HAND, 9_000 if pay_9_grand else 1):
                player.output("Skip pushes a chipped plate with some hash sitting on it towards you. "
                              "Hesitantly, you decide to sample his wares. "
                              "The hash is greasy, but hot and nourishing.")
                current_hp = player.hit_points
                adjusted_hp = current_hp + 5
                player.hit_points = adjusted_hp
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    player.output(f"(Your hit points have gone up by 5, from {current_hp} to {adjusted_hp}.)")
            else:
                player.output(f'"Sorry, pal," Skip mutters, "I{apostrophe}m not running a charity here."')

        elif command == 'c':
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

        elif command == '?':
            menu(player)
            continue

        elif command in ['l', '']:
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
