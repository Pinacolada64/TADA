# from dataclasses import dataclass
from typing import NamedTuple, Callable, Any
from dataclasses import dataclass


# text editor module imports:
# import text_editor.text_editor
# from text_editor.text_editor import Buffer
# from text_editor.text_editor import Editor as editor


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
            # range supplied:
            if argc >= 1 and dot_range:
                # set appropriate line range based on dot cmd defaults:
                # FIXME: crash with zero arguments
                start, end = parse_line_range(dot_cmd, args[1])
                dot_args.update({'range': (start, end)})
            # additional parameters supplied:
            if argc >= 2:
                dot_args.update({'params': args[2:]})
            for k, v in dot_args.items():
                logging.info(f'{k}: {v}')

            if callable(dot_func):
                """
                print command text:
                -> if 'immediate' in dot_params: hitting CR is not necessary. Call function
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
                # line_range_len = len(args[2])
                if dot_range:
                    _, end = parse_line_range(dot_func, args[1])

                # wait for Return/Backspace unless dot_params contains 'immediate'
                if 'immediate' not in dot_flag:
                    """
                    char, asc = editor.functions.get_character()
                    if char == keymap.keybinding(user_keymap, "delete_char_left"):
                        # cancel command:
                        # out_backspace(len(dot_text + line_range_len))
                    """
                    pass
                result = dot_func(**dot_args)
                if result:
                    print(f'{result=}')
        else:
            print(f"Unrecognized dot command '.{dot_cmd_letter}'.")
            # print(out_backspace(len(COMMAND_PROMPT))


def parse_line_range(dot_func: DotCommand, line_range: str):
    """
    parse line range string in the form of:
    x   line x
    x-  line x to the end of the buffer
    x-y line x to line y
    -y line 1 to line y

    Whether the command needs all these ranges is governed by
    'dot_cmd.dot_range':

    'single':   x
    'all':      x, x-, x-y, -y accepted
    None:       No range needed

    When no range is entered, the defaults depend on the dot command's
    'dot_cmd.dot_range_default':

    'all':      all lines in buffer
    'first':    first line entered,
    'last':     last line entered

    :param line_range:
    :param dot_func: function being ultimately called; this is needed to
     inspect the function's dot_range and dot_range_defaults
    :returns:
    tuple(x): just line x
    tuple(x, y): lines x - y
    tuple(0, y): lines start of buffer - y
    tuple(x, 0): lines x - end of buffer
    None: no line range entered. if default_last is in dot_params, set current_line to Editor.last_line
    """
    log_function = "parse_line_range:"
    # TODO: (maybe) prompt if range_string is missing?
    """
    if expert_mode is False:
        while True:
            start = input("First line: ")
            end = input("Last line: ")
    ...etc...
    """
    # range starts out as string:
    start, end = line_range.split("-")
    # ensure both start/end (if present) are ints
    if start.isalpha() or end.isalpha():
        # line ranges are ints, not chars
        logging.info(f"{log_function} found alpha chars in range")
        return None
    # convert '' to None:
    if start == '':
        start = None
    if end == '':
        end = None
    logging.info(f'{log_function} {start=} {end=}')

    # TODO: normalize 1 <= start <= Editor.max_lines, start <= end <= Editor.max_lines

    # set range defaults if start / end not specified:
    # e.g., '1-', '-10'
    if start == '':
        if dot_func.dot_range_default == 'all':
            start = 1
        if dot_func.dot_range_default == 'first':
            start = 1
        if dot_func.dot_range_default == 'last':
            start = buffer.max_lines

    if end == '':
        if dot_func.dot_range_default == 'all':
            end = buffer.max_lines
        if dot_func.dot_range_default == 'first':
            end = 1
        if dot_func.dot_range_default == 'last':
            end = buffer.max_lines

    #
    if dot_func.dot_range == 'single':
        if start == '':
            start = 1
            end = None
    if dot_func.dot_range == 'all':
        if start == '' and end != '':
            start = 1
            end = buffer.max_lines

    return start, end


def cmd_abort(**kwargs):
    # response = editor.functions.yes_or_no(default=False)
    # if response:
    #     editor.mode["editing"] = False
    print("Reached .Abort -- kwargs:")
    for k, v in enumerate(kwargs):
        print(f'{k=} {v=}')


def cmd_columns(**kwargs):
    if kwargs['line_range'] is None:
        print("Columns set to {editor.column_width}.")
    pass


def cmd_delete(**kwargs):
    if kwargs['line_range'] is None:
        print("Deleting line {self.buffer.line}.")
        # TODO: Buffer.put_in_undo(line_range) or something
        # work_buffer = ['']


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

    start, end = line_range[0], line_range[1]
    # start += 1
    # end += 1
    line_num = start
    # can't use enumerate() here; it has a 'start=' param, but no 'end=' param
    for line in range(start, end):
        print(f"{line_num}:\n{line}")
        line_num += 1
    """


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
    # line_numbering = editor.mode["line_numbers"]
    line_numbering = not line_numbering
    # editor.mode = {"line_numbers": line_numbering}
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
    print("Editor version 2023-05-20")


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
    # editor = text_editor.text_editor.Editor

    # test instantiating a dot command:
    """
    yada_yada = DotCommand(dot_text="Abort",
                           dot_func=cmd_abort,
                           dot_flag="immediate",
                           dot_range=None,
                           dot_range_default="all")
    print(yada_yada)
    """

    # {"dot_key": ("dot_text", dot_func, ["dot_flag", ...], dot_range)}:
    DOT_CMD_TABLE = {"a": DotCommand(dot_text="Abort",
                                     dot_func=cmd_abort,
                                     dot_flag="immediate",
                                     dot_range=None,
                                     dot_range_default=None),
                     "c": DotCommand(dot_text="Columns",
                                     dot_func=cmd_columns,
                                     dot_flag=None,
                                     dot_range=None,
                                     dot_range_default=None),
                     "d": DotCommand(dot_text="Delete",
                                     dot_func=cmd_delete,
                                     dot_flag=None,
                                     dot_range="all",
                                     dot_range_default="last"),
                     "e": DotCommand(dot_text="Edit",
                                     dot_func=cmd_edit,
                                     dot_flag=["subcmd"],
                                     dot_range="first-last",
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
                                     dot_flag=[],
                                     dot_range="single",
                                     dot_range_default="last"),
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
                                     dot_flag=["all"],
                                     dot_range_default="last"),
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
