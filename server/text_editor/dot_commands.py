import logging
from typing import Callable, Any
from dataclasses import dataclass

# text editor package imports
from text_editor import Buffer, Editor


@dataclass
class DotCommand:
    # dot_key: keyboard key to type to select function
    # dot_key: str
    # dot_text: text to display
    dot_text: str
    # dot_func: function to call
    # TODO: this works, but I don't understand it -- copied from scratches/dict_menu.py
    dot_func: Callable[[], Any]
    """
    dot_flag:
        'None': None of the following flags apply
        'immediate': Return key not required to select command
            (.A Abort, .H Help, .# Scale, .N New Text, .O Line Number Mode,
             .Q Query, .S Save, .U Undo)
        'subcmd': Additional keystroke required as a parameter to the main command:
            (.E Edit [M]ove, .E Edit [C]opy,
             .J Justify [L]eft, [C]entered, [R]ight, [E]xpand, [P]ack, [I]ndent, [U]nindent)
    """
    dot_flag: str | list | None
    """
    dot_range:
        'all': you can type x, x-, x-y, -y after the command, or
            Return = set line_range to [ first | last | all ] depending on dot_range_default
        None: No line range needed
        'single': one value accepted:
            (.C Columns <x>)
    """
    dot_range: str | None
    """
    dot_range_default:
        'first': Return key by itself chooses first line in buffer
            (.I Insert)
        'last': Return key by itself chooses last line in buffer
            (.D Delete, .E Edit)
        'all': Return key by itself chooses all lines in buffer
            (.F Find, .K Find and Replace, .L List, .R Read)
    """
    dot_range_default: str | None

    def __str__(self):
        bla = f"         Text: '{self.dot_text}'\n" \
              f"     Function: {self.dot_func}\n" \
              f"        Flags: {self.dot_flag}\n" \
              f"       Ranges: {self.dot_range}\n" \
              f"Range Default: {self.dot_range_default}\n"
        return bla


def parse_dot_command(input_line: str):
    """
    Dot commands are called such since they traditionally begin with typing
    "." in column zero. Later revisions of the BBS software added "/" since
    many text editors also used that character, so that is reproduced here.

    :param input_line: text typed
    :return:
    """
    # print(COMMAND_PROMPT, end="", flush=True)
    # check for space(s) in input:
    args = input_line.split()
    # argument count:
    argc = len(args)
    if argc > 0:
        logging.info(f"{argc=}")
        for num, arg in enumerate(args):
            logging.info(f"{num=} {arg=}")
    if len(args[0]) != 2:
        print("Dot needs a command letter after it.")
    else:
        # get dot command letter:
        dot_cmd_letter = args[0][1:2].lower()
        logging.info(f'Cmd: .{dot_cmd_letter}')
        if dot_cmd_letter in DOT_CMD_TABLE:
            dot_cmd = DOT_CMD_TABLE[dot_cmd_letter]
            dot_text = dot_cmd.dot_text
            dot_func = dot_cmd.dot_func
            dot_flag = dot_cmd.dot_flag
            dot_range = dot_cmd.dot_range
            logging.info(f'{dot_text=}')
            logging.info(f'{dot_func=}, {type(dot_func)}')
            # build an option list to pass to function:
            # pass dot_func so the called function has a clue if dot_range is correct
            dot_args = {'dot_func': dot_func}
            # pass buffer so called functions requiring a buffer object have it:
            dot_args.update({'buffer': buffer})

            # just bare command:
            if argc == 1:
                # let parse_line_range apply default line range:
                start, end = parse_line_range(dot_cmd)
            # range supplied:
            if argc > 1 and dot_range:
                # set appropriate line range based on dot cmd defaults:
                start, end = parse_line_range(dot_cmd, args[1])
            dot_args.update({'line_range': [start, end]})

            # additional parameters supplied:
            if argc > 2:
                dot_args.update({'params': args[2:]})
            for k, v in dot_args.items():
                logging.info(f'{k}: {v}')

            if callable(dot_func):
                """
                print command text:
                -> if 'immediate' in dot_flag: hitting CR is not necessary. Call function
                       immediately
                   Examples: # (Scale), H (Help), Q (Query)
                -> if dot_range is True: print additional space after dot_text.
                   Examples: L (List), R (Read)
                """
                output = dot_cmd.dot_text
                if 'immediate' in dot_flag:
                    # this is concatenated to for correct Backspace count if
                    # command get canceled
                    output += "\n"
                if dot_range is not None:
                    output += " "

                print(output, end='', flush=True)
                # FIXME: for backspacing over cancelled command later
                if dot_range:
                    # line_range_len = len(args[2])
                    pass
                # wait for Return/Backspace unless dot_params contains 'immediate'
                """
                if 'immediate' not in dot_flag:
                    char, asc = editor.functions.get_character()
                    if char == keymap.keybinding(user_keymap, "delete_char_left"):
                        # cancel command:
                        # out_backspace(len(dot_text + line_range_len))
                """
                if 'immediate' in dot_flag:
                    # no parameters needed
                    dot_args = {}
                result = dot_func(**dot_args)
                if result:
                    print(f'{result=}')
        else:
            print(f"Unrecognized dot command '.{dot_cmd_letter}'.")
            # print(out_backspace(len(COMMAND_PROMPT))


def parse_line_range(dot_cmd: DotCommand, line_range: str = "-") -> list[int | None, int | None]:
    """
    parse line range string in the form of:

    x   line x

    x-  line x to the end of the buffer

    x-y line x to line y

    -y line 1 to line y

    :param dot_cmd: command being ultimately called; this is needed to
     inspect the function's dot_range and dot_range_defaults
    Whether the command needs zero, one or two parameters is governed by
    'dot_cmd.dot_range':

    :param line_range: a string governing which ranges the command accepts
    'single':   x

    'all':      x, x-, x-y, -y accepted

    None:       No range needed

    When no range is entered, the defaults depend on the dot command's
    'dot_cmd.dot_range_default':

    'all':      all lines in buffer
    'first':    first line entered
    'last':     last line entered

    :returns:
    list[x, x]: just line x
    list[x, y]: lines x - y
    list[1, y]: lines start of buffer - y
    list[x, editor.max_lines]: lines x - end of buffer
    None: no line range entered. if default_last is in dot_params, set current_line to Editor.last_line
    >>> test_buffer = Buffer(max_lines = 5)

    >>> test_buffer.test_fill_buffer()

    >>> kwargs = {'buffer': 'test_buffer', 'line_range': "1-5"}

    # should list lines 1-5
    >>> cmd_list(**kwargs)
    1:
    line 1
    2:
    line 2
    3:
    line 3
    4:
    line 4
    5:
    line 5

    >>> test_dot_cmd = DOT_CMD_TABLE["l"]

    >>> print(test_dot_cmd)

    >>> test_dot_cmd.dot_range
    'all'

    # test passing a start-end line range to command
    >>> parse_line_range(test_dot_cmd, line_range="3-5")
    [3, 5]
    """
    log_function = "parse_line_range:"
    # TODO: (maybe) prompt if range_string is missing?
    dot_range = dot_cmd.dot_range
    dot_range_default = dot_cmd.dot_range_default
    """
    if expert_mode is False:
        while True:
            start = input("First line: ")
            end = input("Last line: ")
    ...etc...
    """
    logging.info(f'{log_function} enter: {dot_range=}')
    # determine the value(s) which calling function needs:
    start, end = line_range.split("-")
    # range starts out as string:
    logging.info(f'{log_function} line_range enter: {start=} {end=}')

    # ensure both start/end (if present) are ints
    if start.isalpha() or end.isalpha():
        # line ranges are ints, not chars
        logging.info(f"{log_function} found alpha chars in range")
        # TODO: define this as an error condition
        return [0, 0]

    # convert '' to None:
    debug_null = False
    if start == '':
        start = None
        debug_null = True
    if end == '':
        end = None
        debug_null = True
    if debug_null:
        logging.info(f"{log_function} Null converted to None")

    """
    # start out with null strings, convert to None later if missing:
    if len(line_range) == 1:
        # only one parameter entered:
        start = line_range[0]
    if len(line_range) == 2:
        # two parameters entered:
        # ['', <int>]:
        if line_range[0] == '':
            end = line_range[1]
        # [<int>, '']:
        if line_range[1] == '':
            start = line_range[0]
    """
    """
    if dot_range == 'single':
        # start
        end = start
    if dot_range == "all":
        # start, start-, start-end, -end
        if start != '':
            start = int(start)
        if end != '':
            end = int(end)
    """
    # TODO: normalize 1 <= start <= Editor.max_lines, start <= end <= Editor.max_lines

    # supply missing values if start / end not specified:
    # e.g., '1-', '-10'
    if start is None:
        if dot_range_default == 'all':
            start = 1
        if dot_range_default == 'first':
            start = 1
        if dot_range_default == 'last':
            start = buffer.max_lines
    if end is None:
        if dot_range_default == 'all':
            end = buffer.max_lines
        if dot_range_default == 'first':
            end = 1
        if dot_range_default == 'last':
            end = buffer.max_lines

    if dot_range == 'single':
        if start == '':
            if dot_range_default == "first":
                start, end = 1, 1
            if dot_range_default == "last":
                start = editor.max_lines
                end = start
    if dot_range == 'all':
        if start == '' and end != '':
            start = 1
            end = editor.max_lines

    # a quick & dirty cast: start / end could be None
    if type(start) == 'str':
        logging.info(f'{log_function} start: str cast to int')
        start = int(start)
    if type(end) == 'str':
        logging.info(f'{log_function} end: str cast to int')
        end = int(end)

    # FIXME: ".l 4" raises ValueError: not enough values to unpack (expected 2, got 1)
    # exit:
    logging.info(f'{log_function} line range at exit: {start=} {end=}')
    return [start, end]


def cmd_abort(**kwargs):
    # response = editor.functions.yes_or_no(default=False)
    # if response:
    #     editor.mode["editing"] = False
    print("Reached .Abort -- kwargs:")
    for k, v in kwargs.items():
        print(f'{k=} {v=}')


def cmd_columns(**kwargs):
    if 'line_range' not in kwargs:
        print(f"Column width is set to {editor.column_width}.")
    if 'line_range' in kwargs:
        # get first value of tuple:
        width = kwargs['line_range'][0]
        logging.info(f'{width=}')
        print(f"Column width is now changed to {width}.")
        editor.column_width = width
    pass


def cmd_delete(**kwargs):
    if 'line_range' not in kwargs:
        print(f"Deleting line {buffer.line[buffer.current_line]}.")
    else:
        start, end = kwargs['line_range'][0], kwargs['line_range'][1]
        print(f"Deleting lines {start}-{end}.")
        # TODO: Buffer.put_in_undo(line_range) or something
        # undo_buffer.line = [for x in ]


def cmd_edit(**kwargs):
    """
    Edit a single line or range of lines.
    When no line range is specified, edit the last line in buffer.
    """
    pass


def cmd_find(**kwargs):
    """
    Find text in a single line or range of lines.
    When no line range is specified, default to all text in buffer.
    """
    pass
    """
    search = input("Find what: ")
    found = False
    for line_num in range(start, end):
        if search in buffer.lines[line_num]:
            found = True
            print(f"{line_num}:")
            # TODO: highlight match
            print(buffer.lines[line_num])
    if found is False:
        print(f"No match for '{search}' was found.")
    """


def cmd_help(**kwargs):
    """.h or .?"""
    """
    TODO: Enhancement: type [.h] <dot_key> for help on topic <dot_key>,
    instead of [.h] displaying a huge file on all commands.
    """
    print("Help:\n")
    for cmd_letter in DOT_CMD_TABLE:
        # e.g., DOT_CMD_TABLE['a'].dot_flag
        # display dot command letter, command name:
        print(f'.{cmd_letter}: {DOT_CMD_TABLE[cmd_letter].dot_text}')


def cmd_insert(**kwargs):
    """.I Insert <starting_line>
    Turns on Insert mode and Line Numbering mode for the duration of
    inserting lines.

    [.I]nsert At: [4]
    User is prompted:
    I4:
    [The quick brown fox jumped over the lazy dog.]
    I5:
    [The same.]

    User ends Insert mode by typing:
    [.]Command: Exit
    """
    # TODO: normalize line range: check if 1 > start > editor.max_lines
    pass


def cmd_replace(**kwargs):
    """.K Find and Replace <line_range>"""
    print("TODO: Find what: ")
    print("TODO: Replace with: ")


def cmd_list(**kwargs):
    """
    .L List <line_range>
    List a single line or range of lines.
    Line numbers are printed regardless of editor.mode["line_numbers"] status.

    Example:
    1:
    This is line 1
    2:
    This is line 2
    3:
    This is line 3

    When no line range is specified, list all lines in buffer.

    TODO: save line numbering status, enable line numbers,
        show_raw_lines(line_range), restore line numbering status
    """
    """
    :param kwargs['buffer']: buffer object to work with
    :param kwargs['line_range']: [start, end]: line range
    """
    start, end = int(kwargs["line_range"][0]), int(kwargs["line_range"][1])
    log_function = "cmd_list:"
    logging.info(f"{log_function} {start=} {end=}")
    buffer = kwargs['buffer']
    # can't use enumerate() here; it has a 'start=' param, but no 'end=' param
    for line_num in range(start, end + 1):
        print(f"{line_num}:\n{buffer.line[line_num]}")
        line_num += 1


def cmd_new(**kwargs):
    """
    response = editor.functions.yes_or_no(prompt="Erase buffer?", default=False)
    response = input("Clear buffer?")
    if response is True:
        # TODO: swap buffer with undo buffer
        # print("You can restore the text by selecting .Undo.")
        # editor.buffer = ['']
        buffer.lines = 0
    """
    print("Erased text.")


def cmd_line_nums(**kwargs):
    """.O Toggle displaying line numbers on or off"""
    line_numbering = editor.mode["line_numbers"]
    print(f"Line numbering is now {'on' if line_numbering is True else 'off'}.")


def cmd_query(**kwargs):
    """.Q Query buffer contents"""
    # in_mem = buffer.last_line()
    # editor.show_available_lines(buffer=buffer)
    pass


def cmd_read(**kwargs):
    """.R <[x-y]> Read text"""
    pass


def cmd_save(**kwargs):
    """.S Save Text"""
    # TODO: what if file exists:
    # [A]ppend, [R]eplace, [N]ew Name, [R]eturn to Editor
    pass


def cmd_undo(**kwargs):
    """.U Undo Edit"""
    pass


def cmd_version(**kwargs):
    """.V Version"""
    print("Editor version 2023-06-05")


def cmd_word_wrap(**kwargs):
    """.W Word-wrap text"""
    pass


def cmd_scale(**kwargs):
    """
    .# Scale
    Display a ruler with numbered screen columns to assist with, among
    other things, aligning text at a certain column
    """
    # TODO: expand the printed output to match Editor.max_line_length
    print(f"{1:10}{2:10}{3:10}{4:10}")
    print("1234567890" * 4)


if __name__ == '__main__':
    # init logging:
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    # test stuff:
    # instantiate Buffer first since Editor needs Buffer object:
    buffer = Buffer(max_lines=20)  # max_lines = (int)
    buffer.test_fill_buffer()

    editor = Editor(max_line_length=80, buffer=buffer)
    editor.column_width = 40
    # force buffer text to be listed:
    kwargs = {"line_range": (1, buffer.max_lines), "buffer": buffer}
    cmd_list(**kwargs)

    # {"dot_key": ("dot_text", dot_func, ["dot_flag", ...], dot_range,
    #  dot_range_default)}:
    DOT_CMD_TABLE = {"a": DotCommand(dot_text="Abort",
                                     dot_func=cmd_abort,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "c": DotCommand(dot_text="Columns",
                                     dot_func=cmd_columns,
                                     dot_flag=[],
                                     dot_range="single",
                                     dot_range_default=None),
                     "d": DotCommand(dot_text="Delete",
                                     dot_func=cmd_delete,
                                     dot_flag=[],
                                     dot_range="all",
                                     dot_range_default="last"),
                     "e": DotCommand(dot_text="Edit",
                                     dot_func=cmd_edit,
                                     dot_flag=["subcmd"],
                                     dot_range="all",
                                     dot_range_default="last"),
                     "f": DotCommand(dot_text="Find",
                                     dot_func=cmd_find,
                                     dot_flag=[],
                                     dot_range="all",
                                     dot_range_default="all"),
                     "h": DotCommand(dot_text="Help",
                                     dot_func=cmd_help,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "i": DotCommand(dot_text="Insert",
                                     dot_func=cmd_insert,
                                     dot_flag=["dot_exits"],
                                     dot_range="single",
                                     dot_range_default="first"),
                     # TODO: Justify: could use textwrap module
                     """
                     "j": DotCommand(dot_text="Justify",
                                     dot_func=cmd_justify,
                                     dot_flag=["subcmd"],
                                     dot_range="all",
                                     dot_range_default="last"),
                     """
                     "k": DotCommand(dot_text="Find and Replace",
                                     dot_func=cmd_replace,
                                     dot_flag=[],
                                     dot_range="all",
                                     dot_range_default="all"),
                     "l": DotCommand(dot_text="List",
                                     dot_func=cmd_list,
                                     dot_range="all",
                                     dot_flag=[],
                                     dot_range_default="all"),
                     "n": DotCommand(dot_text="New Text",
                                     dot_func=cmd_new,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "o": DotCommand(dot_text="Line Numbering",
                                     dot_func=cmd_line_nums,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "q": DotCommand(dot_text="Query",
                                     dot_func=cmd_query,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "r": DotCommand(dot_text="Read",
                                     dot_func=cmd_read,
                                     dot_flag=[],
                                     dot_range="all",
                                     dot_range_default="all"),
                     "s": DotCommand(dot_text="Save",
                                     dot_func=cmd_save,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default="last"),
                     "u": DotCommand(dot_text="Undo",
                                     dot_func=cmd_undo,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default="last"),
                     "v": DotCommand(dot_text="Version",
                                     dot_func=cmd_version,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "w": DotCommand(dot_text="Word-Wrap",
                                     dot_func=cmd_word_wrap,
                                     dot_flag=[],
                                     dot_range="all",
                                     dot_range_default=None),
                     "#": DotCommand(dot_text="Scale",
                                     dot_func=cmd_scale,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None)}

    while True:
        input_line = input(": ")
        if input_line.startswith(".") or input_line.startswith('/'):
            parse_dot_command(input_line=input_line)
