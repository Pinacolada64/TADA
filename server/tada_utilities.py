import logging
import textwrap

from server import Player
from net_server import UserHandler, Message

"""
utilities such as:
* grammatically correct list output
* display a header with underlined text
* prompt requiring yes/no response
* prompt for a range of numbers
* prompt with response string editing
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


def output(lines: list, conn: Player, bracket_coloring: bool = True) -> Message:
    """
    Word-wrap string to Player.client['cols'] width.
    If a line break in the string is needed, make two separate calls to output(), one per line.
    Ending a string with a CR or specifying CR in the join() call won't do what you want.

    :param lines: list of strings to output
    :param conn: player to output() data to
    :param bracket_coloring: if False, do not recolor text within brackets
     (e.g., set to False when drawing bar so as to not color '[] ... []' table graphics)
     :return Message: list
    """
    from colorama import Fore as foreground
    import re
    from net_server import Message
    """
    we want to wrap the un-substituted text first. substituting ANSI
    color codes adds 5-6 characters per substitution, and that wraps
    text in the wrong places.
    """
    wrapped_text = []
    for i, v in enumerate(lines):
        # returns wrapped_text[]
        wrapped_text.append(textwrap.wrap(v, width=conn.client['cols']))
        # print(i, wrapped_text[i])
    new_lines = wrapped_text
    # color text inside brackets using re and colorama:
    # '.+?' is a non-greedy match (finds multiple matches, not just '[World...a]')
    # >>> re.sub(r'\[(.+?)]', r'!\1!', string="Hello [World] this [is a] test.")
    # 'Hello !World! this !is a! test.'
    """
    if bracket_coloring and conn.client['translation'] != "ASCII":
        colored_lines = []
        for i, line in enumerate(wrapped_text):
            # FIXME print(line)
            temp = re.sub(r'[(.+?)]', f'{foreground.RED}' + r'\1' + f'{foreground.RESET}', line)
            colored_lines.append(temp)
        new_lines = colored_lines
    else:
        # for ASCII clients, no color substitution for [bracketed text]:
        new_lines = wrapped_text
    # put output in list, otherwise enumerate() goes through individual
    # characters of a single string
    
    output = []
    for k, v in enumerate(new_lines):
        print(k, v)
        output.append(v)
        
        if i % conn.client['rows'] == 0 and conn.flag['more_prompt'] is True:
            # print(f'{i=} {client["rows"]=} {i % client["rows"]=}')
            temp, _ = input_prompt(prompt=f"[A]bort or {conn.client['return_key']} to continue: ",
                                   help=False)
            if temp == 'a':
                output.append("[Aborted.]")
                break  # out of the loop

        rows = 25
        for i in range(1,58):
            print(f'{i=}', end='')
            if i % rows == 0:
                print(f' [pause]', end='')
            print()
    """
    return Message(lines=wrapped_text)


def input_number_range(prompt: str, lo: int, hi: int, conn: Player, reminder=None, default=None):
    """input 'prompt', accept numbers lo < value < hi
    e.g.
    "'prompt' ['lo'-'hi']: "

    :param prompt: prompt user with this string
    :param default: if not None, and expert mode is False, {return_key} keeps 'default'
    :param lo: lowest number accepted
    :param hi: highest number accepted
    :param conn: Player to output text to
    :param reminder: string to display if lo < temp < hi
    """
    if default is not None and conn.flag['expert_mode'] is False:
        output([f"{conn.client['return_key']} keeps '{default}'."], conn)
    while True:
        temp = input(f"{prompt} [{lo}-{hi}]: ")
        # just hitting Return keeps original number
        if temp.isalpha():
            output(["Numbers only, please."], conn)
        if default is not None and temp == '':
            if conn.flag['expert_mode'] is False:
                output([f"(Keeping '{default}'.)"], conn)
            return default
        else:
            temp = int(temp)
            if lo - 1 < temp < hi + 1:
                return temp
            else:
                output(reminder, conn)


def input_prompt(prompt: str, conn: Player, help=False):
    """
    Prompt user for something

    :param prompt: string to prompt for, minus space at end
    :param conn: connection to output to
    :param help: if True and Expert Mode is off, tell that '?' gets help
    :return: tuple(last_command, command)
    """
    import net_server as ns
    global command, last_command
    if conn.flag['expert_mode'] is False and help is True:
        prompt = f"['?' for menu] {prompt}"
    temp = ns.UserHandler.promptRequest(lines=[], prompt=f'{prompt} ', choices=None)
    print()
    if temp != '':
        command = temp.lower()
        last_command = command
    if temp == '':
        command = last_command
        if conn.flag["expert_mode"] is False:
            output([f"(Repeating '{command}'.)\n"], conn)
    return last_command, command


def input_string(prompt: str, default: str, conn: Player, reminder="Please enter something."):
    """
    input 'prompt', accept numbers lo < value < hi
    e.g.:
    [Return] keeps 'Druid.'  # if expert mode off
    "'prompt' : "

    :param prompt: prompt user with this string
    :param default: True: print/accept {return_key} keeps 'keep_string',
     return 'string' if null string entered
    :param default: [if expert mode off] print "Return keeps 'keep_string'"
    :param conn: Player to output text to
    :param reminder: what to display if edit_mode is False and null string entered
    """
    if default and conn.flag['expert_mode'] is False:
        output([f"{conn.client['return_key']} keeps '{default}.'"], conn)
    while True:
        temp = input(f"{prompt}: ")
        # just hitting Return keeps original string
        if default and (temp == '' or temp == default):
            if conn.flag['expert_mode']:
                output([f"(Keeping '{default}'.)"], conn)
            return default
        else:
            output([reminder], conn)


def input_yes_no(prompt: str, conn: Player) -> bool:
    """input 'prompt', accept 'y' or 'n'
    e.g.
    "'prompt' [y/n]: "

    :param prompt: prompt user with this string
    :param conn: Player to output text to
    :return False: 'no' entered. True: 'yes' entered
    """
    while True:
        temp = input(f"{prompt} [y/n]: ")[0:1].lower()
        if temp == 'y':
            return True
        if temp == 'n':
            return False


def file_read(filename: str, conn: Player) -> list:
    """
    Return a list containing a text file to the calling Player
    Output is handled by tada_utilities.output()

    :param filename: filename to read, minus '-<column_width>.txt' suffix
    :param conn: needed for client["cols"] width suffix on filename
    :return: list text of the file
    """
    # AttributeError: 'list' object has no attribute 'client'
    cols = conn.client['cols']
    fh = f"{filename}-{cols}.txt"  # file handle
    logging.info(f"file_read: {cols=} {fh=}")
    with open(f'{fh}', newline='\n') as file:
        try:
            lines = file.readlines()
            output = []
            for k, v in enumerate(lines):
                output.append(v.strip('\n'))
                # print(k, output[k])
            """
            # more prompt stuff
            if conn.flag['more_prompt'] and k % conn.client['rows'] == 0:
                ===
                This call is a little different: choices{} is empty because we don't want a menu,
                and we'll validate temp here (instead of in promptRequest) because of the possible
                null represented by just hitting Return/Enter.
                ===
                temp = UserHandler.promptRequest(# self,
                                                 lines=[],
                                                 prompt='[Enter]: Continue, [Q]uit: ',
                                                 choices={},
                                                 )
                logging.info(f'{repr(temp)}')
                # returns dict('text': 'response')
                choice = temp.get('text')
                if choice.lower() == 'q':
                    text.append("(You quit reading.)")
                # otherwise, assume Enter was pressed and continue...
            """
            return list(output)
        except FileNotFoundError:
            logging.warning(f'File {fh} not found.')
            return list("(Error.)")


def game_help(params: list, conn: Player) -> Message:
    from net_server import Message
    """
    Display various help menus.
    If no parameter is given, display the main menu.
    If parameter(s) given, display help for that command.
    
    :param params: what's typed after HELP <...>
    :return: Message object with help text
    """
    # function name 'help' shadows built-in name
    logging.info(f'game_help: {params=}')
    # if len(params) == 0:
    lines = file_read(filename="main-menu", conn=conn)
    return Message(lines=[lines, "Done."])


if __name__ == '__main__':
    from server import Player
    data = {'name': 'Darmok',
            'flag': {'expert_mode': False},
            'client': {'columns': 80,
                       'translation': 'PetSCII',
                       'return_key': 'Return'}}
    temp = Player(**data)
    print(temp)
    # player.name = 'Darmok'
    # player.flags = {'expert_mode': False}
    # player.client = {'columns': 80, 'translation': 'PETSCII'}
    # return_key = '[Enter]'

    input_yes_no("Is this a good demo", conn=temp)
    n = input_number_range(prompt="Enter a value", default=18, lo=10, hi=45, conn=temp)
    print(f"Entered {n}")

    items = ['orange', 'dry bones', 'book']
    print(f'You see: {grammatical_list(items)}.')
