import logging
import textwrap

# import net_server  # for promptRequest and Message
from net_server import Message
from server import Player

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
    return Message(lines=[(", ".join(result_list))])


def header(text: str):
    """
    Show 'text' passed, a newline, and a line the length of 'text'
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


def output(string: str, conn: Player.connection_id):
    """
    Print <string> word-wrapped to client's column width to Player

    :param: string: string to output
    :param: conn: connection to output text to
    :return: none
    """
    """
    TODO: implement cbmcodec2 ASCII -> PETSCII translation

    TODO: implement different success messages for Player originating action vs. other Players in room
    use player.
    for cxn in all_Players_in_room:
        if char.(something, idk what at this point) == Player.who_performed_action:
            output(f"You throw the snowball at {target}.", player)
        else:
            output(f"{actor} throws the snowball at {target}.", player)
    """
    if conn.client['translation'] == 'PETSCII':
        pass  # until cbmcodecs2 is fixed
    return Message(lines=[textwrap.fill(text=string, width=conn.client['columns'])])


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
    if default is not None and p.flag['expert_mode'] is False:
        output(f"{return_key} keeps '{default}'.", p)
    while True:
        temp = input(f"{prompt} [{lo}-{hi}]: ")
        # just hitting Return keeps original number
        if temp.isalpha():
            output("Numbers only, please.", p)
        if default is not None and temp == '':
            if p.flag['expert_mode'] is False:
                output(f"(Keeping '{default}'.)", p)
            return default
        else:
            temp = int(temp)
            if lo - 1 < temp < hi + 1:
                return temp
            else:
                output(reminder, p)


def input_string(prompt: str, default: str, player: Player, reminder="Please enter something."):
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
    if default and player.flag['expert_mode'] is False:
        output(f"{player.return_key} keeps '{default}.'", player)
    while True:
        temp = input(f"{prompt}: ")
        # just hitting Return keeps original string
        if default and (temp == '' or temp == default):
            if player.flag['expert_mode']:
                output(f"(Keeping '{default}'.)", player)
            return default
        else:
            output(reminder, player)


def input_yes_no(prompt: str):
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


def fileread(self, filename: str):
    """
    display a file to a user in 40 or 80 columns with more_prompt paging
    also handles highlighting [text in brackets] via re and colorama
    """
    from net_server import Message
    from net_server import UserHandler  # promptResponse and _sendData
    from colorama import Fore  # , Back, Style
    import re  # regular expressions library

    p = self.player
    logging.info(f"fileread(): read {filename=}")

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
                    new_line = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=line)
                    print(new_line)
                    # if char.flag['more_prompt']:
                    self.line_count += 1
                    # if line_count == char.client['rows']:
                    if self.line_count == 20:
                        self.line_count = 0
                        """
                        This call is a little different: choices{} is empty because we don't want a menu,
                        and we'll validate temp here (instead of in promptRequest) because of the possible
                        null represented by just hitting Return/Enter.
                        """
                        temp = UserHandler.prompt_request(self, lines=[],
                                                          prompt='[Enter]: Continue, [Q]uit: ',
                                                          choices={})
                        logging.debug("fileread: temp = %s" % repr(temp))
                        # returns dict('text': 'response')
                        choice = temp.get('text')
                        if choice.lower() == 'q':
                            return Message(lines=["(You quit reading.)"])
                        # otherwise, assume Enter was pressed and continue...
        except FileNotFoundError:
            return Message(lines=[], error_line=f'File {fh} not found.')


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
        return
    else:
        try:
            if callable(arg[0]):
                print(arg[0].__docstring__)
        except not callable(arg[0]):
            print(f"Can't find help for {arg[0]}.")

    return Message(lines=["Done."])


if __name__ == '__main__':
    Player = server.Player()
    Player.name = 'Darmok'
    Player.flags = {'expert_mode': False}
    Player.client = {'columns': 80, 'translation': 'PETSCII'}

    return_key = '[Enter]'

    input_yes_no("Is this a good demo")
    n = input_number_range(prompt="Enter a value", default=18, lo=10, hi=45)
    print(f"Entered {n}")

    items = ['orange', 'dry bones', 'book']
    print(f'You see: {grammatical_list(items)}.')
