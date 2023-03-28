import re

try:
    import getch
except ImportError as e:
    print(f"Can't import getch: {e}.")
import re
import logging

class Buffer:
    def __init__(self, max_lines):
        """
        Buffer object which holds up to <max_lines> of <line> text
        :param max_lines: how many lines of text can be entered
        :param buffer: a list of empty elements, representing an empty buffer
        """
        self.max_lines = max_lines
        # lines in buffer: 0
        self.lines = 0
        # start with empty buffer, but 1-indexed:
        self.buffer = ['' for x in range(0, max_lines + 1)]
        self.current_line = 1

    def get_last_line(self, buffer) -> int:
        """
        Enumerate backwards through buffer.lines[] looking for the first non-
        empty list item. This is considered the highest line number in the text
        buffer, printed during .Query, and considered the highest possible
        <end> value in a line range expression.

        Enumerating forwards through buffer.lines[] stops at the first blank line.

        :return: last_line
        """
        count = 0  #
        last_line = editor.max_lines  # start from the last line
        """
        >>> [x for x in range(10, 0, -1)]
        [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        """
        for line in range(editor.max_lines, 0, -1):
            if buffer.lines[line] == '':
                last_line = line
        return last_line

    def insert_lines(self, buffer: Buffer, start, end: int):
        """
        Instantiate a separate buffer for entering the inserted text into.
        After the text is entered, somehow weave the buffers together
        properly.

        :param start:
        :return:
        """
        """
        :param max_lines: editor.max_lines - (last_line + 1) I think
        TODO: check if any lines left; if not: "Buffer full." message 
        """
        lines_remaining = editor.max_lines - buffer.get_last_line() + 1
        logging.debug(f'{lines_remaining=}')
        if max_lines <= 0:
            raise MemoryError  # i guess :)
        """
        Line 1
        Line 2
        Line 3
        Line 4
        [.I]nsert [4]
        I4:
        The quick brown fox jumped over the lazy dog.
        [.I]nsert mode off.
        [.L]ist
        1:
        Line 1
        2:
        Line 2
        3:
        Line 3
        4:
        The quick brown fox jumped over the lazy dog.
        5:
        Line 4
                
        Turns on Insert mode and Line Numbering mode for the duration of
        inserting lines.
        
        :param start: line # to start inserting at
        :return: new List
        """
        insert_buffer = Buffer(max_lines=editor.max_lines, lines=[])

        # TODO: put lines in the right place.
        buffer.insert(insert_buffer)

    def put_in_undo(self, line_range):
        if line_range is None:
            undo_buffer = work_buffer


class DotCommand:
    def parse_dot_command(self, char: str):
        """
        Dot commands are called such since they traditionally begin with typing
        "." in column zero. Later revisions of the BBS software added "/" since
        many text editors also used that character, so that is reproduced here.

        :param char: character typed
        :return:
        """
        # char, asc = get_character()
        if char in ("/", "."):
            print(editor_prompt, end="", flush=True)
            key, asc = get_character()
            dot_cmd = key.lower()

        if dot_cmd in dot_cmd_table:
            dot_key, dot_text, dot_function, dot_params, dot_range = dot_cmd_table[dot_cmd]
            # print command text:
            # -> if 'immediate' in dot_params: hitting CR is not necessary. Call function
            #        immediately
            #    Examples: # (Scale), H (Help), Q (Query)
            # -> if accept_ranges is True: print additional space after dot_text.
            #    Examples: L (List), R (Read)
            ending = ''
            if 'immediate' in dot_params:
                ending = "\n"
            if 'accept_ranges' in dot_params:
                ending = " "

            print(dot_text, end=f"{ending}", flush=True)
            line_range_len = 0
            if dot_range:
                line_range = get_line_range()

            # wait for Return/Backspace unless dot_params contains 'immediate'
            if 'immediate' not in dot_params:
                char, asc = get_character()
                if char == KEY_BACKSPACE:
                    # cancel command:
                    out_backspace(len(dot_text + line_range_len))
            else:
                pass
                dot_function(line_range=line_range, params=dot_params)

    def cmd_abort(self):
        response = yes_or_no(default=False)
        if response:
            editor.mode["editing"] = False

    def cmd_columns(self, line_range):
        if line_range is None:
            print(f"Columns set to {editor.column_width}.")
        pass

    def cmd_delete(self, line_range):
        if line_range is None:
            print("Deleting line {self.buffer.line}.")
            # TODO: Buffer.put_in_undo(line_range) or something
            # work_buffer = ['']

    def cmd_edit(self, line_range: tuple):
        """
        Edit a single line or range of lines.
        When no line range is specified, edit the last line in buffer.
        """
        pass

    def cmd_find(self, buffer, start, end: int):
        """
        Find text in a single line or range of lines.
        When no line range is specified, default to all text in buffer.
        """
        search = input("Find what: ")
        found = False
        for line_num in range(start, end):
            if search in buffer.lines:
                found = True
                print(f"{line_num}:")
                # TODO: highlight match
                print(buffer.lines[line_num])
        if found is False:
            print(f"No match for '{search}' was found.")

    def cmd_help(self):
        """.h or .?"""
        """TODO: Enhancement: type [.h] <dot_letter> for specific help"""
        pass

    def cmd_insert(self):
        """.i"""
        pass

    def cmd_replace(self):
        """.K"""
        pass

    def cmd_list(self, line_range: tuple):
        """
        List a single line or range of lines.
        Line numbers are printed regardless of editor.mode["line_numbers"].

        Example:
        1:
        This is line 1
        2:
        This is line 2
        3:
        This is line 3

        When no line range is specified, list all lines in buffer.
        """
        start, end = line_range[0], line_range[1]
        # start += 1
        # end += 1
        line_num = start
        for line in range(start, end):
            print(f"{line_num}:\n{line}")
            line_num += 1

    def cmd_new(self, buffer):
        response = yes_or_no(prompt="Erase buffer?", default=False)
        if response is True:
            # TODO: swap buffer with undo buffer
            # print("You can restore the text by selecting .Undo.")
            editor.buffer = ['']
            buffer.lines = 0
            print("Erased text.")

    def cmd_line_nums(self):
        """toggle displaying line numbers on or off"""
        line_numbering = editor.mode["line_numbers"]
        line_numbering = not line_numbering
        Editor.mode = {"line_numbers": line_numbering}
        print(f"Line numbering is now {'on' if line_numbering is True else 'off'}.")

    def cmd_query(self):
        # in_mem = buffer.last_line()
        editor.show_available_lines()

    def cmd_read(self):
        pass

    def cmd_scale(self):
        print(f"{1:10}{2:10}{3:10}{4:10}")
        print("1234567890" * 4)
        # TODO: scale this (hah) to terminal column_width


class Editor:
    def __init__(self, max_line_length, buffer: Buffer):
        # editor modes:
        #              toggled with .O (Line Numbering):
        self.mode = {"show_line_numbers": False,
                     # toggled with .I (Insert Mode)
                     "insert": False}
        self.max_line_length = max_line_length
        # modified with .Columns <value>, this is independent of max_line_length
        # but is set to the same value initially:
        self.column_width = max_line_length
        # how many lines in buffer:
        self.max_lines = buffer.max_lines
        # line number being edited:
        self.current_line = 1
        # position within line:
        self.char_pos = 1
        logging.info(f'Buffer: init {buffer}, {self.max_lines=}, {self.max_line_length=} ')

    def input_line_range(self):
        line_range = input("Line range: ")
        if line_range.lower() == "h" or line_range == "?":
            print("""
x      Just line x
x-     Lines x to the end of the buffer
x-y    Lines x to y
 -y    Lines 1 to y
""")
        # line_range_len = len(line_range)  # FIXME: for backspacing that too, maybe?

    def run(self, buffer: Buffer):
        Editor.show_available_lines(self, buffer=buffer)
        while True:
            get_character()
            if editor.mode["line_numbers"]:
                print(f'{buffer.lin}')



    def show_available_lines(self, buffer):
        # TODO: display this at init, and after .Q Query (.G Get File if ever implemented)
        in_mem = buffer.get_last_line()
        print("Total lines:")
        print(f"Available: {editor.max_lines}")
        print(f"In Memory: {in_mem}")
        print(f"Remaining: {editor.max_lines - in_mem}")

    def edit_existing_line(self, line_num: int, text: str):
        """
        Edit string <line_num>.
        """
        # first, show existing line:
        self.show_line_raw(line_num, text)
        # TODO: Allow Ctrl-key editing.
        pass

    def show_line_raw(self, line_num, text):
        print(line_num)
        print(text)


def get_character():
    """
    Wait for a character to be typed.
    return tuple: 'in_char': character, 'asc': ascii value
    """
    in_char = None
    data = ''
    while in_char is None:
        # getch.getch() does not echo input
        in_char = getch.getch()
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

    # TODO: (maybe)
    # if expert_mode = False:
    # while True:
    #     start = input("First line: ")
    #     end = input("Last line: ")
    # ...etc...

    # print(f'{range_str=} ', end='')
    evaluate = line_range_re.search(range_str)
    # print(f'{evaluate=} ', end='')
    if evaluate:
        # split 'evaluate' into capture groups (returns a tuple)
        result = evaluate.groups()
        logging.info(f"{result=}")
    else:
        # print("<no regex match>")
        result = None
    # TODO: validate start/end are within 1 < Editor.last_line < Editor.max_lines
    return result


def input_line(flags=None):
    """
    flags:
    dot_exits: True: "." or "/" on column 1 exits

    :return None: no line entered, str: line input
    """
    editor.input_line = ''
    while True:
        asc, char = get_character()
        # handle column 0 dot/slash commands:
        if editor.char_pos == 0 and char == "." or char == "/":
            print("Command: ", end='', flush=True)
            if 'dot_exits' in flags:
                print("Exit")
                return None
            DotCommand.parse_dot_command(char=char)

        # handle backspace:
        if asc == KEY_BACKSPACE and editor.char_pos > 0:
            # print("BS", end='')
            editor.char_pos -= 1
            editor.current_line = editor.current_line[:editor.char_pos]
            print(out_backspace(1), end='', flush=True)

        # handle word wrap:
        if editor.char_pos == buffer.line_length:
            pass

        # handle Return key:
        elif asc == 10:
            # print(" [Return/Enter hit]\n")
            print()
            buffer[editor.current_line] = editor.current_line
            editor.line_number += 1
            editor.current_line = ''
            editor.char_pos = 0

        else:
            # filter out control chars for now:
            if 31 < asc < 197:
                # print(f"{asc if debug else ''}{char}", end='', flush=True)
                print(f"{char}", end='', flush=True)
                editor.char_pos += 1
                editor.current_line = editor.current_line + char


def out_backspace(count) -> str:
    """
    Output <count> backspaces.
    FIXME: character used depends on terminal
    """
    backspace = "\b \b"  # Linux terminal
    # if Character.terminal['translation'] == "PetSCII" then:
    #     backspace = chr(20)
    return backspace * count


def show_line_raw(line_number: int, text: str):
    if editor.mode["show_line_numbers"]:
        print(f'{line_number}:')
    print(r'{text}')


def yes_or_no(prompt="Are you sure", default=False):
    """
    Ask a yes-or-no question, with default answer.
    the response is yes (True), or no (False).
    editor_prompt: configurable string
    default: unless any other key but 'y' for True or 'n' for False is typed
    returns: response: yes = True, no = False
    """
    if default is True:
        chars = "Y/n"
    if default is False:
        chars = "y/N"
    print(f"{prompt} [{chars}]: ", end="", flush=True)
    key, asc = get_character()
    command_char = key.lower()
    if default is True and command_char != "n":
        response = True
        print("Yes.\n")
    if default is False and command_char != "y":
        response = False
        print("No.\n")
    return response


# init:
logging.basicConfig()

# this works:
# line range regular expression. all three elements (start, delimiter and end) are optional.
line_range_re = re.compile(r"(\d+)?(-)?(\d+)?")

KEY_BACKSPACE = 127
KEY_RETURN = 10  # last char of CR/LF pair

editor_prompt = "Command: "
debug = True

"""
tuple(dot_key, dot_text, dot_function, dot_params, accept_ranges)
dot_key: keyboard key to type to select function
dot_text: text to display
dot_function: function to call
dot_params:
    'first': Return key by itself chooses first line in buffer
        (.I Insert)
    'immediate': Return key not required to select command
        (.A Abort, .H Help, .# Scale, .N New Text, .O Line Number Mode,
         .Q Query, .S Save, .U Undo)
    'last': Return key by itself chooses last line in buffer
        (this overrides accept_ranges, which should be set to False anyway)
        (.D Delete, .E Edit)
    'all': Return key by itself chooses all lines in buffer
        (.F Find, .K Find and Replace, .L List, .R Read)
    'subcmd': Additional keystroke required as a parameter to the main command:
        (.E Edit [M]ove, .E Edit [C]opy,
         .J Justify [L]eft, [C]entered, [R]ight, [E]xpand, [P]ack, [I]ndent, [D]edent)
accept_ranges:
    True: you can type x, x-, x-y, -y after the command, or
        Return = set line_range to [ default_all | default_last ] depending on dot_params contents
    'single': one value accepted:
        (.C Columns <x>)
"""
dot_cmd_table = [{"a": ("Abort", DotCommand.cmd_abort, "immediate", False)},
                 {"c": ("Columns", DotCommand.cmd_columns, "single", True)},
                 {"d": ("Delete", DotCommand.cmd_delete, "all", True)},
                 {"e": ("Edit", DotCommand.cmd_edit, ["last", "subcmd"], True)},
                 {"f": ("Find", DotCommand.cmd_find, "all", True)},
                 {"h": ("Help", DotCommand.cmd_help, "immediate", False)},
                 {"i": ("Insert", DotCommand.cmd_insert, "single", True)},
                 # TODO: Justify: could use textwrap module
                 # {"j": ("Justify", DotCommand.cmd_justify, ["all", "subcmd"], True)},
                 {"k": ("Find and Replace", DotCommand.cmd_replace, "all", False)},
                 {"l": ("List", DotCommand.cmd_list, "all", True)},
                 {"n": ("New Text", DotCommand.cmd_new, "immediate", False)},
                 {"o": ("Line Numbering", DotCommand.cmd_line_nums, "immediate", False)},
                 {"q": ("Query", DotCommand.cmd_query, "immediate", False)},
                 {"r": ("Read", DotCommand.cmd_read, "all", False)},
                 {"s": ("Save", DotCommand.cmd_save, "immediate", False)},
                 {"u": ("Undo", DotCommand.cmd_undo, "immediate", False)},
                 {"w": ("Word-Wrap", DotCommand.cmd_word_wrap, "all", True)},
                 {"#": ("Scale", DotCommand.scale, "immediate", False)}
                 ]

"""
editing: Boolean whether we're in the editor
char_pos: character position within line
line: the string input so far
current_line: the line number being edited (1-based)
char: character typed
asc: ascii value of char
"""

work_buffer = Buffer(max_lines=10)
undo_buffer = Buffer(max_lines=10)

editor = Editor(max_line_length=80, buffer=work_buffer)
while True:
    Editor.run(buffer=work_buffer)
