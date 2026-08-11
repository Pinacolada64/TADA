#!/usr/bin/env python3
"""commands/help.py

Help metadata, formatter, and the HelpCommand itself.

Attach a Help() instance to every Command subclass:

    class SayCommand(Command):
        name = "say"
        help = Help(
            summary  = "Say something to players in your room.",
            category = HelpCategory.COMMUNICATION,
            usage    = [("say <message>", "Speak aloud to everyone here.")],
        )
"""

from __future__ import annotations

import logging
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from commands.base_command import Command, Mode
from formatting import hrule_char, _visible_len

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Color scheme -- |token| markup, resolved per-terminal by
# formatting.ansi_encode()/petscii_encode() downstream in ctx.send(). Same
# four tokens render correctly on both ANSI and PETSCII (see
# formatting.ANSI_COLOR_CODES / PETSCII_CONTROL_CODES).
# ---------------------------------------------------------------------------

def _heading(text: str) -> str:
    """Section headings and titles: 'Usage:', category names, etc."""
    return f'|yellow|{text}|reset|'


def _rule(text: str) -> str:
    """Horizontal rule lines."""
    return f'|dark_gray|{text}|reset|'


def _cmd(text: str) -> str:
    """A command (or topic) name."""
    return f'|cyan|{text}|reset|'


def _alias(text: str) -> str:
    """A command's alias(es) -- deliberately darker/dimmer than _cmd()."""
    return f'|dark_gray|{text}|reset|'


def _vis_ljust(text: str, width: int) -> str:
    """Left-justify *text* to *width* visible columns, ignoring |token| markup
    (str.ljust() would otherwise pad based on raw length, under-padding any
    colored text and breaking column alignment)."""
    pad = width - _visible_len(text)
    return text + (' ' * pad if pad > 0 else '')


# ---------------------------------------------------------------------------
# Help categories
# ---------------------------------------------------------------------------

class HelpCategory(Enum):
    ADMINISTRATIVE = "Administrative"   # boot, ban, shutdown, restart
    AUTHENTICATION = "Authentication"   # login, connect
    COMBAT         = "Combat"           # attack
    COMMUNICATION  = "Communication"    # say, shout, whisper, page, mail
    CONCEPT        = "Concept"          # rooms, exits, items, monsters
    GENERAL        = "General"
    INTERACTION    = "Interaction"
    MISCELLANEOUS  = "Miscellaneous"
    MOVEMENT       = "Movement"         # cardinal directions, teleport


# One-line description of each category, shown by "help categories"/"help #cat".
_CATEGORY_DESCRIPTIONS: Dict["HelpCategory", str] = {
    HelpCategory.ADMINISTRATIVE: "Admin-only tools: banning, editing players/monsters, server control.",
    HelpCategory.AUTHENTICATION: "Logging in, creating a character, and connecting to the game.",
    HelpCategory.COMBAT:         "Attacking, fleeing, and other fighting mechanics.",
    HelpCategory.COMMUNICATION:  "Talking to other players: say, shout, whisper, page, mail.",
    HelpCategory.CONCEPT:        "Explanations of game terms and ideas, not tied to one command.",
    HelpCategory.GENERAL:        "Everyday actions: inventory, items, equipment, food and drink.",
    HelpCategory.INTERACTION:    "Interacting with objects, allies, and the world around you.",
    HelpCategory.MISCELLANEOUS:  "Commands that don't fit neatly into another category.",
    HelpCategory.MOVEMENT:       "Moving around the world: compass directions, looking, teleporting.",
}


# ---------------------------------------------------------------------------
# Help metadata dataclass
# ---------------------------------------------------------------------------

@dataclass
class Help:
    """Structured help metadata attached to a Command subclass.

    Example
    -------
        help = Help(
            summary     = "Say something to players in your room.",
            description = "The say command broadcasts a message to all players
                           currently in your room.",
            category    = HelpCategory.COMMUNICATION,
            usage       = [("say <message>", "Speak aloud.")],
            examples    = [("say Hello!", "Greet everyone nearby.")],
            notes       = ["Shouting reaches adjacent rooms."],
        )
    """
    summary:     str                   = "No summary available."
    description: str                   = "No description available."
    category:    HelpCategory          = HelpCategory.GENERAL
    usage:       List[Tuple[str, str]] = field(default_factory=list)
    examples:    List[Tuple[str, str]] = field(default_factory=list)
    notes:       List[str]             = field(default_factory=list)
    # Extra notes appended only for viewers with PlayerFlags.ADMIN or
    # DUNGEON_MASTER set -- e.g. admin-only switches or behavior that would
    # just be noise (or an unwanted hint) for a regular player. See
    # format_help()'s is_privileged parameter / _is_privileged_viewer().
    admin_notes: List[str]             = field(default_factory=list)
    # Same idea as admin_notes, but formatted like `examples` (its own
    # "Admin Examples:" section, syntax + one-line explanation) -- for an
    # example that only makes sense to demonstrate for a privileged
    # viewer, e.g. a CONCEPT topic illustrating command syntax with a
    # real admin-only command as its example. See format_help()'s
    # is_privileged parameter / _is_privileged_viewer().
    admin_examples: List[Tuple[str, str]] = field(default_factory=list)
    # Extra notes appended only for viewers on a real Commodore (PETSCII)
    # connection -- e.g. an alternate keystroke that only matters on that
    # keyboard, and would just be noise for an ANSI/plain-text player. See
    # format_help()'s is_petscii parameter / _is_petscii_viewer().
    petscii_notes: List[str]           = field(default_factory=list)
    # Related command/topic names to point a player at -- rendered as a
    # "See Also:" line of 'help <name>'-able names (resolved the same way
    # HelpCommand's own lookup works: command name/alias first, then
    # _TOPICS). Doesn't validate that a name actually resolves to
    # something at Help() construction time (commands and topics can be
    # registered in either order), so a typo here just silently 404s if a
    # player follows it -- double-check names exist via 'help <name>'.
    see_also:    List[str]             = field(default_factory=list)


# ---------------------------------------------------------------------------
# Standalone help topics — not tied to any Command, so they work anywhere
# 'help' does, including the LOGIN prompt (help itself is Mode.ANY) before a
# player has even connected. Use for background/concept explanations that
# don't belong to one specific command (HelpCategory.CONCEPT).
# ---------------------------------------------------------------------------

_TOPICS: Dict[str, Help] = {}

# id(Help instance) -> its first-registered name, i.e. the canonical name
# a substring match should redirect to (see _find_topic_by_substring()).
# Keyed by id() rather than the Help instance itself since Help isn't
# hashable in a useful way here and identity, not equality, is what
# distinguishes "same topic, different alias" from "coincidentally equal
# Help objects."
_TOPIC_PRIMARY_NAME: Dict[int, str] = {}


def register_topic(*names: str, help_obj: Help) -> None:
    """Register a standalone help topic under one or more names/aliases."""
    for n in names:
        _TOPICS[n.lower()] = help_obj
    _TOPIC_PRIMARY_NAME[id(help_obj)] = names[0].lower()


def _exact_category(token: str) -> Optional["HelpCategory"]:
    """Full category value/name match only, no substring fallback --
    safe to call unconditionally at the top of HelpCommand.execute()'s
    dispatch, before command/alias lookup. _match_categories()'s
    bidirectional substring check is NOT safe there: a short command
    alias (e.g. 't') is trivially a substring of most category names
    ('adminisTrative', 'combaT', ...), so using it pre-emptively would
    hijack alias resolution into a category listing. The substring
    fallback still applies, just later -- see _show_command_help()'s
    cmd-is-None branch, reached only once exact command lookup has
    already failed.
    """
    token = token.lower()
    return next((c for c in HelpCategory if token in (c.value.lower(), c.name.lower())), None)


def _match_categories(token: str) -> List["HelpCategory"]:
    """Return every HelpCategory *token* could plausibly mean.

    Exact match (full value/name, case-insensitive) always wins outright
    and short-circuits -- if the token IS a category, that's the answer,
    full stop. Otherwise falls back to a *bidirectional* substring check
    (token-in-category, e.g. 'admin' -> Administrative, AND category-in-
    token, e.g. 'concepts' -> Concept) so both a trimmed prefix and an
    extended typo/plural resolve. Ambiguous (2+) or empty results are
    both valid outcomes for a caller to handle -- this never guesses.
    """
    token = token.lower()
    if not token:
        return []
    exact = [c for c in HelpCategory if token in (c.value.lower(), c.name.lower())]
    if exact:
        return exact
    return [
        c for c in HelpCategory
        if token in c.value.lower() or c.value.lower() in token
        or token in c.name.lower() or c.name.lower() in token
    ]


def _find_topic_by_substring(token: str) -> Optional[str]:
    """'help ease' -> 'easeofuse' -- if *token* is a substring of exactly
    one registered topic's set of names/aliases, return that topic's
    canonical name for a redirect. Returns None if it matches zero topics
    (falls through to the normal "no help found" message) or more than
    one distinct topic (ambiguous -- also falls through, rather than
    guessing which one the player meant).

    Deliberately topic-only, not command names too: a command typo
    silently redirecting to an unrelated command would be far more
    surprising than a concept-topic shortcut expanding, and commands
    already have their own alias mechanism for the common-abbreviation
    case ('help' aliases 'h'/'?', etc).
    """
    token = token.lower()
    if not token:
        return None
    matched_ids = {id(help_obj) for name, help_obj in _TOPICS.items() if token in name}
    if len(matched_ids) == 1:
        return _TOPIC_PRIMARY_NAME.get(next(iter(matched_ids)))
    return None


register_topic(
    "about", "tada", "mud", "whatisthis",
    help_obj=Help(
        summary="What is TADA?",
        description=(
            "TADA -- \"Totally Awesome Dungeon Adventure\" -- is a MUD "
            "(Multi-User Dungeon): a text-based, multi-player online game "
            "world you explore, fight monsters, and talk to other players "
            "in, all through typed commands.\n\n"
            "It's a modern re-implementation of \"The Land of Spur,\" a "
            "1980s Apple BBS door game, originally single-player and "
            "played one at a time over dial-up. TADA rebuilds it as a real "
            "multi-player game with a Python client/server (and, "
            "eventually, a native Commodore 64 client) so many "
            "adventurers can share the same dungeon at once."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("connect guest",              "Look around without an account."),
            ("new",                        "Create a character and dive in."),
            ("help",                       "See what commands are available."),
        ],
        notes=[
            "The original game is still playable: telnet://dura-bbs.net:6359",
        ],
    ),
)

register_topic(
    "commandline", "command-line", "switches", "parameters",
    help_obj=Help(
        summary="How command syntax works: switches vs. parameters",
        description=(
            "Most commands take plain words as parameters -- the actual "
            "thing you're acting on, like a player name, item name, or "
            "number.\n\n"
            "A token starting with '#' is a switch instead: a flag or "
            "sub-option that changes how the command behaves, rather than "
            "data the command acts on. Switches are usually specific to "
            "the command they're used with -- `groups #add friends Alice`, "
            "`ban #view`, `wa #hide` -- so check a command's own `help "
            "<command>` for what its switches do.\n\n"
            "In a command's own Usage line, angle brackets and square "
            "brackets mean two different things: <name> marks a "
            "required placeholder -- type your own value there, not "
            "the brackets themselves -- while [[name]] marks something "
            "optional you can leave out entirely. 'page <name[[,name2]]>"
            "=<message>' means: name is required, a second comma-"
            "separated name is optional, and so is everything after it "
            "up to the message."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("<command> <parameter>",  "Plain words: data the command acts on."),
            ("<command> #<switch>",    "A '#'-prefixed flag: changes command behavior."),
            ("<required>",             "Angle brackets: type your own value here, not the brackets."),
            ("[optional]",             "Square brackets: this part can be left out."),
        ],
        examples=[
            ("page Alice=Hello",        "Page (send a message to a player in a different room) "
                                         "a player (named Alice). The '=' separates one (or "
                                         "multiple) players from the message (\"Hello\")."),
            ("groups #add friends Bob", "Groups help you automate writing messages to "
                                         "multiple people at once. Here, '#add' is a switch "
                                         "saying you want to add Bob to a group named "
                                         "'friends'."),
            ("connect Alice",           "To log in as Alice and be prompted for the password "
                                         "separately, type 'connect Alice'."),
        ],
        notes=[
            "A command-specific switch (like '#hide' or '#add') only makes "
            "sense to the command that defines it -- see that command's "
            "own help for details.",
        ],
        # Admin/DM-only -- #version/#ver is itself gated to those flags in
        # commands/command_processor.py, so regular players don't need (or
        # get shown) this detail. See format_help()'s is_privileged param.
        admin_notes=[
            "'#version'/'#ver' works the same way on every command (e.g. "
            "'attack #version') -- reports when that command's own code "
            "was last changed instead of running it. Handled centrally in "
            "command_processor.py, gated to Admin/Dungeon Master.",
        ],
        # TELEPORT itself is Admin/DM-gated (commands/teleport.py's
        # execute() checks PlayerFlags.ADMIN/DUNGEON_MASTER), so these
        # syntax examples only make sense to demonstrate for a viewer who
        # can actually run them -- see Help.admin_examples.
        admin_examples=[
            ("teleport 42",              "An administrative command: teleports you to room #42 on your current level."),
            ("teleport #learn [<name>]", "The name is optional -- omit it to use the room's own name."),
        ],
    ),
)

register_topic(
    "bhr", "badhombre", "bad hombre",
    help_obj=Help(
        summary="What's BHR (\"Bad Hombre Rating\")?",
        description=(
            "BHR -- \"Bad Hombre Rating\" -- is a quick, single-number "
            "gauge of how dangerous a character looks, shown at the top of "
            "your STATS sheet. It rolls hit points, character level, half "
            "your Energy/Dexterity/Strength total, and a quarter of your "
            "Shield+Armor condition into one number, so you can size "
            "someone up at a glance instead of comparing six separate "
            "stats.\n\n"
            "BHR is a rough estimate, not a full combat prediction -- it "
            "deliberately leaves out your weapon and its class/race bonus "
            "(item_system.weapon_bonus()), so two characters with the same "
            "BHR can still fight very differently depending on what "
            "they're carrying.\n\n"
            "This is the same danger rating DUEL points you at before you "
            "decide whether to accept a challenge -- worth checking on "
            "STATS before you say yes to a stranger."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("stats",       "Show your own BHR along with the rest of your character sheet."),
            ("duel accept", "Accept a pending duel challenge -- check the challenger's BHR first."),
        ],
        # Admin/DM-only -- the exact formula lets a player reverse-engineer
        # and min-max toward a target BHR instead of it staying a rough,
        # at-a-glance gauge. See format_help()'s is_privileged param.
        admin_notes=[
            "Formula: hit points + (character level x 2) + "
            "((Energy + Dexterity + Strength) / 2) + ((Shield + Armor) / 4) "
            "-- ported directly from the original game (SPUR.DUEL2.S / "
            "SPUR.MISC5.S), where it was shown when sizing up other "
            "adventurers before a duel.",
        ],
        see_also=["combat", "weaponclass", "easeofuse", "basedamage"],
    ),
)

register_topic(
    "combat", "fighting",
    help_obj=Help(
        summary="How a fight actually works: what governs hitting vs. damage",
        description=(
            "ATTACK and READY show several numbers at once (Weapon Class, "
            "Best targets, Base damage, Ease of use, Battle exp.) and it's "
            "not obvious which ones matter for landing a hit versus which "
            "matter for how hard that hit lands. They split cleanly into "
            "two separate questions:\n\n"
            "1. Do you hit at all? Purely your weapon's Weapon Class "
            "against the monster's size (see 'help weaponclass') plus your "
            "Battle Experience tier and character level. Base damage and "
            "Ease of use play no part in whether the swing connects.\n\n"
            "2. If you hit, how much damage? A random roll scaled by Base "
            "damage (the ceiling on that roll) and Ease of use (a "
            "multiplier on top of it) -- see 'help basedamage' and "
            "'help easeofuse'. A weapon can be very likely to hit and "
            "still hit soft, or unlikely to hit and still hit hard, "
            "depending on these two independently.\n\n"
            "Bad Hombre Rating (BHR, 'help bhr') is a different thing "
            "again -- a rough, single-number size-up of a whole character "
            "(hit points, level, stats, armor condition), not tied to any "
            "one weapon or swing."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("attack", "Fight the monster in your current room."),
            ("ready <weapon>", "See a weapon's own numbers before you fight with it."),
        ],
        notes=[
            "Landing the killing blow with a weapon builds Battle "
            "Experience with it specifically: VETERAN at 40 kills "
            "(+1 to-hit, +1 damage), ELITE at 99 (+2 to-hit, +damage "
            "scaling with your level). This is separate from character "
            "experience, which you earn every swing regardless of outcome.",
        ],
        see_also=["weaponclass", "basedamage", "easeofuse", "weaponaffinity", "bhr"],
    ),
)

register_topic(
    "weaponclass", "besttargets", "best targets",
    help_obj=Help(
        summary="Weapon Class and \"Best targets\": what actually decides a hit",
        description=(
            "Every weapon belongs to one of six classes, and each class is "
            "naturally suited to certain monster sizes -- READY's "
            "\"Best targets\" line translates this into plain English for "
            "whatever weapon you're about to ready (see Notes below for "
            "the full table).\n\n"
            "Fighting a monster your weapon class favors raises your hit "
            "threshold (easier to hit); fighting outside it lowers that "
            "threshold. This is the single biggest factor in whether a "
            "swing connects -- bigger than Battle Experience, bigger than "
            "character level. A weapon with great Base damage and Ease of "
            "use ('help basedamage', 'help easeofuse') still whiffs a lot "
            "against the wrong monster size."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("ready <weapon>", "Shows this weapon's own Best targets line."),
        ],
        notes=[
            "Bash/Slash  -- Swift, Small, Short; Light Armor",
            "Poke/Jab    -- Huge, Swift",
            "Pole/Ranged -- Man-sized, Big, Short",
            "Projectile  -- Huge, Large (+10% surprise)",
            "Proximity   -- Anybody",
            "Energy      -- Huge, Large; Light Armor",
        ],
        admin_notes=[
            "combat/resolution.py's hit_threshold() (SPUR.COMBAT.S "
            "p.attack, lines 106-113): p2 (the d10-roll-under threshold) "
            "is computed from weapon class integer (wa) vs. monster size "
            "(ma, 1=huge...7=swift) via a per-class formula, then "
            "min(7, p2 + zu + xp_level). Base damage/Ease of use "
            "(wd/ws) never enter this calculation at all.",
        ],
        see_also=["combat", "basedamage", "easeofuse", "weaponaffinity"],
    ),
)

register_topic(
    "basedamage", "base damage",
    help_obj=Help(
        summary="What \"Base damage\" on READY means",
        description=(
            "Base damage is the ceiling on the random damage roll a hit "
            "draws from -- shown on READY as a score of 3-9 (weapons.json "
            "stores it as that digit x10, e.g. 60 for a score of 6). "
            "Higher Base damage means a wider range of possible damage per "
            "hit, not a bigger guaranteed number: a hit always rolls "
            "somewhere between a small floor and (Base damage + 2), then "
            "Ease of use scales that roll up or down ('help easeofuse').\n\n"
            "Base damage has nothing to do with whether you hit in the "
            "first place -- that's entirely Weapon Class vs. monster size "
            "('help weaponclass')."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("ready <weapon>", "Shows this weapon's own Base damage score."),
        ],
        admin_notes=[
            "Stored as weapon.to_hit in weapons.json/items.py (SPUR wd, "
            "raw digit x10) -- confusingly named after the JSON field, "
            "not the actual to-hit chance. combat/resolution.py's "
            "_calc_player_damage(): b = random(2.0, wd+2), then scaled by "
            "ws (see 'help easeofuse' admin notes) before surprise/charge/"
            "armor adjustments.",
        ],
        see_also=["easeofuse", "weaponclass", "combat"],
    ),
)

register_topic(
    "easeofuse", "ease of use",
    help_obj=Help(
        summary="What \"Ease of use\" on READY means",
        description=(
            "Ease of use is a multiplier applied on top of a hit's random "
            "damage roll ('help basedamage') -- shown on READY as a score "
            "of 5-9 (weapons.json stores it as that digit x10, e.g. 90 for "
            "a score of 9). A higher score means more of that roll's raw "
            "damage actually lands.\n\n"
            "There's also a hidden perk: on a strong enough attack roll, "
            "\"ease of use helps!\" kicks in and applies this same damage "
            "formula through a faster, slightly more forgiving path -- a "
            "weapon with high Ease of use benefits from this more often.\n\n"
            "Like Base damage, Ease of use has nothing to do with whether "
            "you hit in the first place -- that's entirely Weapon Class "
            "vs. monster size ('help weaponclass')."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("ready <weapon>", "Shows this weapon's own Ease of use score."),
        ],
        admin_notes=[
            "Stored as weapon.stability in weapons.json/items.py (SPUR ws, "
            "raw digit x10). combat/resolution.py: fast-path check is "
            "`d10_roll > ws + 2` (SPUR.COMBAT.S line 139); "
            "_calc_player_damage() applies `b = (b * ws / 10) + zv - 1` "
            "where zv is the assembled class/race + battle-exp damage "
            "bonus.",
        ],
        see_also=["basedamage", "weaponclass", "combat"],
    ),
)

register_topic(
    "weaponaffinity", "weapon affinity", "bestweapon", "best weapon", "class weapon",
    help_obj=Help(
        summary="Which weapons suit your class and race",
        description=(
            "Every weapon secretly favors (or penalizes) certain classes "
            "and races -- a hidden skill/damage bonus baked into the "
            "weapon itself, on top of everything covered in 'help combat'. "
            "READY shows the result as \"Skill bonus\"/\"Damage bonus\" "
            "lines once you ready a weapon your class or race actually "
            "has an affinity for; no line at all means no bonus either "
            "way for that weapon.\n\n"
            "Class and race bonuses are separate and stack -- a Gnome "
            "Thief readying a dagger gets both the Thief's Poke/Jab bonus "
            "and the Gnome's dagger bonus at once. There's no in-game "
            "listing of every weapon's exact affinities; the patterns "
            "below are the general shape of it, but the real answer for "
            "any specific weapon is whatever READY actually shows you "
            "once you ready it.\n\n"
            "By class, roughly:"
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("ready <weapon>", "Shows Skill bonus/Damage bonus if this weapon favors your class/race."),
        ],
        notes=[
            "Wizard   - staffs, bolts; blades ok",
            "Druid    - sabre, sling, club, bow",
            "Fighter  - good all-round, avoid bow",
            "Paladin  - good all-round, avoid bow",
            "Ranger   - bows, swords; avoid spear",
            "Thief    - daggers only",
            "Archer   - bows only",
            "Assassin - daggers, not bow/sling",
            "Knight   - sword, lance; Excalibur!",
            "",
            "By race, roughly:",
            "",
            "Human    - guns, cannons, dynamite",
            "Ogre     - clubs, hammers, knuckles",
            "Pixie    - daggers, knives",
            "Elf      - bows",
            "Hobbit   - slings; also spears",
            "Gnome    - daggers, knives, axes",
            "Dwarf    - axes, hatchets, crossbows",
            "Orc      - daggers, knuckles, guns",
            "Half-Elf - bows, swords",
        ],
        admin_notes=[
            "item_system.py's weapon_bonus(weapon, player_class, "
            "player_race) -> (skill_bonus, damage_bonus), ported from "
            "SPUR.WEAPON.S's 'special' subroutine. Matches via substring "
            "checks on the weapon's uppercased name (or last 4 chars) "
            "plus its WeaponClass. Class sets (skill, damage) outright; "
            "race branches always += on top, so they stack with class "
            "and (for a race matching two of its own substrings, e.g. "
            "Hobbit sling + Pole/Ranged, or Orc UZI matching both its "
            "'NIFE/GGER/ UZI/KLES' and firearm lists) can even stack with "
            "themselves.",
            "Exact class table: WIZARD ball/staff/bolt=+2/+1 else -0/-2 "
            "(dagger/knife -0/+1); DRUID sabre/sling/club/spear/staff/"
            "bow=+1/+1; FIGHTER base +2/+1, projectile +0/-1, energy "
            "+2/+2; PALADIN +0/+1, projectile +0/-1; RANGER sword/sabre="
            "+1/+1, pole_range=-1/-1; THIEF poke_jab=+1/+1 else +0/-1; "
            "ARCHER bow=+2/+2, bash_slash or pole_range=-1/-2; ASSASSIN "
            "poke_jab=+2/+1, but bow/sling=-1/-1 (overrides); KNIGHT "
            "sword/lance/sabre=+2/+3, EXCALIBUR=+4/+4, projectile=+0/-1.",
            "Exact race table (all additive): HUMAN firearm-ish name=+0/"
            "+1; OGRE club/hammer/knuckles=+3/+0; PIXIE dagger/knife="
            "+1/+2; ELF bow=+1/+1; HOBBIT sling=+1/+2 AND pole_range=+1/"
            "+2 (both can apply); GNOME dagger/knife/battleaxe=+1/+2; "
            "DWARF axe/hatchet/crossbow=+1/+1; ORC dagger/knife/uzi/"
            "knuckles=+2/+0 AND firearm-ish name=+0/+2 (both can apply); "
            "HALF_ELF bow/sword=+0/+1.",
            "Special case: any weapon with 'PHASER' in its name has its "
            "skill bonus floored at a minimum of +1 regardless of class/"
            "race (item_system.py line ~369).",
            "Not part of weapon_bonus() itself, but relevant to weapon "
            "fit: commands/ready.py enforces a flat Strength >= 4 "
            "minimum to ready any weapon at all (not per-weapon), gates "
            "EXCALIBUR to Knight class + Honor >= 1200 (rejection blast "
            "otherwise), and STORM-prefixed weapons have their own "
            "accept/reject-as-servant logic independent of class/race.",
        ],
        see_also=["combat", "weaponclass", "basedamage", "easeofuse"],
    ),
)

register_topic(
    "rooms", "room",
    help_obj=Help(
        summary="What's a \"room\"?",
        description=(
            "In TADA (and MUDs generally), \"room\" is the traditional term "
            "for any single space you can occupy -- it doesn't mean an "
            "indoor space with four walls. A forest clearing, a mountain "
            "ledge, a stretch of open road, and an actual indoor chamber "
            "are all \"rooms\": each one is just a distinct location with "
            "its own description, exits, and contents.\n\n"
            "This comes from the genre's text-adventure roots, where the "
            "world is a network of discrete locations connected by exits "
            "(north, south, up, down, ...) rather than a continuous map. "
            "Don't take \"room\" too literally -- outdoors, underground, "
            "in a building, it's all the same concept under the hood."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("look",  "Show the room you're currently in again."),
            ("n/s/e/w/u/d", "Move to an adjacent room in that direction."),
        ],
    ),
)

register_topic(
    "colors", "color", "markup",
    help_obj=Help(
        summary="How TADA's ||color|| text codes work",
        description=(
            "Game text sometimes contains pipe-delimited color codes: "
            "write ||red||some text||reset|| and everything between the "
            "two markers renders in that color (or effect) instead of "
            "the normal text color, the same way on an ANSI terminal or "
            "a real Commodore. Here's an actual example: |red|like "
            "this|reset|.\n\n"
            "This is different from the [bracketed] auto-highlighting "
            "your own PREFS 'C' text/highlight colors control: a color "
            "code always renders as its exact named color regardless of "
            "your personal color preferences, while [brackets] pick up "
            "whatever colors you've chosen.\n\n"
            "Some codes can also repeat with a count -- ||tab:5|| means "
            "five tabs in a row instead of one.\n\n"
            "Doubled pipes like the examples above (||red||...||reset||) "
            "are themselves an escape: they show the raw ||code|| syntax "
            "literally instead of applying it. That's how this help "
            "topic can display the syntax without triggering it -- you "
            "won't normally need it yourself unless you're writing game "
            "text that needs to show a ||code|| example rather than use one."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("||color||some text||reset||", "Colors 'some text'; 'reset' returns to normal after it."),
            ("||tab||",                     "A tab -- a real Tab character or simulated spaces, per PREFS 'K'."),
            ("||tab:5||",                   "A count after the code repeats it -- five tabs in a row here."),
            ("||code||...||code||",         "Doubled pipes: show raw ||code|| syntax literally instead of applying it."),
        ],
        examples=[
            ("You find |red|a ruby|reset| on the floor.",
             "'a ruby' renders in red; the rest is normal text."),
            ("Name:|tab|Alice", "Lines up 'Alice' at the next tab stop."),
        ],
        notes=[
            "Colors that work on every terminal type: black, white, red, "
            "cyan, green, blue, yellow, purple, orange, brown, light_red, "
            "light_green, light_blue, light_gray, dark_gray, mid_gray. "
            "ANSI terminals also get magenta, light_cyan, light_yellow, "
            "light_white, bold, and dim.",
            "A misspelled or unsupported code (e.g. ||glorp||) is left "
            "as plain text rather than breaking the rest of the line.",
        ],
        # PETSCII-only -- see Help.petscii_notes / format_help()'s
        # is_petscii parameter. Not shown to ANSI/plain-text players,
        # since '!' isn't recognized as a code delimiter for them at all
        # (see formatting._PETSCII_TOKEN_RE's own comment for why).
        petscii_notes=[
            "'!' works exactly like '|' here -- !!red!!some text!!reset!! "
            "-- since '|' needs an awkward Shift+- on a Commodore "
            "keyboard. The two can't be mixed within one code (|red! "
            "isn't valid).",
        ],
    ),
)

register_topic(
    "tokens", "substitution", "pronouns", "percent",
    help_obj=Help(
        summary="%-tokens: pronouns and names in game text",
        description=(
            "Any text the game sends you can contain a %-token that gets "
            "filled in with something about you -- your name, your "
            "pronouns, your class, or your race -- so the same message "
            "reads correctly no matter who receives it.\n\n"
            "For example, the game might send \"%%n draws %%p sword\" and "
            "you'd see \"Alice draws her sword\" while someone else typing "
            "the same command sees \"Bob draws his sword\" -- one template, "
            "correct for everyone.\n\n"
            "This isn't something you type yourself day-to-day -- it's how "
            "the game's own text is written under the hood -- but it's "
            "worth knowing about so a stray '%' in something you're told "
            "(a time format, a percentage) doesn't look mysterious: an "
            "unrecognized %-token is always left exactly as typed instead "
            "of being replaced."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("%%n", "Your name."),
            ("%%s / %%o", "Subjective / objective pronoun -- he/she, him/her."),
            ("%%p / %%P", "Possessive adjective / pronoun -- his/her, his/hers."),
            ("%%r", "Reflexive pronoun -- himself/herself."),
            ("%%c / %%e", "Your character class / race -- e.g. Wizard, Elf."),
            ("%%%%", "A literal '%' character."),
        ],
        examples=[
            ("%%n draws %%p sword.", "Alice draws her sword. / Bob draws his sword."),
            ("%%s looks determined.", "She looks determined. / He looks determined."),
        ],
        notes=[
            "A '%' not followed by a recognized letter (like a bare "
            "percentage, or the end of a sentence) is left exactly as "
            "typed -- it never breaks the rest of the message.",
        ],
        admin_notes=[
            "Implemented in tada_utilities.substitute_tokens(), applied to "
            "every outbound line/prompt in network_context.py and "
            "terminal_context.py, keyed to the recipient. "
            "ally_events/farewell.py has its own separate, ally-targeted "
            "copy of this scheme (predates this general version) -- its "
            "%-tokens resolve against the ally, not the receiving player, "
            "and are already plain text by the time they reach ctx.send(). "
            "Traces back to an unfinished C64 asm draft, "
            "assembly-language/%-substitution.lbl, that sketched the same "
            "%<letter> idea (plus class/race tokens) but never wired it up.",
        ],
    ),
)

register_topic(
    "honor", "alignment",
    help_obj=Help(
        summary="Honor points and your current alignment",
        description=(
            "Honor is a 0-2000 point score, separate from your other "
            "stats, that tracks how you've been playing rather than how "
            "strong you are. Where it sits determines your \"current "
            "alignment\", shown on STATS:\n\n"
            "  Above 1600: Saintly\n"
            "  1201-1600:  Good\n"
            "  800-1200:   Neutral\n"
            "  400-799:    Bad\n"
            "  399 and under: Evil\n\n"
            "Every character starts with a race-dependent amount: 1250 "
            "for Pixies and Elves, 750 for Ogres and Orcs, 1000 for "
            "everyone else -- so a good-aligned race starts closer to "
            "Good than a Human or Dwarf does, and an evil-aligned race "
            "starts closer to Evil.\n\n"
            "Honor moves in small steps as you play, not in one big "
            "swing: eating a ration nudges it up a couple of points, "
            "praying can raise or lower it depending on how it's "
            "answered, and some encounters (like meeting a Ringwraith) "
            "drain it outright. It's capped at 2000, and some effects "
            "only trigger while it's below or above a threshold -- for "
            "example, a Ringwraith recognizes \"one of his own kind\" and "
            "skips the fight entirely if your honor is under 800, and an "
            "ally's own courage stat is compared against your honor to "
            "decide whether it stands and fights or flees. Stealing from "
            "another player with LOOT always costs you honor too, whether "
            "or not it succeeds."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("stats", "Shows your current Honor score and alignment."),
        ],
        notes=[
            "Your alignment isn't fixed at character creation -- it's "
            "just a live readout of your current Honor score, so it can "
            "drift between Saintly and Evil over a long enough session.",
        ],
        admin_notes=[
            "_current_alignment() (commands/stats.py, ported from "
            "SPUR.MISC5.S lines 199-201) computes the band shown above. "
            "Starting/max values: PlayerRaceMaxHonor (base_classes.py), "
            "ported from SPUR.NEW.S / SPUR.LOGON.S's set.honor. Honor "
            "deltas are scattered per-mechanic rather than centralized -- "
            "see ally_events/__init__.py (ration eating, ally-loyalty "
            "courage-vs-honor check), commands/pray.py, commands/loot.py, "
            "and encounters/ringwraith.py for representative examples.",
        ],
        see_also=["experience"],
    ),
)

register_topic(
    "experience", "xplevel", "xp level", "levels",
    help_obj=Help(
        summary="Character level vs. battle experience -- two different things",
        description=(
            "TADA has two unrelated systems that both use the word "
            "\"experience\", which trips people up:\n\n"
            "Character level (xp_level) is your overall progress through "
            "the game -- it rises as you accumulate XP from fights and "
            "quests, and drives your general power level (hit points, "
            "stat caps, and so on). This is what people usually mean by "
            "\"what level are you\".\n\n"
            "Battle experience is completely separate: it's tracked "
            "per-weapon, not per-character. Every killing blow you land "
            "with a given weapon adds one point to that weapon's own "
            "tally. READY a weapon to see its badge: green with no "
            "label below 40 kills, VETERAN at 40, ELITE at 99. A high "
            "battle-experience badge on your sword says nothing about "
            "your character level, and vice versa -- a level-20 wizard "
            "who just picked up a mace for the first time still shows a "
            "plain green badge on it.\n\n"
            "Shield proficiency works the same way, tracked per-shield "
            "rather than per-weapon, with its own similarly-tiered badge."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("ready <weapon>", "Wield a weapon and see its battle-exp badge."),
            ("stats", "Shows your overall character level."),
        ],
        admin_notes=[
            "player.xp_level vs. player.weapon_experience "
            "(gain_weapon_experience(), +1 per killing blow, per "
            "SPUR.MISC.S:384) / player.shield_proficiency "
            "(gain_shield_proficiency()). Tier thresholds and badge "
            "labels: combat/resolution.py's battle_exp_bonuses() / "
            "tier_label() -- VETERAN at 40, ELITE at 99.",
        ],
        see_also=["easeofuse", "weaponaffinity"],
    ),
)

register_topic(
    "armorcondition", "armor condition", "shieldcondition", "shield condition",
    "intact", "intactness",
    help_obj=Help(
        summary="What the \"NN% intact\" on your shield/armor means",
        description=(
            "Your shield and armor each carry their own intactness "
            "rating, shown as a percentage on STATS -- 'Shield: NN% "
            "intact' / 'Armor: NN% intact'. Gear that starts with any "
            "protective value at all rolls somewhere in the 10-69% "
            "range at character creation, on an independent coin-flip "
            "for each of the two.\n\n"
            "In a fight, a shield or suit of armor with any protection "
            "left can absorb some incoming damage before it reaches "
            "you, but each block also has a chance to chip away at that "
            "gear's own condition -- and a bad enough hit can destroy "
            "the piece outright, leaving you with no more block from it "
            "until it's repaired or replaced. Rolls are independent for "
            "shield and armor, so it's entirely possible for one to fail "
            "while the other holds.\n\n"
            "There's no separate readout for how much block value "
            "you'll get from a given percentage -- higher intactness "
            "simply means more punishment absorbed and slower "
            "degradation, lower means less protection and a piece "
            "closer to breaking."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("stats", "Shows your current Shield/Armor intactness percentages."),
        ],
        admin_notes=[
            "starting_equipment.py's _roll_intactness() (10-69, 50/50 "
            "roll per slot). Per-swing block/degrade math: "
            "combat/resolution.py's monster_attacks() shield-block "
            "(lines ~771-795) and armor-block (lines ~797-813) sections "
            "-- each computes its own block threshold and degrade roll "
            "from the current shield/armor value, with a separate roll "
            "for outright destruction.",
        ],
    ),
)

register_topic(
    "specialweapon", "special weapon", "silverbullet", "silver bullet",
    help_obj=Help(
        summary="Some monsters only fall to one specific weapon",
        description=(
            "A handful of monsters are effectively immune to ordinary "
            "weapons -- the classic example is the Werewolf, who only "
            "goes down to a silver bullet. Fighting one of these with "
            "the wrong weapon isn't just less effective, it can be "
            "outright wasted effort: your swing lands but does nothing "
            "useful.\n\n"
            "There's no way to see a monster's required weapon in "
            "advance from the game's UI -- it's something you learn "
            "from experience, a tip, or trial and error. If a fight "
            "against a particular monster feels like it's going "
            "nowhere no matter how hard you hit, that's the sign to "
            "try switching weapons rather than just hitting harder."
        ),
        category=HelpCategory.CONCEPT,
        see_also=["weaponaffinity", "weaponclass"],
        admin_notes=[
            "combat/resolution.py's check_special_weapon() "
            "(SPUR.COMBAT.S lines 127-151, SPUR.MISC4.S lines 132-137). "
            "monster['special_weapon'] (characters.py) holds the "
            "required weapon's number, 0 = no requirement; wrong weapon "
            "-> is_ineffective, matching weapon -> normal combat. A few "
            "named weapons (EXCALIBUR, WRAITH DAGGER, any STORM weapon) "
            "have their own always-on special-case bonuses independent "
            "of this per-monster requirement.",
        ],
    ),
)

register_topic(
    "examine", "lookfirst", "look first",
    help_obj=Help(
        summary="Why to EXAMINE/LOOK before you pick something up",
        description=(
            "Some items lying around are magical or cursed, and picking "
            "one up blind carries risk: a cursed item can hurt you the "
            "moment you grab it. EXAMINE (or LOOK at an item) lets you "
            "check first without that risk -- a successful examine "
            "reveals whether an item is Magical or cursed before you've "
            "committed to taking it.\n\n"
            "The check isn't guaranteed to succeed, and once you've "
            "successfully examined a given item this session, examining "
            "it again just tells you so rather than re-rolling -- so a "
            "failed attempt is worth trying again, but there's nothing "
            "more to learn once it's worked."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("examine <item>", "Check an item on the ground (or in your inventory) before taking it."),
            ("get <item>",     "Pick it up -- risky if it's cursed and unexamined."),
        ],
        admin_notes=[
            "commands/examine.py's _examine_item() (SPUR.MISC3.S's "
            "exam.a/exam2/exam3) -- magic weapons (weapons.json "
            "kind=='magic') and cursed treasures (objects.json "
            "type=='cursed') roll against _EXAMINE_SUCCESS_PCT, with a "
            "one-shot memory in player.last_examined. The actual GET-"
            "time penalty for grabbing a cursed item unexamined is "
            "commands/get.py's _cursed_penalty() (SPUR.MISC.S's hp.5: "
            "-5 INT, HP set to 5).",
        ],
    ),
)

register_topic(
    "parties", "party", "allies", "ally",
    help_obj=Help(
        summary="Parties and allies -- companions who fight alongside you",
        description=(
            "An ally is an NPC companion (a hired hand, a rescued "
            "prisoner, a tamed animal, ...) that joins your party and "
            "fights at your side. Your party is just the list of allies "
            "currently traveling with you -- there's no fixed party "
            "size limit, though juggling a lot of allies at once means "
            "more mouths to feed.\n\n"
            "You can GIVE an ally food, a weapon, or other gear to carry "
            "and use, and TAKE it back later. An ally's loyalty depends "
            "on how well you treat it -- an ally tagged [Elite] on STATS "
            "is extra loyal, lightly armored, and won't abandon you just "
            "for refusing it food the way an ordinary ally might."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("give <item> <ally>", "Hand an ally something to carry or wield."),
            ("take <item> <ally>", "Take an item back from an ally."),
        ],
        see_also=["eliteally"],
        admin_notes=[
            "party.py's Party class (add_member()/remove()) and "
            "bar/ally_data.py's Ally (also characters.py's Horse(Ally)) "
            "back this. No hard cap on party size is enforced anywhere "
            "in add_member().",
        ],
    ),
)

register_topic(
    "eliteally", "elite ally",
    help_obj=Help(
        summary="What the [Elite] tag on an ally means",
        description=(
            "An ally tagged [Elite] on STATS (or in an ally-picker "
            "listing) is more loyal than an ordinary ally, lightly "
            "armored (a small bonus to how much damage it can block in "
            "a fight), and it won't turn on you the way an ordinary "
            "ally might if you refuse to feed it."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("stats", "Shows [Elite] and any other ally flags in the Allies table's Notes column."),
        ],
        see_also=["parties"],
        admin_notes=[
            "AllyFlags.ELITE (bar/ally_data.py) -- SPUR's own source uses "
            "a '!' sigil (instr(\"!\",zt$)) for this internally, but this "
            "port never surfaces that character to the player; the "
            "player-facing tag is always the rendered '[Elite]' string "
            "(commands/stats.py's _ally_flag_tags(), bar/allies.py's "
            "pick_ally() listing). combat/resolution.py's "
            "has_light_armor param (set from AllyFlags.ELITE in "
            "combat/engine.py) grants a +2 armor_bonus in monster/ally "
            "combat math.",
        ],
    ),
)

register_topic(
    "guilds", "guild",
    help_obj=Help(
        summary="Guilds: Civilian, Iron Fist, Sword, Claw, or Outlaw",
        description=(
            "During character creation you choose a guild -- Civilian, "
            "The Iron Fist, Mark of the Sword, Mark of the Claw, or "
            "Outlaw -- which is mostly a roleplaying/flavor choice, but "
            "guild membership does gate a few real things: each guild "
            "has its own headquarters (a virtual area with a food "
            "locker, item locker, and guild bank), guildmates in the "
            "room with you lend a combat bonus when you SPORT DUEL "
            "someone, and winning a guild-vs-guild duel captures that "
            "room's territory for your guild.\n\n"
            "Outlaw is the odd one out -- you make yourself a target "
            "for nearly everyone else in exchange for solo-play "
            "opportunities the other guilds don't get. Civilian is the "
            "safest choice and the one recommended for a first "
            "character.\n\n"
            "GUILD FOLLOW MODE (an on/off toggle, see FOLLOW) is "
            "separate from which guild you're in -- it controls whether "
            "you automatically tag along when a fellow guild member "
            "moves, not membership itself."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("follow",          "Toggle Guild Follow Mode."),
            ("duel <player>",   "Challenge a player in your room to a SPORT DUEL."),
            ("duel #standings", "Show guild win/loss duel standings."),
        ],
        notes=[
            "The guild-choice screen advertises Civilians as \"safe from "
            "dueling by anyone but an Outlaw\" -- that restriction isn't "
            "actually enforced yet; DUEL currently lets any player "
            "challenge any other player regardless of guild.",
        ],
        admin_notes=[
            "Guild StrEnum (base_classes.py); guild choice UI is "
            "commands/new_player.py's _choose_guild() (_GUILD_INFO). "
            "PlayerFlags.GUILD_MEMBER/GUILD_AUTODUEL/GUILD_FOLLOW_MODE "
            "(flags.py) -- GUILD_FOLLOW_MODE is wired to live behavior "
            "(commands/follow.py); GUILD_AUTODUEL is set but has no "
            "consuming logic yet. Guild HQ virtual area: "
            "guild_hq/main.py. combat/duel.py's DuelCommand.execute() "
            "has no guild-eligibility check on who can challenge whom -- "
            "the Civilian/Outlaw dueling-immunity rule from the choice "
            "screen isn't ported. Territory capture: room_alignment.py "
            "(Ryan's own extension, no SPUR precedent -- SPUR's guild "
            "territory is baked into room names at map-build time and "
            "never mutated by combat). Guild standings persistence: "
            "guild_standings.py (SPUR.DUEL2.S's guild label).",
        ],
        see_also=["virtualareas", "bhr"],
    ),
)

register_topic(
    "virtualareas", "virtual area", "virtual areas",
    help_obj=Help(
        summary="Virtual areas: the Bar, Shoppe, Elevator, and guild HQs",
        description=(
            "Most of the game is ordinary rooms connected by compass "
            "exits, but a few locations work differently: the Wall Bar "
            "& Grill, the Shoppe, and each guild's headquarters are "
            "\"virtual areas\" -- self-contained, menu-driven places you "
            "enter from a specific room rather than a room number of "
            "their own on the map. You don't LOOK around and pick an "
            "exit direction there; you get a menu of options instead, "
            "and a dedicated command (often just a letter) leaves it and "
            "puts you back in the ordinary room you entered from.\n\n"
            "The Elevator works the same way for Up/Down travel in "
            "certain rooms -- rather than a compass exit to a specific "
            "room, it's a connection that can route you into the "
            "Shoppe or to a real staircase destination on the same "
            "level, depending on the room."
        ),
        category=HelpCategory.CONCEPT,
        see_also=["rooms", "guilds"],
        admin_notes=[
            "bar/main.py, shoppe/main.py, shoppe/elevator.py, "
            "annex/main.py, guild_hq/main.py. A room's exits dict can "
            "carry rc/rt fields (MECHANICS.md:343-358) separate from "
            "compass exits: rc=1/2 marks an Up/Down elevator connection, "
            "rt==0 routes into the Shoppe, rt>0 is a real same-level "
            "staircase to that room number. commands/movement.py's "
            "MoveCommand and Server._move() (simple_server.py) resolve "
            "these.",
        ],
    ),
)

register_topic(
    "moreprompt", "more prompt", "paging", "pagination",
    help_obj=Help(
        summary="The '-- More --' pause between screenfuls of output",
        description=(
            "When More Prompt is on, any output longer than one screen "
            "pauses partway through with a '-- More --' prompt instead "
            "of scrolling everything past you at once. From that "
            "prompt: Enter shows the next page, B or - goes back a "
            "page, and Q stops and discards the rest.\n\n"
            "Turn it off and everything sends in one go regardless of "
            "length -- better for a client that already scrolls back "
            "comfortably or logs its own output, worse if long listings "
            "(like a big room or inventory) fly past faster than you "
            "can read them."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("mp",                "Quickly toggle More Prompt on/off."),
            ("prefs",             "Open PREFS; 'M' also toggles More Prompt."),
        ],
        admin_notes=[
            "PlayerFlags.MORE_PROMPT (flags.py); toggled by "
            "commands/more_prompt.py's MorePromptCommand (name 'mp') and "
            "commands/prefs.py's 'M' row -- both call "
            "commands/prefs.py's toggle_more_prompt().",
        ],
    ),
)

register_topic(
    "petscii", "ansi", "terminaltype", "terminal type", "clienttype", "client type",
    help_obj=Help(
        summary="Why the game looks different depending on your terminal",
        description=(
            "TADA renders the same game text differently depending on "
            "what kind of terminal/client you're connecting with, set "
            "via PREFS' Client Type row. A real Commodore (PETSCII) "
            "gets Commodore's own character set and color codes; an "
            "ANSI terminal gets standard ANSI escape codes and a wider "
            "color palette; a plain ASCII client gets neither -- just "
            "text, with color codes stripped.\n\n"
            "This is why some things (like a guild's sigil, or a boxed-"
            "text tip) can look different -- or not appear at all -- "
            "between two players connected with different clients: the "
            "game picks the right rendering for your Client Type "
            "automatically once it's set correctly, so if something "
            "looks wrong (garbled symbols, missing color, boxes drawn "
            "with the wrong characters), check PREFS' Client Type first."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("prefs", "Open PREFS; Client Type is on the Terminal Settings submenu."),
        ],
        see_also=["colors"],
        admin_notes=[
            "terminal.py's Translation enum (PETSCII/ASCII/ANSI -- only "
            "three values; earlier notes in this file mentioning a "
            "fourth 'COMMODORE' value were wrong, no such member "
            "exists). Selected via commands/prefs.py's Client Type row; "
            "consumed throughout formatting.py (e.g. codec_for_settings(), "
            "PETSCIICodec) for anything that renders differently per "
            "terminal.",
        ],
    ),
)

register_topic(
    "statrolling", "stat rolling", "rollstats", "roll stats", "4d6",
    help_obj=Help(
        summary="How your starting attributes are rolled (4d6, drop lowest)",
        description=(
            "Each of your six starting attributes (Strength, Dexterity, "
            "Constitution, Intelligence, Wisdom, Energy) is rolled with "
            "four six-sided dice: the lowest of the four is dropped, "
            "and the remaining three are added together, giving a "
            "result from 3 to 18. You see all six rolls at once during "
            "character creation and can accept them or re-roll the "
            "whole set as many times as you like before locking them in "
            "-- there's no limit on re-rolling, so there's little reason "
            "to accept a set you're unhappy with.\n\n"
            "Your class and race then apply their own fixed bonuses/"
            "penalties on top of whatever you rolled."
        ),
        category=HelpCategory.CONCEPT,
        admin_notes=[
            "commands/new_player.py's _roll_stats()/_roll_one_stat() "
            "(4d6-drop-lowest per PlayerStat in _STAT_ORDER); class/race "
            "bonuses applied separately via PlayerClassBonuses/"
            "PlayerRaceBonuses (base_classes.py).",
        ],
    ),
)

register_topic(
    "itempersistence", "item persistence", "respawn",
    help_obj=Help(
        summary="Why an item you left behind is there again next session",
        description=(
            "Ground items (things, weapons, and rations sitting in a "
            "room, not something you found in a chest) reappear the "
            "next time you visit -- but only if you're not still "
            "carrying the one you took. The moment you log in, the "
            "game checks what's currently in your inventory: anything "
            "you've eaten, dropped, sold, or otherwise no longer have "
            "counts as available to find again, while anything still "
            "on you stays marked as already taken so it doesn't "
            "duplicate.\n\n"
            "In practice this means a ration you're saving for later "
            "won't respawn a second copy in the room while you're "
            "still holding it -- but eat it (or drop it) before you log "
            "off, and it'll be back next time. This surprises people "
            "coming from MUDs where a picked-up item is gone from the "
            "world for good."
        ),
        category=HelpCategory.CONCEPT,
        admin_notes=[
            "player.item_history / player.ration_history (player.py) -- "
            "session ring buffers, reseeded from current inventory on "
            "login. commands/get.py's _room_available_items() and "
            "simple_server.py's room-item display both hide any item ID "
            "present in the relevant history list; record_item_pickup()/"
            "record_ration_pickup() append to it on GET.",
        ],
    ),
)

register_topic(
    "horses", "horse", "mounts", "mount",
    help_obj=Help(
        summary="Horses: acquiring, mounting, and fighting from the saddle",
        description=(
            "A horse is a special kind of ally: you get one either by "
            "LASSOing a wild horse during combat, or buying one at "
            "Jake's Stable. Once you have one, MOUNT climbs into the "
            "saddle and DISMOUNT gets off -- you're automatically "
            "dismounted if your horse dies/leaves the party or you "
            "walk into water.\n\n"
            "Mounted combat has its own flavor: you sometimes get a "
            "free CHARGE opportunity for extra damage on the first "
            "exchange of a fight, a monster's attack can sometimes hit "
            "your horse instead of you, and CHARGE itself carries a "
            "risk of being thrown from the saddle afterward (a Saddle "
            "gives you a second chance to stay seated if that happens). "
            "A Saddle and Horse Armor, bought at Jake's Stable and then "
            "USEd on your horse, equip it for that fight -- and enough "
            "gold buys Train Horse, which upgrades an equipped horse to "
            "Elite.\n\n"
            "Pixies are too small to mount a horse at all."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("lasso",      "Attempt to capture a wild horse you're fighting."),
            ("mount",      "Climb onto your horse."),
            ("dismount",   "Get off your horse."),
            ("use <item>", "Equip a Saddle or Horse Armor onto your mounted horse."),
        ],
        see_also=["parties"],
        admin_notes=[
            "MECHANICS.md's 'Horses' section (Phase 1-3 implementation "
            "notes) is the authoritative reference. commands/mount.py/"
            "dismount.py/lasso.py; AllyFlags.MOUNT/SADDLED/ARMORED "
            "(bar/ally_data.py); CHARGE eligibility/bonus/unseat: "
            "combat/engine.py's _roll_charge_first_strike()/"
            "_charge_unseat_check(), combat/resolution.py's "
            "player_attacks(is_charge=True). Known gap: horse HP isn't "
            "meaningfully tracked yet (a lassoed mount's hit_points "
            "seeds to 0), so a 'mount redirects a hit' save is "
            "narrative-only, not real mount damage.",
        ],
    ),
)

register_topic(
    "victory", "escape", "winning", "conqueror",
    help_obj=Help(
        summary="How to actually win/escape the dungeon",
        description=(
            "Victory ('Conqueror' status) is reached at level 6's "
            "Shimmering Portal room by going Up -- but only once every "
            "gate is satisfied. First, the King of the Wraiths must be "
            "dead, no matter what else is true. Beyond that, the exact "
            "requirement depends on the server's configured victory "
            "type: carrying a specific treasure item, holding enough "
            "silver in hand, or both -- ask an admin (or check CONFIG, "
            "if you have access) which applies on this server.\n\n"
            "A common misconception carried over from the original "
            "game's own flavor text is that you need to personally "
            "defeat SPUR himself to win -- that's not actually checked "
            "anywhere; only the Wraith King's death (plus whatever "
            "item/gold gate applies) matters."
        ),
        category=HelpCategory.CONCEPT,
        admin_notes=[
            "victory.py (SPUR.MISC7.S's win/win2/win5/nowin), triggered "
            "by commands/movement.py's rc/rt handling on level 6 room "
            "117 ('Shimmering Portal', the only rc==1 'Ladder Up' room "
            "in the dataset). Gates: PlayerFlags.WRAITH_KING_ALIVE must "
            "be False (unconditional); config.victory_type "
            "('gold'/'item'/'both') then further requires "
            "config.victory_gold_amount silver in hand and/or carrying "
            "objects.json item #config.victory_item_number. On success: "
            "winners.py records the win, a battle.log entry and "
            "permanent news post follow.",
        ],
    ),
)

register_topic(
    "pawnshop", "pawn shop", "pawn",
    help_obj=Help(
        summary="The Pawn Shop: sell (almost) anything you find",
        description=(
            "The Shoppe's Pawn Shop buys back nearly any item you're "
            "carrying for quick cash -- a handy way to convert loot "
            "you don't need into gold without hunting down a "
            "specialty buyer. A couple of quest-tier treasures are too "
            "valuable for the pawnbroker to touch and are refused "
            "outright.\n\n"
            "Everything sold this way goes into the shop's own back-"
            "room stock, which you (or anyone else) can browse and buy "
            "back later at a markup -- so a pawned item isn't "
            "necessarily gone for good, just changed hands."
        ),
        category=HelpCategory.CONCEPT,
        notes=[
            "Reached via the Shoppe's own menu -- take the elevator "
            "(Up/Down at a room with one) to reach the Shoppe, then "
            "pick Pawn Shop from its options.",
        ],
        admin_notes=[
            "shoppe/pawn.py (SPUR.SHOP.S's pawn.shp section). "
            "_REFUSED_IDS (Crown of Midas #73, Amulet of Life #76) are "
            "hardcoded no-resale items. Buy-back stock: server.pawn_stock "
            "(session-only, _STOCK_CAP=30, oldest evicted first), sold "
            "back at _BUY_MARKUP (×40) -- no SPUR precedent for buy-back, "
            "this port's own addition.",
        ],
    ),
)

register_topic(
    "dwarf", "thedwarf", "the dwarf",
    help_obj=Help(
        summary="The Dwarf: what the STATS 'Dwarf: Alive!/Dead...' line means",
        description=(
            "The Dwarf is a single, world-shared NPC thief wandering "
            "level 1 -- a short, bearded fellow who periodically robs "
            "you as you move around: your silver in hand if you're "
            "carrying any, otherwise a random item from your "
            "inventory. He relocates to a new room every so often, so "
            "he isn't a fixed target you can camp.\n\n"
            "Find his current room and fight him like any other "
            "monster to kill him -- doing so hands you his entire "
            "accumulated hoard (everything he's stolen from everyone, "
            "not just you) and stops him robbing you specifically. He "
            "keeps roaming and stealing from anyone else who hasn't "
            "killed him yet -- 'killed' is tracked per player, not "
            "server-wide, so one player's kill doesn't retire him for "
            "everyone."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("stats", "Shows 'Dwarf: Alive! [N silver]' or 'Dwarf: Dead...' for you specifically."),
        ],
        admin_notes=[
            "encounters/dwarf.py (SPUR.MAIN.S 'dwarf'/'no.dwarf', "
            "SPUR.MISC5.S 'dwarf' theft subroutine, SPUR.MISC.S:385-388 "
            "'p.a4' award-on-death). PlayerFlags.DWARF_ALIVE (per-player "
            "kill tracking, not a ported SPUR mechanic -- SPUR retires "
            "him server-wide on death). Periodic relocation "
            "(config.dwarf_move_interval_minutes) is also this port's "
            "own addition, replacing SPUR's fixed world-init placement. "
            "Hoard total: config.dwarf_silver (server-wide, sysop-"
            "editable via CONFIG); his current room: "
            "run/server/dwarf_state.json.",
        ],
    ),
)

register_topic(
    "combination", "combinations", "combo",
    help_obj=Help(
        summary="Combinations: what they unlock, and where Elevator's comes from",
        description=(
            "A combination is a three-number code (e.g. 42-07-93) that "
            "unlocks something. You'll deal with up to three kinds:\n\n"
            "-- Castle: yours from the moment your character is "
            "created. You'll never need to hunt this one down.\n\n"
            "-- Locker: assigned the first time you visit the Private "
            "Locker in the Merchant Shoppe -- the attendant hands it "
            "to you on the spot (and engraves it on your claim tag, in "
            "case you forget it later).\n\n"
            "-- Elevator: the one you have to go earn. It doesn't "
            "exist for your character until you find and read a "
            "scrap of paper somewhere out in the dungeon -- that's "
            "the only way to learn it. Where that scrap turns up is "
            "part of the adventure; this topic won't spoil it."
        ),
        category=HelpCategory.CONCEPT,
        notes=[
            "Lost or forgot a combination you already have? It isn't "
            "rerolled or consumed by checking it again -- Locker's is "
            "reprinted on your claim tag (READ it), and Elevator's "
            "stays the same if you still have the scrap of paper to "
            "re-read.",
        ],
        see_also=["pawnshop", "rooms"],
        admin_notes=[
            "base_classes.py's CombinationTypes/Combination (three "
            "random 1-99 digits). Castle is generated for every "
            "character up front (player.py's set_up_combinations()). "
            "Locker is granted by shoppe/locker.py's _first_visit(). "
            "Elevator is generated on first READ of objects.json #69 "
            "'scrap of paper' (commands/read.py's "
            "_read_scrap_of_paper() -- SPUR.MISC2.S's `elev` "
            "subroutine); deliberately not consumed or rerolled on "
            "later reads (see MECHANICS.md's 'Elevator Combination' "
            "section).",
        ],
    ),
)


# ---------------------------------------------------------------------------
# Helper function - guards against Mode.NONE instead of a set {Mode.NONE}
# ---------------------------------------------------------------------------

def _is_available(cmd, mode) -> bool:
    """Safe wrapper around cmd.is_available_in() — guards against modes=None or modes=Mode."""
    modes = getattr(cmd, "modes", None)
    if modes is None:
        return True   # no restriction declared → show it
    if isinstance(modes, set):
        from commands.base_command import Mode
        return Mode.ANY in modes or mode in modes
    return False      # misconfigured — hide it and log


def _is_privileged_viewer(ctx) -> bool:
    """Whether ctx's player has PlayerFlags.ADMIN or DUNGEON_MASTER set --
    gates Help.admin_notes (see format_help()'s is_privileged param).
    Safe to call with a ctx that has no real player (e.g. the LOGIN-mode
    fallback dict some tests pass): returns False rather than raising.
    """
    player     = getattr(ctx, "player", None)
    query_flag = getattr(player, "query_flag", None)
    if not callable(query_flag):
        return False
    from flags import PlayerFlags
    try:
        return bool(query_flag(PlayerFlags.ADMIN) or query_flag(PlayerFlags.DUNGEON_MASTER))
    except Exception:
        return False


def _is_petscii_viewer(ctx) -> bool:
    """Whether ctx's player is on a real Commodore (PETSCII) connection --
    gates Help.petscii_notes (see format_help()'s is_petscii param). Safe
    to call with a ctx that has no real player/client_settings (e.g. the
    LOGIN-mode fallback dict some tests pass): returns False rather than
    raising."""
    player         = getattr(ctx, "player", None)
    client_settings = getattr(player, "client_settings", None)
    if client_settings is None:
        return False
    try:
        from formatting import codec_for_settings, PETSCIICodec
        return isinstance(codec_for_settings(client_settings), PETSCIICodec)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Formatter  (pure — no I/O)
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Escape [optional] syntax notation so highlight_brackets renders it literally."""
    return re.sub(r'\[([^\[\]]+)\]', r'[[\1]]', text)


def format_two_column(items: List[Tuple[str, str]], width: int) -> List[str]:
    """Render (left, right) pairs as an aligned two-column block.

    `left` is left-padded to a shared column width; `right` is word-wrapped
    to fit what's left of `width`, with continuation lines aligned under it.
    Every returned line already fits within `width`, so it's safe to send
    each one as its own ctx.send() argument -- the client-side formatter
    re-wraps by splitting on spaces, which would otherwise mangle manual
    alignment (and ignore embedded '\\n's) if lines were pre-joined into one
    string instead.

    Padding uses _visible_len(), not raw len()/str.ljust() -- `left` can
    contain a [[bracket]]-escaped syntax example (see format_help()'s
    _esc()), which is 2 characters longer than what actually renders once
    highlight_brackets() collapses the escape at send time. Padding on
    raw length would under-pad exactly those rows relative to plain ones.

    Used for Usage/Examples-style (syntax, description) listings in
    format_help(), and for HelpCommand's category listing.
    """
    out: List[str] = []
    if not items:
        return out
    left_col  = min(max(_visible_len(s) for s, _ in items), int(width * 0.4), 30)
    left_col  = max(left_col, 10)
    right_col = max(width - 4 - left_col - 2, 10)

    for left, right in items:
        pad = " " * max(0, left_col - _visible_len(left))
        if right:
            wrapped = textwrap.wrap(right, width=right_col) or [""]
            out.append(f"  {left}{pad}  {wrapped[0]}")
            for cont in wrapped[1:]:
                out.append(f"  {'':{left_col}}  {cont}")
        else:
            out.append(f"  {left}")
    return out


def format_summary_table(items: List[Tuple[str, str]], width: int) -> List[str]:
    """Render (name, summary) pairs as a zebra-striped, borderless table.

    No box-drawing characters -- just two aligned columns, one command per
    row. Alternating rows tint the summary text (dark_gray / mid_gray) so
    long lists stay easy to scan without a box or rule lines cluttering it;
    the command name itself stays cyan (via _cmd()) on every row so it
    reads consistently with the rest of help's formatting.

    Used by HelpCommand's 'help #summary' switch.
    """
    out: List[str] = []
    if not items:
        return out
    left_col  = min(max(len(s) for s, _ in items), int(width * 0.4), 30)
    left_col  = max(left_col, 10)
    right_col = max(width - 4 - left_col - 2, 10)

    for i, (name, summary) in enumerate(items):
        stripe  = 'dark_gray' if i % 2 else 'mid_gray'
        wrapped = textwrap.wrap(summary, width=right_col) or [""]
        name_col = _vis_ljust(_cmd(name), left_col)
        out.append(f"  {name_col}  |{stripe}|{wrapped[0]}|reset|")
        for cont in wrapped[1:]:
            out.append(f"  {'':{left_col}}  |{stripe}|{cont}|reset|")
    return out


def _search_snippet(cmd, term: str, context: int = 20) -> str:
    """Return an elided snippet of surrounding text around the first
    occurrence of *term* in *cmd* -- checked in the same name/alias/summary/
    description priority order as CommandProcessor.search_commands(), so the
    snippet always comes from whichever field actually matched.

    e.g. term='caravan' against a longer description yields something like
    "...merchants running a caravan through the pass..." rather than the
    whole paragraph.
    """
    term_l = (term or "").lower()
    if not term_l:
        return ""

    help_obj = getattr(cmd, "help", None)
    fields = [
        getattr(cmd, "name", "") or "",
        *(getattr(cmd, "aliases", []) or []),
        getattr(help_obj, "summary", "") or "",
        getattr(help_obj, "description", "") or "",
    ]

    for field in fields:
        idx = field.lower().find(term_l)
        if idx == -1:
            continue
        start = idx - context
        end   = idx + len(term) + context
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(field) else ""
        snippet = " ".join(field[max(start, 0):min(end, len(field))].split())
        return f"{prefix}{snippet}{suffix}"

    return ""


def format_help(help_obj: Help, command_name: str = "", width: int = 78,
                rule_char: str = "-", is_privileged: bool = False,
                is_petscii: bool = False,
                aliases: Optional[List[str]] = None) -> Optional[str]:
    """Format a Help instance into a display string.

    :param help_obj: Help (or a str, or None)
    :param command_name: shown as a header when present
    :param width: total line width; defaults to 78 columns
    :param rule_char: character to use for a horizontal rule line
    :param is_privileged: when True, help_obj.admin_notes are rendered as
        their own "Admin Notes:" section (see Help.admin_notes) -- pass
        _is_privileged_viewer(ctx) from a call site that has a live ctx.
    :param is_petscii: when True, help_obj.petscii_notes are appended to
        the Notes section (see Help.petscii_notes) -- pass
        _is_petscii_viewer(ctx) from a call site that has a live ctx.
    :param aliases: other names this command is also reachable under
        (cmd.aliases, minus command_name itself) -- rendered as its own
        "Aliases:" line. The general 'help' listing already shows these
        inline (_show_general_help()'s 'name (alias1, alias2)'); this is
        the same information surfaced on the per-command detail view,
        which previously never read cmd.aliases at all.
    """
    if help_obj is None:
        return None
    if isinstance(help_obj, str):
        return textwrap.fill(help_obj.strip(), width=width)

    wrap_width = width - 4
    lines: List[str] = []

    # Summary / header
    summary = getattr(help_obj, "summary", None)
    if summary:
        if command_name:
            cat      = getattr(help_obj, "category", None)
            cat_str  = f"Category: {cat.value.title()}" if cat else ""
            # Left: command name  Right: category label — padded to width
            # (gap computed from the plain, uncolored lengths -- color
            # markup is applied after, so it doesn't throw off the math)
            gap      = width - len(command_name) - len(cat_str)
            if gap >= 1:
                lines.append(_cmd(command_name) + " " * gap + _heading(cat_str))
            else:
                lines.append(_cmd(command_name))
                if cat_str:
                    lines.append(_heading(cat_str.rjust(width)))
        lines.extend(textwrap.wrap(str(summary).strip(), width=width))
        lines.append(_rule(rule_char * width))

    # Aliases -- other names this same command answers to
    if aliases:
        lines.append(_heading("Aliases: ") + ", ".join(_cmd(a) for a in aliases))

    # Description — blank lines in the source string (\n\n) become paragraph
    # breaks; each paragraph is wrapped independently so multi-paragraph
    # descriptions (e.g. concept topics) don't collapse into one block.
    desc = getattr(help_obj, "description", None)
    if desc and desc != "No description available.":
        lines.append("")
        paragraphs = str(desc).strip().split("\n\n")
        for i, para in enumerate(paragraphs):
            if i:
                lines.append("")
            lines.extend(textwrap.wrap(" ".join(para.split()), width=wrap_width))

    # Usage
    usage = getattr(help_obj, "usage", None)
    if usage:
        lines.append("")
        lines.append(_heading("Usage:"))
        items = [(_esc(str(u[0])), str(u[1]) if len(u) > 1 and u[1] else "")
                 for u in usage]
        lines.extend(format_two_column(items, width))

    def _render_examples(singular: str, plural: str, examples: List[Tuple[str, str]]) -> None:
        if not examples:
            return
        lines.append("")
        lines.append(_heading(singular if len(examples) == 1 else plural))
        for item in examples:
            lines.append(f"  {_esc(item[0])}")
            if len(item) > 1 and item[1]:
                lines.extend(textwrap.wrap(
                    str(item[1]),
                    width=wrap_width,
                    initial_indent=" " * 6,
                    subsequent_indent=" " * 6,
                ))

    # Examples
    _render_examples("Example:", "Examples:", list(getattr(help_obj, "examples", None) or []))

    # Admin Examples -- privileged (Admin/Dungeon Master) viewers only,
    # same shape as Examples but for an example that only makes sense to
    # demonstrate for staff -- e.g. a CONCEPT topic illustrating syntax
    # with a real admin-only command. See Help.admin_examples and this
    # function's is_privileged parameter.
    if is_privileged:
        _render_examples("Admin Example:", "Admin Examples:",
                          list(getattr(help_obj, "admin_examples", None) or []))

    def _render_notes(heading: str, notes: List[str]) -> None:
        if not notes:
            return
        lines.append("")
        lines.append(_heading(heading))
        for note in notes:
            if note == '':
                lines.append('')
            else:
                lines.extend(textwrap.wrap(
                    str(note),
                    width=wrap_width,
                    initial_indent=" " * 4,
                    subsequent_indent=" " * 4,
                ))

    # Notes (petscii_notes appended only for PETSCII viewers -- see
    # Help.petscii_notes and this function's is_petscii parameter)
    notes = list(getattr(help_obj, "notes", None) or [])
    if is_petscii:
        notes += list(getattr(help_obj, "petscii_notes", None) or [])
    _render_notes("Notes:", notes)

    # Admin Notes -- privileged (Admin/Dungeon Master) viewers only, kept
    # as its own section rather than folded into Notes so staff-only
    # background/implementation detail reads as clearly separate from
    # player-facing notes (see Help.admin_notes and this function's
    # is_privileged parameter)
    if is_privileged:
        _render_notes("Admin Notes:", list(getattr(help_obj, "admin_notes", None) or []))

    # See Also -- related command/topic names, each rendered as a cyan
    # 'help <name>'-able token on one wrapped line rather than Notes'
    # one-bullet-per-line layout, since these are short names meant to
    # be scanned at a glance rather than read as sentences.
    see_also = list(getattr(help_obj, "see_also", None) or [])
    if see_also:
        lines.append("")
        lines.append(_heading("See Also:"))
        joined = ", ".join(_cmd(name) for name in see_also)
        lines.extend(textwrap.wrap(
            joined, width=wrap_width,
            initial_indent=" " * 4, subsequent_indent=" " * 4,
            break_long_words=False, break_on_hyphens=False,
        ))

    return lines if lines else None


# ---------------------------------------------------------------------------
# HelpCommand
# ---------------------------------------------------------------------------

class HelpCommand(Command):
    """The 'help' / 'h' / '?' command.

    Registered with CommandProcessor like any other Command.
    Reads the processor from ctx.client.command_processor.
    """

    name    = "help"
    aliases = ["h", "?"]
    modes   = {Mode.ANY}

    help = Help(
        summary     = "Display help for commands.",
        description = (
            "Lists available commands by category and shows detailed "
            "information about each one."
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ("help",               "List all available commands"),
            ("help <command>",     "Detailed help for a command"),
            ("help <category>",    "Commands in a category"),
            ("help #cat",          "List all categories"),
            ("help #summary",      "List every command with a one-line summary, by category"),
            ("help #search <term>", "Search command names and descriptions"),
        ],
        examples = [
            ("help",          "Show all commands"),
            ("help say",      "Help for the 'say' command"),
            ("help #cat",     "List all categories"),
            ("help #summary", "List all commands with their summaries"),
            ("help #search caravan", "Search for commands mentioning 'caravan'"),
        ],
        notes = [
            "You can use 'help', 'h', or '?' interchangeably.",
            "Command names are case-insensitive.",
            "A category name (with or without '#cat') accepts a "
            "substring if it's unambiguous, in either direction -- "
            "'help admin' and 'help concepts' both work, same as the "
            "full 'help administrative'/'help concept'.",
            "A concept topic name (e.g. 'help easeofuse') also accepts "
            "an unambiguous substring, e.g. 'help ease'.",
        ],
    )

    async def execute(self, ctx, *args):
        from commands.base_command import CommandResult

        # Resolve processor: prefer ctx.client.command_processor, fall back to ctx itself
        processor = (
            getattr(getattr(ctx, "client", None), "command_processor", None)
            or getattr(ctx, "command_processor", None)
        )

        if not args:
            return await self._show_general_help(ctx, processor)

        token = args[0].lower()
        rest  = args[1:]

        # Category listing
        if token in ("categories", "category", "cat", "#cat", "#c"):
            if rest:
                return await self._show_category_help(ctx, rest[0].lower(), processor)
            return await self._show_categories_list(ctx)

        # Summary table -- every category, one zebra-striped table per
        # category listing each command's Help.summary
        if token in ("#summary", "#sum"):
            return await self._show_summary_table(ctx, processor)

        # Search
        if token in ("search", "find", "#search", "#find") and rest:
            return await self._help_search(ctx, " ".join(rest), processor)

        # Category name used directly (e.g. "help movement") -- exact
        # match only here; the substring/pluralized-typo fallback (e.g.
        # "help concepts" -> Concept) lives later, after exact command
        # lookup has had first crack at the token (see _exact_category()'s
        # docstring for why).
        if _exact_category(token):
            return await self._show_category_help(ctx, token, processor)

        # Standalone concept topic (e.g. "help about") -- not tied to a
        # Command, so this works even at the LOGIN prompt before a player
        # has connected.
        if token in _TOPICS:
            return await self._show_topic_help(ctx, token)

        # Specific command
        return await self._show_command_help(ctx, token, processor)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _screen_width(ctx) -> int:
        try:
            return ctx.player.client_settings.screen_columns
        except AttributeError:
            return 78

    async def _show_general_help(self, ctx, processor) -> Any:
        from commands.base_command import CommandResult

        width = self._screen_width(ctx)
        rchar = hrule_char(ctx)
        title = f"{'Available Commands by Category':^{width}}"
        lines = [f"\n{_heading(title)}",
                 "  help <command>: detailed help   |   help #cat: list categories\n"]

        current_mode = getattr(processor, "current_mode", None)
        all_cmds = [
            cmd for cmd in (processor.get_all_commands().values() if processor else [])
    if current_mode is None or _is_available(cmd, current_mode)
        ]
        by_cat: Dict = defaultdict(list)
        for cmd in all_cmds:
            help_obj = getattr(cmd, "help", None)
            cat      = getattr(help_obj, "category", HelpCategory.GENERAL)
            by_cat[cat].append(cmd)

        for cat in sorted(by_cat, key=lambda c: c.value):
            cmds = sorted(by_cat[cat], key=lambda c: getattr(c, "name", ""))
            lines.append(f"\n{_heading(cat.value.upper() + ':')}")
            lines.append(_rule(rchar * (len(cat.value) + 1)))
            entries = []
            for cmd in cmds:
                name = getattr(cmd, "name", "?")
                als  = [a for a in (getattr(cmd, "aliases", []) or []) if a != name]
                alias_str = f" ({', '.join(als)})" if als else ""
                entries.append(_cmd(name) + (_alias(alias_str) if alias_str else ""))

            col_w  = max(_visible_len(e) for e in entries) + 2
            n_cols = max(1, min(3, (width - 4) // (col_w + 2)))
            for i in range(0, len(entries), n_cols):
                lines.append("  " + "  ".join(_vis_ljust(e, col_w) for e in entries[i : i + n_cols]))

        lines += ["", "Type 'help <command>' for more detail."]
        await ctx.send(*lines)
        return CommandResult.ok("General help displayed.")

    async def _show_summary_table(self, ctx, processor) -> Any:
        """'help #summary' -- every category, one zebra-striped, borderless
        table per category, listing each command's Help.summary."""
        from commands.base_command import CommandResult

        width = self._screen_width(ctx)
        title = f"{'Commands by Category, with Summaries':^{width}}"
        lines = [f"\n{_heading(title)}"]

        current_mode = getattr(processor, "current_mode", None)
        all_cmds = [
            cmd for cmd in (processor.get_all_commands().values() if processor else [])
            if current_mode is None or _is_available(cmd, current_mode)
        ]
        by_cat: Dict = defaultdict(list)
        for cmd in all_cmds:
            help_obj = getattr(cmd, "help", None)
            cat      = getattr(help_obj, "category", HelpCategory.GENERAL)
            by_cat[cat].append(cmd)

        for cat in sorted(by_cat, key=lambda c: c.value):
            cmds = sorted(by_cat[cat], key=lambda c: getattr(c, "name", ""))
            lines.append(f"\n{_heading(cat.value.upper() + ':')}")
            items = [
                (getattr(cmd, "name", "?"),
                 getattr(getattr(cmd, "help", None), "summary", "No summary available."))
                for cmd in cmds
            ]
            lines.extend(format_summary_table(items, width))

        lines += ["", "Type 'help <command>' for full detail on one command."]
        await ctx.send(*lines)
        return CommandResult.ok("Summary table displayed.")

    async def _show_categories_list(self, ctx) -> Any:
        from commands.base_command import CommandResult

        # format_two_column() returns lines already wrapped to fit width, so
        # sending each as its own ctx.send() argument (not pre-joined into
        # one string) reaches the player intact -- ctx.send() re-wraps every
        # item to the player's actual screen width by splitting on spaces,
        # which would otherwise mangle manual alignment and treat embedded
        # '\n' characters as just more text instead of line breaks.
        width = self._screen_width(ctx)
        items = [(cat.value, _CATEGORY_DESCRIPTIONS.get(cat, "")) for cat in HelpCategory]

        lines = [_heading("Available categories:"), ""]
        lines.extend(format_two_column(items, width))
        lines.append("")
        lines.append("Type 'help #cat <category>' to list its commands/topics.")
        await ctx.send(*lines)
        return CommandResult.ok()

    async def _show_category_help(self, ctx, category_name: str, processor) -> Any:
        from commands.base_command import CommandResult

        matches = _match_categories(category_name)
        matched  = matches[0] if len(matches) == 1 else None
        if len(matches) > 1:
            names = ", ".join(c.value for c in matches)
            await ctx.send(
                f"'{category_name}' matches more than one category: {names}. "
                "Type more of the name to narrow it down."
            )
            return CommandResult.fail(error="ambiguous_category")

        if not matched:
            await ctx.send(
                f"Unknown category '{category_name}'. Type 'help #cat' for a list."
            )
            return CommandResult.fail(error="unknown_category")

        current_mode = getattr(processor, "current_mode", None)
        all_cmds = [
            cmd for cmd in (processor.get_all_commands().values() if processor else [])
            if current_mode is None or cmd.is_available_in(current_mode)
        ]
        names = []
        for cmd in all_cmds:
            help_obj = getattr(cmd, "help", None)
            cat      = getattr(help_obj, "category", HelpCategory.GENERAL)
            # Compare by .name, not identity: a command module that predates
            # (or postdates) the last 'reload commands.help' holds a
            # reference to a *different* HelpCategory class object than
            # `matched` here, even for "the same" category -- enums compare
            # by identity by default, so cat == matched can silently miss
            # commands whose module wasn't reloaded in lockstep with this
            # one. Matching on the plain string name survives that.
            if getattr(cat, "name", None) == matched.name:
                names.append(getattr(cmd, "name", "?"))

        # Standalone topics (e.g. "about") registered under this category —
        # these aren't Commands, so they're listed separately from names above.
        topics = sorted({
            n for n, h in _TOPICS.items()
            if getattr(h.category, "name", None) == matched.name
        })

        if not names and not topics:
            await ctx.send(f"No commands in category '{matched.value}'.")
            return CommandResult.ok()

        lines = [_heading(f"Commands in {matched.value}:")]
        lines += [f"  {_cmd(n)}" for n in sorted(names)]
        if topics:
            lines.append(_heading("Topics:"))
            lines += [f"  {_cmd(n)}" for n in topics]
        await ctx.send(*lines)
        return CommandResult.ok()

    async def _help_search(self, ctx, term: str, processor) -> Any:
        from commands.base_command import CommandResult

        matches = processor.search_commands(term) if processor else []
        if not matches:
            await ctx.send(f"No commands found matching '{term}'.")
            return CommandResult.ok()

        width = self._screen_width(ctx)
        matches = sorted(matches, key=lambda c: getattr(c, "name", ""))
        items = [
            (getattr(cmd, "name", "?"), _search_snippet(cmd, term))
            for cmd in matches
        ]
        lines = [_heading(f"Commands matching '{term}':")]
        lines.extend(format_summary_table(items, width))
        await ctx.send(*lines)
        return CommandResult.ok()

    async def _show_command_help(self, ctx, command_name: str, processor) -> Any:
        from commands.base_command import CommandResult

        cmd = None
        if processor:
            cmd, _ = processor.find_command(command_name)

        if cmd is None:
            # Neither an exact command nor an exact category/topic
            # matched -- last chance: a substring/pluralized-typo match
            # against category names ('help concepts' -> Concept) or
            # topic names/aliases ('help ease' -> 'easeofuse'), each
            # only when unambiguous. Category checked first since it's
            # the coarser-grained match of the two.
            cat_matches = _match_categories(command_name)
            if len(cat_matches) == 1:
                return await self._show_category_help(ctx, command_name, processor)
            if len(cat_matches) > 1:
                names = ", ".join(c.value for c in cat_matches)
                await ctx.send(
                    f"'{command_name}' matches more than one category: {names}. "
                    "Type more of the name to narrow it down."
                )
                return CommandResult.fail(error="ambiguous_category")

            topic = _find_topic_by_substring(command_name)
            if topic:
                return await self._show_topic_help(ctx, topic)

            await ctx.send(
                f"No help found for '{command_name}'. "
                "Type 'help' for a list of commands."
            )
            return CommandResult.fail(error="no_help")

        width    = self._screen_width(ctx)
        rchar    = hrule_char(ctx)
        help_obj = getattr(cmd, "help", None)

        if help_obj and hasattr(help_obj, "summary"):
            als = [a for a in (getattr(cmd, "aliases", []) or []) if a != command_name]
            formatted = format_help(help_obj, command_name=command_name, width=width,
                                    rule_char=rchar, is_privileged=_is_privileged_viewer(ctx),
                                    is_petscii=_is_petscii_viewer(ctx), aliases=als)
            if formatted:
                await ctx.send(*formatted)
                return CommandResult.ok("\n".join(formatted))

        # Fallback: docstring of execute()
        doc = getattr(getattr(cmd, "execute", None), "__doc__", None)
        if doc:
            await ctx.send(*doc.strip().splitlines())
            return CommandResult.ok(doc.strip())

        await ctx.send(f"No detailed help available for '{command_name}'.")
        return CommandResult.fail(error="no_help")

    async def _show_topic_help(self, ctx, topic_name: str) -> Any:
        """Display a standalone concept topic (e.g. 'help about') -- not
        backed by a Command, so this works before login too."""
        from commands.base_command import CommandResult

        width     = self._screen_width(ctx)
        rchar     = hrule_char(ctx)
        help_obj  = _TOPICS[topic_name]
        formatted = format_help(help_obj, command_name=topic_name, width=width,
                                rule_char=rchar, is_privileged=_is_privileged_viewer(ctx),
                                is_petscii=_is_petscii_viewer(ctx))
        if formatted:
            await ctx.send(*formatted)
            return CommandResult.ok("\n".join(formatted))

        await ctx.send(f"No detailed help available for '{topic_name}'.")
        return CommandResult.fail(error="no_help")
