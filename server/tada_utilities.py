import textwrap

from players import Player
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
