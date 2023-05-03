import logging


def show_keymap():
    for value, key_name in keymap.items():
        print(f"{value:3} {key_name}")
        if value % 20 == 0:
            _ = input("Pause ('Q' quits): ")
            if _.lower() == "q":
                print("Aborted.")
                break


if __name__ == '__main__':
    # init logging:
    logging.basicConfig()

    # keyboard key constants:
    # TODO: inherit from Player.terminal

    # ANSI/Linux terminal stuff:
    KEY_RETURN = chr(10)  # last char of CR/LF pair
    KEY_ESC = chr(27)
    KEY_BACKSPACE = chr(8)
    KEY_DELETE = chr(127)

    # ANSI Control Sequence Introducer
    # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
    CSI = f'{KEY_ESC}['

    # map functions in KEYMAP table to more readable names:
    KEY_CLASSES = {"move_char_left": "Move Character Left",
                   "move_char_right": "Move Character Right",
                   "move_word_left": "Move Word Left",
                   "move_word_right": "Move Word Right",
                   "move_line_start": "Move Start of Line",
                   "move_line_end": "Move End of Line",
                   "del_char_right": "Delete Char to Right",
                   "char_insert": "Insert Char to Right",
                   "del_word_right": "Delete Word to Right",
                   "del_word_left": "Delete Word to Left",
                   "del_char_left": "Backspace Char to Left",
                   "char_retype": "Retype character",
                   "key_return": "New Line"}

    # ctrl-key tables: keyboard maps
    # (currently taken from 'bash' shell and the Image BBS text editor
    # will be used at prompts and in line editor

    # https://www.gnu.org/software/bash/manual/html_node/Readline-Movement-Commands.html
    KEYMAPS = [{'name': 'bash', 'keys': {
        # per-character keys:
        'char_insert': None,
        'char_retype': chr(6),  # Ctrl-f, move forward 1 character
        'move_char_left': f"{CSI}1C",  # Esc [1C
        'move_char_right': f"{CSI}1D",  # Esc [1D
        'del_char_left': KEY_BACKSPACE,
        'del_char_right': KEY_DELETE,
        'key_return': KEY_RETURN,  # 10
        # per-word keys:
        'move_word_left': None,  # TODO: Meta-b
        'move_word_right': None,  # TODO: Meta-f
        'del_word_left': None,
        'del_word_right': None,  # Meta-b?
        # per-line keys:
        'move_line_start': chr(1),  # Ctrl-A
        'move_line_end': chr(5)}},  # Ctrl-E

               # https://pinacolada64.github.io/ImageBBS3-docs.github.io/12b-text-editor.html#editor-control-keys
               {'name': 'Image BBS', 'keys': {
                   # per-character keys:
                   'char_insert': chr(148),  # ctrl-shift-T (or ctrl-i)
                   'char_retype': chr(21),  # ctrl-u
                   'move_char_left': chr(157),
                   'move_char_right': chr(29),
                   'del_char_left': chr(20),  # ctrl-t
                   'del_char_right': chr(4),  # ctrl-d
                   'key_return': chr(13),
                   # per-word keys:
                   'move_word_left': None,
                   'move_word_right': chr(25),  # ctrl-y
                   'del_word_left': chr(23),  # ctrl-w
                   'del_word_right': None,
                   # per-line keys:
                   'move_line_start': chr(2),  # ctrl-b
                   'move_line_end': chr(14)  # ctrl-n
               }}]

    key_nums = [x for x in range(0, 256)]
    # list comprehension makes a list within a list, so that's out

    # start out with '<null>' in list index 0
    # this list will be used for ANSI/keytable editor
    # this also works:
    # ctrl_key_list = [f"Ctrl-{chr(x + 64)}" for x in range(0, 27)]
    ctrl_key_list = ["Null"]
    # iterate through ['Ctrl-A', 'Ctrl-B' ... 'Ctrl-Y', 'Ctrl-Z']
    for x in range(ord("A"), ord("Z") + 1):
        ctrl_key_list.append(f"Ctrl-{chr(x)}")

    # iterate through [27 ... 255]
    for x in range(27, 255 + 1):
        ctrl_key_list.append(f'{chr(x)}')

    keymap = {value: name for value, name in zip(key_nums, ctrl_key_list)}

    """
    print("Before key name replacement:")
    show_keymap()
    """

    # Commodore terminal:
    # override generic "Ctrl-<letter>" keys with more meaningful names:
    ctrl_key_nice_names = {0: "Null", 3: "Stop", 5: "White", 8: "Disable Shift + C=",
                           9: "Enable Shift + C=", 13: "Return", 14: "Lowercase",
                           17: "Cursor Down", 18: "Reverse On", 19: "Home", 20: "Delete",
                           28: "Red", 29: "Cursor Right", 30: "Green", 31: "Blue",
                           129: "Orange",
                           133: "f1", 134: "f3", 135: "f5", 136: "f7",
                           137: "f2", 138: "f4", 139: "f6", 140: "f8",
                           141: "Shift + Return", 142: "Uppercase",
                           144: "Black", 145: "Cursor Up", 147: "Clear", 148: "Insert",
                           149: "Brown", 150: "Lt. Red", 151: "Gray 1", 152: "Gray 2",
                           153: "Lt. Green", 154: "Lt. Blue", 155: "Gray 3",
                           156: "Purple", 157: "Cursor Left", 158: "Yellow",
                           159: "Cyan", 160: "Shift + Space"}

    # assign descriptive name from ctrl_key_nice_names dict:
    # TODO: this table is also used when doing a .Read to show nice ctrl function names:
    #    e.g., instead of '\x95', show '[Brown]'
    keymap.update(ctrl_key_nice_names)

    """
    print("After key name replacement:")
    show_keymap()
    """

    # set user's keymap to Image BBS:
    # KEYMAPS is a list of dicts:
    USER_KEYMAP_NAME = KEYMAPS[1]["name"]  # ['Image BBS']
    USER_KEYMAP_KEYS = KEYMAPS[1]["keys"]

    # Display keymap:
    # iterate through keymap, displaying plain ctrl key names,
    # functions bound to them (if any, could be None):
    print(f"Using '{USER_KEYMAP_NAME}' keymap:\n")

    # THIS WORKS
    """
    num = 0
    for function, key_chr in USER_KEYMAP_KEYS.items():
        if key_chr:
            # we use ctrl_key_list[] since ctrl_key_nice_names[] makes
            # output more confusing (e.g., "Lowercase: Move Line End" is
            # technically correct (Ctrl-N is Lowercase), but we want to keep
            # the output as "Ctrl-N: Move End of Line"
            ctrl_key = ctrl_key_list[ord(key_chr)]
            function_name = KEY_CLASSES[function]
            num += 1
            print(f"{num:2}) {ctrl_key}: {function_name}")
    """
    # None = Unassigned
    SHOW_USER_KEYS = {ctrl_key_list[_]: None for _ in range(1, 27)}
    # print(f"{len(SHOW_USER_KEYS) == 26}")

    # build a dict of ctrl keys and their assigned functions to show in two columns:
    index = 0
    # e.g., {'char_retype': chr(21)}
    for key_class, ascii_char in USER_KEYMAP_KEYS.items():
        # if None, it is not supported, so skip it:
        if ascii_char is None:
            print(f'{key_class} not supported, skipping')
        else:
            key_value = ord(ascii_char)
            print(f"{key_value=} {ascii_char=}")
            if 1 < key_value < 27:
                SHOW_USER_KEYS[ctrl_key_list[key_value]] = KEY_CLASSES[key_class]
                print(f"{ctrl_key_list[key_value]}"
                      f": {SHOW_USER_KEYS[ctrl_key_list[key_value]]}")
            else:
                # TODO: add this to output
                print(f"Extended character, using {ctrl_key_nice_names[key_value]}")
                print(f"Out of range: {key_value}: {key_class}, skipping")
    _ = input("Pause: ")


    """
    finally, print this whole mess to see if it's somewhat understandable:
    ideal output:
    '[Custom]' would have to check that a reassigned keystroke was not already
    assigned to an existing function

    Using 'Image BBS' keymap [Custom]:

        ctrl_key_list[]                           key_classes[]
     1) Ctrl-A: ---                   14) Ctrl-N: Move End of Line
     2) Ctrl-B: Move Start of Line    15) Ctrl-O: ---       
     3) Ctrl-C: ---                   16) Ctrl-P: ---       
    [...]
    11) Ctrl-K: ---                   24) Ctrl-X: ---       
    12) Ctrl-L: ---                   25) Ctrl-Y: Move Word Right
    13) Ctrl-M: Return                26) Ctrl-Z: ---       
    """
    # spaces = len(max([x for x in str(SHOW_USER_KEYS.values())], key=len))

    # e.g., {'ctrl-a': 'Unassigned'}
    for index in range(1, 14):
        key_1 = ctrl_key_list[index]
        function_1 = SHOW_USER_KEYS[key_1]

        key_2 = ctrl_key_list[index + 13]
        function_2 = SHOW_USER_KEYS[key_2]

        # "xx) Ctrl-T Delete char to right"
        if function_1 is None:
            function_1 = "---"
        print(f"{index:2}) {key_1}: {function_1:20}", end='')

        if function_2 is None:
            function_2 = "---"
        print(f"{index + 13:2}) {key_2}: {function_2:20}")

    # TODO: later
    """
    keymap_num = None
    while keymap_num is None:
        _ = int(input("Keymap number: "))
        if 1 < _ < len(KEYMAPS):
            keymap_num = _
            print(f"Switched to keymap '{KEYMAPS[_]['name']}.'")
    """
