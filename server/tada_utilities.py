import doctest
import logging
import random

import net_server  # for promptRequest and Message
from net_server import Message
from player import Player
from flags import PlayerFlags
from user_settings import Translation

"""
utilities such as:
* grammatically correct list output
* display a header with underlined text
* prompt requiring yes/no response
* prompt for a range of numbers
* prompt with string editing
* generate a random ID from 1-65536 (inclusive)
"""


def grammatical_list(item_list: str | list) -> str:
    """
    This function lists items in a room in a grammatically correct form,
    handling multiple items (which themselves can be singular or plural in quantity),
    or

    if the object is singular (the name does not end in 's'):
    'a (object starting with a consonant)', 'an (object starting with a vowel)'.
    If the object is plural (the name ends in 's'): 'some <object>'
    If there is one item in the list, print it.
    If there are two items in the list, print the first, an Oxford comma, and the second.
    If there are more than two items, print the first, second, [...] 'and {a|an} <object>'.
    """
    """
    >>> items = ['orange', 'dry bones', 'book']
    
    >>> print(f'You see: {grammatical_list(items)}.')
    You see: an orange, some dry bones, and a book.
    """
    result_list = []
    if isinstance(item_list, str):
        # assumes 1 item:
        return f"You see: {i_dont_know_a_function_name(item_list)}."

    # assumes a list of items (could still just be 1 item!):
    for item in item_list:
        result_list.append(i_dont_know_a_function_name(item))
    # tanabi: Add 'and' if we need it
    if len(result_list) > 1:
        result_list[-1] = f"and {result_list[-1]}"
    # Join it together
    # return Message(lines=[(", ".join(result_list))])
    return ", ".join(result_list)

def i_dont_know_a_function_name(item: str):
    if item.endswith("s"):
        # plural:
        return f"some {item}"
    elif item.startswith(('a', 'e', 'i', 'o', 'u')):
        return f"an {item}"
    else:
        return f"a {item}"


def list_players_in_room(player_list: str | list):
    """List players in room in a grammatically correct way:

    "Rulan is here."
    "Rulan and J'ee are here."
    "Rulan, J'ee, and Argentilane are here."

    TODO: Later, when players can lead/join parties, display e.g.,
        "Rulan (and his party) are here."
    """
    pass

def header(text: str):
    """
    Show `text` passed, a newline, and a line the length of `text`
    e.g.,

    This is a header
    ----------------

    :param text: string to display
    :return: None
    """
    line = f"\n{text}\n{'*' * len(text)}\n"
    # print()
    # print(text)
    # print("-" * len(text))
    # print()
    return Message(lines=[line])


def input_number_range(prompt: str, lo: int, hi: int, p=Player, reminder=None, default=None):
    """Display input 'prompt', accept numbers lo < value < hi
    e.g.
    "'prompt' ['lo'-'hi']: "

    :param prompt: prompt user with this string
    :param default: if not None, and expert mode is False, {return_key} keeps 'default'
    :param lo: lowest number accepted
    :param hi: highest number accepted
    :param p: Player to output text to
    :param reminder: string to display if lo < temp < hi
    """
    if default is not None and not p.query_flag(PlayerFlags.EXPERT_MODE):
        p.output(f"{p.client_settings.RETURN_KEY} keeps '{default}'.")
    while True:
        temp = input(f"{prompt} [{lo}-{hi}]: ")
        # just hitting Return keeps original number
        if temp.isalpha():
            p.output("Numbers only, please.")
        if default is not None and not temp:
            if p.query_flag(PlayerFlags.EXPERT_MODE) is False:
                p.output(f"(Keeping '{default}'.)")
            return default
        else:
            temp = int(temp)
            if lo - 1 < temp < hi + 1:
                return temp
            else:
                p.output(string=reminder)


def input_string(prompt: str, default: bool, player: Player, reminder="Please enter something."):
    """input 'prompt', accept numbers lo < value < hi
    e.g.:
    [Return] keeps 'Druid.'  # if expert mode off
    "'prompt' : "

    :param prompt: prompt user with this string
    :param default: True: print/accept {return_key} keeps 'keep_string',
     return 'string' if null string entered
    :param default: [if expert mode off] print "Return keeps 'keep_string'"
    :param player: Player to output text to
    :param reminder: what to display if edit_mode is False and null string entered
    """
    if default and player.query_flag(PlayerFlags.EXPERT_MODE) is False:
        player.output(f"{player.terminal_settings.return_key} keeps '{default}.'")
    while True:
        temp = input(f"{prompt}: ")
        # just hitting Return keeps original string
        if default and (not temp or temp == default):
            if player.query_flag(PlayerFlags.EXPERT_MODE):
                player.output(f"(Keeping '{default}'.)")
            return default
        else:
            player.output(reminder)


def input_yes_no(prompt: str) -> bool:
    """input 'prompt', accept 'y' or 'n'
    e.g.
    "'prompt' [y/n]: "

    :param prompt: prompt user with this string
    :return False: 'no' entered. True: 'yes' entered
    """
    while True:
        temp = input(f"{prompt} [y/n]: ")[0:1].lower()
        if temp == 'y':
            return True
        if temp == 'n':
            return False


def fileread(self, filename: str, player: Player):
    """
    display a file to a user in 40 or 80 columns with more_prompt paging
    also handles highlighting [text in brackets] via re and colorama
    """
    from net_server import Message
    from net_server import UserHandler  # promptResponse and _sendData
    from colorama import Fore  # , Back, Style
    import re  # regular expressions library

    logging.info(f"fileread(): read {filename=}")

    self.line_count = 0
    # FIXME: cols = player.client.terminal_settings.COLUMNS
    cols = 80
    file_handle = f"{filename}-{cols}.txt"
    logging.info(f"fileread: {file_handle=}")

    with open(f'{file_handle}', newline='\n') as file:
        try:
            reading = True
            while reading is True:
                line = file.readline().rstrip('\n')
                # comment lines in the file are skipped:
                if line.startswith('#') is False:
                    if line == '':
                        reading = False  # EOF
                    # FIXME: how to output data to user without using 'return Message(lines=[])'?
                    #  UserHandler._sendData(line) -- access to a protected member fails
                    # x = Message(lines=[line])  # ???

                    # color text inside brackets using re and colorama
                    # '.+?' is a non-greedy match (finds multiple matches, not just '[World...a]')
                    # >>> re.sub(r'\[(.+?)\]', r'!\1!', string="Hello [World] this [is a] test.")
                    # 'Hello !World! this !is a! test.'
                    new_line = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=line)
                    print(new_line)
                    # FIXME: there is an itertools function which would simplify looping through 1...SCREEN_HEIGHT
                    #    repeatedly -- what is it?
                    self.line_count += 1
                    # FIXME: if line_count == player.client_settings.SCREEN_ROWS:
                    if self.line_count == 20 and player.query_flag(PlayerFlags.MORE_PROMPT):
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


def game_help(self, arg: list):
    from net_server import Message
    """
    :param self:
    :param arg: what's typed after HELP <...>
    :return:
    """
    # function name 'help' shadows built-in name
    logging.info(f'game_help: {arg=}')
    if len(arg) == 0:
        fileread(self, filename="main-menu")
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


if __name__ == '__main__':
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)

    # set up doctest
    doctest.testmod(verbose=True)

    player = Player(name="Darmok")
    player.clear_flag(PlayerFlags.EXPERT_MODE)
    player.client_settings.SCREEN_WIDTH = 80
    player.client_settings.SCREEN_HEIGHT = 25
    player.client_settings.TRANSLATION = Translation.ANSI
    player.client_settings.RETURN_KEY = '[Enter]'

    input_yes_no("Is this a good demo")
    n = input_number_range(prompt="Enter a value", default=18, lo=10, hi=45)
    print(f"Entered {n}")
