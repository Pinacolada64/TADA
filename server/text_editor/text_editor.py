from __future__ import annotations

import os
from dataclasses import dataclass
import doctest
import logging

import text_editor.functions
# text editor module imports:
from .. import keymap

# https://en.wikipedia.org/wiki/Memento_pattern#Python_example

try:
    if os.getenv("os") == "NT":
        logging.info("Running on NT: Importing msvcrt.getch()")
        from msvcrt import getch
except ImportError as e:
    logging.info(f"Can't import getch: {e}.")

import re


class Buffer:
    def __init__(self, max_lines):
        """
        Instantiate buffer object which holds up to <editor.max_lines> of list <line>
        :param max_lines: how many lines of text can be entered

        Variables created by __init__:
        :var line: a list of empty elements (None) [1 - editor.max_lines],
         representing an empty buffer
        :var current_line: line # currently being edited
        TODO: self.modified flag?
        """
        self.max_lines = max_lines
        # start with empty buffer, but 1-indexed:
        self.line = [None for _ in range(0, max_lines + 1)]
        self.current_line = 1

    def get_last_line(self, buffer: Buffer) -> int | None:
        """
        Enumerate backwards through buffer.lines[] looking for the first non-
        empty list item. This is considered the highest line number in the text
        buffer, printed during .Query, and considered the highest possible
        <end> value in a line range expression.

        Enumerating forwards through <buffer.lines[]> stops at the first blank line.

        :param buffer: list of text lines
        :return last_line: int value of last line which is not None
        :return None: buffer full (no empty lines) | int (last non-None line)

        # quick example of range() function:
        >>> [_ for _ in range(10, 0, -1)]  # start, end, stride
        [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

        # instantiate buffer of 11 lines (0-10):
        >>> test_buffer = Buffer(max_lines=10)

        # fill it with some text:
        >>> test_buffer.line = [None, 'line 1', 'line 2', 'line 3', 'line 4',
        ...                     None, 'line 6', 'line 7', 'line 8', None, None]

        # print lines out (should not print test_buffer.line[0] because users won't
        # expect to edit/interact with line 0, plus it avoids coding e.g.:
        # 'buffer.line[current + 1])' repeatedly, to "normalize" referring to
        # line numbers 0-n as 1-n+1.
        >>> for index in range(test_buffer.max_lines, 0, -1):  # start, end, stride
        ...     print(f"{index} {test_buffer.line[index]}")
        10 None
        9 None
        8 line 8
        7 line 7
        6 line 6
        5 None
        4 line 4
        3 line 3
        2 line 2
        1 line 1

        # determine last line with text in buffer (lines free)
        # (line[10] is None, line[9] is not None):
        >>> test_buffer.get_last_line(buffer=test_buffer)
        8

        # determine last line with all lines full in a new buffer:
        >>> test_buffer = Buffer(max_lines=10)

        >>> test_buffer.line = [f"line {_}" for _ in range(test_buffer.max_lines)]

        # verify all lines are full, plus line numbers are as expected:
        >>> test_buffer.line
        ['line 0', 'line 1', 'line 2', 'line 3', 'line 4', 'line 5', 'line 6', 'line 7', 'line 8', 'line 9']

        # verify a full buffer returns None
        # FIXME: an empty buffer also returns None, use sentinel marker to tell difference?
        >>> test_buffer.get_last_line(test_buffer)
        None
        """
        last_line = buffer.max_lines
        for line_num in range(last_line, 1, -1):  # start, end, stride
            logging.info(f"{line_num=} {buffer.line[line_num]=}")
            if buffer.line[line_num] is None and buffer.line[line_num - 1]:
                last_line = line_num - 1
                logging.debug(f'get_last_line: {last_line=}')
                return last_line
        return None

    def insert_lines(self, buffer: Buffer, start: int):
        """
        Instantiate a separate buffer for entering the inserted text into.

        Buffer.line[start - end].

        TODO: After the text is entered, somehow weave the buffers together
            properly.

        :param buffer: Buffer object to insert lines into
        :param start: line # to start inserting text at
        :return: buffer object with Buffer.line[start - <however many lines entered>]

        TODO: check if any lines left; if not, or buffer becomes full,
            display: "Buffer full." message

        :param max_insertable: editor.max_lines - (Buffer.get_last_line + 1) I think
        """
        lines_remaining = editor.max_lines - self.get_last_line(buffer=buffer)
        if lines_remaining is None:
            print("Memory full. Enter .S to save, .A to abort.")
            raise MemoryError  # i guess :)
            # FIXME
        else:
            lines_remaining += 1
        """
        Line 1
        Line 2
        Line 3
        Line 4
        [.I]nsert [4]
        I4:
        The quick brown fox jumped over the lazy dog.
        [.]Command: Exit
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
                
        :param start: line # to start inserting at
        :return: new List
        """
        insert_buffer = Buffer(max_lines=editor.max_lines)

        # TODO: put lines in the right place.
        # FIXME: buffer.insert(insert_buffer)

    def put_in_undo_buffer(self, line_range):
        if line_range is None:
            # FIXME
            undo_buffer = work_buffer

    def test_fill_buffer(self):
        for line_num in range(1, self.max_lines + 1):
            self.line[line_num] = f"test {line_num}"
        # for .O (Line Numbering) mode:
        self.current_line = self.max_lines + 1


@dataclass
class DotCommand:
    definition: dict  # FIXME: better name
    dot_key: str
    dot_text: str
    dot_function: str
    dot_params: str | list

    """
    def __init__(self, definition: dict, dot_key, dot_text, dot_function: str,
                 dot_params: list | str) -> dict:

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
    pass

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
            print(COMMAND_PROMPT, end="", flush=True)
            key, asc = text_editor.functions.get_character()
            dot_cmd = key.lower()
            if dot_cmd in dot_cmd_table:
                dot_key, dot_text, dot_function, dot_params, dot_range = dot_cmd_table[dot_cmd]
                """
                print command text:
                -> if 'immediate' in dot_params: hitting CR is not necessary. Call function
                       immediately
                   Examples: # (Scale), H (Help), Q (Query)
                -> if accept_ranges is True: print additional space after dot_text.
                   Examples: L (List), R (Read)
                """
                ending = ''
                if 'immediate' in dot_params:
                    ending = "\n"
                if 'accept_ranges' in dot_params:
                    ending = " "

                print(dot_text, end=f"{ending}", flush=True)
                line_range_len = 0
                if dot_range:
                    line_range = text_editor.functions.get_line_range()

                # wait for Return/Backspace unless dot_params contains 'immediate'
                if 'immediate' not in dot_params:
                    char, asc = text_editor.functions.get_character()
                    if char == keymap.keybinding(user_keymap, "delete_char_left"):
                        # cancel command:
                        out_backspace(len(dot_text + line_range_len))
                else:
                    pass
                    dot_function(line_range=line_range, params=dot_params)

            else:
                # not a dot command:
                print(out_backspace(len(COMMAND_PROMPT)))

    def cmd_abort(self):
        response = text_editor.functions.yes_or_no(default=False)
        if response:
            editor.mode["editing"] = False

    def cmd_columns(self, line_range: tuple):
        if line_range is None:
            print(f"Columns set to {editor.column_width}.")
        pass

    def cmd_delete(self, line_range: tuple):
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
            if search in buffer.lines[line_num]:
                found = True
                print(f"{line_num}:")
                # TODO: highlight match
                print(buffer.lines[line_num])
        if found is False:
            print(f"No match for '{search}' was found.")

    def cmd_help(self):
        """.h or .?"""
        """
        TODO: Enhancement: type [.h] <dot_key> for help on topic <dot_key>,
        instead of [.h] displaying a huge file on all commands.
        """
        pass

    def cmd_insert(self, start_line: int):
        """.i Insert <starting_line>
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

    def cmd_replace(self):
        """.K Find and Replace <line_range>"""
        print("TODO: Find what: ")
        print("TODO: Replace with: ")

    def cmd_list(self, line_range: tuple):
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
        start, end = line_range[0], line_range[1]
        # start += 1
        # end += 1
        line_num = start
        # can't use enumerate() here; it has a 'start=' param, but no 'end=' param
        for line in range(start, end):
            print(f"{line_num}:\n{line}")
            line_num += 1

    def cmd_new(self, buffer):
        response = text_editor.functions.yes_or_no(prompt="Erase buffer?", default=False)
        if response is True:
            # TODO: swap buffer with undo buffer
            # print("You can restore the text by selecting .Undo.")
            editor.buffer = ['']
            buffer.lines = 0
            print("Erased text.")

    def cmd_line_nums(self):
        """.O Toggle displaying line numbers on or off"""
        line_numbering = editor.mode["line_numbers"]
        line_numbering = not line_numbering
        Editor.mode = {"line_numbers": line_numbering}
        print(f"Line numbering is now {'on' if line_numbering is True else 'off'}.")

    def cmd_query(self):
        """.Q Query buffer contents"""
        # in_mem = buffer.last_line()
        editor.show_available_lines()

    def cmd_read(self):
        """.R <[x-y]> Read text"""
        pass

    def cmd_save(self):
        """.S Save Text"""
        pass

    def cmd_undo(self):
        """.U Undo Edit"""
        pass

    def cmd_version(self):
        """.V Version"""
        print("Editor version 2023-05-20")

    def cmd_word_wrap(self):
        """.W Word-wrap text"""
        pass

    def cmd_scale(self):
        """
        .# Scale
        Display a ruler with numbered screen columns to assist with, among
        other things, aligning text at a certain column
        """
        # TODO: expand the printed output to match Editor.max_line_length
        print(f"{1:10}{2:10}{3:10}{4:10}")
        print("1234567890" * 4)


class Editor:
    def __init__(self, max_line_length, buffer: Buffer):
        # editor modes:
        #            toggled with .O (Line Numbering):
        self.mode = {"line_numbers": False,
                     # toggled with .I (Insert Mode):
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
        self.column = 1
        # text being edited:
        self.line_input = ''
        logging.info(f'Buffer: init {buffer}, {self.max_lines=}, {self.max_line_length=}')

    def input_line_range(self):
        if expert_mode is False:
            line_range = input("Line range ['?' or 'h' for help]: ")
            if line_range.lower() == "h" or line_range == "?":
                print("""
    x      Just line x
    x-     Lines x to the end of the buffer
    x-y    Lines x to y
     -y    Lines 1 to y
    """)
            # line_range_len = len(line_range)  # FIXME: for backspacing that too, maybe?

    def run(self, buffer: Buffer):
        editor.show_available_lines(self, buffer=buffer)
        while True:
            char, asc = get_character()
            if editor.mode["line_numbers"]:
                print(f'{buffer.current_line}')

    def show_available_lines(self, buffer: Buffer):
        # TODO: display this at init, and after .Q Query (.G Get File if ever implemented)
        in_mem = buffer.get_last_line(buffer=buffer)
        print("Total lines:")
        print(f"Available: {editor.max_lines}")
        print(f"In Memory: {in_mem}")
        print(f"Remaining: {editor.max_lines - in_mem}")

    def edit_existing_line(self, line_num: int):
        """
        Edit string <line_num>.
        """
        # first, show existing line:
        self.show_line_raw(line_num)
        # TODO: Allow Ctrl-key editing.
        pass

    def show_line_raw(self, line_num: int, buffer: Buffer):
        # TODO: .L List, more...
        print(line_num)
        print(buffer.line[line_num])


def input_line(flags=None) -> None | str:
    """
    :param flags: dot_exits: True: "." or "/" on column 1 exits
    :return None: no line entered, str: line input
    """
    # the line as typed so far:
    editor.input_line = ''
    while True:
        asc, char = text_editor.functions.get_character()
        # handle column 0 dot/slash commands:
        if editor.column == 0 and char == "." or char == "/":
            print("Command: ", end='', flush=True)
            if 'dot_exits' in flags:
                print("Exit")
                return None
            DotCommand.parse_dot_command(char=char)

        # handle backspace:
        if asc == keymap.keybinding(user_keymap, 'delete_char_left'):
            if 0 < editor.column < editor.max_line_length:
                # the cursor is anywhere between the second character of the
                # line to the second-to-last character of the line.
                # 1) shift characters from there to the end of the
                #    line to the left
                editor.column -= 1
                # TODO: make generic edit function to backspace x chars
                # shift all chars from [:editor.column] left:
                temp = editor.input_line[:editor.column] + \
                    editor.input_line[editor.column + 1:]
                editor.input_line = temp
                print(out_backspace(1))
            if editor.column == editor.max_line_length:
                # the cursor is at the end of the line:
                editor.input_line = editor.input_line[:editor.column]
                # TODO: find last space on line
                print(out_backspace(1), end='', flush=True)
            if editor.column < editor.max_line_length:
                # 2)
                print(out_backspace(1), end='', flush=True)

        # handle word wrap:
        if editor.column == editor.max_line_length:
            # TODO: iterate backwards through string, looking for space

            word_wrap_pos = editor.input_line.find(" ", editor.input_line)
            # TODO: if no space found, hard Return, make new line:
            if word_wrap_pos is None:
                logging.info("TODO: no space found, making new line")
            else:
                # TODO: add that word to next line
                new_line = editor.input_line[:word_wrap_pos]
                editor.input_line = editor.input_line[word_wrap_pos]
                # backspace over it:
                out_backspace(editor.column_width - word_wrap_pos)
                # new line:
                print()
        # handle Return key:
        elif asc == keymap.keybinding(user_keymap, 'new_line'):
            logging.info(f'[Return/Enter hit]')
            print()
            # put editor.line_input into buffer:
            buffer.line[editor.current_line] = editor.line_input
            buffer.current_line += 1
            editor.line_input = ''
            editor.column = 0
            return editor.input_line

        else:
            # filter out control chars for now:
            if 31 < asc < 197:
                logging.info(f"{asc if debug else ''}{char}")
                print(f"{char}", end='', flush=True)
                editor.column += 1
                editor.current_line = editor.current_line + char


def out_backspace(count: int) -> str:
    """
    Output <count> backspaces.
    FIXME: backspace key value + character output depends on translation
    """
    backspace = "\b \b"  # Linux terminal
    # if Character.terminal['translation'] == "PetSCII" then:
    #     KEY_BACKSPACE = chr(20)  # ctrl-t
    #     KEY_INSERT = chr(20 + 128)  # ctrl-shift-t
    return backspace * count


def show_line_raw(line_number: int, buffer: list):
    """
    Show a single line in the buffer.
    Used for things like .E Edit, .L List
    """
    if editor.mode["show_line_numbers"]:
        print(f'{line_number}:')
    print(f'{buffer[line_number]}')


if __name__ == '__main__':
    # init logging
    logging.basicConfig()

    # this works:
    # line range regular expression. all three elements (start, delimiter and end) are optional.
    line_range_re = re.compile(r"(\d+)?(-)?(\d+)?")

    # environment constants:
    COMMAND_PROMPT = "Command: "

    # TODO: get from Player.flag{} dict
    # per-user flags:
    debug = True
    expert_mode = False  # just for testing purposes

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
                     {"v": ("Version", DotCommand.cmd_version, "immediate", False)},
                     {"w": ("Word-Wrap", DotCommand.cmd_word_wrap, "all", True)},
                     {"#": ("Scale", DotCommand.cmd_scale, "immediate", False)}
                     ]

    doctest.testmod(verbose=True)
    """
    editing: Boolean whether we're in the editor
    column: character position within line
    line: the string input so far
    current_line: the line number being edited (1-based)
    char: character typed
    asc: ascii value of char
    """

    # see https://en.wikipedia.org/wiki/Command_pattern

    # initialize some buffers:
    work_buffer = Buffer(max_lines=10)
    undo_buffer = Buffer(max_lines=10)

    # initialize keymap:
    user_keymap = keymap.USER_KEYMAP_KEYS
    print(user_keymap)
    _ = text_editor.functions.pause()

    # initialize editor:
    editor = Editor(max_line_length=80, buffer=work_buffer)

    while True:
        editor.run(buffer=work_buffer)
