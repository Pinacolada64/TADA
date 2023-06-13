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
                start, end = parse_line_range(dot_cmd=dot_cmd, buffer=buffer)
            # range supplied:
            if argc > 1 and dot_range:
                # set appropriate line range based on dot cmd defaults:
                start, end = parse_line_range(dot_cmd=dot_cmd, buffer=buffer, line_range=args[1])
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

                # TODO: 'end=' will change when getch() is possible:
                print(output, end='\n', flush=True)
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


def parse_line_range(dot_cmd: DotCommand, buffer: Buffer, line_range: str = "-") -> list[int | None, int | None]:
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

    :param buffer: buffer object (needs to know how many lines in it)

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

    # first, create an empty buffer to work with:
    >>> buffer = Buffer(max_lines = 5)

    # fill it with test text:
    >>> buffer.test_fill_buffer()

    # set some info up:
    >>> kwargs = {'buffer': buffer, 'line_range': [1, 5]}

    # should list lines 1-5
    >>> cmd_list(**kwargs)
    1:
    test 1
    2:
    test 2
    3:
    test 3
    4:
    test 4
    5:
    test 5

    # make a new test dot command - all we're interested in is testing various
    # line ranges, both legal and illegal:
    >>> cmd_test = DotCommand(dot_text="Test", dot_func=cmd_list, dot_flag=[],
    ...                       dot_range='all', dot_range_default='all')

    >>> cmd_test.dot_range
    'all'

    # test passing various line ranges to test command:
    >>> for test in ('', '3', '-3', '3-5', '2-'):
    ...     parse_line_range(dot_cmd=cmd_test, buffer=buffer, line_range=test)
    [1, 5]
    [3, 3]
    [1, 3]
    [3, 5]
    [2, 5]
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

    # only one parameter entered: end should equal start:
    if "-" not in line_range:
        # only one parameter entered: end should equal start:
        logging.info(f"{log_function} only one line, {line_range=}")
        line_range = line_range + "-" + line_range
        logging.info(f"{log_function} {line_range=}, end changed to match")

    # ensure both start/end (if present) are ints
    if line_range.isalpha():
        # line ranges are ints, not chars
        logging.error(f"{log_function} found alpha chars in range")
        # TODO: define this as an error condition
        # raise ValueError
        return [0, 0]

    # range starts out as string:
    start, end = line_range.split("-")
    logging.info(f'{log_function} line range enter: {start=} {end=}')

    # missing param will be '', so convert to 0
    if start == '':
        start = 0
    if end == '':
        end = 0

    # convert strings to ints (no effect if already int):
    start = int(start)
    end = int(end)

    # supply missing values if start / end not specified:
    # e.g., '1-', '-10'
    if start == 0:
        if dot_range_default == 'all':
            start = 1
        if dot_range_default == 'first':
            start = 1
        if dot_range_default == 'last':
            start = buffer.max_lines
    if end == 0:
        if dot_range_default == 'all':
            end = buffer.max_lines
        if dot_range_default == 'first':
            end = 1
        if dot_range_default == 'last':
            end = buffer.max_lines

    # normalize values:
    if start < 1:
        start = 1
        logging.warning(f"{log_function} 'start' < 1, now {start=}")
    if start > buffer.max_lines:
        start = buffer.max_lines
        logging.warning(f"{log_function} 'start' > buffer.max_lines, now {start=}")

    if end > buffer.max_lines:
        end = buffer.max_lines
        logging.warning(f"{log_function} 'end' > buffer.max_lines, now {end=}")

    if end < start:
        end = start
        logging.warning(f"{log_function} 'end' < 'start', now {start=}")
    if start > end:
        start = end
        logging.warning(f"{log_function} 'start' > 'end', now {start=}")

    if dot_range == 'single':
        if start == 0:
            if dot_range_default == "first":
                start, end = 1, 1
            if dot_range_default == "last":
                start = buffer.max_lines
                end = start
            logging.info(f"{log_function} 'single' range: adjusting to {start=}, {end=}")

    if dot_range == 'all':
        if start == 0 and end != 0:
            start = 1
            end = buffer.max_lines
            logging.info(f"{log_function} 'all' range: adjusting to {start=}, {end=}")

    # exit:
    logging.info(f'{log_function} line range exit: {start=} {end=}')
    return [start, end]


def cmd_abort(**kwargs):
    """
    Ask whether you want to abandon editing text in the buffer.

      * If [Y]es is selected, the editor is exited and any unsaved changes
        are lost.

      * If [N]o is selected, you are returned to the editor to continue
        editing text.
    """
    import functions
    response = functions.yes_or_no(prompt="Exit editor: Are you sure?",
                                   default=False)
    if response is True:
        print("Quitting.")
        editor.mode["running"] = False
    else:
        print("Aborted.")


def cmd_columns(**kwargs):
    """
    This is used to adjust the length of lines you type in the editor before
    word-wrap creates a new line.
    The editor's column width is independent of your terminal's line length.
    The column width can be set shorter than or equal to the line length,
    but not larger than the line length.
    For example, if your terminal's line length is 80 characters, but you set
    your column width to 40 characters, you can't type more than 40 characters
    before word-wrap takes effect.
      Examples:
        * Typing [.C] reports your current column width.
        * Typing [.C 80] sets your column width to 80 characters.
    """
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
    """
    Delete a line (or range of lines).

    If a line range is not given, the last line entered is deleted.
    """
    if 'line_range' not in kwargs:
        print(f"Deleting line {buffer.line[buffer.current_line]}.")
    else:
        start, end = kwargs['line_range'][0], kwargs['line_range'][1]
        print(f"Deleting lines {start}-{end}.")
        # TODO: Buffer.put_in_undo(line_range) or something
        # undo_buffer.line = [for x in ]


def cmd_edit(**kwargs):
    """
        Edit a single line (or range of lines).

        Pressing [Enter] by itself on a line during editing leaves that line
    unchanged.

        If a line range is given, typing [.] by itself on a line ends editing
    early.

        When no line range is specified, edit the last line in buffer.
    """
    start, end = kwargs["line_range"][0], kwargs["line_range"][1]
    log_function = "cmd_edit:"
    buffer = kwargs['buffer']

    print(". ends editing early.")
    print("Enter by itself leaves line unchanged.")

    for line_num in range(start, end + 1):
        print(f"{line_num}:")
        print(buffer.line[line_num])
        edit = input("> ")
        if edit == '':
            print("(Line unchanged.)")
        if edit == ".":
            print("(Editing ended.)")
            break
        else:
            buffer.line[line_num] = edit


def cmd_find(**kwargs):
    """
    Find text in a single line (or range of lines).
    When no line range is specified, search through all text in buffer.
    """
    start, end = kwargs["line_range"][0], kwargs["line_range"][1]
    log_function = "cmd_find:"
    buffer = kwargs['buffer']

    search = input("Find what: ")
    if search == '':
        print("Aborted.")
        return

    found = False
    count = 0
    for line_num in range(start, end + 1):
        if search in buffer.line[line_num]:
            found = True
            count += 1
            print(f"{line_num}:")
            # TODO: highlight match
            print(buffer.line[line_num])
    if found is False:
        print(f"No match for '{search}' was found.")
    else:
        print(f"'{search}' was found {count} time"
              f"{'s' if count != 1 else ''}.")


def cmd_help(**kwargs):
    """View help for all dot commands"""
    # TODO: Enhancement: type [.h] <dot_key> for help on topic <dot_key>,
    #     instead of [.h] displaying a huge file on all commands.
    help_text = []
    for cmd_letter in DOT_CMD_TABLE:
        # e.g., DOT_CMD_TABLE['a'].dot_flag
        # display dot command letter, command name:
        command = DOT_CMD_TABLE[cmd_letter]
        help_text.append(f'.{cmd_letter}: {command.dot_text}')
        # type 'str':
        docstring = command.dot_func.__doc__
        if docstring is None:
            help_text.append(f"(No documentation for '{command.dot_text}'.)")
        else:
            for line_num, text in enumerate(docstring.split('\n')):
                """
                Word-wrap string to Player.client['cols'] width.
                If a line break in the string is needed, make two separate calls to output(), one per line.
                Ending a string with a CR or specifying CR in the join() call won't do what you want.

                :param lines: list of strings to output
                :param bracket_coloring: if False, do not recolor text within brackets
                 (e.g., set to False when drawing bar so as to not color '[] ... []' table graphics)
                 :return Message: list
                """
                help_text.append(text)
    page_text(format_text(input_list=help_text, bracket_coloring=True, text_wrap=False))


def format_text(input_list: list, bracket_coloring: bool, text_wrap=False) -> list:
    from colorama import Fore as foreground
    import re
    import textwrap
    function_name = "format_text:"
    # rip-off of tada_utilities.output() except for socket stuff:
    logging.info(f"{function_name} entry:")
    if text_wrap:
        # FIXME: wrapping text makes each line into a list element
        #  so displays e.g., ['Text'] later
        """
        we want to wrap the un-substituted text first. substituting ANSI
        color codes adds 5-6 characters per substitution, and that wraps
        text in the wrong places.
        """
        wrapped_text = []
        for line_num, text in enumerate(input_list):
            # wrapped_text.append(textwrap.wrap(text, width=conn.client['cols']))
            wrapped_text.append(textwrap.wrap(text, width=editor.max_line_length))
            print(f'{line_num:3} {wrapped_text[line_num]}')
        input_list = wrapped_text
    """
    color text inside brackets using 're' and 'colorama' modules:
    '.+?' is a non-greedy match (finds multiple matches, not just '[World ... a]')

    # demonstrate replacing '[' and ']' with '!':
    >>> re.sub(r'[(.+?)]', r'!\1!', string="Hello [World] this [is a] test.")
    'Hello !World! this !is a! test.'
    """
    if bracket_coloring:  # ... and player.client['translation'] != "ASCII":
        colored_text = []
        for idx, txt in enumerate(input_list):
            if txt != '':
                # <class 'str'>
                # print(txt, type(txt))
                regex = re.sub(pattern=r"\[(.+)]",
                               repl=f'{foreground.RED}' + r'\1' + f'{foreground.RESET}',
                               string=f"{txt}")
                colored_text.append(regex)
            else:
                # txt is '', apparently regex doesn't like that:
                colored_text.append(txt)
        # logging.info(f'{idx:3} | {temp}')
        input_list = colored_text
    # for ASCII clients, or bracketed_text is False, don't color bracketed text:
    return input_list


def page_text(help_text: list) -> None:
    if len(help_text) == 0:
        print("No help text to display.")
        return
    else:
        total_lines = len(help_text)
        line_count = 0
        window_top = 1
        window_height = 24
        # if line_count % 25 == 0:
        while True:
            for page in range(window_top, window_top + window_height):
                print(help_text[page])
            _ = input("[Return]: next page, [-] last page, [A]: abort: ").lower()
            if _ == "a":
                print(f"Read {line_count} lines. Aborted.")
                break
            if _ == "" and window_top < total_lines:
                window_top += window_height
                # FIXME: stop early instead of "index out of range" error
                if window_top > total_lines:
                    window_top += window_height - total_lines
                line_count += 24
            if _ == "-" and window_top > 24:
                window_top -= 24
                if window_top < 1:
                    window_top = 1


def cmd_insert(**kwargs):
    """Insert <starting_line>
    Turns on Insert mode and Line Numbering mode for the duration of
    inserting lines.

    Example:
        [.I]nsert At: [4]

    User is prompted:
        I4:
        [The quick brown fox jumped over the lazy dog.]
        I5:
        [The same.]

    User ends Insert mode by typing:
        [.]Command: Exit
    """
    pass


def cmd_replace(**kwargs):
    """Find text and replace with different text."""
    print("TODO: Find what: ")
    print("TODO: Replace with: ")


def cmd_list(**kwargs):
    """
    List a single line (or range of lines).
    Line numbers are printed regardless of editor.mode["line_numbers"] status.

    Example:

        [.L 1-3]
        1:
        This is line 1
        2:
        This is line 2
        3:
        This is line 3

    When no line range is specified, list all lines in buffer.

    """
    """
    :param kwargs['buffer']: buffer object to work with
    :param kwargs['line_range']: [start, end]: line range

    TODO: save line numbering status, enable line numbers,
        show_raw_lines(line_range), restore line numbering status
    editor.mode["line_numbering"]
    """
    start, end = kwargs["line_range"][0], kwargs["line_range"][1]
    log_function = "cmd_list:"
    logging.info(f"{log_function} {start=} {end=}")
    buffer = kwargs['buffer']
    # can't use enumerate() here; it has a 'start=' param, but no 'end=' param
    for line_num in range(start, end + 1):
        print(f"{line_num}:\n{buffer.line[line_num]}")
        line_num += 1


def cmd_new(**kwargs):
    """
    Be prompted to erase text in buffer. If you reply with Yes, text is erased.
    """
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
    """
    Toggle displaying line numbers as you enter new lines on or off.
    """
    line_numbering = editor.mode["line_numbers"]
    print(f"Line numbering is now {'on' if line_numbering is True else 'off'}.")


def cmd_query(**kwargs):
    """
    Query buffer contents. This shows how many lines you have available to
    type in, how many are full, and how many remain empty.
    """
    # in_mem = buffer.last_line()
    # editor.show_available_lines(buffer=buffer)
    pass


def cmd_read(**kwargs):
    """
    Read text in buffer. This shows text without line numbers.
    """
    start, end = kwargs["line_range"][0], kwargs["line_range"][1]
    log_function = "cmd_read:"
    logging.info(f"{log_function} {start=} {end=}")
    buffer = kwargs['buffer']
    # can't use enumerate() here; it has a 'start=' param, but no 'end=' param
    for line_num in range(start, end + 1):
        print(f"{buffer.line[line_num]}")
        line_num += 1


def cmd_save(**kwargs):
    """
    Save text in buffer.
    """
    # TODO: what if file exists:
    # [A]ppend, [R]eplace, [N]ew Name, [R]eturn to Editor
    pass


def cmd_undo(**kwargs):
    """
    Undo an edit that has been made. This includes...
    """
    pass


def cmd_version(**kwargs):
    """
    Show the editor version information.
    """
    print("Editor version: 2023-06-05")


def cmd_word_wrap(**kwargs):
    """
    Word-wrap text
    """
    pass


def cmd_scale(**kwargs):
    """
    Display a ruler with numbered screen columns to assist with, among
    other things, aligning text at a certain column.
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

    # instantiate editor and set some parameters:
    editor = Editor(max_line_length=80, buffer=buffer)
    editor.mode["running"] = True
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

    while editor.mode["running"]:
        input_line = input(": ")
        if input_line.startswith(".") or input_line.startswith('/'):
            parse_dot_command(input_line=input_line)
