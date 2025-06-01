import logging
from dataclasses import dataclass

from enum import Enum
import codecs
import cbmcodecs2
from colorama import init, Fore

# Define a custom error handling function
def replace_with_color_code(exception):
    return '?', exception.start + 1

class Translation(str, Enum):
    PETSCII = "PetSCII"
    ANSI = "ANSI"

#@dataclass
class Player:
    translation: Translation = Translation.PETSCII

    def output(self, string: str):
        """
        Outputs the given string, replacing color codes within braces {}
        with the corresponding CBM or Colorama color codes, depending on
        the Player.TerminalType setting.

        :param string: The input string containing color codes.
        :return string: transformed string
        """
        """
        >>> print(f"{colorama.Fore.RED}Hello {colorama.Fore.GREEN}There {colorama.Fore.RESET}")
        """
        encoded_string = ""
        if self.translation == Translation.PETSCII:
            codec = "petscii_c64en_lc"
        elif self.translation == Translation.ANSI:
            codec = 'utf-8'
        i = 0
        while i < len(string):
            if string[i] == '{':
                end_brace = string.find('}', i)
                if end_brace != -1:
                    color_name = string[i+1:end_brace].upper()
                    logging.debug("color_name: %s" % color_name)
                    try:
                        # Get the color code value:
                        if self.translation == Translation.PETSCII:
                            color_code = chr(int(getattr(CBMColors, color_name).value))
                            logging.debug("color_code (CBM): %s" % repr(color_code))
                            encoded_string += color_code
                        elif self.translation == Translation.ANSI:
                            color_code = getattr(ColoramaColors, color_name).value
                            logging.debug("color_code (ANSI): %s" % repr(color_code))
                            if color_code != 'None':
                                # if the ANSI terminal don't support the CBM colors, the mapping will be None:
                                encoded_string += color_code
                        # Move pointer after closing brace:
                        i = end_brace
                    except AttributeError:
                        # this is expected:
                        # WARNING:root:Unknown color: PLUM
                        logging.warning(f"Unknown color: {color_name}")
                        i = end_brace + 1
                        continue
            else:
                # not a color code:
                try:
                    # encoded_string += string[i].encode(codec)
                    encoded_string += string[i]
                except UnicodeEncodeError:
                    logging.warning(f"Unable to encode character: {string[i]}")
            # advance pointer:
            i += 1
        # Simplified hex output
        logging.info(f"Encoded string (hex): {bytes(encoded_string, encoding=codec).hex(' ')}")
        return encoded_string

class CBMColors(str, Enum):
    BLACK = 144
    WHITE = 5
    RED = 28
    CYAN = 159
    PURPLE = 156
    DARK_GREEN = 30
    DARK_BLUE = 31
    YELLOW = 158
    ORANGE = 129
    BROWN = 149
    LIGHT_RED = 150
    DARK_GRAY = 151
    MEDIUM_GRAY = 152
    LIGHT_GREEN = 153
    LIGHT_BLUE = 154
    LIGHT_GRAY = 155
    RESET = MEDIUM_GRAY  # TODO: player's default color


class ColoramaColors(str, Enum):
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

if __name__ == '__main__':
    # Register the error handler
    # codecs.register_error('custom_replace', replace_with_color_code)

    # initialize colorama
    init()

    # set up logging level:
    logging.basicConfig(format='%(levelname)10s | %(funcName)15s() | %(message)s',
                        level=logging.DEBUG)

    player = Player(translation=Translation.ANSI)

    # Example usage
    print(player.output("{red}Red {orange}Orange {yellow}Yellow {dark_green}Green {dark_blue}Blue {purple}Purple "
                        "{cyan}Cyan{reset}! {plum}"))