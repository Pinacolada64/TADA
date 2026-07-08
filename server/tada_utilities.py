#!/bin/env python3

import doctest
import logging
import random
import textwrap
from typing import TYPE_CHECKING

from base_classes import PronounType
from terminal_context import GameContext

if TYPE_CHECKING:
    from player import Player
    from network_context import GameContext

"""
utilities such as:
* grammatically correct list output
* display a header with underlined text
* prompt requiring yes/no response
* prompt for a range of numbers
* prompt with string editing
* generate a random ID from 1-65536 (inclusive)
"""


# ---------------------------------------------------------------------------
# Core async I/O primitives
# ---------------------------------------------------------------------------

async def prompt_client(ctx: 'GameContext | TerminalContext',
                        preamble_lines: list[str] | None = None,
                        prompt_text: str = '') -> str:
    """
    Send optional preamble lines and a prompt to the client, then await
    a single-line response. Returns the response string, or '' on failure.

    :param ctx: GameContext
    :param preamble_lines: lines to display before the prompt (optional)
    :param prompt_text: the prompt string shown to the user
    :return: stripped response string, or '' on failure/disconnect
    """
    from net_common import Message, from_jsonb

    if not ctx.writer or not ctx.reader:
        return ''

    if preamble_lines is None:
        preamble_lines = []

    # Wrap preamble lines to player's screen width
    screen_width = ctx.player.client_settings.screen_columns
    wrapped: list[str] = []
    for line in preamble_lines:
        if line.strip():
            wrapped.extend(textwrap.wrap(line, width=screen_width))
        else:
            wrapped.append('')   # preserve intentional blank lines

    try:
        msg = Message(lines=wrapped, prompt=prompt_text or '> ')
        await ctx.send(wrapped)
        await ctx.send(prompt_text)

        raw = await ctx.reader.readline()
        if not raw:
            return ''
        obj = from_jsonb(raw)
        if isinstance(obj, dict):
            lines = obj.get('lines')
            if isinstance(lines, list) and lines:
                return str(lines[0]).strip()
            return str(obj.get('text', '')).strip()
        return ''
    except Exception:
        logging.exception('prompt_client: error reading response')
        return ''


async def header(ctx: 'GameContext', header_text: str = '') -> None:
    """
    Display a section header with an underline, e.g.:

        This Is A Header
        ================

    :param ctx: GameContext
    :param header_text: string to display
    """
    await ctx.send(f'\n{header_text}\n{"=" * len(header_text)}\n')


# ---------------------------------------------------------------------------
# Async input helpers (all built on prompt_client)
# ---------------------------------------------------------------------------

async def input_string(ctx: 'GameContext',
                       default: str = '',
                       prompt: str = '',
                       allow_empty: bool = True,
                       keep_msg: bool = True,
                       reminder: str = 'Please enter something.') -> str:
    """
    Prompt for a string, returning ``default`` if the user hits Return.

    :param ctx: GameContext
    :param default: returned if user hits Return without typing
    :param prompt: prompt text shown to the user
    :param allow_empty: if True, an empty response returns ``default``
    :param keep_msg: if True and not expert mode, show 'Return keeps <default>'
    :param reminder: shown when allow_empty=False and user enters nothing
    :return: the entered string, or ``default``
    """
    from flags import PlayerFlags
    expert_mode = ctx.player.query_flag(PlayerFlags.EXPERT_MODE)
    return_key  = ctx.player.client_settings.return_key

    if keep_msg and not expert_mode and default:
        await ctx.send(f"{return_key} keeps '{default}'.")

    while True:
        answer = await prompt_client(ctx, prompt_text=f'{prompt}: ')

        if answer in ('', default):
            if allow_empty:
                return default
            else:
                await ctx.send(reminder)
                if expert_mode:
                    await ctx.send(f"(Keeping '{default}'.)")
                    return default
        else:
            return answer


async def input_number_range(ctx: 'GameContext',
                             default: int | None = None,
                             prompt_msg: str = '',
                             min_value: int = 1,
                             max_value: int = 10,
                             out_of_bounds_msg: str | None = None) -> int | None:
    """
    Prompt for an integer in [min_value, max_value].
    Returns ``default`` if the user hits Return without typing.

    :param ctx: GameContext
    :param default: returned on empty input
    :param prompt_msg: prompt text
    :param min_value: lowest accepted value (inclusive)
    :param max_value: highest accepted value (inclusive)
    :param out_of_bounds_msg: shown when the value is out of range
    :return: validated integer, or ``default``
    """
    from flags import PlayerFlags
    expert_mode = ctx.player.query_flag(PlayerFlags.EXPERT_MODE)
    return_key  = ctx.player.client_settings.return_key

    if default is not None and not expert_mode:
        await ctx.send(f"{return_key} keeps '{default}'.")

    oob = out_of_bounds_msg or f'Please enter a number between {min_value} and {max_value}.'

    while True:
        raw = await ctx.prompt(ctx, prompt_text=f'{prompt_msg} [{min_value}-{max_value}]: ')

        if raw == '':
            return default

        if not raw.lstrip('-').isdigit():
            await ctx.send('"Numbers only, please."')
            continue

        number = int(raw)
        if min_value <= number <= max_value:
            return number
        await ctx.send(oob)


async def input_yes_no(ctx: 'GameContext', prompt: str,
                       default: bool | None = None) -> bool | None:
    """
    Prompt for a yes/no response, returning True for 'y' and False for 'n'.
    Loops until a valid response is given.

    :param ctx: GameContext
    :param prompt: question text (without the [y/n] suffix)
    :param default: if given, blank input (Enter) returns this instead of
                     re-prompting; the suffix shown reflects it ('[Y/n]' /
                     '[y/N]'). None (the default) requires an explicit y/n.
    :return: True if yes, False if no, None if the connection dropped
             mid-prompt
    """
    suffix = {True: '[Y/n]', False: '[y/N]', None: '[y/n]'}[default]
    while True:
        raw = await ctx.prompt('y/n', preamble_lines=[f'{prompt} {suffix}'])
        if raw is None:
            return None
        ch = raw.strip()[:1].lower()
        if not ch and default is not None:
            return default
        if ch == 'y':
            return True
        if ch == 'n':
            return False
        await ctx.send("Please enter 'y' or 'n'.")


async def set_logging_level(ctx: 'GameContext') -> None:
    """
    Display the current logging level, prompt the user to select a new one,
    and apply the change.
    """
    root_logger = logging.getLogger()
    levels = {
        'D': logging.DEBUG,
        'I': logging.INFO,
        'W': logging.WARNING,
        'E': logging.ERROR,
        'C': logging.CRITICAL,
    }
    current = logging.getLevelName(root_logger.level)
    await ctx.send('', '--- Logging Level Control ---',
                   f'Current level: {current}',
                   'Select a new logging level:')
    for key, level_int in levels.items():
        await ctx.send(f'  {key}. {logging.getLevelName(level_int)}')

    return_key = ctx.player.client_settings.return_key
    choice = await input_string(ctx,
                                default=current,
                                prompt=f'Enter choice (or press {return_key} to cancel)',
                                allow_empty=True,
                                keep_msg=True)
    choice = choice.upper()
    if choice in levels:
        root_logger.setLevel(levels[choice])
        await ctx.send(f'Logging level changed to {logging.getLevelName(levels[choice])}.')
    else:
        await ctx.send('Cancelled. Logging level unchanged.')


# ---------------------------------------------------------------------------
# Pure string utilities (no ctx, no I/O)
# ---------------------------------------------------------------------------

def a_or_an(string: str, capitalize: bool = False) -> str:
    """
    Return 'a' or 'an' '<string>' based on the first letter.

    >>> a_or_an('banana')
    'a banana'
    >>> a_or_an('apple')
    'an apple'
    >>> a_or_an('elephant', capitalize=True)
    'An elephant'
    """
    article = 'an' if string.lower().startswith(('a', 'e', 'i', 'o', 'u')) else 'a'
    return f'{article.title() if capitalize else article} {string}'


def get_article_and_quantity(item_name: str) -> str:
    """
    Determines the correct article ('a', 'an', or 'some') for a given item name.
    Assumes plurality if the name ends in 's'.

    >>> get_article_and_quantity('banana')
    'a banana'
    >>> get_article_and_quantity('orange')
    'an orange'
    >>> get_article_and_quantity('dry bones')
    'some dry bones'
    """
    if item_name.lower().endswith('s'):
        return f'some {item_name}'
    return a_or_an(item_name)


def oxford_comma_list(items: list) -> str:
    """
    Return a grammatically correct comma-separated list with Oxford comma.

    >>> oxford_comma_list(['apple', 'banana', 'cherry'])
    'apple, banana, and cherry'
    >>> oxford_comma_list(['apple', 'banana'])
    'apple and banana'
    >>> oxford_comma_list(['apple'])
    'apple'
    >>> oxford_comma_list([])
    ''
    """
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def grammatical_list(item_list: str | list) -> str:
    """
    List items with correct articles and Oxford comma.

    >>> grammatical_list(['orange', 'dry bones', 'book'])
    'an orange, some dry bones, and a book'
    >>> grammatical_list(['apple', 'banana'])
    'an apple and a banana'
    >>> grammatical_list('sword')
    'a sword'
    >>> grammatical_list([])
    'nothing'
    """
    if isinstance(item_list, str):
        return get_article_and_quantity(item_list)

    if not item_list:
        return 'nothing'
    processed = [get_article_and_quantity(i) for i in item_list]
    return oxford_comma_list(processed)


def list_players_in_room(player_list: str | list) -> str:
    """
    List players in a room grammatically.

    >>> list_players_in_room('Rulan')
    'Rulan is here.'
    >>> list_players_in_room(["Rulan", "J'ee"])
    "Rulan and J'ee are here."
    >>> list_players_in_room(["Rulan", "J'ee", "Argentilane"])
    "Rulan, J'ee, and Argentilane are here."
    >>> list_players_in_room([])
    'No one is here.'
    """
    # TODO: Later, when players can lead/join parties, display e.g.,
    #     "Rulan (and his party) are here."

    if isinstance(player_list, str):
        return f'{player_list} is here.'
    if not player_list:
        return 'No one is here.'
    if len(player_list) == 1:
        return f'{player_list[0]} is here.'
    return f'{oxford_comma_list(player_list)} are here.'


def format_quote(quote_text: str | None, reader_name: str) -> str | None:
    """Format a player's personal quote for display to *reader_name*.

    A "$" in the quote is replaced by the *reading* player's name, not
    the quote's author (SPUR.MISC2.S:491,496-497 / SPUR.MAIN.S:480-483)
    -- e.g. the author writes "Hello $, welcome!" and each viewer sees
    their own name substituted in. Only the first "$" is replaced,
    matching SPUR's instr()-based single-substitution behavior.

    :param quote_text: the author's saved quote, or None/empty if unset
    :param reader_name: the name of whoever is viewing the quote
    :return: the quote wrapped in single quotes, or None if unset

    >>> format_quote("Hello $, welcome!", "Rulan")
    "'Hello Rulan, welcome!'"
    >>> format_quote("Trespassers will be shot.", "Rulan")
    "'Trespassers will be shot.'"
    >>> format_quote(None, "Rulan") is None
    True
    """
    if not quote_text:
        return None
    if '$' in quote_text:
        quote_text = quote_text.replace('$', reader_name, 1)
    return f"'{quote_text}'"


def bulleted_list_format(text: str, width: int,
                         initial_indent: str = '* ',
                         subsequent_indent: str = '  ') -> str:
    """Format a paragraph as a wrapped bullet point."""
    return textwrap.fill(textwrap.dedent(text).strip(), width=width,
                         initial_indent=initial_indent,
                         subsequent_indent=subsequent_indent)


def make_random_id() -> int:
    """Return a random ID in the range [1, 65536]."""
    random_id = random.randrange(1, 65537)  # 256 ** 2
    logging.debug("%i" % random_id)
    return random_id


# ---------------------------------------------------------------------------
# Player-aware display utilities (return list[str], no I/O)


def get_pronoun(character: 'Player',
                pronoun_type: PronounType,
                capitalize: bool = False) -> str:
    """Returns the correct pronoun based on character and grammatical type.

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
    from base_classes import Gender
    _STR_TO_GENDER = {
        'm': Gender.MALE, 'M': Gender.MALE, 'Male': Gender.MALE,
        'f': Gender.FEMALE, 'F': Gender.FEMALE, 'Female': Gender.FEMALE,
    }
    try:
        gender = getattr(character, 'gender', None)
        if isinstance(gender, str) and not isinstance(gender, Gender):
            gender = _STR_TO_GENDER.get(gender)
        pronoun = PRONOUN_MAP[gender][pronoun_type]
        return pronoun.title() if capitalize else pronoun
    except (KeyError, TypeError):
        logging.warning("Pronoun not found for '%s' type '%s'",
                        getattr(character, 'name', '?'), pronoun_type.name)
        return ''


def frame_text(ctx: GameContext, text: str, title: str = '') -> list[str]:
    """
    Wrap a string in a box using box-drawing characters.
    Returns a list of strings; does not send to player directly.
    """
    from base_variables import BOX_CHARS
    # Calculate the inner width available for text, accounting for borders and padding.
    # Box is: │<space>TEXT<space>│
    screen_width = ctx.player.client_settings.screen_columns
    inner_width = screen_width - 4
    title_text  = f' {title.title()} ' if title else ' '
    top_bar     = title_text.center(screen_width - 2, BOX_CHARS['horz'])
    top_border  = BOX_CHARS['top_left'] + top_bar + BOX_CHARS['top_right']
    body_lines  = [
        f"{BOX_CHARS['vert']} {line.ljust(inner_width)} {BOX_CHARS['vert']}"
        for line in textwrap.wrap(text, width=inner_width)
    ]
    bottom_border = (BOX_CHARS['bottom_left'] +
                     BOX_CHARS['horz'] * (screen_width - 2) +
                     BOX_CHARS['bottom_right'])
    return [top_border] + body_lines + [bottom_border]


def tip(ctx: GameContext, title: str, message: str) -> list[str]:
    """
    Return a formatted tip box, or [] if the player is in expert mode.
    Caller is responsible for sending the returned lines.
    """
    if not ctx.player.is_expert:
        return frame_text(ctx, message, title)
    return []


# ---------------------------------------------------------------------------
# File display (needs full rewrite — currently placeholder)
# ---------------------------------------------------------------------------

async def fileread(ctx: 'GameContext', filename: str) -> None:
    """
    Display a text file to the player.
    Pagination is handled automatically by ctx.send() when the file
    has more lines than the player's screen height.
    TODO: handle column-specific filenames (e.g. main-menu-80.txt)
    TODO: handle [bracketed] highlight syntax
    """
    cols      = ctx.player.client_settings.screen_columns
    file_path = f'{filename}-{cols}.txt'
    try:
        with open(file_path, newline='\n') as fh:
            lines = [line.rstrip('\n') for line in fh
                     if not line.startswith('#')]
        await ctx.send(*lines)
    except FileNotFoundError:
        await ctx.send(f'File not found: {file_path}')


# ---------------------------------------------------------------------------
# Module self-test
# ---------------------------------------------------------------------------

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
    n = input_number_range(ctx,
                           prompt_msg="Enter a value",
                           out_of_bounds_msg=f"Try again ({lo}-{hi}).",
                           min_value=lo,
                           max_value=hi,
                           default=42)
    print(f"Entered the number {n}")
