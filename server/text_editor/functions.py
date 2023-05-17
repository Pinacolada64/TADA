import doctest
import logging
from msvcrt import getch, getche
from text_editor import text_editor


def yes_or_no(prompt="Are you sure", default=False):
    """
    Ask a yes-or-no question, with default answer.
    the response is yes (True), or no (False).

    :param prompt: configurable string
    :param default: unless any other key but 'y' for True or 'n' for False is typed
    :return: response: yes = True, no = False
    """
    if default is True:
        chars = "Y/n"
    if default is False:
        chars = "y/N"
    print(f"{prompt} [{chars}]: ", end="", flush=True)
    key, asc = get_character()
    command_char = key.lower()
    response = ''
    if default is True and command_char != "n":
        response = True
        print("Yes.\n")
    if default is False and command_char != "y":
        response = False
        print("No.\n")
    return response


def pause():
    """
    Pause, allowing user to abort by replying with '[qQ]'
    :return: _continue = True
    """
    _ = input("Pause ('Q' quits): ")
    _continue = _.lower() == "q"
    if _continue is False:
        print("Aborted.")
    return _continue


def find_nth(haystack: str, needle: str, n: int):
    """
    find nth occurrence of needle in haystack
    :param haystack: string to search through
    :param needle: string to search for
    :param n: *n*th occurrence to find
    :return: n if nth occurence found, None if not found
    """
    """
    >>> find_nth("duplicate word word", "word", 2)
    15
    
    >>> find_nth("not here", "is", 1)
    None
    """
    start = haystack.find(needle)
    # -1 is end of line, so not found:
    if start == -1:
        return None
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start


def get_character():
    """
    Wait for a character to be typed.
    return tuple: 'in_char': character, 'asc': ascii value
    """
    in_char = None
    data = ''
    while in_char is None:
        # getch.getch() does not echo input
        in_char = getch()
        asc = ord(in_char)
        data = (in_char, asc)
    return data


def get_line_range(range_str: str) -> tuple:
    """
    parse line range string in the form of:
    x   line x
    x-  line x to the end of the buffer
    x-y line x to line y
    -y line 1 to line y
    Nothing entered: defaults to last line entered,
    depending on "default_last" in dot_params

    returns:
    tuple(x): just line x
    tuple(x, y): lines x - y
    tuple(0, y): lines start of buffer - y
    tuple(x, 0): lines x - end of buffer
    None: no line range entered. if default_last is in dot_params, set current_line to Editor.last_line
    """

    # TODO: (maybe) prompt if range_string is missing?
    """
    if expert_mode is False:
        while True:
            start = input("First line: ")
            end = input("Last line: ")
    ...etc...
    """

    evaluate = text_editor.line_range_re.search(range_str)
    logging.info(f'get_line_range: {range_str=} {evaluate=}')
    if evaluate:
        # split 'evaluate' into capture groups (returns a tuple)
        result = evaluate.groups()
        logging.info(f"get_line_range: {result=}")
    else:
        logging.info("get_line_range: <no regex match>")
        result = None
    # TODO: validate 1 <= start <= Editor.max_lines, start <= end <= Editor.max_lines
    return result


def search_backwards(text: str, index: int, search_string: str):
    """
    :param text: text to search backwards in
    :param index: where to start (usually editor.column)
    :param search_string: what to search for
    :return: found_pos: None: not found | int: position of match
    """
    """
    >>> test = "words, many words"
    
    >>> test_find = test.find("ma")
    
    >>> backwards = search_backwards(text=test, index=len(test), search_string="ma")
    
    >>> backwards == 7
    True
    >>> test_find == 7
    True
    >>> backwards == test_find
    True
    """
    if text == '':
        return None
    for search_pos in list(range(index - 1, -1, -1)):
        if text[search_pos:search_pos + len(search_string)] == search_string:
            found_pos = search_pos
            return found_pos
    # not found:
    return None


if __name__ == '__main__':
    logging.basicConfig()
    doctest.testmod(verbose=True)
