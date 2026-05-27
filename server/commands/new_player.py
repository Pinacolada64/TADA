"""
New player command implementation for handling new player creation.
This will be a room on the map where new players can create their characters.
It also allows helpstaff or other player to be summoned to assist the new player.
The room description will change to the text of the step in the creation process,
so the client can just display the room description as the prompt.
"""
import logging
from typing import Dict, Any, List, Coroutine
from pathlib import Path
import random

from base_classes import PlayerRace, Gender
from flags import PlayerFlags
from menu_system import MenuItem
from net_common import Mode, MessageType
from base_command import Command, CommandResult
from command_processor import command
from net_common import Message, to_jsonb, from_jsonb
from network_context import GameContext
from player import Player
from simple_client import send_message
from tada_utilities import prompt_client, text_pager
from terminal import Translation, TerminalColors, CBMColors, KeyboardKeyName
from utils import get_player_from_context

# Room where new players will be placed after creation
# (this is a "hole" in map level 1 where there is no room)
CREATION_ROOM = 5  # Default starting room


async def prologue(self, ctx, *args):
    # step 0
    from tada_utilities import prompt_client
    lines = [
        "Welcome to 'Totally Awesome Dungeon Adventure', or TADA for short!",
        "Before you begin your adventure, let's set up your character.",
        "You'll be guided through a series of steps to create your unique persona in this world.",
        "Your faithful servant Verus will assist you through this process.",
        "If you need help at any point, you can type 'help', 'h' or '?' for assistance.",
        # TODO: "You may type "helpstaff" to summon a helper if you need assistance.",
        # TODO: "You may join the "new players" chat channel by typing "chat #join newplayers"
    ]
    await prompt_client(ctx, *args, prompt_text='prologue> ')


async def choose_client(ctx, *args):
    # step 1
    from tada_utilities import prompt_client
    # If a client is present, run the interactive creation flow
    if ctx.player.client:
        # Ensure the user_dir exists
        user_dir = Path('run') / 'server' / 'net'
        user_dir.mkdir(parents=True, exist_ok=True)
        # Step 1a: choose client settings (screen size / translation mock)
        # if client told server which kind of client it is, skip this step
        # Provide simple client choices with screen dimensions: C64 (40x25), 128 (80x25), TADA (80x25, ANSI)')
        # TODO: introspect the terminal types to get screen dimensions and translation:
        options = [
            ('1', 'Commodore 64 (40x25, PetSCII)'),
            ('2', 'Commodore 128 (40x25, PetSCII)'),
            ('3', 'Commodore 128 (80x25, PetSCII)'),
            ('4', 'TADA Client (80x25, ANSI)')
        ]
        while True:

            lines = ['Which client will you use?',
                     '',
                     '##  Type      Screen size   Translation'] + [f"{i + 1}. {o[1]}" for i, o in enumerate(options)]
            ans = (await prompt_client(ctx, lines,
                                       prompt_text='client> ')).strip()
            if ans == '1':
                ctx.player.client_settings.screen_columns = 40
                ctx.player.client_settings.screen_rows = 25

                # TODO: Apply terminal settings from Terminal class
                ctx.player.client_settings.colors = CBMColors
                ctx.player.client_settings.translation = Translation.PETSCII
                ctx.player.client_settings.return_key = KeyboardKeyName.RETURN
                break
            if ans == '2':
                ctx.player.client_settings.screen_columns = 40
                break
            if ans == '3':
                ctx.player.client_settings.screen_columns = 80
                # {'name': 'Commodore 128 (80 cols)', 'screen_columns': 80, 'screen_rows': 25,
                #  'translation': 'PETSCII', 'return_key': 'Return'}
                break
            if ans == '4':
                # set common defaults:
                await set_defaults(ctx.player)
                break
    # no client present, return some defaults:
    if not ctx.client:
        logging.info("No client; setting defaults")
        await set_defaults(ctx.player)
    # return player


async def set_defaults(self, ctx, *args):
    # set some default client settings
    from server.terminal import KeyboardKeyName, ClientSettings
    ctx.player.client_settings.colors = TerminalColors
    ctx.player.client_settings.name = 'TADA Client'
    ctx.player.client_settings.screen_rows = 25
    ctx.player.client_settings.screen_columns = 80
    ctx.player.client_settings.translation = Translation.ANSI
    ctx.player.client_settings.return_key = KeyboardKeyName.ENTER
    await send_message("set_defaults: {pprint(ctx.player.client_settings)}")


async def confirm_creation(self, ctx: GameContext, *args) -> Player:
    """
    Confirm final creation; standardized signature to accept ctx (includes player).
    Returns the player (caller can inspect attributes or set a flag).
    """
    logging.info("Final character '%s' summary: %s", (ctx.player.name, ctx.player))
    # TODO: For simplicity, always confirm in this mockup; set an attribute and return player
    # Setting this here allows a connection drop to resume char creation if they log in under the same
    # account; Verus can then say something about "wanting to continue creation"
    # this flag can get deleted on first login, it doesn't need to get saved beyond this point
    ctx.player.creation_done = True
    await ctx.send("Confirm creation: Finish this")
    return ctx.player


async def final_edit_prompt(self, ctx: GameContext, *args):
    """
    Display a summary of character, allow some editing options before final confirmation.

    :param ctx:
    :param args:
    :return:
    """
    # TODO: finish this
    logging.info("Not done yet")
    await ctx.send("TODO: not done yet")


async def check_info(self, ctx: GameContext, *args) -> int | bool:
    """Verify that the choice is a call for class / race info:
    the input starts with 'i', and is followed by a digit 1-9.

    :param ctx: str - input from the player
    :return: option int if input is 'i#', False otherwise
    """
    choice = await ctx.prompt("Prompt: ")  # FIXME - is a prompt necessary here?
    # Numeric choice: select option by number
    if choice.isdigit():
        try:
            number_choice = int(choice)
        except ValueError:
            return False

    # Info request: I# or i#
    low = choice.lower()
    if len(low) == 2 and low[0] == 'i' and low[1].isdigit():
        idx = int(low[1])
        if 1 <= idx <= 9:
            return idx
        # Not recognized
        msg = ("Verus shakes his head. 'That's not a choice I understand. "
               "Try a number 1-9, or I followed by a number 1-9: e.g., 1 or I1.'")
        # TODO: support inputting digit followed by I, also
        await ctx.send(msg)
    return False


@command(name='new', aliases=['create', 'newplayer'], summary='Create a new character account')
class NewPlayerCommand(Command):
    async def execute(self, ctx: GameContext, *args) -> CommandResult | None:
        """
        Handles new player creation in a non-blocking way.

        The command expects `new <username> <password>` and returns a CommandResult
        with data describing changes the server should apply (authenticated, username, mode).
        """
        # Only available during login/creation flow
        login_only = True

        # Validate arguments; support interactive prompting if a real client is present
        client = ctx.get('client') or context.get('client')
        player_context = get_player_from_context(context, client)
        # Case: interactive prompting if args incomplete and client supports prompts

        if not args or len(args) < 2:
            from tada_utilities import prompt_client
            if client and getattr(client, 'writer', None) and getattr(client, 'reader', None):
                # ask for username if missing
                if not args or len(args) == 0:
                    user_id = await prompt_client(getattr(client, 'reader'), getattr(client, 'writer'), None,
                                                  ['Choose a username:'], prompt_text='username> ')
                else:
                    user_id = args[0]
                # ask for password
                # TODO: call SetPasswordCommand (which asks twice, verifies match)
                password = await prompt_client(getattr(client, 'reader'), getattr(client, 'writer'), None,
                                               ['Choose a password (will be echoed):'], prompt_text='password> ')
                if not user_id or not password:
                    return CommandResult(success=False, error='missing_args', message='Username and password required.',
                                         data={'mode': Mode.login})
            else:
                return CommandResult(success=False, error='missing_args', message='Usage: new <username> <password>',
                                     data={'mode': Mode.login})
        else:
            user_id = args[0]
            password = args[1]
        # Simple player representation
        from player import Player
        player = Player()

async def choose_settings(self, player_obj, reader=None, writer=None):
        # Standardized helper: choose settings prompt
        async def choose_settings_prompt(player_obj, reader=None, writer=None):
            lines = ['Settings: choose any to toggle (not persisted in this simple flow)']
            lines += ['1. Regional Settings', '2. Colors', '3. Other Settings', '', "Press Enter to continue"]
            await prompt_client(reader, writer, player_obj, ['Settings (press Enter to continue)'],
                                prompt_text='settings> ')
            return player_obj

        # Standardized helper: choose age & birthday - now returns the player with attributes set
        async def choose_age_prompt(ctx: GameContext):
            from datetime import date, datetime
            from random import randrange
            import calendar
            while True:
                ans = await ctx.prompt("Enter age (0=Unknown, [R]andom, 15-50)").strip().lower()
                if not ans:
                    continue
                if ans == 'r':
                    age = randrange(15, 51)
                    ctx.player.age = age
                    ctx.player.birthday = datetime.now()
                    return ctx
                if ans.isdigit():
                    age = int(ans)
                    player_obj.age = age
                    # quick birthday flow
                    today = date.today()
                    temp = await ctx.prompt(f"Use [T]oday's date ({today}) or [A]nother date for birthday? (T/A)")
                    if temp in ('t', 'today'):
                        ctx.player.birthday = datetime(date.today().year, date.today().month, date.today().day)
                        logging.info(f"Set birthday to today: {player_obj.birthday}")
                        return ctx
                    # custom date
                    months = ["Select month:", ""] + [f"{i + 1}. {calendar.month_name[i + 1]}" for i in range(12)]
                    await ctx.send(months)
                    m = await ctx.prompt("Enter birth month (1-12):")
                    try:
                        m_i = max(1, min(12, int(m)))
                    except ValueError:
                        m_i = date.today().month
                    days_in_month = calendar.monthrange(date.today().year, m_i)[1]
                    d = await ctx.prompt(f"Enter birth day (1-{days_in_month}):")
                    try:
                        d_i = max(1, min(days_in_month, int(d)))
                    except Exception:
                        d_i = date.today().day
                    player_obj.birthday = datetime(date.today().year, m_i, d_i)
                    return player_obj
                # else loop until valid

            # Final edit prompt: summary and simple edits using ctx.prompt
            async def final_edit_prompt(player: Player) -> None:
                while True:
                    # Show summary and give edit options
                    from menu_system import Menu
                    edit_menu = Menu(title=f"{player.name}'s Summary")
                    edit_menu.add_item(MenuItem(shortcuts=['1', 'n'],
                                                text='Name',
                                                dot_leader_handler=lambda: player.name,
                                                action=choose_name
                                                ))
                    edit_menu.add_item(MenuItem(shortcuts=['2', 'a'],
                                                text='Age',
                                                dot_leader_handler=lambda: player.age,
                                                action=choose_age_prompt
                                                ))
                    edit_menu.add_item(MenuItem(shortcuts=['3', 'ge'],
                                                text='Gender',
                                                dot_leader_handler=lambda: player.gender
                                                )),
                    edit_menu.add_item(MenuItem(shortcuts=['4', 'c'],
                                                text='Class',
                                                dot_leader_handler=lambda: player.char_class
                                                )),
                    edit_menu.add_item(MenuItem(shortcuts=['5', 'r', ],
                                                text='Race',
                                                dot_leader_handler=lambda: player.char_race,
                                                action=edit_race
                                                ))
                    edit_menu.add_item(MenuItem(shortcuts=['6', 'gu'],
                                                text='Guild',
                                                dot_leader_handler=lambda: player.guild
                                                ))
                    edit_menu.add_item(MenuItem(shortcuts=['7', player.return_key],
                                                text='Accept and Finish Creation')
                                       )

                    lines.append("Stats:")
                    for idx, (k, v) in enumerate(player.stats.items(), 1):
                        lines.append(f"  {idx}. {k}: {v}")
                    lines.append('Enter number to edit, or press Enter to accept:')
                    ans = (await prompt_client(lines, player_obj=player, prompt_text='edit> ')).strip()
                    if ans == '1':
                        player.name = await choose_name(reader, writer)
                    elif ans == '2':
                        gender = await prompt_client(writer, ['M or F:'], reader, prompt_text='gender> ')
                        player.gender = Gender.MALE if gender == 'm' else Gender.FEMALE
                    elif ans == '3':
                        player.char_class = await choose_class
                    elif ans == '4':
                        player.char_race = await edit_race
                    elif ans == '5':
                        player.guild = await choose_guild
                    elif ans == '':
                        break
                    else:
                        # invalid, loop
                        continue

            return None

        # Option 1: edit race

        async def edit_race(player_obj, reader=None, writer=None):
            # simple informational response
            if writer:
                await send_message(writer,
                                   Message(lines=['Called by Menu, just a simple line of text to display to the user.'],
                                           type=MessageType.REGULAR))
            return player_obj

        async def choose_gender(player_obj, reader=None, writer=None) -> Player:
            while True:
                ans = (await prompt_client(reader, writer, player_obj, ["Are you Male or Female? (M/F)"],
                                           prompt_text='gender> ')).strip().lower()
                if ans in ['m', 'male']:
                    if writer:
                        await send_message(writer,
                                           Message(lines=[f"{player_obj.name} is male."], type=MessageType.REGULAR))
                    player_obj.gender = Gender.MALE
                    return player_obj
                if ans in ['f', 'female']:
                    if writer:
                        await send_message(writer,
                                           Message(lines=[f"{player_obj.name} is female."], type=MessageType.REGULAR))
                    player_obj.gender = Gender.FEMALE
                    return player_obj
                # invalid, re-prompt

        async def choose_name(player_obj, reader=None, writer=None):
            while True:
                name = (await prompt_client(reader, writer, player_obj,
                                            ["Enter a character name (or 'R' for a random name):"],
                                            prompt_text='name> ')).strip()
                if not name:
                    continue
                if name.lower() == 'r':
                    try:
                        # pass player_obj to determine player's gender for proper gender-aware name generation
                        name = generate_random_name(player_obj)
                    except Exception:
                        name = f"Player{random.randint(1000, 9999)}"
                user_file = Path(user_dir) / f'login-{name}.json'
                if user_file.exists():
                    await send_message(writer,
                                       Message(f"There is someone already here by that name. Choose another.",
                                               type=MessageType.REGULAR),
                                       )
                    continue
                player_obj.name = name
                return player_obj

        async def check_is_digit(player_input: str, reader=None, writer=None) -> bool:
            """Verify that the choice is a digit 1-9.

            :param player_input: str - input from the player
            :param reader: asyncio StreamReader (optional)
            :param writer: asyncio StreamWriter (optional)
            :return: bool: True if player_input is within range, False otherwise
            """
            # quick debug message if writer present
            if writer:
                await send_message(writer, Message(lines=['Checking choice...'], type=MessageType.REGULAR))

            if not player_input:
                await send_message(writer, Message(lines=['No input provided.'], type=MessageType.REGULAR))
                return False

            choice = player_input.strip()
            if choice.isdigit():
                try:
                    number_choice = int(choice)
                    if 1 <= number_choice <= 9:
                        return True
                except ValueError:
                    return False

            # Not recognized
            msg = "Verus shakes his head. 'That's not a choice I understand. Try a number 1-9.'"
            if writer:
                await send_message(writer, Message(lines=msg, type=MessageType.REGULAR))
            else:
                try:
                    player_obj.output(msg)
                except Exception:
                    logging.info(msg)
            return False

        async def set_class(player_obj, class_name: str, reader=None, writer=None):
            # called from either edit_class or choose_class
            from base_classes import PlayerClass

        async def choose_class(player_obj, reader=None, writer=None):
            from base_classes import PlayerClass
            if not player_obj.query_flag(PlayerFlags.EXPERT_MODE):
                # Beginner mode: display prompts, info on what classes are:
                # TODO: rewrite tada_utilities.paged_text to support async and use send_message
                await send_message(writer, Message(lines=["Classes Overview:"]))
                from base_classes import PlayerClassText
                for class_text in PlayerClassText:
                    await send_message(writer, Message(lines=[str(class_text)]))
            lines = ['Verus says, "Choose a class by number, or I# for info."']
            classes = [c for c in PlayerClass.name]
            lines += [f"{i + 1}. {c}" for i, c in enumerate(classes)]
            while True:
                ans = (await prompt_client(reader, writer, player_obj, lines, prompt_text='class> ')).strip()
                if not ans:
                    continue
                # check for numeric choice:
                number = await check_is_digit(ans, reader, writer)
                if number and player_obj.char_class:
                    player_obj.char_class = [c for c in classes][number - 1]
                # check for 'i#' choice:
                info = await check_info(ans, reader, writer)
                if info:
                    from base_classes import PlayerClassText
                    await send_message(writer, Message(lines=[ct for ct in PlayerClassText][number - 1]))
            classes = [c for c in PlayerClass.name]
            lines = ['Verus says, "Choose a class:"', [f"{i + 1}. {c}" for i, c in enumerate(classes)]]
            while True:
                ans = (await prompt_client(reader, writer, player_obj, lines, prompt_text='class> ')).strip()
                if not ans:
                    continue
                # TODO: validate input in range 1 < ans < len(classes), show info if requested
                if ans.isdigit():
                    idx = int(ans) - 1
                    if 0 <= idx < len(classes):
                        player_obj.char_class = classes[idx]
                        return player_obj
                for c in classes:
                    if ans.lower() == c.lower():
                        player_obj.char_class = c
                        return player_obj
                msg = f'To get class info, enter I followed by a number between 1 and {len(classes)}.'
                if writer:
                    await send_message(writer, Message(lines=[msg], type=MessageType.REGULAR))

        return None


async def choose_race(ctx, *args):
    from base_classes import PlayerRace
    races = [race for race in PlayerRace]
    lines = ['Choose a race:'] + [f"{i + 1}. {r.name}" for i, r in enumerate(races)]
    while True:
        ans = (await prompt_client(ctx, lines, 'race> ')).strip()
        if not ans:
            continue
        verified = (ans)
        try:
            races = [r.name for r in PlayerRace]
        except Exception:
            races = ['Human', 'Elf', 'Dwarf']
        race_lines = ['Choose a race:'] + [f"{i + 1}. {r}" for i, r in enumerate(races)]
        while True:
            ans = (await prompt_client(reader, writer, player, race_lines, prompt_text='race> ')).strip()
            if not ans:
                await send_message(writer, "Please enter a choice.")
                continue
            race = check_selection(ans)
            if race:
                idx = int(race) - 1
                if 0 <= idx < len(races):
                    player.char_race = races[idx]
                    break
            info = await check_info(ans, reader, writer)
            if info:
                from base_classes import PlayerClassText, PlayerClass
                texts = list(PlayerClassText)
                if 1 <= idx <= len(texts):
                    class_text = texts[idx - 1]
                    # class_text may be a long string or structure; output it
                    if writer:
                        await text_pager(reader, writer, class_text)
                        # paged_text(writer, Message(lines=[str(class_text)], type=MessageType.REGULAR))
                    else:
                        try:
                            print(class_text)
                        except Exception:
                            logging.info(str(class_text))


async def choose_guild(player_obj, reader=None, writer=None):
    guilds = [
        ('C', 'Civilian'),
        ('M', 'Mark of the Claw'),
        ('F', 'Iron Fist'),
        ('S', 'Mark of the Sword'),
        ('O', 'Outlaw')
    ]
    lines = ['Choose a guild:'] + [f"{i + 1}. {g[1]}" for i, g in enumerate(guilds)]
    short_lines = ['Options:'] + [f"{g[0]} => {g[1]}" for g in guilds]
    while True:
        ans = (await prompt_client(reader, writer, player_obj, lines + short_lines,
                                   prompt_text='guild> ')).strip().lower()
        if ans.isdigit():
            idx = int(ans) - 1
            if 0 <= idx < len(guilds):
                player_obj.guild = guilds[idx][1]
                return player_obj
        for short, name in guilds:
            if ans == short.lower() or ans == name.lower():
                player_obj.guild = name
                return player_obj


async def roll_stats_enhanced(player_obj, reader=None, writer=None):
    import random
    order = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']

    def one_roll():
        rolls = [random.randint(1, 6) for _ in range(4)]
        rolls.sort()
        return sum(rolls[1:]), rolls

    while True:
        stats = {}
        details = []
        for s in order:
            val, rolls = one_roll()
            stats[s] = val
            details.append(f"{s}: {val} (rolls: {rolls})")

        bonus_lines = ['(Bonuses preview not implemented in full)']
        lines = ['Rolled stats:', details, bonus_lines]
        await send_message(writer, lines)
        accept_msg = 'Accept these stats? (Y)es / (R)eroll'
        ans = (await prompt_client(reader, writer, player_obj, accept_msg, prompt_text='stats> ')).strip().lower()
        if ans in ('y', 'yes', ''):
            player_obj.stats = stats
            return player_obj
        # else reroll


def check_selection(ans: str) -> int | bool:
    """Check if the answer is a valid selection digit 1-9.

    :param ans: str - input from the player
    :return: int if valid selection, False otherwise
    """
    if ans.isdigit():
        try:
            number_choice = int(ans)
            if 1 <= number_choice <= 9:
                return number_choice
        except ValueError:
            return False
    return False


async def main_flow(player, client=None) -> CommandResult:
    # Run the standardized flow, wiring reader/writer from client when available
    reader = getattr(client, 'reader', None)
    writer = getattr(client, 'writer', None)

    # Settings
    player = await choose_settings_prompt(player, reader, writer)

    # Age and birthday
    player = await choose_age_prompt(player, reader, writer)

    # Gender
    player = await choose_gender(player, reader, writer)

    # Name
    player = await choose_name(player, reader, writer)

    # Class
    player = await choose_class(player, reader, writer)

    # Race selection (inline)

    # Guild
    player = await choose_guild(player, reader, writer)

    # Roll stats
    player = await roll_stats_enhanced(player, reader, writer)

    # Final review/edit
    player = await final_edit_prompt(player, reader, writer)

    # Confirm creation
    player = await confirm_creation(player, reader, writer)

    # return success with data for server to persist or act upon
    return CommandResult(success=True, message='Player created',
                         data={'player': player, 'mode': Mode.app, 'room': CREATION_ROOM})


# interactive path (no client reader/writer): return success and leave it to server
def help_text(self) -> str:
    return (
        "New Player Command\n"
        "-----------------\n"
        "Creates a new player account.\n\n"
        "Usage: new <username> <password>\n"
    )


def generate_random_name(player) -> str:
    import random
    male_given_names = [
        'Aldric', 'Baldwin', 'Cedric', 'Dunstan', 'Edric', 'Falk', 'Godwin', 'Harold', 'Ivo',
        'Jasper', 'Kenric', 'Lancel', 'Merrick', 'Osric', 'Peregrin', 'Quentin', 'Roderick',
        'Sigurd', 'Theobald', 'Ulric', 'Wulfric'
    ]

    female_given_names = [
        'Alina', 'Beatrice', 'Cecily', 'Dawn', 'Edith', 'Gwen', 'Jacqueline', 'Matilda', 'Rosamund',
        'Rhiannon', 'Sybil'
    ]

    surnames = [
        'Cooper', 'Smith', 'Baker', 'Fletcher', 'Cartwright', 'Sawyer', 'Fuller', 'Tanner',
        'Chandler', 'Taylor', 'Clarke', 'Hayward', 'Miller', 'Harper', 'Turner', 'Marsh',
        'Langley', 'Hawthorne', 'Ashby', 'Blackwood', 'Stone', 'Kingsley', 'Oakenshield', 'Ironmonger'
    ]

    # choose a random given name based on the player's gender
    first_name = male_given_names if player.gender == Gender.MALE else female_given_names

    # 75% chance to include a surname
    if random.random() < 0.75:
        return f"{first_name} {random.choice(surnames)}"
    return first_name


if __name__ == '__main__':
    import asyncio
    from tada_utilities import MockClient


    async def test_new_player_command():
        cmd = NewPlayerCommand()
        mock_client = MockClient()
        context = {'client': mock_client}
        result = await cmd.execute(context, ['testuser', 'testpass'])
        print('Result:', result)


    asyncio.run(test_new_player_command())
