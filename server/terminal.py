# Terminal declarations
from dataclasses import dataclass
from enum import Enum, auto

import colorama
from colorama import Fore

class KeyboardKeyName(str, Enum):
    RETURN = "Return"
    ENTER = "Enter"
    # for text editor:
    BACKSPACE = "Backspace"
    DELETE = "Delete"
    INSERT = "Insert"


class LineEnding:
    CR = "\r"
    LF = "\n"
    CRLF = "\r\n"


class ANSIColors(Enum):
    # text colors:
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


@dataclass
class ClientSettings:
    # client (i.e., Python, C64, C128...?)
    name: str = "Generic Client"
    # screen dimensions:
    screen_rows: int = 25
    screen_columns: int = 40
    # translation: None | ASCII | ANSI | Commodore
    translation: Translation = Translation.ANSI
    # colors for [bracket reader] text highlighting on C64/128:
    # ColorName (e.g., Blue, Brown, Cyan, etc.) or ColorNumber?
    text_color: int = 1
    highlight_color: str = ""
    background_color: str = ""
    border_color: str = ""
    # whether the keyboard has a Return or Enter key:
    return_key: KeyboardKeyName = KeyboardKeyName.ENTER
    # graphics tricks:
    has_color: bool = True
    start_underline: str = ""
    stop_underline: str = ""


@dataclass
class CommodoreClient:
    # could be the PET with no color
    name: str = "Generic Commodore Client"
    rows: int = 25
    columns: int = 40
    translation: Translation = Translation.PETSCII
    return_key: KeyboardKeyName = KeyboardKeyName.RETURN
    line_ending: str = LineEnding.CR


class Commodore128_80Col:
    rows: int = 40
    columns: int = 80
    has_color: bool = True
    start_underline: chr(2)  # Ctrl-B
    stop_underline: None  # FIXME: is there a stop_underline char?


if __name__ == '__main__':
    # Initialize colorama
    colorama.init()

    from player import Player
    player = Player()
    player.colors = ANSIColors

    # Example usage
    color_string = ("{red}Red {orange}Orange {yellow}Yellow {dark_green}Green {dark_blue}Blue {purple}Purple "
                    "{cyan}Cyan {light_green}-{dark_green}-{reset}! {plum}")

    player.output(color_string)
