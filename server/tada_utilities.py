import logging
import textwrap

from players import Player

import net_server  # for promptRequest and Message

"""
utilities such as:
* grammatically correct list output
* display a header with underlined text
* prompt requiring yes/no response
* prompt for a range of numbers
* prompt with string editing
"""


def grammatical_list(item_list):
    result_list = []
    for item in item_list:
        if item.endswith("s"):
            result_list.append(f"some {item}")
        elif item.startswith(('a', 'e', 'i', 'o', 'u')):
            result_list.append(f"an {item}")
        else:
            result_list.append(f"a {item}")

    # tanabi: Add 'and' if we need it
    if len(result_list) > 1:
        result_list[-1] = f"and {result_list[-1]}"
    # Join it together
    return ", ".join(result_list)


def header(text: str):
    """
    Show 'text' passed, a newline, and a line the length of 'text'
    e.g.,
    This is a header
    ----------------
    :param text: string to display
    :return: None
    """
    print()
    print(text)
    print("-" * len(text))
    print()


def output(string: str, conn: Player):
    """
    Print 'string' word-wrapped to client's column width to Player

    :param string: string to output
    :param conn: connection to output text to
    :return: none
    """
    """
    TODO: implement cbmcodec2 ASCII -> PETSCII translation

    TODO: implement different success messages for player originating action vs. other players in room
    for cxn in all_players_in_room:
        if p.(something, idk what at this point) == player.who_performed_action:
            output(f"You throw the snowball at {target}.", player)
        else:
            output(f"{actor} throws the snowball at {target}.", player)
    """
    if conn.client['translation'] == 'PETSCII':
        pass  # until cbmcodecs2 is fixed
    print(textwrap.fill(text=string, width=conn.client['columns']))


def input_number_range(prompt: str, lo: int, hi: int, p=Player, reminder=None, default=None):
    """input 'prompt', accept numbers lo < value < hi
    e.g.
    "'prompt' ['lo'-'hi']: "

    :param prompt: prompt user with this string
    :param default: if not None, and expert mode is False, {return_key} keeps 'default'
    :param lo: lowest number accepted
    :param hi: highest number accepted
    :param p: Player to output text to
    :param reminder: string to display if lo < temp < hi
    """
    if default is not None and p.flags['expert_mode'] is False:
        output(f"{return_key} keeps '{default}'.", p)
    while True:
        temp = input(f"{prompt} [{lo}-{hi}]: ")
        # just hitting Return keeps original number
        if temp.isalpha():
            output("Numbers only, please.", p)
        if default is not None and temp == '':
            if p.flags['expert_mode'] is False:
                output(f"(Keeping '{default}'.)", p)
            return default
        else:
            temp = int(temp)
            if lo - 1 < temp < hi + 1:
                return temp
            else:
                output(reminder, p)


def input_string(prompt: str, default: str, p: Player, reminder="Please enter something."):
    """input 'prompt', accept numbers lo < value < hi
    e.g.:
    [Return] keeps 'Druid.'  # if expert mode off
    "'prompt' : "

    :param prompt: prompt user with this string
    :param default: True: print/accept {return_key} keeps 'keep_string',
     return 'string' if null string entered
    :param default: [if expert mode off] print "Return keeps 'keep_string'"
    :param p: Player to output text to
    :param reminder: what to display if edit_mode is False and null string entered
    """
    if default and p.flags['expert_mode'] is False:
        output(f"{return_key} keeps '{default}.'", p)
    while True:
        temp = input(f"{prompt}: ")
        # just hitting Return keeps original string
        if default and (temp == '' or temp == default):
            if p.flags['expert_mode']:
                output(f"(Keeping '{default}'.)", p)
            return default
        else:
            output(reminder, p)


def input_yes_no(prompt: str):
    """input 'prompt', accept 'y' or 'n'
    e.g.
    "'prompt' [y/n]: "

    :param prompt: prompt user with this string
    :param p: Player to output text to
    :return False: 'no' entered. True: 'yes' entered
    """
    while True:
        temp = input(f"{prompt} [y/n]: ")[0:1].lower()
        if temp == 'y':
            return True
        if temp == 'n':
            return False


def fileread(self, filename: str):
    """
    display a file to a user in 40 or 80 columns with more_prompt paging
    also handles highlighting [text in brackets] via re and colorama
    """
    from net_server import Message
    from net_server import UserHandler  # promptResponse and _sendData
    from colorama import Fore, Back, Style
    import re

    p = self.player
    logging.info(f"fileread: read {filename=}")

    self.line_count = 0
    # cols = self.client['columns']
    cols = 80
    fh = f"{filename}-{cols}.txt"
    logging.info(f"fileread: {fh=}")

    with open(f'{fh}', newline='\n') as file:
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
                    l = re.sub(r'\[(.+?)\]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=line)
                    print(l)
                    # if p.flags['more_prompt']:
                    self.line_count += 1
                    # if line_count == p.client['rows']:
                    if self.line_count == 20:
                        self.line_count = 0
                        """
                        This call is a little different: choices{} is empty because we don't want a menu,
                        and we'll validate temp here (instead of in promptRequest) because of the possible
                        null represented by just hitting Return/Enter.
                        """
                        temp = UserHandler.promptRequest(self, lines=[],
                                                         prompt='[Enter]: Continue, [Q]uit: ',
                                                         choices={})
                        logging.info(f'{repr(temp)}')
                        logging.debug("fileread: temp = %s" % repr(temp))
                        # returns dict('text': 'response')
                        choice = temp.get('text')
                        if choice.lower() == 'q':
                            return Message(lines=["(You quit reading.)"])
                        # otherwise, assume Enter was pressed and continue...
        except FileNotFoundError:
            return Message(lines=[], error_line=f'File {fh} not found.')


def game_help(self, params: list):
    from net_server import Message
    """
    :param self:
    :param params: what's typed after HELP <...>
    :return:
    """
    # function name 'help' shadows built-in name
    logging.info(f'game_help: {params=}')
    # if len(params) == 0:
    fileread(self, filename="main-menu")
    return Message(lines=["Done."])


if __name__ == '__main__':
    from players import Player
    player = Player()
    player.name = 'Darmok'
    player.flags = {'expert_mode': False}
    player.client = {'columns': 80, 'translation': 'PETSCII'}

    return_key = '[Enter]'

    input_yes_no("Is this a good demo")
    n = input_number_range(prompt="Enter a value", default=18, lo=10, hi=45)
    print(f"Entered {n}")

    items = ['orange', 'dry bones', 'book']
    print(f'You see: {grammatical_list(items)}.')
