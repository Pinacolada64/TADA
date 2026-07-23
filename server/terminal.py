# Terminal declarations
from dataclasses import asdict, dataclass
from enum import Enum, auto, StrEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    # Back style is used for reverse text
    # Style is used for underline and reverse
    try:
        from colorama import Fore, Back, Style
    except ModuleNotFoundError:
        print("colorama not available.")
    from menu_system import MenuColor
import logging

# TADA-specific imports:
from player import Player
from flags import FlagDisplayTypes
from tada_utilities import input_number_range, input_yes_no
try:
    import cbmcodecs2
except ImportError:
    print("cbmcodecs2 not found, Commodore graphics will not be available")

# --- Keyboard settings -------------------------------------------------------------------
class KeyboardKeyName(str, Enum):
    RETURN = "Return"
    ENTER = "Enter"
    # for text editor:
    BACKSPACE = "Backspace"
    DELETE = "Delete"
    INSERT = "Insert"

class KeyboardKeyCodes(Enum):
    RETURN = "\r"
    ENTER = "\n"
    BACKSPACE = "\b"
    DELETE = "\x7f"
    INSERT = "\x12"

class KeyCodes(Enum):
    RETURN = "\r"
    ENTER = "\n"
    BACKSPACE = "\b"
    DELETE = "\x7f"
    INSERT = "\x12"
    ESCAPE = "\x1b"
    SPACE = " "
    CURSOR_LEFT = "\x1b[D"
    CURSOR_RIGHT = "\x1b[C"
    CURSOR_UP = "\x1b[A"
    CURSOR_DOWN = "\x1b[B"
    TAB = "\t"

class CommodoreKeyCodes:
    # classes cannot inherit from Enums, so we have to copy the values
    RETURN = chr(13)
    LINEFEED = None
    BACKSPACE = chr(20)
    DELETE = chr(ord(BACKSPACE))
    INSERT = chr(ord(BACKSPACE) + 128)
    CURSOR_LEFT = chr(ord(BACKSPACE) + 128)
    CURSOR_RIGHT = chr(ord(CURSOR_LEFT) + 128)
    CURSOR_DOWN = chr(17)
    CURSOR_UP = chr(ord(CURSOR_DOWN) + 128)
    # on the Commodore 128, anyway:
    TAB = chr(9)

# --- Graphics characters ------------------------------------------------------------
class ANSIGraphicsChars(StrEnum):
    # TODO make sure this is using UTF-8
    CORNER_UPPER_LEFT = "╔"
    CORNER_UPPER_RIGHT = "╗"
    CORNER_LOWER_LEFT = "╚"
    CORNER_LOWER_RIGHT = "╝"
    HORIZONTAL_LINE = "═"
    VERTICAL_LINE = "║"
    TOP_TEE = "╦"
    BOTTOM_TEE = "╩"
    LEFT_TEE = "╠"
    RIGHT_TEE = "╣"
    CROSS_TEE = "╬"

class CommodoreGraphicsChars(StrEnum):
    # TODO: inherit from cbmcodecs2
    DISABLE_CASE_SWITCH = chr(8)
    ENABLE_CASE_SWITCH = chr(9)
    LOWERCASE = chr(14)
    REVERSE_ON = chr(18)
    REVERSE_OFF = chr(ord(REVERSE_ON) + 128)
    UPPERCASE = chr(ord(LOWERCASE) + 128)  # 142
    CORNER_UPPER_LEFT = chr(176)
    CORNER_UPPER_RIGHT = chr(174)
    CORNER_LOWER_LEFT = chr(173)
    CORNER_LOWER_RIGHT = chr(189)
    TOP_TEE = chr(178)
    BOTTOM_TEE = chr(180)
    LEFT_TEE = chr(178)
    RIGHT_TEE = chr(181)
    CROSS_TEE = chr(219)
    HORIZONTAL_LINE = chr(221)
    VERTICAL_LINE = chr(186)

class LineEnding:
    CR = "\r"
    LF = "\n"
    CRLF = "\r\n"

class ColorName(StrEnum):
    BLACK = "Black"
    WHITE = "White"
    RED = "Red"
    CYAN = "Cyan"
    PURPLE = "Purple"
    DARK_GREEN = "Dark Green"
    DARK_BLUE = "Dark Blue"
    YELLOW = "Yellow"
    ORANGE = "Orange"
    BROWN = "Brown"
    LIGHT_RED = "Light Red"
    DARK_GRAY = "Dark Gray"
    MEDIUM_GRAY = "Medium Gray"
    LIGHT_GREEN = "Light Green"
    LIGHT_BLUE = "Light Blue"
    LIGHT_GRAY = "Light Gray"
    RESET = "Reset"
    REVERSE_ON = "Reverse On"
    REVERSE_OFF = "Reverse Off"

class ANSIColors(Enum):
    # text colors - if terminal cannot output a given color, it is set to None
    # TODO: in settings display, use ColorName instead of ANSIColors or CommodoreColors
    # Colorama: https://github.com/tartley/colorama
    try:
        from colorama import Fore, Back, Style
        BLACK = Fore.BLACK
        WHITE = Fore.WHITE
        RED = Fore.RED
        CYAN = Fore.CYAN
        PURPLE = None
        DARK_GREEN = Fore.GREEN
        DARK_BLUE = Fore.BLUE
        YELLOW = Fore.YELLOW
        ORANGE = None
        BROWN = None
        LIGHT_RED = Fore.LIGHTRED_EX
        DARK_GRAY = Fore.LIGHTBLACK_EX
        MEDIUM_GRAY = Fore.LIGHTBLACK_EX
        LIGHT_GREEN = Fore.LIGHTGREEN_EX
        LIGHT_BLUE = Fore.LIGHTBLUE_EX
        LIGHT_GRAY = Fore.LIGHTBLACK_EX
        RESET = Fore.RESET
        # changing background color to white and resetting style to reverse off:
        REVERSE_ON = Back.WHITE + Style.DIM
        REVERSE_OFF = Style.RESET_ALL
    except ImportError:
        logging.debug("ANSIColors: Colorama not installed")


class CBMColors(Enum):
    BLACK = chr(144)
    WHITE = chr(5)
    RED = chr(28)
    CYAN = chr(159)
    PURPLE = chr(156)
    DARK_GREEN = chr(30)
    DARK_BLUE = chr(31)
    YELLOW = chr(158)
    ORANGE = chr(129)
    BROWN = chr(149)
    LIGHT_RED = chr(150)
    DARK_GRAY = chr(151)
    MEDIUM_GRAY = chr(152)
    LIGHT_GREEN = chr(153)
    LIGHT_BLUE = chr(154)
    LIGHT_GRAY = chr(155)
    RESET = MEDIUM_GRAY


class Translation(Enum):
    PETSCII = auto()
    ASCII = auto()
    ANSI = auto()


class TabSettings:
    def __init__(self):
        self.has_tab_key: bool = True
        self.tab_type: str = "\t"
        self.tab_width: int = 8
        self.tab_output: str = "\t"

    def to_dict(self) -> dict:
        return {
            'has_tab_key': self.has_tab_key,
            'tab_type':    self.tab_type,
            'tab_width':   self.tab_width,
            'tab_output':  self.tab_output,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TabSettings':
        instance = cls()
        for key in ('has_tab_key', 'tab_type', 'tab_width', 'tab_output'):
            if key in data:
                setattr(instance, key, data[key])
        return instance

class TerminalColors:
    def __init__(self):
        self.text_color: ColorName = ColorName.WHITE
        self.border_color: ColorName = ColorName.BLACK
        self.highlight_color: ColorName = ColorName.RED
        self.normal_color: ColorName = ColorName.WHITE
        self.background_color: ColorName = ColorName.BLACK

    def to_dict(self) -> dict:
        return {
            'text_color':       self.text_color.name,
            'border_color':     self.border_color.name,
            'highlight_color':  self.highlight_color.name,
            'normal_color':     self.normal_color.name,
            'background_color': self.background_color.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TerminalColors':
        instance = cls()
        for key in ('text_color', 'border_color', 'highlight_color',
                    'normal_color', 'background_color'):
            # isinstance guard, not just try/except KeyError: a save file
            # from before ClientSettings had a real to_dict() dumped enum
            # members via a generic __dict__ fallback -- a dict of the
            # Enum class's own reflection (_value_/_name_/__objclass__),
            # not a plain name string. ColorName[<dict>] raises TypeError
            # (unhashable), not KeyError, so it slipped past this same
            # guard before -- found live via player-botdummy.json still
            # carrying one of these from before the fix.
            if key in data and isinstance(data[key], str):
                try:
                    setattr(instance, key, ColorName[data[key]])
                except KeyError:
                    logging.info(
                        "TerminalColors.from_dict: %r is not a known "
                        "ColorName -- keeping default %s",
                        data[key], getattr(instance, key),
                    )
            elif key in data:
                logging.info(
                    "TerminalColors.from_dict: %s is a legacy non-string "
                    "value (%r) from before to_dict()/from_dict() existed "
                    "-- keeping default %s",
                    key, data[key], getattr(instance, key),
                )
        return instance

class ClientSettings:
    from colorama import Fore, Back, Style
    # screen dimensions:
    screen_rows: int = 25
    screen_columns: int = 40
    # translation: None | ASCII | ANSI | Commodore
    translation: Translation = Translation.ANSI
    # colors for [bracket reader] text highlighting:
    # ColorName (e.g., Blue, Brown, Cyan, etc.) or ColorNumber?
    # TODO: ensure text_color cannot be the same as background_color to avoid invisible text
    colors: TerminalColors = TerminalColors()
    border_style: str = 'single'   # 'ascii' | 'single' | 'double'
    # graphics tricks:
    has_color: bool = True
    start_underline: None
    stop_underline: None
    reverse_on: str = Back.WHITE + Style.DIM
    reverse_off: str = Style.RESET_ALL
    tab_settings: TabSettings = TabSettings()
    # Label for the client's Enter/Return key, shown in prompts like
    # "(Enter: Attack)" or "press Return to cancel" -- see Player.return_key.
    return_key: str = 'Enter'
    # New in TADA: player-chosen display timezone/date format for
    # player-facing dates (currently just commands/connect.py's "You
    # last connected on ..."; other date displays -- birthdays, ban
    # expiry -- are a follow-up, see TODO.md). Editable via PREFS 'Z'/'D'
    # (commands/prefs.py). Empty timezone means "use the server's own
    # local time" (this codebase's timestamps are stored via bare
    # datetime.now(), so that's the only timezone they're meaningfully
    # already in) -- an IANA zone name (e.g. 'America/New_York') converts
    # to that zone instead. See formatting.format_player_datetime().
    timezone:    str = ''
    date_format: str = '%B %d, %Y'
    # 12-hour ('%I:%M %p', e.g. '2:30 PM') or 24-hour ('%H:%M', e.g.
    # '14:30' -- the default, matching this codebase's previous hardcoded
    # Hourglass behavior). Editable via PREFS 'F' (Time Format). See
    # formatting.format_player_time() -- used by the Hourglass clock
    # (network_context.py/terminal_context.py's prompt()) and available
    # for any other player-facing time-of-day display.
    time_format: str = '%H:%M'
    # Editable via commands/prefs.py's 'L' (Line Ending) row. Stored/reported
    # only for now -- not yet threaded through formatting.py's actual
    # send path (every line goes out as a JSON array element for ANSI/
    # plain clients, so this only has real bearing for a raw-byte PETSCII
    # or future raw-terminal client).
    line_ending: str = LineEnding.LF
    # Set automatically as a side effect of picking a client type (PREFS
    # 'T') -- true for the Commodore 128, TADA/ANSI, and Custom presets
    # (all have a real Tab key sending chr(9)); false only for the
    # Commodore 64, whose keyboard has no dedicated Tab key. Distinct
    # from tab_settings above (the general has-a-tab-key/simulated-width
    # picker under PREFS 'K'), which is asked separately.
    has_tab: bool = False
    tab_char: str = chr(9)
    # Per-player menu color scheme (menu_system.MenuColor) -- None means
    # "use menu_system.DEFAULT_MENU_COLORS". Not yet editable from PREFS;
    # this field exists so format_menu_lines() has somewhere to read a
    # player's chosen scheme from once that UI is built.
    menu_colors: 'Optional[MenuColor]' = None

    # New in TADA: Player._load() never restored client_settings at all
    # (only save() dumped it, via a generic __dict__ fallback that also
    # serialized Enum members as their full class reflection instead of
    # just a name/value) -- every PREFS choice silently reset to defaults
    # on reconnect. to_dict()/from_dict() give save()/_load() a real,
    # clean round trip. Found while adding the timezone/date_format
    # fields above, which would have inherited the same bug.
    def to_dict(self) -> dict:
        return {
            'screen_rows':    self.screen_rows,
            'screen_columns': self.screen_columns,
            'translation':    self.translation.name,
            'colors':         self.colors.to_dict(),
            'border_style':   self.border_style,
            'has_color':      self.has_color,
            'reverse_on':     self.reverse_on,
            'reverse_off':    self.reverse_off,
            'tab_settings':   self.tab_settings.to_dict(),
            'return_key':     self.return_key,
            'timezone':       self.timezone,
            'date_format':    self.date_format,
            'time_format':    self.time_format,
            'line_ending':    self.line_ending,
            'has_tab':        self.has_tab,
            'tab_char':       self.tab_char,
            'menu_colors':    (asdict(self.menu_colors)
                                if self.menu_colors is not None else None),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ClientSettings':
        instance = cls()
        for key in ('screen_rows', 'screen_columns', 'border_style', 'has_color',
                    'reverse_on', 'reverse_off', 'return_key', 'timezone',
                    'date_format', 'time_format', 'line_ending', 'has_tab', 'tab_char'):
            if key in data:
                setattr(instance, key, data[key])
        # isinstance guard, not just try/except KeyError: a save file from
        # before ClientSettings had a real to_dict() dumped the Translation
        # enum member via a generic __dict__ fallback -- a dict of the
        # Enum class's own reflection (_value_/_name_/__objclass__), not a
        # plain name string. Translation[<dict>] raises TypeError
        # (unhashable), not KeyError, so it slipped past this same guard
        # before -- found live via player-botdummy.json still carrying one
        # of these from before the fix.
        if isinstance(data.get('translation'), str):
            try:
                instance.translation = Translation[data['translation']]
            except KeyError:
                logging.info(
                    "ClientSettings.from_dict: %r is not a known "
                    "Translation -- keeping default %s",
                    data['translation'], instance.translation,
                )
        elif 'translation' in data:
            logging.info(
                "ClientSettings.from_dict: translation is a legacy "
                "non-string value (%r) from before to_dict()/from_dict() "
                "existed -- keeping default %s",
                data['translation'], instance.translation,
            )
        if isinstance(data.get('colors'), dict):
            instance.colors = TerminalColors.from_dict(data['colors'])
        if isinstance(data.get('tab_settings'), dict):
            instance.tab_settings = TabSettings.from_dict(data['tab_settings'])
        if isinstance(data.get('menu_colors'), dict):
            from menu_system import MenuColor
            instance.menu_colors = MenuColor(**data['menu_colors'])
        return instance

# ---------------------------------------------------------------------------
# Everything below (settings_menu, tab_edit, edit_screen_rows,
# keyboard_settings, color_settings, test_graphics_output) is an early,
# never-finished prototype -- blocking print()/input() calls, references
# to an unimported `menu_system`/`ms` and an undefined `terminal_colors`,
# `self` used outside any class. Not reachable from any real command.
# The actual, working preferences UI is commands/prefs.py's prefs_menu()
# (async, wired to the real PREFS command and character creation) --
# screen dimensions/translation ('T'), tab settings ('K'), and line
# ending ('L') all live there now.
# ---------------------------------------------------------------------------

def settings_menu(player: Player):
    from menu_system import Menu, MenuItem
    # sub-menu of Terminal Settings:
    terminal_translation = menu_system.Menu(title="Terminal Translation")
    p_c = player.client_settings
    terminal_translation.add_item(MenuItem("TR", "Translation", dot_leader_handler=p_c.translation.name.title()))
    terminal_translation.add_item(MenuItem("TC", "Text Colors", dot_leader_handler=p_c.colors.text_color.name.title()))

    terminal_translation.add_item(MenuItem("HC", "Highlight Color", dot_leader_handler=p_c.colors.highlight_color.name.title()))
    terminal_translation.add_item(MenuItem("BA", "Background Color", dot_leader_handler=p_c.colors.background_color.name.title()))
    terminal_translation.add_item(MenuItem("BO", "Border Color", dot_leader_handler=p_c.colors.border_color.name.title()))

    translation = menu_system.Menu("Translation Settings")
    for translation_type in Translation:
        translation.add_item(text=translation_type.name.title(),
                             shortcuts=translation_type.name[0],
                             dot_leader_handler=translation_type.name.title(),
                             edit_function=self.edit_translation(player.client_settings.translation))
    
    keyboard_settings = menu_system.Menu("Keyboard Settings")
    keyboard_settings.add_item(shortcut="R",
                               text="Return key is named",
                               dot_leader_handler=p_c.return_key.name.title(),
                               edit_function=lambda: self.edit_return_key())

    # top level menu:
    terminal_settings = menu_system.Menu("Terminal Settings")
    terminal_settings.add_item("N", "Client Name", dot_leader_handler=self.name)
    terminal_settings.add_item("R", "Screen Rows", dot_leader_handler=self.screen_rows,
                               edit_function=lambda: self.edit_screen_rows())
    terminal_settings.add_item("C", "Screen Columns", dot_leader_handler=self.screen_columns,
                               edit_function=lambda: self.edit_screen_columns())
    terminal_settings.add_item("T", "Translation", dot_leader_handler=self.translation.name.title(),
                               submenu=translation)
    terminal_settings.add_item("H", "Has Color", dot_leader_handler="Yes" if self.has_color else "No")
    terminal_settings.add_item("S", "Start Underline", dot_leader_handler="Yes, chr({ord(self.start_underline)})" if self.start_underline else "No")
    terminal_settings.add_item("Stop Underline", dot_leader_handler="Yes, chr({ord(self.stop_underline)})" if self.stop_underline else "No")
    terminal_settings.add_item("Has Tab Key", dot_leader_handler="Yes" if self.tab_settings.has_tab_key else "No")
    terminal_settings.add_item("Tab Type/Width", leading_dot_leader_handler=self.tab_settings.tab_type, edit_function=lambda: self.tab_edit())
    terminal_settings.add_item("Edit Terminal Colors", submenu=terminal_colors)
    terminal_settings.add_item("Edit Keyboard Settings", submenu=keyboard_settings)

    tab_menu = ms.Menu("Tab Settings")
    tab_menu.add_item("Tab", dot_leader_handler=self.tab)
    if self.tab_type == "Tab":
        tab_type = "Tab key"
    else:
        tab_type = "Space {self.tab_width}"
    
    tab_menu.add_item("Tab Type/Width", leading_dot_leader_handler=self.tab_type, edit_function=lambda: self.tab_edit())

def tab_edit(player: Player):
    # tab width, in characters
    player.client_settings.tab_settings.tab_width = input_number_range(prompt_msg="Enter tab width",
                                                                       out_of_bounds_msg=f"Tab width must be between 0 and {player.client_settings.screen_columns}.",
                                                                       min_value=0,
                                                                       max_value=player.client_settings.screen_columns)
    # if Tab key is not available, simulate by printing {space * tab_width}
    player.client_settings.tab_settings.tab = " " * player.client_settings.tab_settings.tab_width
    
    menu_collection = [terminal_settings, keyboard_settings, terminal_colors]

    ms.run_menu(player, menu_collection)

    def edit_screen_columns(player: Player):
        player.client_settings.screen_columns = input_number_range(prompt_msg="Enter screen width (columns)",
                                                                   out_of_bounds_msg="Screen columns must be between 1 and 80.",
                                                                   min_value=1, max_value=80)
def horizontal_ruler(player: Player):
    """Display a horizontal ruler for x-position debugging"""
    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    # TODO: use screen ruler from bar debugging
    ruler_length = player.client_settings.screen_columns
    digits = "0123456789"
    print("   ", end='')
    print(" ", end='')  # extra space for first '0'
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        print(f'{tens:> 10}', end='')
    print()
    print("   ", end='')
    print((digits * 10)[:ruler_length])

    print(horizontal_ruler(player))
    print("The screen ruler should show numbers all the way across the screen.")
    correct = input_yes_no("Is the screen ruler correct?")
    if correct:
        return



def edit_screen_rows(player: Player):
    while True:
        for num in range(player.client_settings.screen_rows, 1):
            print(num)
        player.client_settings.screen_rows = input_number_range(
            prompt_msg="Enter the biggest number you see at the top of the screen",
            out_of_bounds_msg="Screen rows must be between 1 and 25.", min_value=1, max_value=25)


def keyboard_settings(player: Player):
    import menu_system as ms
    keyboard_settings = ms.Menu("Keyboard Settings")
    keyboard_settings.add_item("Return Key", dot_leader_handler=self.return_key.name.title())
    keyboard_settings.add_item("Has Color", dot_leader_handler="Yes" if self.has_color else "No")
    keyboard_settings.add_item("Start Underline", dot_leader_handler="Yes" if self.start_underline else "No")
    keyboard_settings.add_item("Stop Underline", dot_leader_handler="Yes" if self.stop_underline else "No")
    keyboard_settings.add_item("Tab settings...", submenu=self.tab_settings)
    keyboard_settings.run_menu(player)
    return terminal_settings

def color_settings(player: Player):
    import menu_system as ms
    graphics_string_sample = [f"{{corner_upper_left}}{{upper_tee}}{{corner_upper_right}}",
                                f"{{left_tee}}{{cross_tee}}{{right_tee}}",
                                f"{{corner_lower_left}}{{bottom_tee}}{{corner_lower_right}}"]

    joined_reverse_string_sample = []
    reverse_mode = ["R", "O"]
    for i, line in enumerate(graphics_string_sample):
        joined_reverse_string_sample[i].append(f"{reverse_mode[i % 2]}{line}{line}{line}")
    print(joined_reverse_string_sample)

    color_string_sample = ("|red|Red |orange|Orange |yellow|Yellow |dark_green|Green "
                            "|dark_blue|Blue |purple|Purple |cyan|Cyan |light_green|-"
                            "|dark_green|-|reset|! |plum|")
    
    color_settings = ms.Menu("Color Settings")
    color_settings.add_item("Type:", dot_leader_handler="Name")
    """
    Mockup:

       Color Settings
    B. Background............: Black
    T. Text..................: White
    H. Highlight.............: Red
    N. Normal................: Medium Gray
       Sample: This is [highlighted] text. (parse this string of course)
    """
    edit_functions = {ColorName.BACKGROUND: lambda: player.background_color,
                      ColorName.TEXT: lambda: player.text_color,
                      ColorName.HIGHLIGHT: lambda: player.highlight_color,
                      ColorName.NORMAL: lambda: player.normal_color}
    for color_setting in [ColorName.BACKGROUND, ColorName.TEXT, ColorName.HIGHLIGHT, ColorName.NORMAL]:
        color_settings.add_item(color_setting.name.title(), dot_leader_handler=color_setting.name.title(),
                                edit_function=edit_functions[color_setting])
    color_settings.add_item(shortcut="V", text="View Highlighting Sample",
                            edit_function=lambda: player.output(["[This is highlighted text.]{return}",
                            "[This is normal text.]{return}",
                            ]),
                            )

    color_settings.add_item(shortcut="T", text="View Text Color Sample",
                            edit_function=lambda: player.output(joined_reverse_string_sample))
    color_settings.add_item(shortcut="G", text="View Character Graphics Sample",
                            edit_function=lambda: player.output(graphics_string_sample))

    menu_collection = [color_settings, keyboard_settings, terminal_settings]
    run_menu(player, player_handler, menu_collection)
    return color_settings
    

def test_graphics_output(player: Player):
    color_string = ("|red|Red |orange|Orange |yellow|Yellow |dark_green|Green |dark_blue|Blue |purple|Purple "
                    "|cyan|Cyan |light_green|-|dark_green|-|reset|! |plum|")
    player.output(color_string)

@dataclass
class CommodoreClient:
    # could be the PET with no color
    name: str = "Generic Commodore Client"
    rows: int = 25
    columns: int = 40
    translation: Translation = Translation.PETSCII
    return_key: KeyboardKeyName = KeyboardKeyName.RETURN
    line_ending: str = LineEnding.CR
    tab: str = "     "
    has_color: bool = True
    start_underline: str = ""
    stop_underline: str = ""

class Commodore128_40Col:
    def __init__(self):
        self.rows: int = 25
        self.columns: int = 40
        self.has_color: bool = True
        self.start_underline: str = ""  # (no underline in 40 cols)
        self.tab: str = chr(9)
        self.stop_underline: str = ""

    def __post_init__(self):
        self.name = f"Commodore 128 ({self.columns} columns)"

class Commodore128_80Col(Commodore128_40Col):
    def __init__(self):
        super().__init__()
        self.columns = 80
        self.has_color = True
        self.start_underline = chr(2)  # Ctrl-B
        self.stop_underline = None  # FIXME: is there a stop_underline char?
        self.tab = chr(9)

    def __post_init__(self):
        self.name = f"Commodore 128 ({self.columns} columns)"


class Commodore64(ClientSettings):
    def __init__(self):
        super().__init__()
        self.rows = 25
        self.columns = 40
        self.has_color = True
        self.tab_width = 8
        self.tab_type = "Space"
        self.start_underline = ""
        self.stop_underline = ""
        self.name = f"Commodore 64 ({self.columns} columns)"

class Commodore128_40Col(Commodore64):
    def __init__(self):
        super().__init__()
        self.name = f"Commodore 128 ({self.columns} columns)"
        self.has_tab_key = True
        self.tab_width = 8
        self.tab_type = chr(8)
        self.tab = "\t"

class Commodore128_80Col(Commodore64):
    def __init__(self):
        super().__init__()
        self.columns = 80
        self.name = f"Commodore 128 ({self.columns} columns)"
        self.has_tab_key = True
        self.tab_width = 8
        self.tab_type = chr(9)
        self.has_underline = True
        self.start_underline = chr(2)
        self.stop_underline = chr(2)  # FIXME: I think

class Output:
    def __init__(self, player: Player):
        self.player = player

    def output(self, message: str):
        processed_message = self.process_message(message)
        self.player.output(processed_message)

    def process_message(self, player: Player, message: str) -> str:
        # TODO: parse message for {color_name} and replace with colorama color
        # TODO: handle multipliers in strings (e.g., {color_name:3})
        # TODO: handle {return}, varying methods of outputting {tab} to client, etc.
        # TODO: handle {reverse_on} and {reverse_off}
        # Regex to match {token:count}
        import re
        regex = r"{(?P<token>[a-zA-Z_]+)(?::(?P<count>\d+))?}"
        matches = re.finditer(regex, message)
        if matches:
            for match in matches:
                token = match.group("token")
                count = match.group("count")
                logging.debug("{token=}")
                logging.debug("{count=}")
        # Look up codes based on Translation type
        colors = CommodoreGraphicsChars if self.player.client_settings.translation == Translation.COMMODORE else ANSIGraphicsChars

        # Replace tokens with appropriate codes
        if matches:
            for match in matches:
                token = match.group("token")
                count = match.group("count")
                if token in colors.__dict__:
                    code = colors.__dict__[token] * (int(count) if count else 1)
                    message = message.replace(f"{{{token}:{count}}}", code)
        if self.player.client_settings.translation == Translation.ANSI:
            if self.player.client_settings.has_color:
                match message:
                    case REVERSE_ON.value:
                        return message.replace(REVERSE_ON.value, Terminal.ANSIColors.REVERSE_ON).replace(REVERSE_OFF.value, Terminal.ANSIColors.REVERSE_OFF)
                    case REVERSE_OFF.value:
                        return message.replace(REVERSE_ON.value, "").replace(REVERSE_OFF.value, "")
                    case RESET.value:
                        return message.replace(RESET.value, Terminal.ANSIColors.RESET)
                    case _:
                        return message
            else:
                return message.replace(REVERSE_ON.value, "").replace(REVERSE_OFF.value, "")
        elif self.player.client_settings.translation == Translation.COMMODORE:
            if matches:
                match message:
                    case REVERSE_ON.value:
                        return message.replace(REVERSE_ON.value, CBMColors.REVERSE_ON).replace(REVERSE_OFF.value, CBMColors.REVERSEOFF)
                    case REVERSE_OFF.value:
                        return message.replace(REVERSE_ON.value, "").replace(REVERSE_OFF.value, "")
                    case RESET.value:
                        return message.replace(RESET.value, CBMColors.RESET)
                    case _:
                        return message
            else:
                return message
        else:
            return message
        

if __name__ == '__main__':
    # set up logging:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Terminal is running")

    # Initialize colorama
    colorama.init()

    from player import Player
    player = Player()
    player.colors = ANSIColors
    player.client_settings = ClientSettings()
    player.client_settings.translation = Translation.ANSI

    # call terminal settings menu to test the display of the graphics string sample:
    bla = settings_menu(player)
    print(bla)
