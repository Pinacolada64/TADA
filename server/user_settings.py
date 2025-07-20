from enum import Enum

# TODO: client settings editor here, pull stuff from terminal.py

class ClientSettingsNames(str, Enum):
    NAME = "Name"
    SCREEN_HEIGHT = "Screen rows"
    SCREEN_WIDTH = "Screen columns"
    RETURN_KEY = "Return/Enter"
    TRANSLATION = "Character translation"
    # colors for [bracket reader] text highlighting on C64/128:
    TEXT_COLOR = "Text color"
    HIGHLIGHT_COLOR = "Highlight color"
    BACKGROUND_COLOR = "Background color"
    BORDER_COLOR = "Border color"


class Translation(str, Enum):
    PETSCII = "PetSCII"
    ASCII = "ASCII"
    ANSI = "ANSI"


class ClientValues(int, Enum):
    name: str
    rows: int
    columns: int
    translation: Translation
    # '1' [ColorValue] or "white" [ColorName], possibly:
    text_color: int | str
    background: int | str
    border: int | str
