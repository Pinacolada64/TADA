#!/bin/env python3

import doctest
import logging
import random
import textwrap
from enum import Enum, auto
from typing import TYPE_CHECKING, List

from simple_client import send_message

if TYPE_CHECKING:
    from player import Player
    from net_common import Message, to_jsonb, from_jsonb

"""
utilities such as:
* grammatically correct list output
* display a header with underlined text
* prompt requiring yes/no response
* prompt for a range of numbers
* prompt with string editing
* generate a random ID from 1-65536 (inclusive)
"""


def a_or_an(string: str, capitalize: bool = False) -> str:
    """
    Return 'a' or 'an' '<string>' based on the first letter of the string being a vowel or not.
    If 'capitalize' is True, return 'A' or 'An' '<string>'
    """
    """
    >>> print(f"{a_or_an("banana", False)}")
    'a banana'
    """
    starts_with_vowel = string.lower().startswith(("a", "e", "i", "o", "u"))
    article = "an" if starts_with_vowel else "a"
    return f"{article} {string}" if not capitalize else f'{article.title()} {string}'


def bulleted_list_format(text: str, width: int, initial_indent: str = "* ", subsequent_indent: str = ' ' * 2) -> str:
    """
    Formats a single paragraph into a bulleted list string, handling wrapping.
    This function is primarily for *creating* bulleted content from raw text.
    It returns a single string that may contain newlines if the text wrapped.
    """
    import textwrap
    logging.info(f"bulleted_list_format input text: '{text}', width: {width}")
    # Dedent only if needed, but for direct bullet content, strip is often more reliable
    dedented_text = textwrap.dedent(text).strip()

    # Fill the text with the specified indents. This will handle the wrapping.
    formatted_text = textwrap.fill(dedented_text, width=width,
                                   initial_indent=initial_indent, subsequent_indent=subsequent_indent)
    logging.info(f"bulleted_list_format output: '{formatted_text}'")
    return formatted_text


def set_logging_level(p: "Player"):
    """
    An action function that displays the current logging level,
    prompts the user to select a new one, and applies the change.
    """
    root_logger = logging.getLogger()
    levels = {
        '1': logging.DEBUG,
        '2': logging.INFO,
        '3': logging.WARNING,
        '4': logging.ERROR,
        '5': logging.CRITICAL,
    }

    current_level_name = logging.getLevelName(root_logger.level)
    p.output(["", f"--- Logging Level Control ---",
              f"Current level: {current_level_name}",
              "Select a new logging level:"])

    for key, level_int in levels.items():
        p.output(f"  {key}. {logging.getLevelName(level_int)}")

    return_key = p.client_settings.return_key
    choice = input_string(p, f"Enter choice (or press {return_key} to cancel):",
                          default_answer=current_level_name, allow_empty = True, keep_msg=True)

    if choice in levels:
        new_level = levels[choice]
        root_logger.setLevel(new_level)
        p.output(f"Logging level has been changed to {logging.getLevelName(new_level)}.")
    else:
        p.output("Canceled. Logging level is unchanged.")



def oxford_comma_list(items: list) -> str:
    """
    Returns a string that lists items in a grammatically correct form,
    using the Oxford comma.

    If there is one item in the list, return it.
    If there are two items in the list, return the first, and the second (no Oxford comma).
    If there are more than two items, return the first, second, [...] ', and last'.

    >>> print(f"{oxford_comma_list(['apple', 'banana', 'cherry'])}")
    apple, banana, and cherry
    >>> print(f"{oxford_comma_list(['apple', 'banana'])}")
    apple and banana
    >>> print(f"{oxford_comma_list(['apple'])}")
    apple
    >>> print(f"{oxford_comma_list([])}")
    (an empty string)
    """
    if not items:
        return ""
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f"{items[0]} and {items[1]}"
    else:
        return f"{', '.join(items[:-1])}, and {items[-1]}"


async def text_pager(player, text_lines: list, reader=None, writer=None):
    # async def choose_class(player_obj, reader=None, writer=None):
    """
    Display a list of strings in a paged fashion, accounting for Player's screen height
    and wrapping text using textwrap. Empty list elements are considered newlines.

    :param text_lines: list of strings to display. Each string is treated as a paragraph
                       that needs to be wrapped.
    :param player: Player object holding screen_height and screen_columns values.
    :return: None
    """
    """
    >>> import re
    >>> re.sub(r'\[(.+?)\]', r'!\1!', string="Hello [World] this [is a] test.")
    'Hello !World! this !is a! test.'
    """
    import re
    from colorama import Fore  # text foreground color
    screen_height = player.client_settings.screen_rows
    screen_width = player.client_settings.screen_columns

    wrapped_content = []
    for line_raw in text_lines:  # Renamed 'line' to 'line_raw' for clarity
        if not line_raw.strip():  # Check if line is empty or just whitespace
            wrapped_content.append("")  # Treat empty/blank lines as explicit newlines
            continue  # Skip to next line_raw in input

        # Apply highlighting before wrapping to avoid breaking color codes
        # color text inside brackets using re and colorama
        # '.+?' is a non-greedy match (finds multiple matches, not just '[World...a]')
        highlighted_line_content = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=line_raw)

        # Now, handle wrapping based on content type
        if highlighted_line_content.strip().startswith("* "):
            # This is a bullet point. We need to handle its indentation specifically.
            # Remove the initial '* ' for wrapping, then re-add it with initial_indent.
            content_after_bullet = highlighted_line_content.strip()[2:].strip()

            # Use textwrap.wrap for line-by-line control
            # The 'initial_indent' applies only to the first line of the wrapped output
            # The 'subsequent_indent' applies to all following wrapped lines
            wrapped_bullet_lines = textwrap.wrap(content_after_bullet, width=screen_width,
                                                 initial_indent="* ", subsequent_indent=' ' * 2)
            wrapped_content.extend(wrapped_bullet_lines)
        else:
            # Regular paragraph, just wrap it
            wrapped_paragraph_lines = textwrap.wrap(highlighted_line_content, width=screen_width)
            wrapped_content.extend(wrapped_paragraph_lines)

    total_display_lines = len(wrapped_content)
    current_line_index = 0

    # Calculate total pages upfront
    lines_per_page = screen_height - 1  # One line for the prompt
    total_pages = (total_display_lines + lines_per_page - 1) // lines_per_page
    if total_pages == 0 and total_display_lines > 0:
        total_pages = 1
    elif total_pages == 0 and total_display_lines == 0:  # Handle completely empty content
        total_pages = 1  # Or 0 depending on the desired behavior for an empty file. 1 allows a prompt to show.

    while True:
        # Calculate current page number
        current_page = (current_line_index // lines_per_page) + 1

        # Clear screen (optional, depending on your terminal/game environment)
        # print("\033c", end="") # ANSI escape code to clear screen

        lines_to_display = wrapped_content[current_line_index: current_line_index + lines_per_page]

        for display_line in lines_to_display:
            await send_message(writer, display_line)

        remaining_lines = total_display_lines - (current_line_index + len(lines_to_display))

        # Pager prompt
        # Adjust prompt based on whether there's more content or if back is possible
        prompt_options = []
        if remaining_lines > 0:
            prompt_options.append("[Enter]: Continue")
        if current_line_index > 0:  # Only offer 'B' if not on the first page
            prompt_options.append("[-, B]: Back")
        prompt_options.append("[Q]: Quit")

        # Dynamically build the prompt message including page numbers
        page_info = f"(Page {current_page}/{total_pages}) " if total_pages > 1 else ""

        status_message = f"-- More {page_info}--" if remaining_lines > 0 else f"-- End {page_info}--"
        prompt_message = f"{status_message} {', '.join(prompt_options)}: "

        user_input = await prompt_client(player_obj=prompt_message).strip().lower()
        print()  # Add a newline after user input for better readability

        if user_input == 'q':
            print("(You quit reading.)")
            break
        elif user_input == '' and remaining_lines > 0:
            current_line_index += lines_per_page
            # Don't "snap back" immediately here, let the next loop iteration handle end-of-content check naturally.
            # If current_line_index goes beyond total_display_lines, remaining_lines will be <= 0 in next iter.
        elif user_input == '' and remaining_lines <= 0:  # Use <= 0 to catch 0 and negative (overflow)
            print("(Done.)")
            break  # Quit if Enter at end of content
        elif user_input in ['b', '-']:
            current_line_index = max(0, current_line_index - lines_per_page)
        else:
            print("Invalid input. Please use 'Enter' to continue, 'B' to go back, or 'Q' to quit.")


def get_article_and_quantity(item_name: str) -> str:
    """
    Determines the correct article ('a', 'an', or 'some') for a given item name.
    Assumes plurality if the name ends in 's'.

    >>> print(f"{get_article_and_quantity('banana')}")
    a banana
    >>> print(f"{get_article_and_quantity('orange')}")
    an orange
    >>> print(f"{get_article_and_quantity('dry bones')}")
    some dry bones
    """
    vowels = "aeiouAEIOU"

    # Simple check for plural (ends in 's')
    if item_name.lower().endswith('s'):
        return f"some {item_name}"
    else:
        # Check for vowel start for 'an'
        if item_name[0] in vowels:
            return f"an {item_name}"
        else:
            return f"a {item_name}"


def grammatical_list(item_list: str | list) -> str:
    """
    This function lists items in a grammatically correct form,
    handling singular/plural quantities and proper conjunctions.

    If the object is singular (the name does not end in 's'):
    'a (object starting with a consonant)', 'an (object starting with a vowel)'.
    If the object is plural (the name ends in 's'): 'some <object>'

    If there is one item in the list, print it.
    If there are two items in the list, print the first, and the second (no Oxford comma).
    If there are more than two items, print the first, second, [...] ', and {a|an|some} <object>'.

    >>> print(f'You see: {grammatical_list(["orange", "dry bones", "book"])}.')
    You see: an orange, some dry bones, and a book.
    >>> print(f'You see: {grammatical_list(["apple", "banana"])}.')
    You see: an apple and a banana.
    >>> print(f'You see: {grammatical_list("sword")}.')
    You see: a sword.
    >>> print(f'You see: {grammatical_list(["keys"])}.')
    You see: some keys.
    >>> print(f'You see: {grammatical_list([])}.')
    You see: nothing.
    """
    processed_items = []

    if isinstance(item_list, str):
        # If input is a single string, process it directly
        return get_article_and_quantity(item_list)

    if not item_list:
        return "nothing"

    # If input is a list, process each item
    for item in item_list:
        processed_items.append(get_article_and_quantity(item))

    num_items = len(processed_items)

    if num_items == 1:
        return processed_items[0]
    elif num_items == 2:
        return f"{processed_items[0]} and {processed_items[1]}"
    else:  # num_items > 2 (with Oxford comma)
        return f"{', '.join(processed_items[:-1])}, and {processed_items[-1]}"


def list_players_in_room(player_list: str | list) -> str:
    """List players in room in a grammatically correct way:

    "Rulan is here."
    "Rulan and J'ee are here."
    "Rulan, J'ee, and Argentilane are here."

    >>> list_players_in_room("Rulan")
    'Rulan is here.'
    >>> list_players_in_room(["Rulan", "J'ee"])
    "Rulan and J'ee are here."
    >>> list_players_in_room(["Rulan", "J'ee", "Argentilane"])
    "Rulan, J'ee, and Argentilane are here."
    >>> list_players_in_room([])
    'No one is here.'
    >>> list_players_in_room(["Solo"])
    'Solo is here.'
    """
    # TODO: Later, when players can lead/join parties, display e.g.,
    #     "Rulan (and his party) are here."

    if isinstance(player_list, str):
        # Single player case
        return f"{player_list} is here."

    if not player_list:
        # No players in the list
        return "No one is here."

    # Process the list of players
    num_players = len(player_list)

    if num_players == 1:
        return f"{player_list[0]} is here."
    elif num_players == 2:
        return f"{player_list[0]} and {player_list[1]} are here."
    else:
        # More than two players (with Oxford comma)
        # Join all but the last player with commas, then add "and" before the last one
        return f"{oxford_comma_list(player_list)} are here."


async def header(player, reader = None, writer = None, header_text: str = None) -> None:
    """
    Show `headline_text` passed, a newline, and a line the length of `text`
    e.g.,

    This is a header
    ----------------

    :param player: Player object
    :param reader:
    :param header_text: string to display
    :return: None
    """
    # TODO: underline_char = player.client_settings.charset.MIDLINE or something like it
    await send_message(writer, f"\n{header_text}\n{'=' * len(header_text)}\n")


async def input_number_range(player: "Player",
                             reader=None,
                             writer=None,
                             default: int = None,
                             prompt_msg: str = None,
                             min_value: int = 1,
                             max_value: int = 10,
                             out_of_bounds_msg: str = None) -> int:
    """Display input 'prompt', accept numbers lo < value < hi
    e.g.
    "'prompt' ['lo'-'hi']: "

    :param reader: reader object
    :param writer: writer object
    :param player: Player to output text to
    :param prompt_msg: prompt user with this string
    :param default: number to return if user hits Return
    :param min_value: lowest number accepted
    :param max_value: highest number accepted
    :param out_of_bounds_msg: string to display if lo < temp < hi
    :return value: integer number of selection
    """
    from flags import PlayerFlags
    lines = []
    if default is not None and not player.query_flag(PlayerFlags.EXPERT_MODE):
        await send_message(writer, f"{player.client_settings.return_key} keeps '{default}'.")
    while True:
        temp = input(f"{prompt_msg} [{min_value}-{max_value}]: ")
        if temp.isalpha():
            await send_message(writer, '"Numbers only, please," Verus reminds you.')
        # just hitting Return keeps the original number
        if temp == '':
            if default:
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    await send_message(writer, f"(Keeping '{default}'.)")
            return default
        elif temp.isdigit():
            number = int(temp)
            if min_value <= number <= max_value:
                return number
            else:
                await send_message(writer, f"{out_of_bounds_msg}")
        else:
            await send_message(writer, f"{out_of_bounds_msg}")
            logging.info("Edge case")
            continue


async def input_string(reader=None,
                       writer=None,
                       player="Player",
                       default: str = "",
                       prompt_msg: str = "",
                       allow_empty: bool = True,
                       keep_msg: bool = True,
                       reminder: str = "Please enter something."):
    """

    :param reader:
    :param writer:
    :param player:
    :param default:
    :param prompt_msg:
    :param allow_empty:
    :param keep_msg:
    :param reminder:
    :return:

    # async def input_number_range(player: Player,
                                 reader=None,
                                 writer=None,
                                 default: int = None,
                                 prompt_msg: str = None,
                                 min_value: int = 1,
                                 max_value: int = 10,
                                 out_of_bounds_msg: str = None) -> int:

    Input 'prompt', accept a string
    e.g.:
    [Return] keeps 'Druid.'  # if expert mode off
    "'prompt' : "

    :param default: this is returned if `answer` is null
    :param prompt: prompt user with this string
    :param keep_msg: True: print "{return_key} keeps 'default_string'"
    :param allow_empty: True: allow hitting Return. False: Must enter a string.
    :param player: Player to output text to
    :param reminder: what to display if return_string is False and null string entered
    """
    from flags import PlayerFlags
    # FIXME: this is kind of a mess
    if keep_msg and not player.query_flag(PlayerFlags.EXPERT_MODE):
        player.output(f"{player.client_settings.return_key} keeps '{default_answer}.'")
    while True:
        answer = await prompt_client(writer, player_obj=reader, prompt_text=f"{prompt}: ")
        # just hitting Return (or user types the original string) keeps the original string
        if answer == '' or answer == default_answer:
            # 1) empty response:
            if allow_empty:
                # FIXME a) [...]
                return ""
            # 2) empty response not allowed:
            elif not allow_empty:
                # have to enter something:
                player.output(reminder)

                if player.query_flag(PlayerFlags.EXPERT_MODE):
                    answer = default_answer
                    player.output(f"(Keeping '{answer}'.)")
                return answer
        else:
            return answer
            # player.output(reminder)


def input_yes_no(prompt: str) -> bool:
    """input `prompt`, accept `y` or `n` to choose yes or no response

    e.g.:

    "'prompt' [y/n]: "

    :param prompt: prompt user with this string
    :return True: 'yes' entered; False: 'no' entered
    """
    # TODO: implement 'default=True for 'yes' [Y/n], False for 'no' [y/N]
    while True:
        temp = input(f"{prompt} [y/n]: ")[0:1].lower()
        if temp == 'y':
            return True
        if temp == 'n':
            return False


def fileread(self, filename: str, p: "Player"):
    """
    display a file to a user in 40 or 80 columns with more_prompt paging
    also handles highlighting [text in brackets] via re and colorama
    """
    from net_common import Message
    from net_server import UserHandler  # promptResponse and _sendData
    from colorama import Fore  # , Back, Style
    import re  # regular expressions library
    from flags import PlayerFlags

    logging.info(f"fileread(): read {filename=}")

    self.line_count = 0
    cols = 80
    file_handle = f"{filename}-{cols}.txt"
    logging.info(f"fileread: {file_handle=}")

    with open(f'{file_handle}', newline='\n') as file:
        try:
            reading = True
            while reading:
                line = file.readline().rstrip('\n')
                # comment lines in the file are skipped:
                if not line.startswith('#'):
                    if line == '':
                        reading = False  # EOF
                    # FIXME: how to output data to user without using 'return Message(lines=[])'?
                    #  UserHandler._sendData(line) -- access to a protected member fails
                    # x = Message(lines=[line])  # ???

                    new_line = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=line)
                    print(new_line)
                    # FIXME: there is an itertools function which would simplify looping through 1...SCREEN_HEIGHT
                    #    repeatedly -- what is it?
                    self.line_count += 1
                    # FIXME: if line_count == p.client_settings.SCREEN_ROWS:
                    if self.line_count % p.client_settings.screen_rows == 0 and p.query_flag(PlayerFlags.MORE_PROMPT):
                        self.line_count = 0
                        """
                        This call is a little different: choices{} is empty because we don't want a menu,
                        and we'll validate temp here (instead of in promptRequest) because of the possible
                        null represented by just hitting Return/Enter.
                        """
                        temp = UserHandler.prompt_request(self, lines=[],
                                                          prompt='[Enter]: Continue, [Q]uit: ',
                                                          choices={})
                        logging.debug("temp = %s" % repr(temp))
                        # returns dict('text': 'response')
                        choice = temp.get('text')
                        if choice.lower() == 'q':
                            return Message(lines=["(You quit reading.)"])
                        # otherwise, assume Enter was pressed and continue...
        except FileNotFoundError:
            return Message(lines=[], error_line=f'File {file_handle} not found.')


def game_help(self, player: "Player", arg: list):
    from net_server import Message
    """
    Read the command's docstring as help text.
    
    :param self:
    :param arg: what's typed after HELP <...>
    :return:
    """
    from player import Player
    # function name 'help' shadows built-in name
    logging.info(f'game_help: {arg=}')
    if len(arg) == 0:
        fileread(self, filename="main-menu", p=player)
        return None
    else:
        try:
            if callable(arg[0]):
                print(arg[0].__docstring__)
        except not callable(arg[0]):
            print(f"Can't find help for {arg[0]}.")
    return Message(lines=["Done."])


def make_random_id() -> int:
    """Returns a random ID, 1-65536"""
    random_id = random.randrange(1, 65536)  # 256 ** 2
    logging.debug("%i" % random_id)
    return random_id


class PronounType(Enum):
    """Defines the grammatical type of pronoun needed."""
    SUBJECTIVE = auto()           # e.g., "HE went to the store."
    OBJECTIVE = auto()            # e.g., "I gave the book to HIM."
    POSSESSIVE_ADJECTIVE = auto() # e.g., "That is HIS book."
    POSSESSIVE_PRONOUN = auto()   # e.g., "The book is HIS."
    REFLEXIVE = auto()            # e.g., "He did it HIMSELF."


def get_pronoun(character: "Player", pronoun_type: PronounType, capitalize: bool = False):
    """
    Returns the correct pronoun based on character and grammatical type.

    :param character: the Player, Ally, or Monster object to work with
    :param pronoun_type: one of the PronounType Enums
    :param capitalize: bool, whether to capitalize the pronoun or not
    :return: string - The correct pronoun as a string, or an empty string if not found.

    # Create some characters
    >>> from base_variables import PRONOUN_MAP
    >>> from tada_utilities import PronounType
    >>> setup = {"name": "Arthur", "gender": Gender.MALE}
    >>> arthur = Player(**setup)

    >>> setup = {"name": "Guinevere", "gender": Gender.FEMALE}
    >>> guinevere = Player(**setup)

    >>> setup = {"name": "Merlin", "gender": Gender.MALE}
    >>> merlin = Player(**setup)

    # --- Demonstrations ---

    # Subjective: "He/She/They"
    >>> print(f"{arthur.name} draws {get_pronoun(arthur, PronounType.POSSESSIVE_PRONOUN)} sword. "
    ...       f"{get_pronoun(arthur, PronounType.SUBJECTIVE).capitalize()} looks determined.")
    Arthur draws his sword. He looks determined.

    # Objective: "him/her/them"
    >>> print(f"Merlin gives the message to {guinevere.name}. "
    ...       f"{get_pronoun(merlin, PronounType.SUBJECTIVE)} gives it to {get_pronoun(guinevere, PronounType.OBJECTIVE)}.")
    Merlin gives the message to Guinevere. He gives it to her.

    # Possessive Adjective: "his/her/their"
    >>> print(f"Merlin . "
    ...       f"This is {get_pronoun(merlin, PronounType.POSSESSIVE_ADJECTIVE)} duty.")
    The golem stands guard over the treasure. This is its duty.

    # Possessive Pronoun: "his/hers/theirs"
    >>> print(f"The crown belongs to Arthur. "
    ...      f"It is {get_pronoun(arthur, PronounType.POSSESSIVE_PRONOUN)}.")
    The crown belongs to Arthur. It is his.

    >>> print(f"The castle belongs to Guinevere. "
    ...      f"It is {get_pronoun(guinevere, PronounType.POSSESSIVE_PRONOUN)}.")
    The castle belongs to Guinevere. It is hers.

    # Reflexive: "himself/herself/themselves"
    >>> print(f"Guinevere must handle this task {get_pronoun(guinevere, PronounType.REFLEXIVE)}.")
    Guinevere must handle this task herself.
    """
    from base_variables import PRONOUN_MAP
    try:
        gender = character.gender
        pronoun = PRONOUN_MAP[gender][pronoun_type]
        return f"{pronoun}" if not capitalize else f"{pronoun.title()}"
    except KeyError:
        # This will happen if a character or pronoun type isn't in the map
        logging.warning("Pronoun not found for character '%s' and type '%s'" %
                        (character.name, pronoun_type.name))
        return ""


def frame_text(p: 'Player', text: str, title: str = "", width: int = 60) -> list[str]:
    """
    Wraps a string in a text box using ANSI box-drawing characters and
    sends it to the player's output.

    :param p: The Player object, used for the output channel.
    :param text: The string content to be framed.
    :param title: An optional title to be centered on the top border.
    :param width: The total maximum width of the box.
    :return: list[string]
    """
    from base_variables import BOX_CHARS
    # Calculate the inner width available for text, accounting for borders and padding.
    # Box is: │<space>TEXT<space>│
    inner_width = width - 4

    # --- Build Top Border ---
    if title:
        # Center the title with padding and surround with the horizontal character
        title_text = f" Tip: {title.title()} "
    else:
        title_text = f" Tip: "

    top_bar = title_text.center(width - 2, BOX_CHARS["horz"])
    top_border = BOX_CHARS["top_left"] + top_bar + BOX_CHARS["top_right"]

    # --- Build Text Body ---
    wrapped_text = textwrap.wrap(text, width=inner_width)
    body_lines = []
    for line in wrapped_text:
        # Add side borders and padding to each line of text
        padded_line = line.ljust(inner_width)
        body_lines.append(f"{BOX_CHARS['vert']} {padded_line} {BOX_CHARS['vert']}")

    # --- Build Bottom Border ---
    bottom_border = BOX_CHARS["bottom_left"] + (BOX_CHARS["horz"] * (width - 2)) + BOX_CHARS["bottom_right"]

    # --- Combine and return ---
    return [top_border] + body_lines + [bottom_border]

def tip(p: 'Player', title: str, message: str) -> list[str]:
    """
    Displays a helpful tip to the player in a formatted box, but only
    if the player is NOT in expert mode.

    :param p: The Player object, used to check flags and for output.
    :param title: the title of the tip, centered in the box
    :param message: The tip to be displayed.
    :return: A list of strings for the tip box, or an empty list if in expert mode.
    """
    # This function will only run if the player does not have the EXPERT_MODE flag set.
    if not p.query_flag(PlayerFlags.EXPERT_MODE):
        return frame_text(p, message, f"{title}", p.client_settings.screen_columns)
    else:
        return []


# Centralized prompt helper: standardized signature uses (player, reader, writer, prompt_lines, prompt_text)
async def prompt_client(reader=None,
                        writer=None,
                        player_obj=None,
                        prompt_lines=None,
                        prompt_text: str = '') -> str:
    """
    Send a prompt Message to the client and await a single-line response.

    Returns the first line of the client's reply, or empty string on failure.
    """
    if prompt_lines is None:
        prompt_lines = ['']
    from net_common import Message, to_jsonb, from_jsonb
    import textwrap

    if not writer or not reader:
        return ''
    try:
        # split and wrap prompt lines according to player's screen width
        prompt_lines = '\n'.join(prompt_lines)
        wrapped_lines = textwrap.wrap(prompt_lines, width=player_obj.client_settings.screen_columns)
        prompt_lines = wrapped_lines if wrapped_lines else prompt_lines
        msg = Message(lines=prompt_lines, prompt=prompt_text if prompt_text else '> ')
        await send_message(writer, msg)
        # Wait for a single line response
        raw = await reader.readline()
        if not raw:
            return ''
        obj = from_jsonb(raw)
        if isinstance(obj, dict):
            lines = obj.get('lines')
            if isinstance(lines, list) and lines:
                return str(lines[0]).strip()
            # legacy: maybe it's direct text
            return str(obj.get('text', '')).strip()
        return ''
    except Exception:
        return ''



if __name__ == '__main__':
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)

    # set up doctest
    doctest.testmod(verbose=True)

    from player import Player
    from flags import PlayerFlags
    from terminal import Translation
    darmok = Player(name="Darmok")
    darmok.clear_flag(PlayerFlags.EXPERT_MODE)
    darmok.client_settings.screen_columns = 80
    darmok.client_settings.screen_rows = 25
    darmok.client_settings.translation = Translation.ANSI
    darmok.client_settings.return_key = 'Enter'

    yn = input_yes_no("Is this a good demo")

    lo, hi = 10, 45
    n = input_number_range(player=darmok,
                           prompt_msg="Enter a value",
                           out_of_bounds_msg=f"Try again ({lo}-{hi}).",
                           min_value=lo,
                           max_value=hi,
                           default=42)
    print(f"Entered the number {n}")
