import abc
import logging
from datetime import datetime, timedelta
from typing import Optional

from astral import LocationInfo, sun, moon
import pytz  # python time zones
from enum import Enum

# import create_character
from combat import CombatSystem, Monster

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)10s | %(funcName)15s() | %(message)s')


class Season(Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"  # Or FALL = "fall"
    WINTER = "winter"
    UNKNOWN = "unknown"  # For initial state or errors


# --- NEW: Terrain Enumeration ---
class Terrain(Enum):
    OUTDOORS = "outdoors"
    IN_BUILDING = "in_building"
    INDOORS_CAVE = "indoors_cave"
    SNOWY = "snowy"  # Specific for snowy areas
    FOREST = "forest"  # Specific for forests
    # Add more as needed, e.g.:
    WATER = "water"
    # URBAN = "urban"
    DESERT = "desert"

    def __str__(self):
        return self.value


# --- Game Clock and Location Information ---
# In GameClock class definition:
class GameClock:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GameClock, cls).__new__(cls)
        return cls._instance

    def __init__(self, start_date=None, location_name="Puyallup, WA", region="USA",
                 timezone_name="America/Los_Angeles", latitude=47.195, longitude=-122.290):
        if not hasattr(self, '_initialized'):
            self.location_info = LocationInfo(location_name, region, timezone_name, latitude, longitude)
            local_tz = pytz.timezone(timezone_name)

            self.current_datetime = start_date if start_date else datetime.now(pytz.utc).astimezone(local_tz)
            if self.current_datetime.tzinfo is None:  # Ensure it's localized if a naive datetime was passed
                self.current_datetime = local_tz.localize(self.current_datetime)

            # NEW: Clock control
            self._is_fixed_time = False
            # False means game time advances with p actions (default)
            # True means game time runs on wall clock (real) time
            self._fixed_time_minutes_per_action = 5  # How many minutes advance per p action in fixed mode

            self._current_season = self._determine_season()  # Determine initial season

            logging.info(f"GameClock initialized. Current game time: {self.current_datetime}")
            logging.info(f"Game Location: {self.location_info.name} ({self.location_info.timezone})")
            self._initialized = True

    def get_current_datetime(self):
        # If in wall clock mode, return actual current time
        if not self._is_fixed_time:
            local_tz = pytz.timezone(self.location_info.timezone)
            return datetime.now(pytz.utc).astimezone(local_tz)
        return self.current_datetime

    def advance_time(self, minutes=None):
        """Advances game time by a specified number of minutes.
        If in fixed time mode, it advances by a set amount or specific minutes."""
        if self._is_fixed_time:
            # In fixed time, use the configured minutes per action or override
            minutes_to_advance = minutes if minutes is not None else self._fixed_time_minutes_per_action
            self.current_datetime += timedelta(minutes=minutes_to_advance)
            logging.debug(
                f"Game time advanced by {minutes_to_advance} minutes (fixed mode). New time: {self.current_datetime}")
        else:
            # In wall clock mode, time advances automatically, so this call does nothing
            logging.debug("Game time is running on wall clock; advance_time call ignored.")
            pass  # No explicit advancement needed; get_current_datetime handles it.

        # Always update season when time is logically advanced or retrieved for consistency
        self._current_season = self._determine_season()

    # NEW: Methods for debug control
    def set_fixed_time_mode(self, enable: bool):
        """Sets whether the game clock advances only on p actions (True) or runs on real-world time (False)."""
        self._is_fixed_time = enable
        mode_str = "fixed (per-action advancement)" if enable else "wall clock (real-time)"
        logging.info(f"GameClock mode set to: {mode_str}.")
        print(f"Game time is now {mode_str}.")

    def is_fixed_time_mode(self):
        """Returns True if the clock is in fixed time mode, False if in wall clock mode."""
        return self._is_fixed_time

    def set_datetime(self, year, month, day, hour=0, minute=0, second=0):
        """Sets the game's current date and time to a specific value."""
        try:
            local_tz = pytz.timezone(self.location_info.timezone)
            new_dt = local_tz.localize(datetime(year, month, day, hour, minute, second))
            self.current_datetime = new_dt
            self._current_season = self._determine_season()  # Recalculate season immediately
            logging.info(f"Game clock set to: {self.current_datetime}. Season: {self._current_season.value}")
            print(
                f"Game clock set to: {self.current_datetime.strftime('%Y-%m-%d %H:%M:%S')}."
                f" Current season: {self._current_season.value.capitalize()}.")
            return True
        except Exception as e:
            logging.error(f"Failed to set datetime: {e}")
            print(f"Error setting time: {e}. Please use YYYY MM DD HH MM SS format.")
            return False

    def jump_to_season(self, season_name: str):
        """Attempts to jump to a date representing the middle of the specified season."""
        season_map = {
            "spring": (3, 20),  # March 20th
            "summer": (6, 20),  # June 20th
            "autumn": (9, 20),  # September 20th
            "winter": (12, 20)  # December 20th
        }
        season_name_lower = season_name.lower()
        if season_name_lower in season_map:
            month, day = season_map[season_name_lower]
            current_year = self.current_datetime.year
            # Use noon for a consistent time of day
            return self.set_datetime(current_year, month, day, 12, 0, 0)
        else:
            print(f"Invalid season '{season_name}'. Choose from: {', '.join(season_map.keys())}.")
            logging.warning(f"Attempted to jump to invalid season: {season_name}.")
            return False

    def get_current_season(self):
        """Returns the current season as a Season Enum member."""
        return self._current_season

    def _determine_season(self):
        """Determines the current season based on the month of current_datetime."""
        month = self.current_datetime.month
        if 3 <= month <= 5:
            logging.info("Season has advanced into Spring.")
            return Season.SPRING
        elif 6 <= month <= 8:
            logging.info("Season has advanced into summer.")
            return Season.SUMMER
        elif 9 <= month <= 11:
            logging.info("Season has advanced into Autumn.")
            return Season.AUTUMN
        elif month == 12 or 1 <= month <= 2:
            logging.info("Season has advanced into Winter.")
            return Season.WINTER
        else:
            logging.warning("Season is unknown!")
            return Season.UNKNOWN  # Should not happen with valid dates

    def get_solar_event_info(self):
        """Returns string description of current solar event (day, night, dawn, dusk)."""
        s = sun.sun(self.location_info.observer, date=self.current_datetime.date(), tzinfo=self.location_info.timezone)
        current_time = self.current_datetime.astimezone(None).time()

        dawn_start = s['dawn'].time()
        sunrise_start = s['sunrise'].time()
        sunset_end = s['sunset'].time()
        dusk_end = s['dusk'].time()

        if dawn_start <= current_time < sunrise_start:
            return "the faint glow of dawn breaking"
        elif sunrise_start <= current_time < sunset_end:
            return "daylight"
        elif sunset_end <= current_time < dusk_end:
            return "the twilight hours"
        else:
            return "night"

    def get_detailed_solar_description(self):
        """Returns a detailed string description for the window."""
        s = sun.sun(self.location_info.observer, date=self.current_datetime.date(), tzinfo=self.location_info.timezone)
        current_dt_local = self.current_datetime.astimezone(None)
        current_time = current_dt_local.time()

        dawn_start = s['dawn'].time()
        sunrise_start = s['sunrise'].time()
        noon = s['noon'].time()
        sunset_end = s['sunset'].time()
        dusk_end = s['dusk'].time()

        is_night = (current_time >= dusk_end) or (current_time < dawn_start)

        if dawn_start <= current_time < sunrise_start:
            return "the first light of dawn breaking, painting the horizon with soft colors."
        elif sunrise_start <= current_time < noon:
            return "the early morning sun shining brightly."
        elif noon <= current_time < sunset_end:
            return "the afternoon sun casting long shadows."
        elif sunset_end <= current_time < dusk_end:
            return "the golden light of dusk, as the sun dips below the horizon."
        elif is_night:
            moon_phase = self.get_moon_phase_description()
            return (f"night, with stars twinkling faintly. "
                    f" The moon, currently {moon_phase}, hangs in the sky.")
        else:
            return "the shifting light, though the exact time is unclear."

    def get_moon_phase_description(self):
        """Returns a string description of the current moon phase."""
        phase = moon.phase(self.current_datetime.date())
        if 0 <= phase < 1.84:
            return "a New Moon"
        if 1.84 <= phase < 5.53:
            return "a Waxing Crescent moon"
        if 5.53 <= phase < 9.22:
            return "a First Quarter moon"
        if 9.22 <= phase < 12.91:
            return "a Waxing Gibbous moon"
        if 12.91 <= phase < 16.61:
            return "a Full Moon"
        if 16.61 <= phase < 20.3:
            return "a Waning Gibbous moon"
        if 20.3 <= phase < 24.99:
            return "a Last Quarter moon"
        if 24.99 <= phase < 27.78:
            return "a Waning Crescent moon"
        return "a New Moon"

    def set_logging_level(self, level_name: str):
        """Sets the global logging level for the application."""
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
        level = level_map.get(level_name.lower())
        if level is not None:
            logging.getLogger().setLevel(level)  # Set the root logging level
            print(f"Logging level set to {level_name.upper()}.")
            logging.info(f"Logging level changed to {level_name.upper()}.")
            return True
        else:
            print(f"Invalid logging level '{level_name}'. Choose from:")
            for level in level_map.values():
                print(level)
            logging.warning(f"Attempted to set invalid logging level: {level_name}.")
            return False


# GameClock initialized with actual current time in Puyallup
location_timezone_name = "America/Los_Angeles"
local_timezone = pytz.timezone(location_timezone_name)
current_actual_time = datetime.now(pytz.utc).astimezone(local_timezone)
game_clock = GameClock(start_date=current_actual_time)


# --- 1. Receiver: Game Objects ---
class Player:
    def __init__(self, name="Hero"):
        self.name = name
        self.inventory = []
        self.current_room = None
        self.description = "As good-looking as ever."

        # NEW: Combat stats
        self.max_health = 100  # Maximum health
        self.current_health = 100  # Current health
        self.attack_power = 20  # Base attack damage

        logging.info(f"Player '{self.name}' initialized (HP: {self.current_health}, ATK: {self.attack_power}).")

    # NEW: Combat methods for Player
    def is_alive(self):
        return self.current_health > 0

    def take_damage(self, amount):
        self.current_health -= amount
        if self.current_health < 0:
            self.current_health = 0
        logging.debug(f"{self.name} took {amount} damage. Remaining HP: {self.current_health}.")
        print(f"You take {amount} damage! ({self.current_health}/{self.max_health} HP remaining)")
        if not self.is_alive():
            print("You collapse, unable to continue...")

    def get_item_from_inventory(self, item_name):
        """Helper to get an item from inventory by name (string match, not item object)."""
        return next((item for item in self.inventory if item_name.lower() in item.aliases), None)

    def add_item(self, item):
        self.inventory.append(item)
        item.current_terrain_types = []  # Item is now in inventory, no terrain type
        logging.debug(f"{self.name} picked up the {item.name}.")
        print(f"{self.name} picked up the {item.name}.")

    def describe_self(self):
        # Method to describe the p themselves
        print(f"\nYou look at yourself. {self.description}\n")
        # You could also add more details here, like:
        # TODO: print(f"You are currently wearing: (not implemented yet)")
        # TODO: print(f"You are carrying: {', '.join([item.name for item in self.inventory]) if
        #   self.inventory else 'nothing'}.")

    def remove_item(self, item):
        if item in self.inventory:
            self.inventory.remove(item)
            # Item is about to be dropped into current_room, so its location will be set there
            logging.debug(f"{self.name} dropped the {item.name}.")
            print(f"{self.name} dropped the {item.name}.")
            return True
        logging.warning(f"{self.name} tried to drop {item.name} but doesn't have it.")
        print(f"{self.name} doesn't have the {item.name}.")
        return False

    def get_all_interactable_items(self):
        """Returns a combined list of items in the current room and in p's inventory."""
        return self.current_room.items + self.inventory

    def move_to(self, room):
        # Also update p.move_to to show monsters:
        self.current_room = room
        logging.debug(f"{self.name} moved to {room.name}.")
        # NEW: Display the transition message if it exists
        if room.transition_message:
            print(f"\n{room.transition_message}")

        print(room.name)
        print(room.get_full_description())
        print(f"Exits: {', '.join(room.exits.keys())}")
        if room.items:
            print(f"Ye see: {', '.join([item.name for item in room.items])}.")
        # NEW: Display monsters
        if room.monsters:
            print(f"You see a {', '.join([m.name for m in room.monsters])} here.")

    def look(self):
        logging.debug(f"Player '{self.name}' performed general 'look' action.")
        print(f"You are in the {self.current_room.name}.")
        print(self.current_room.get_full_description())
        if self.current_room.items:
            item_names_and_desc = []
            for item in self.current_room.items:
                item_names_and_desc.append(item.name)  # For the quick list, just the name
            print(f"You see: {', '.join(item_names_and_desc)}.")
        else:
            print("There are no items here.")
        print(f"Exits: {', '.join(self.current_room.exits.keys())}.")
        print(f"Your inventory: {', '.join([item.name for item in self.inventory]) if self.inventory else 'empty'}.")

    def examine_item(self, item):
        logging.debug(f"Player '{self.name}' examining item: {item.name}.")
        # Pass the current room's terrain types to get the context-sensitive description
        print(f"\n{item.name}: {item.get_description(self.current_room.terrain_types)}\n")


class Item:
    def __init__(self, name, base_description: str, readable: bool = False, read_text: str = "",
                 terrain_descriptions: Optional[dict] = None, aliases=None,
                 season_descriptions=None):
        self.name = name
        self.base_description = base_description
        self.readable = readable
        self.read_text = read_text
        self.terrain_descriptions = terrain_descriptions if terrain_descriptions is not None else {}
        # NEW: Dictionary for season-specific item descriptions
        self.season_descriptions = season_descriptions if season_descriptions is not None else {}
        self.current_terrain_types = []  # This is for current *location* terrain, not item's inherent terrain

        self.aliases = set()
        self.aliases.add(name.lower())
        if aliases:
            for alias in aliases:
                self.aliases.add(alias.lower())

        for word in name.lower().split():
            self.aliases.add(word)

        logging.debug(f"Item '{self.name}' created with aliases: {self.aliases}.")

    def get_description(self, current_terrain_types):
        """Returns the appropriate description based on the item's current terrain types and season."""
        # Prioritize inventory description if applicable
        if not current_terrain_types and "inventory" in self.terrain_descriptions:
            return self.terrain_descriptions["inventory"]

        # NEW: Check for season-specific description
        current_season = game_clock.get_current_season()
        if current_season in self.season_descriptions:
            return self.season_descriptions[current_season]

        # Then check for specific terrain type descriptions
        if Terrain.SNOWY in current_terrain_types and Terrain.SNOWY in self.terrain_descriptions:
            return self.terrain_descriptions[Terrain.SNOWY]

        if Terrain.FOREST in current_terrain_types and Terrain.FOREST in self.terrain_descriptions:
            return self.terrain_descriptions[Terrain.FOREST]

        if Terrain.INDOORS_CAVE in current_terrain_types and Terrain.INDOORS_CAVE in self.terrain_descriptions:
            return self.terrain_descriptions[Terrain.INDOORS_CAVE]

        if Terrain.IN_BUILDING in current_terrain_types and Terrain.IN_BUILDING in self.terrain_descriptions:
            return self.terrain_descriptions[Terrain.IN_BUILDING]

        # Finally, if OUTDOORS is present and no more specific terrain matched, use it
        if Terrain.OUTDOORS in current_terrain_types and Terrain.OUTDOORS in self.terrain_descriptions:
            return self.terrain_descriptions[Terrain.OUTDOORS]

        # If no specific season or terrain description matches, return the base description
        return self.base_description


class Room:
    def __init__(self, name, description, transition_message, terrain_types, has_window=False,
                 season_descriptions=None):
        self.name = name
        self.base_description = description
        self.transition_message = transition_message
        self.exits = {}
        self.items = []
        self.terrain_types = terrain_types
        self.has_window = has_window
        self.season_descriptions = season_descriptions if season_descriptions is not None else {}
        self.monsters = []  # NEW: List to hold monsters in the room

        logging.debug(
            f"Room '{self.name}' created (terrain: {[t.value for t in self.terrain_types]}, has_window: {self.has_window}).")

    def add_exit(self, direction, room):
        self.exits[direction] = room
        logging.debug(f"Added exit '{direction}' from '{self.name}' to '{room.name}'.")

    def add_item(self, item):
        self.items.append(item)
        item.current_terrain_types = self.terrain_types
        logging.debug(f"Added item '{item.name}' to room '{self.name}'.")

    # NEW: Methods to add/remove monsters
    def add_monster(self, monster):
        self.monsters.append(monster)
        logging.debug(f"Added monster '{monster.name}' to room '{self.name}'.")

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            item.current_terrain_types = []
            logging.debug(f"Removed item '{item.name}' from room '{self.name}'.")
            return True
        logging.warning(f"Attempted to remove '{item.name}' from '{self.name}' but it wasn't there.")
        return False

    def remove_monster(self, monster):
        if monster in self.monsters:
            self.monsters.remove(monster)
            logging.debug(f"Removed monster '{monster.name}' from room '{self.name}'.")
            return True
        logging.warning(f"Attempted to remove '{monster.name}' from '{self.name}' but it wasn't there.")
        return False

    def get_full_description(self):
        current_season = game_clock.get_current_season()
        # base description is always shown.
        full_desc = [self.base_description]
        # if seasonal flavor text exists, append it:
        if current_season in self.season_descriptions:
            full_desc.append(self.season_descriptions[current_season])

        solar_desc = game_clock.get_detailed_solar_description()
        if self.has_window:
            window_desc = f"\nThrough a nearby window, you see {solar_desc}"
            full_desc.append(window_desc)
        if self.terrain_types == Terrain.OUTDOORS:
            full_desc.append(f"\nIn the sky, you see {solar_desc}")
        return " ".join(full_desc)

    def get_item_from_room(self, item_name):
        """Helper to get an item from the room by name (string match, not item object)."""
        # This iterates through the items in the room and checks if the given
        # item_name (lowercase) matches the item's name or any of its aliases.
        return next((item for item in self.items if item_name.lower() in item.aliases), None)


# --- 2. Command Interface ---
class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self):
        """
        Base method for command execution.
        Subclasses should override this with specific command logic.
        """
        pass


# --- 3. Concrete Command Classes ---
# Create this new class alongside your other Command classes
class AttackCommand(Command):
    def __init__(self, player, combat_system, target_monster=None):
        self.player = player
        self.combat_system = combat_system
        self.target_monster = target_monster  # Will be None, or Monster object if in combat

    def execute(self):
        """Usage: attack [monster_name]
        Initiates combat with a monster or attacks the current monster.
        Example: 'attack goblin'"""
        logging.info(
            f"Executing AttackCommand (target: {self.target_monster.name if self.target_monster else 'current_monster'}).")

        if self.combat_system.in_combat:
            # If already in combat, and the target is the current monster, perform attack
            if self.target_monster and self.target_monster == self.combat_system.current_monster:
                self.combat_system.player_attack(self.player, self.target_monster)
                return True
            elif not self.target_monster and self.combat_system.current_monster:
                # If no target specified but already in combat, assume attack current monster
                self.combat_system.player_attack(self.player, self.combat_system.current_monster)
                return True
            else:
                print(f"You are already fighting the {self.combat_system.current_monster.name}. Focus your attack!")
                return False
        else:
            # Not in combat, try to start it
            if self.target_monster:
                return self.combat_system.start_combat(self.player, self.target_monster)
            else:
                print("Attack what? You are not in combat.")
                logging.warning("AttackCommand failed: no target and not in combat.")
                return False


def menu_handler(title: str, choices: dict):
    """
    Generate and handle a menu system.
    :param title: str, to which " Menu" is automatically appended
    :param choices: dict of {"<letter>": "text"} - EXPECTS LOWERCASE KEYS
    :return: choice (the letter of the option), or None if user selected "exit"
    """
    header = f"--- {title} Menu ---"
    while True:
        print(f"\n{header}")  # Added newline for readability
        for item, text in choices.items():
            print(f"{item.upper()}: {text}")
        print('-' * len(header))
        choice = input("Enter your choice: ").strip().lower()  # Convert input to lowercase

        if not choice:  # Empty input means exit
            print("Exiting.")
            return None
        if choice in choices.keys():  # This check now works because both are lowercase
            logging.info("Choice '%s' made" % choice)
            return choice
        else:
            print("Invalid choice.")


class DebugCommand(Command):
    def __init__(self, game_clock):
        self.game_clock = game_clock
        logging.debug("DebugCommand instance created.")

    def execute(self):
        """Usage: debug
        Opens a debug menu for time, season, and logging level manipulation."""
        while True:
            logging.info("Executing DebugCommand.")
            clock_mode = "Wall clock" if not self.game_clock.is_fixed_time_mode() else "Fixed time"
            menu_items = {"c": f"Toggle Game Clock Mode (using {clock_mode})",
                          "d": "Set Specific Date and Time",
                          "j": "Jump to Season",
                          "l": "Change Logging Level",
                          }
            choice = menu_handler(title="Debug", choices=menu_items)
            if choice == 'c':
                self.toggle_clock_mode()
            elif choice == 'd':
                self.set_specific_datetime()
            elif choice == 'j':
                self.jump_to_season()
            elif choice == 'l':
                self.change_logging_level()
            elif choice is None:
                # print("Exiting Debug Menu.")
                logging.debug("Exited Debug Menu.")
                return True  # Command completed

    def toggle_clock_mode(self):
        current_mode = self.game_clock.is_fixed_time_mode()
        self.game_clock.set_fixed_time_mode(not current_mode)

    def set_specific_datetime(self):
        date_params = "YYYY MM DD HH MM SS"
        print(f"\nEnter target date and time ({date_params}, e.g., 2025 03 15 14 30 00):")
        time_input = input("Date> ").strip().split()
        if len(time_input) == 6:
            try:
                year, month, day, hour, minute, second = map(int, time_input)
                self.game_clock.set_datetime(year, month, day, hour, minute, second)
            except ValueError:
                print(f"Invalid number format. Please use integers for {date_params}.")
        else:
            print(f"Incorrect number of arguments. Please provide {date_params}.")

    def jump_to_season(self):
        while True:
            choices = {"sp": "Spring",
                       "su": "Summer",
                       "a": "Autumn",
                       "w": "Winter"}
            season_abbrreviation = menu_handler("Seasons", choices)
            if season_abbrreviation:
                season_name = choices[season_abbrreviation]
                self.game_clock.jump_to_season(season_name)
                return True
            elif season_abbrreviation is None:
                print("No season change.")

    def change_logging_level(self):
        choices = {"D": "Debug",
                   "I": "Info",
                   "W": "Warning",
                   "E": "Error",
                   "C": "Critical",
                   }
        choice = menu_handler("Logging Level", choices)
        if choice is None:
            print("Logging level unchanged.")
            logging.info("Logging level unchanged.")
            return True
        else:
            logging_level = choices[choice].upper()
            self.game_clock.change_logging_level(logging_level)
            return None


class GoCommand(Command):
    def __init__(self, player, direction):
        self.player = player
        self.direction = direction
        logging.debug(f"GoCommand instance created for direction: '{self.direction}'.")

    def execute(self):
        """Usage: go <direction>
        Move in a cardinal direction (north, south, east, west).
        Example: 'go north'"""
        logging.info(f"Executing GoCommand for direction: '{self.direction}'.")
        target_room = self.player.current_room.exits.get(self.direction)
        if target_room:
            self.player.move_to(target_room)
            game_clock.advance_time(minutes=5)
            logging.debug(f"GoCommand successful: moved to {target_room.name}.")
            return True
        else:
            logging.warning(f"GoCommand failed: no exit in direction '{self.direction}'.")
            print(f"You can't go {self.direction} from here.")
            return False


class TakeCommand(Command):
    def __init__(self, player, item):  # item is now an Item object
        self.player = player
        self.item = item  # Store the actual Item object
        logging.debug(f"TakeCommand instance created for item: '{self.item.name}'.")

    def execute(self):
        """Usage: take <item_name>
        Pick up an item from the current room.
        Example: 'take sword'"""
        logging.info(f"Executing TakeCommand for item: '{self.item.name}'.")
        # Check if the item is still in the room (e.g., p didn't drop it elsewhere before taking)
        if self.item in self.player.current_room.items:
            self.player.current_room.remove_item(self.item)
            self.player.add_item(self.item)
            game_clock.advance_time(minutes=1)
            logging.debug(f"TakeCommand successful: {self.item.name} taken.")
            return True
        else:
            logging.warning(f"TakeCommand failed: '{self.item.name}' not found in room (after disambiguation).")
            print(f"The {self.item.name} is no longer here.")  # Should ideally not happen if logic is tight
            return False


class DropCommand(Command):
    def __init__(self, player, item):  # item is now an Item object
        self.player = player
        self.item = item
        logging.debug(f"DropCommand instance created for item: '{self.item.name}'.")

    def execute(self):
        """Usage: drop <item_name>
        Drop an item from your inventory into the current room.
        Example: 'drop key'"""
        logging.info(f"Executing DropCommand for item: '{self.item.name}'.")
        if self.item in self.player.inventory:  # Check if p still has it
            self.player.remove_item(self.item)
            self.player.current_room.add_item(self.item)
            game_clock.advance_time(minutes=1)
            logging.debug(f"DropCommand successful: {self.item.name} dropped.")
            return True
        else:
            logging.warning(f"DropCommand failed: '{self.item.name}' not found in inventory (after disambiguation).")
            print(f"You don't have the {self.item.name} anymore.")
            return False


class FleeCommand(Command):
    def __init__(self, player, combat_system, current_monster=None):
        self.player = player
        self.combat_system = combat_system
        self.current_monster = current_monster  # Only relevant if in combat

    def execute(self):
        """Usage: flee
        Attempts to flee from the current combat encounter."""
        logging.info("Executing FleeCommand.")
        if self.combat_system.in_combat and self.current_monster:
            self.combat_system.flee_combat(self.player, self.current_monster)
            return True
        else:
            print("You are not currently in combat.")
            logging.warning("FleeCommand failed: not in combat.")
            return False


class LookCommand(Command):
    def __init__(self, player, target_object=None):  # target_object is now an Item object or None
        self.player = player
        self.target_object = target_object  # Could be Item or None
        logging.debug(
            f"LookCommand instance created (target: {self.target_object.name if self.target_object else 'Room'}).")

    def execute(self):
        """Usage: look [object_name]
        Describe your current surroundings and items in the room.
        If an object name is provided, describe that specific object (in room or inventory).
        Examples: 'look', 'look sword', 'look key'"""
        logging.info(f"Executing LookCommand (target: {self.target_object.name if self.target_object else 'Room'}).")

        if self.target_object:  # If an Item object was passed
            self.player.examine_item(self.target_object)
            logging.debug(f"LookCommand successful: described item '{self.target_object.name}'.")
        else:  # No specific object, perform general room look
            self.player.look()
            logging.debug("LookCommand successful: described current room.")

        game_clock.advance_time(minutes=1)
        return True


class InventoryCommand(Command):
    def __init__(self, player):
        self.player = player
        logging.debug("InventoryCommand instance created.")

    def execute(self):
        """Usage: inventory or inv
        List items currently in your inventory."""
        logging.info("Executing InventoryCommand.")
        if self.player.inventory:
            logging.debug(f"InventoryCommand showing inventory: {[item.name for item in self.player.inventory]}.")
            print(f"Your inventory:")
            for num, item in enumerate(self.player.inventory, start=1):
                desc = item.get_description(['inventory'])  # force inventory desc
                print(f"{num: 2}. {item.name.ljust(20)} {desc}")
        else:
            logging.debug("InventoryCommand showing empty inventory.")
            print("Your inventory is empty.")
        game_clock.advance_time(minutes=1)
        return True


class ReadCommand(Command):
    def __init__(self, player, item):  # item is now an Item object
        self.player = player
        self.item = item
        logging.debug(f"ReadCommand instance created for item: '{self.item.name}'.")

    def execute(self):
        """Usage: read <item_name>
        Read the text content of a readable item in your inventory.
        Example: 'read manual'"""
        logging.info(f"Executing ReadCommand for item: '{self.item.name}'.")
        # Ensure the item is still in p's inventory
        if self.item in self.player.inventory:
            if self.item.readable:
                print(f"\nYou read the {self.item.name}:")
                print("---")
                print(self.item.read_text)
                print("---\n")
                game_clock.advance_time(minutes=2)
                logging.debug(f"ReadCommand successful: '{self.item.name}' read.")
                return True
            else:
                print(f"You can't read the {self.item.name}.")
                logging.warning(f"ReadCommand failed: '{self.item.name}' is not readable.")
                return False
        else:
            print(f"You don't have the {self.item.name} anymore.")  # Should ideally not happen if logic is tight
            logging.warning(f"ReadCommand failed: '{self.item.name}' not in inventory (after disambiguation).")
            return False


class HelpCommand(Command):
    def __init__(self, parser_commands, target_command_name=None):
        self.parser_commands = parser_commands
        self.target_command_name = target_command_name
        logging.debug(f"HelpCommand instance created (target: {self.target_command_name or 'All'}).")

    def execute(self):
        """Usage: help [command_name]
        Display a list of all available commands and their usage,
        or provide detailed help for a specific command."""
        logging.info(f"Executing HelpCommand (target: {self.target_command_name or 'All'}).")

        if self.target_command_name:
            command_class = self.parser_commands.get(self.target_command_name)
            if command_class:
                doc = getattr(command_class.execute, '__doc__', None)
                if doc:
                    print(f"\n--- Help for '{self.target_command_name}' ---")
                    print(doc.strip())
                    print("--------------------------------------\n")
                    logging.debug(f"Help for '{self.target_command_name}' displayed.")
                else:
                    print(f"No detailed help available for '{self.target_command_name}'.")
                    logging.warning(f"No docstring found for '{self.target_command_name}'.")
            else:
                print(f"Command '{self.target_command_name}' not recognized. Type 'help' for a list of commands.")
                logging.warning(f"Help requested for unrecognized command: '{self.target_command_name}'.")
        else:
            print("\n--- Available Commands ---")
            for verb, cmd_class in sorted(self.parser_commands.items()):
                doc = getattr(cmd_class.execute, '__doc__', None)
                usage_line = "(No usage info available)"
                if doc:
                    lines = doc.strip().split('\n')
                    usage_line = lines[0].strip()
                print(f"- {verb.ljust(12)}: {usage_line}")
            print("--------------------------\n")
            logging.debug("All commands help displayed.")
        return True


# --- 4. Invoker: The Game Parser ---
class GameParser:
    def __init__(self, player):
        self.player = player
        # NEW: Initialize CombatSystem
        self.combat_system = CombatSystem(game_clock)  # Will be initialized later in game setup
        self.commands = {
            "debug": DebugCommand,
            "go": GoCommand,
            "get": TakeCommand,
            "take": TakeCommand,
            "drop": DropCommand,
            "look": LookCommand,
            "inventory": InventoryCommand,
            "inv": InventoryCommand,
            "read": ReadCommand,
            "help": HelpCommand,
            "attack": AttackCommand,  # NEW
            "fight": AttackCommand,  # NEW alias for attack
            "flee": FleeCommand,  # NEW
        }
        # NEW: Disambiguation state
        self.disambiguation_pending = False
        self.disambiguation_candidates = []  # List of Item objects
        self.pending_command_class = None
        self.pending_command_verb = None
        logging.info("GameParser initialized.")

    def _find_matching_items(self, parsed_object_phrase):
        """
        Finds items whose aliases match the parsed object phrase.
        Returns a list of matching Item objects.
        Prioritizes exact matches of the full phrase, then matches by individual words.
        """
        all_interactable_items = self.player.get_all_interactable_items()
        matches = []
        parsed_words = set(parsed_object_phrase.split())  # Use a set for faster lookups

        # --- Phase 1: Exact match of the entire phrase to an item's full name or alias ---
        for item in all_interactable_items:
            if parsed_object_phrase == item.name.lower():
                matches.append(item)
                # If there's an exact name match, we heavily prioritize it.
                # If multiple items have the exact same name (e.g., "red ball", "red ball"),
                # we'd still add both and let disambiguation handle it.
                # For now, if we found an exact name, it's a very strong candidate.
            elif parsed_object_phrase in item.aliases:
                # If the entire phrase is one of the item's aliases, it's also a strong match
                matches.append(item)

        if len(matches) == 1:
            return matches  # Unique exact match
        elif len(matches) > 1:
            # If multiple items have the same exact name/alias, disambiguate those first.
            # Example: two items both named "key" (unlikely, but possible in complex games).
            # Or if "manual" is an alias for both "Telescope Manual" and "Repair Manual".
            return matches

        # --- Phase 2: Adjective-Noun (partial word) matching ---
        # Only proceed if no strong exact matches were found, or multiple strong matches exist
        # and we want to allow partials to potentially add more context.
        # This part requires careful tuning. For a simple parser, we'll collect any item
        # that has *any* of the words in its aliases, and then let disambiguation sort it out.
        # This will lead to more disambiguation prompts, but is safer than guessing.

        # Clear matches if we are moving to partial match (so we don't duplicate or mix exact/partial)
        # Re-collect all potential items if previous phase didn't yield a single unique match.
        matches = []

        for item in all_interactable_items:
            # Check if all words in the input phrase are present in the item's aliases.
            # This is a simple form of "adjective-noun" matching: "red ball" -> item with "red" and "ball"
            if all(word in item.aliases for word in parsed_words):
                matches.append(item)

        # If still no perfect matches, look for any word match as a last resort
        if not matches:
            for item in all_interactable_items:
                if any(word in item.aliases for word in parsed_words):
                    matches.append(item)

        return matches

    # NEW: _find_matching_monsters method (similar to _find_matching_items)
    def _find_matching_monsters(self, parsed_object_phrase):
        """Finds monsters in the current room whose names match the phrase."""
        all_monsters_in_room = self.player.current_room.monsters
        matches = []
        parsed_words = set(parsed_object_phrase.lower().split())

        for monster in all_monsters_in_room:
            # Check for exact name match
            if parsed_object_phrase == monster.name.lower():
                matches.append(monster)
            # Check if all words in the phrase are in the monster's name (basic alias for now)
            elif all(word in monster.name.lower() for word in parsed_words):
                matches.append(monster)
        # For simplicity, no disambiguation for monsters yet, just return first match or all if multiple match logic.
        # In a real scenario, you'd want disambiguation for monsters too.
        # For now, let's just return the first if found or an empty list.
        if matches:
            return [matches[0]]
        return []

    def parse_and_execute(self, command_string):
        logging.info(f"Parsing user input: '{command_string}'.")
        original_command = command_string.strip()

        # Check if in combat and awaiting a combat-specific command
        if self.combat_system.in_combat:
            # Special handling for combat commands when in combat
            verb = original_command.lower().split(maxsplit=1)[0]
            if verb == "attack":
                # In combat, 'attack' just means attack the current monster
                command = AttackCommand(self.player, self.combat_system, self.combat_system.current_monster)
                command.execute()
                return True
            elif verb == "flee":  # Handle 'flee' during combat
                command = FleeCommand(self.player, self.combat_system, self.combat_system.current_monster)
                command.execute()
                return True
            elif verb in ["l", "look", "inventory", "inv", "help"]:
                # Allow these commands even in combat
                pass  # Let normal parsing handle it
            else:
                print("You are in combat! You can only 'attack', 'flee', 'look/inv/help'.")
                logging.warning(f"Invalid command '{verb}' during combat.")
                return False

        # Handle disambiguation responses (this block remains the same)
        if self.disambiguation_pending:
            resolved_item = None
            response_lower = original_command.lower()

            for item in self.disambiguation_candidates:
                if response_lower in item.aliases or item.name.lower().startswith(response_lower):
                    resolved_item = item
                    break

            if resolved_item:
                logging.debug(f"Disambiguation resolved to: {resolved_item.name}.")
                command_class = self.pending_command_class
                command_instance = command_class(self.player, resolved_item)  # Most common case is an item
                # Special handling if the pending command was for a monster (not yet implemented disambig)
                if command_class == AttackCommand:  # Need to pass combat_system too
                    command_instance = command_class(self.player, self.combat_system, resolved_item)

                command_instance.execute(writer, )
                self.disambiguation_pending = False
                self.disambiguation_candidates = []
                self.pending_command_class = None
                self.pending_command_verb = None
                self.pending_command_args_for_prompt = None
                return True
            else:
                print("I don't understand which one you mean. Please try again or type the full name.")
                logging.warning(f"Disambiguation failed for '{original_command}'.")
                return False

        # Normal command parsing
        parts = original_command.lower().split(maxsplit=1)
        verb = parts[0]
        args = parts[1] if len(parts) > 1 else None

        command_class = self.commands.get(verb)

        if command_class:
            logging.debug(f"Found command class for verb: '{verb}'.")
            command_instance = None

            # Handle commands that require an item (take, drop, read) or 'look'
            if verb in ["take", "drop", "read"] or (verb == "look" and args):
                if not args:
                    print(f"What do you want to {verb}?")
                    logging.warning(f"Missing arguments for '{verb}' command.")
                    return False

                # NEW: Special handling for "look me"
                if verb == "look" and args == "me":
                    self.player.describe_self()
                    game_clock.advance_time(minutes=1)
                    logging.debug("LookCommand successful: described p.")
                    return True  # Command handled, exit parse_and_execute

                # Original item-finding logic follows if not "look me"
                matching_items = self._find_matching_items(args)

                if len(matching_items) == 1:
                    item = matching_items[0]
                    command_instance = command_class(self.player, item)
                elif len(matching_items) > 1:
                    self.disambiguation_pending = True
                    self.disambiguation_candidates = matching_items
                    self.pending_command_class = command_class
                    self.pending_command_verb = verb
                    self.pending_command_args_for_prompt = args

                    print(f"Which {args} do you mean? You can choose from: " +
                          ", ".join([item.name for item in matching_items]) + ".")
                    logging.info(
                        f"Disambiguation required for '{args}'. Candidates: {[i.name for i in matching_items]}.")
                    return False
                else:
                    print(f"You don't see or have a '{args}'.")
                    logging.warning(f"No item found for '{args}' with verb '{verb}'.")
                    return False

            # NEW: Handle Attack/Fight commands
            elif verb in ["attack", "fight"]:
                if not args:
                    # If no args given, and not already in combat, what to attack?
                    print("Attack what?")
                    logging.warning("AttackCommand failed: no target specified.")
                    return False

                matching_monsters = self._find_matching_monsters(args)

                if len(matching_monsters) == 1:
                    monster = matching_monsters[0]
                    command_instance = AttackCommand(self.player, self.combat_system, monster)
                else:
                    # For simplicity, if no unique monster found or multiple, print message
                    print(f"There is no '{args}' to attack here, or you need to be more specific.")
                    logging.warning(f"AttackCommand failed: no unique monster found for '{args}'.")
                    return False

            # Commands that don't need item disambiguation (go, inventory, help, general look)
            elif verb == "debug":
                command_instance = command_class(game_clock)  # maybe?
            elif verb == "go":
                if args:
                    command_instance = command_class(self.player, args)
                else:
                    print("Go where?")
                    logging.warning("Missing direction for 'go' command.")
                    return False
            elif verb in ["inventory", "inv"]:
                command_instance = command_class(self.player)
            elif verb == "look":  # General 'look' (no args)
                command_instance = command_class(self.player, None)  # Pass None for target_object_name
            elif verb == "help":
                command_instance = command_class(self.commands, args)

            if command_instance:
                logging.debug(f"Attempting to execute command instance: {command_instance.__class__.__name__}.")
                command_instance.execute()
                logging.debug(f"Command instance {command_instance.__class__.__name__} execution completed.")
                return None
            else:
                logging.error(
                    "Failed to create command instance due to missing arguments or unrecognized command structure.")
                print("Invalid command arguments.")
                return None
        else:
            logging.warning(f"Unrecognized command verb: '{verb}'.")
            print("I don't understand that command.")
            return None


if __name__ == '__main__':
    # https://gist.github.com/Pinacolada64/a28d39ad241c5d9e03a6b9c1c1c54ed0
    # --- Game Setup ---
    logging.info("Setting up game world...")
    player = Player()

    # NEW: Initialize CombatSystem after game_clock is available
    combat_system = CombatSystem(game_clock)

    # Correctly pass combat_system to GameParser now that it's created
    parser = GameParser(player)  # Parser's __init__ will now get combat_system

    logging.info("Game world setup complete.")

    # NEW: Create a monster
    goblin_loot = Item(
        "Goblin Ear",
        "A shriveled, green goblin ear. Proof of your victory.",
        aliases=["ear", "shriveled ear", "green ear"]
    )
    goblin = Monster(
        "Goblin",
        "A short, green-skinned creature with beady red eyes and a rusty dagger.",
        health=40,
        attack_power=10,
        loot_item=goblin_loot
    )

    # Rooms with their terrain types
    forest = Room(
        "Forest",
        "A dense forest with tall trees. Far off in the distance to the north lies a rocky outcrop.",
        "You push through dense foliage, the trees towering above you.",
        terrain_types=[Terrain.OUTDOORS, Terrain.FOREST],
        season_descriptions={  # NEW
            Season.SPRING: "The forest is vibrant with new growth, and wildflowers carpet the ground.",
            Season.SUMMER: "The forest is lush and green, the canopy so thick little light penetrates.",
            Season.AUTUMN: "The air is crisp, and the forest blazes with red, orange, and gold leaves.",
            Season.WINTER: "The forest is silent and stark, with bare branches and a thin layer of frost.",
        }
    )
    cave_entrance = Room(
        "Cave Entrance",
        "A dark opening is to the east in the side of a mountain. "
        "Towards the northwest, snaking up between two high hills, a path beckons. "
        "At the end of the path, the glint of glass above a rounded dome is visible.",
        "You cautiously approach the ominous maw of the cave.",  # Example transition message
        terrain_types=[Terrain.OUTDOORS, Terrain.INDOORS_CAVE],  # Can be both if it's a transition zone
    )
    dark_cave = Room(
        "Dark Cave",
        "It's pitch black in here. You can hear dripping water.",
        "The darkness swallows you as you step deeper into the earth.",  # Example transition message
        terrain_types=[Terrain.INDOORS_CAVE]

    )
    observatory = Room(
        "Small Observatory",
        "A cozy, circular room filled with dusty charts and a large telescope.",
        "You find yourself inside a small, circular building, the air thick with the scent of old paper.",
        # Example transition message
        [Terrain.IN_BUILDING],
        has_window=True,
        season_descriptions={
            Season.SUMMER: "The summer sky showcases constellations and planets in the heavens."
        }
    )
    snowy_mountaintop = Room(
        "Snowy Mountaintop",
        "A windswept peak, covered in a thick blanket of snow.",
        "The wind whips around you as you ascend to the snowy summit.",  # Example transition message
        [Terrain.SNOWY],
        season_descriptions={
            Season.SUMMER: "Surprisingly, patches of green alpine tundra peek through the melting snow.",
            # Winter will likely use the base_description as it's already snowy
            Season.SPRING: "The mountaintop is still largely snow-covered, but the air has a hint of thaw.",
            Season.AUTUMN: "The mountaintop is brutally cold, and the first heavy snows have arrived."
        }
    )
    # Exits
    forest.add_exit("north", cave_entrance)
    cave_entrance.add_exit("south", forest)
    cave_entrance.add_exit("east", dark_cave)
    dark_cave.add_exit("west", cave_entrance)
    cave_entrance.add_exit("northwest", observatory)
    observatory.add_exit("southeast", cave_entrance)
    cave_entrance.add_exit("up", snowy_mountaintop)
    snowy_mountaintop.add_exit("down", cave_entrance)

    # Place the monster in a room
    dark_cave.add_monster(goblin)  # Let's put a goblin in the dark cave!

    # Items (updated to use terrain_descriptions and aliases)
    sword = Item(
        "Sword",
        "A gleaming, well-balanced steel sword, sharp enough to cut through dense foliage.",
        terrain_descriptions={
            Terrain.FOREST: "A gleaming sword lies half-hidden among the fallen leaves.",
            "inventory": "A sharp, reliable sword."
        },
        aliases=["blade", "weapon", "steel sword"]
    )
    key = Item(
        "Rusty Key",
        "A small, old key, heavily corroded. It looks like it hasn't been used in years.",
        terrain_descriptions={
            Terrain.INDOORS_CAVE: "A rusty key glints faintly on the damp cave floor."
        },
        aliases=["key", "old key", "small key"]
    )
    torch = Item(
        "Torch",
        "A wooden torch with a resin-soaked tip, ready to be lit.",
        terrain_descriptions={
            Terrain.INDOORS_CAVE: "A torch lies here, its unlit tip promising light in the gloom."
        },
        aliases=["light", "torch", "wood torch"]
    )

    telescope_manual_text = """
    --- Telescope Operation Manual ---
    1. Power On: Locate the red switch on the base.
    2. Alignment: Use the manual cranks to align with desired celestial body.
    3. Magnification: Adjust the eyepiece for clarity.
    4. Caution: Do not look directly at the sun without proper filters!
    ----------------------------------
    """
    telescope_manual = Item(
        "Telescope Manual",
        "A weathered manual for operating the telescope, its pages yellowed with age.",
        readable=True,
        read_text=telescope_manual_text,
        terrain_descriptions={
            Terrain.IN_BUILDING: "A weathered manual rests on a dusty table, next to the telescope."
        },
        aliases=["manual", "book", "handbook", "instructions", "guide", "telescope book"]
    )

    # Create a new item to demonstrate disambiguation:
    repair_manual = Item(
        "Repair Manual",
        "A thick, grease-stained manual for repairing mechanical devices.",
        readable=True,
        read_text="""
    --- Repair Manual Excerpt ---
    Chapter 1: Troubleshooting Leaks
               Check for corroded seals. Apply sealant generously.
    Chapter 2: Gear Lubrication
               Use high-viscosity grease for optimal performance.
    ----------------------------
    """,
        terrain_descriptions={
            Terrain.IN_BUILDING: "A repair manual lies discarded under a workbench."
        },
        aliases=["manual", "book", "guide", "repair book"]  # Shares "manual", "book", "guide" with telescope_manual
    )

    great_coat = Item(
        "Great Coat",
        base_description="A heavy, wool coat, perfect for cold weather. It's surprisingly clean.",
        terrain_descriptions={
            Terrain.SNOWY: "A great coat lies here, half-buried in the snow.",
            "inventory": "A great coat. It looks very warm and practical, suitable for any weather.",
            Terrain.OUTDOORS: "A great coat lies here, crumpled on the ground.",
            Terrain.IN_BUILDING: "A great coat lies here, neatly folded on a chair.",
            Terrain.INDOORS_CAVE: "A great coat lies here, damp and forgotten on the cave floor."
        },
        aliases=["coat", "cloak", "garment", "great cloak"],
        season_descriptions={  # NEW
            Season.SUMMER: "This great coat feels a bit heavy for the warm weather.",
            Season.WINTER: "The great coat looks essential for surviving this bitter cold.",
        }
    )

    # Place items in rooms
    forest.add_item(sword)
    cave_entrance.add_item(torch)
    dark_cave.add_item(key)
    observatory.add_item(telescope_manual)
    observatory.add_item(repair_manual)  # Place the repair manual in the same room
    snowy_mountaintop.add_item(great_coat)

    # --- Game Loop ---
    print("\n--- Welcome to the Text Adventure! ---")
    print("Type 'help' for commands, 'help <command>' for specific info, 'quit' to exit.")
    player.move_to(forest)
    # start the character creation process
    # p = create_character.main(p)
    player = Player()
    while True:
        try:
            current_game_time = game_clock.get_current_datetime().strftime("%m/%d/%Y %H:%M:%S")
            print(f"\n[Game Time: {current_game_time}]")
            user_input = input("> ").strip()
            if user_input.lower() == "quit":
                logging.info("User requested to quit. Exiting game.")
                print("Thanks for playing!")
                break
            parser.parse_and_execute(user_input)
        except Exception as e:
            logging.critical(f"An unhandled error occurred in the game loop: {e}", exc_info=True)
            print(f"An unexpected error occurred: {e}. Please report this!")
