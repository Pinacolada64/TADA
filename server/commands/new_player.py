"""commands/new_player.py

New player creation flow.

`NewPlayerCommand` is the entry point — it is auto-discovered by
CommandProcessor and available in Mode.LOGIN.  It drives the player
through a linear series of prompts (prologue → client settings → age →
gender → name → class → race → guild → stat roll → review →
username/password → confirm) using only ctx.send() and ctx.prompt().

Username/password come *after* the character name, not before: username
is a separate login/account identifier (intended for a planned link to a
CommodoreServer.com account) rather than the in-world character name, but
it defaults to that name (sanitized to letters/numbers) since they'll
usually match.

All helper coroutines take (ctx) only and operate on ctx.player directly.
They return True on success and False if the player abandoned the step
(e.g. disconnected mid-flow).

Design notes
------------
- No reader/writer/player_obj arguments anywhere — everything is on ctx.
- No nested function definitions — all helpers are module-level coroutines.
- `main_flow()` is the sequencer; NewPlayerCommand.execute() calls it.
- On completion, returns CommandResult with data={'authenticated': True,
  'username': ..., 'room': CREATION_ROOM} so _login in simple_server.py
  switches the processor to GAME mode exactly the same way ConnectCommand does.

TODOs
-----
* summoning help staff for assistance
* #newbies chat channel
"""

from __future__ import annotations

import calendar
import json
import logging
import random
import re
from datetime import date
from typing import Optional

# TADA imports:
from base_classes import PlayerRace, PlayerClass, PlayerStat
from characters import apply_race_class_deltas
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.quote import confirm_dollar_quote
from net_common import hash_password, user_dir
from network_context import GameContext
from tada_utilities import a_or_an, format_quote, input_yes_no

log = logging.getLogger(__name__)

# Room where newly created players are placed after finishing creation.
# This is a "hole" in map level 1 — no normal room occupies slot 5.
CREATION_ROOM = 5

# Where per-user credential files live: user_dir() resolves this at call
# time via net_common.run_server_dir, so tests can isolate them, same as
# Player._json_path().


# Standalone helpers:

def validate_class_race_combo(ctx) -> tuple[bool, str | None]:
    """
    Returns (ok, message).
      (True,  None)  — valid, or race not set yet (skipped)
      (False, str)   — invalid combination; str is the Verus quip to send

    The actual compatibility table lives in characters.is_class_race_compatible()
    so commands/editplayer.py can check the same rule without duplicating it.
    """
    player = ctx.player
    from characters import is_class_race_compatible
    if is_class_race_compatible(player.char_class, player.char_race):
        return True, None

    from tada_utilities import a_or_an
    msg = (f'Verus remarks, "{a_or_an(player.char_race, capitalize=True)} '
           f'{player.char_class} doth not a good adventurer make. Try again."')
    logging.info("%s picked a bad class/race combination: %s %s",
                 player.name, player.char_class, player.char_race)
    return False, msg

# ---------------------------------------------------------------------------
# NewPlayerCommand
# ---------------------------------------------------------------------------

class NewPlayerCommand(Command):
    """Create a new player account via an interactive guided flow."""

    name    = "new"
    aliases = ["create", "newplayer"]
    modes   = {Mode.LOGIN}

    help = Help(
        summary     = "Create a new character account.",
        description = (
            "Guides you through a series of steps to create your character: "
            "client settings, age, gender, name, class, race, guild, stat "
            "roll, and finally username/password (defaults to your "
            "character name).  Your faithful servant Verus will assist you "
            "through the process."
        ),
        category = HelpCategory.AUTHENTICATION,
        usage    = [
            ("new",                        "Start the interactive creation flow."),
            ("new <username> <password>",  "Skip the username/password prompts."),
        ],
        notes = [
            "Type 'help', 'h', or '?' at any prompt for assistance.",
            "You may type 'quit' at any time to abandon character creation.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        # Pre-supply username / password if given on the command line.
        prefill_username = positional[0] if len(positional) > 0 else None
        prefill_password = positional[1] if len(positional) > 1 else None

        from player import Player
        player_skeleton = Player()
        return await main_flow(ctx, player=player_skeleton, prefill_username=prefill_username, prefill_password=prefill_password)


# ---------------------------------------------------------------------------
# main_flow — sequencer
# ---------------------------------------------------------------------------

async def main_flow(ctx,
                    player=None,
                    prefill_username: Optional[str] = None,
                    prefill_password: Optional[str] = None) -> CommandResult:
    """Run the full creation sequence.  Returns a CommandResult."""

    await _prologue(ctx)

    # Swap the GuestPlayer stub for a real Player immediately so every
    # creation step below (including choosing a character name) has access
    # to full Player methods. id/name aren't known yet -- those are set
    # once a username is chosen, after the character name (see below).
    if player is not None:
        player.client_settings = ctx.player.client_settings
        ctx.player            = player

    # --- creation steps ---
    steps = [
        _edit_settings,
        _choose_client_settings,
        _choose_age,
        _choose_gender,
        _choose_name,
        _choose_class,
        _choose_race,
        _choose_guild,
        _roll_stats,
        _choose_quote,
        _final_review,
    ]
    for step in steps:
        ok = await step(ctx)
        if not ok:
            return CommandResult.fail("Character creation abandoned.", error="abandoned")

    # --- username & password ---
    # Username is a separate login/account identifier -- intended for a
    # planned link to a CommodoreServer.com account -- distinct from the
    # in-world character name chosen above, but it usually matches, so it
    # defaults to the character name (letters/numbers only) and blank
    # Enter accepts that default.
    username = await _choose_username(ctx, prefill=prefill_username, default=ctx.player.name)
    if not username:
        return CommandResult.fail("Character creation abandoned.", error="abandoned")

    password = await _choose_password(ctx, prefill=prefill_password)
    if not password:
        return CommandResult.fail("Character creation abandoned.", error="abandoned")

    if player is not None:
        player.id = username   # used by Player.save()

    # --- persist and confirm ---
    ok = await _confirm_creation(ctx, username, password)
    if not ok:
        return CommandResult.fail("Character creation failed.", error="creation_failed")

    await ctx.send(
        "",
        f"Welcome to TADA, {ctx.player.name}!",
        "Your adventure begins now.",
        "",
    )
    log.info("New player %r created, placed in room %d", ctx.player.name, CREATION_ROOM)

    return CommandResult(
        success=True,
        message=f"Character '{ctx.player.name}' created.",
        data={
            "authenticated": True,
            "username":      username,
            "room":          CREATION_ROOM,
        },
    )


# ---------------------------------------------------------------------------
# Step 0 — prologue
# ---------------------------------------------------------------------------

async def _prologue(ctx) -> bool:
    prologue =[
        "",
        "|yellow|Welcome to |white|'Totally Awesome Dungeon Adventure'|yellow|, "
        "or |white|TADA|yellow| for short!",
        "",
        "Before you begin your adventure, let's set up your character. "
        "You'll be guided through a series of steps to create your unique "
        "persona in this world.  Your faithful servant |light_green|Verus|yellow| will assist you.",
        "",
        "If you need help at any point, type |white|'help'|yellow|, |white|'h'|yellow|, or |white|'?'|yellow|.",
        # TODO: "Type 'helpstaff' to summon a live helper.",
        # TODO: "Type 'chat #join newplayers' to join the new-player chat channel.",
        "",
    ]
    await ctx.send(prologue)
    return True

# ---------------------------------------------------------------------------
# Username & password
# ---------------------------------------------------------------------------

async def _choose_username(ctx, prefill: Optional[str] = None,
                           default: Optional[str] = None) -> Optional[str]:
    """Prompt for a username; return it or None on disconnect/quit.

    :param default: character name to derive a fallback from (letters/
                     numbers only, lowercased) -- blank Enter accepts it.
                     Username is a separate account identifier -- intended
                     for a planned link to a CommodoreServer.com account --
                     so it's allowed to differ from the character name, but
                     usually won't.
    """
    if prefill:
        username = prefill.strip().lower()
        if _username_taken(username):
            await ctx.send(f"The name '{username}' is already taken.  Please choose another.")
            prefill = None
        else:
            return username

    default_username = None
    if default:
        candidate = re.sub(r"[^a-z0-9]", "", default.lower())
        if len(candidate) >= 3 and not _username_taken(candidate):
            default_username = candidate

    preamble = ["", "('quit' or 'q' abandons choosing a user name.)",
                "Your name must be at least 3 characters.",
                "Choose a username (letters and numbers only).",
                "(This is for a planned integration with CommodoreServer.com "
                "<http://www.commodoreserver.com> and has no bearing on "
                "gameplay yet.)"]
    if default_username:
        preamble.append(f"Press Enter to use '{default_username}'.")
    preamble.append("")

    # TODO: capture this from CommodoreServer account name
    while True:
        raw = await ctx.prompt("Choose a username", preamble_lines=preamble)
        if raw is None:
            return None
        username = raw.strip().lower()
        if not username:
            if default_username:
                return default_username
            continue
        if username in ("quit", "q"):
            return None
        if not username.isalnum():
            await ctx.send("Usernames may only contain letters and numbers.  Try again.")
            continue
        if len(username) < 3:
            await ctx.send("Username must be at least 3 characters.  Try again.")
            continue
        if _username_taken(username):
            await ctx.send(f"'{username}' is already taken.  Please choose another.")
            continue
        return username

async def _validate_password(ctx: GameContext, pw: str) -> bool:
    """Ensure passwords meet requirements; return True if valid."""
    password = pw.strip()
    if len(password) < 4:
        await ctx.send("Password must be at least 4 characters.  Try again.")
        return False
    return True


async def _choose_password(ctx, prefill: Optional[str] = None) -> Optional[str]:
    """Prompt for a password twice; return it or None on disconnect/quit."""
    if prefill:
        return prefill

    while True:
        pw1 = await ctx.prompt(
            "Choose a password",
            preamble_lines=[
                "",
                "Choose a password, or 'R' for a random pronounceable one.",
            ],
        )
        if pw1 is None:
            return None
        pw1 = pw1.strip()
        if pw1 in ("quit", "q"):
            return None

        if pw1.lower() == "r":
            # Mirror BASIC line 3172: generate, show, ask, loop until accepted.
            while True:
                pw = _random_pronounceable_password()
                ans = await ctx.prompt(
                    "Y/N/Q",
                    preamble_lines=[f"Your random password is: {pw}", "Is this OK?",
                                    "[Y]es, [N]o, or [Q]uit generating random passwords."],
                )
                if ans is None:
                    return None
                if ans.strip().lower() in ("y", "yes", ""):
                    await ctx.send("Accepted password.")
                    return pw
                if ans.strip().lower() in ("q", "quit"):
                    await ctx.send("Stop generating random passwords.")
                    break
                # any other input → generate a new one
            continue

        if not await _validate_password(ctx, pw1):
            continue

        pw2 = await ctx.prompt("Confirm password")
        if pw2 is None:
            return None
        if pw2.strip() != pw1.strip():
            await ctx.send("Passwords do not match.  Try again.")
            continue
        return pw1


def _username_taken(username: str) -> bool:
    """Return True if a credential file already exists for this username."""
    return (user_dir() / f"login-{username}.json").exists()


# ---------------------------------------------------------------------------
# Step 1 — user preferences
# ---------------------------------------------------------------------------

async def _edit_settings(ctx) -> bool:
    """Delegate to the shared preferences menu (commands/prefs.py)."""
    from commands.prefs import prefs_menu
    return await prefs_menu(ctx, from_new_player=True)

async def _choose_client_settings(ctx) -> bool:
    """Let the player declare their terminal type so we can set screen dimensions,
    translation options, etc."""
    from table import Table
    from formatting import border_style_for_ctx

    lines = [
        "",
        "Which client are you connecting from?",
        "",
        "If unsure, you are probably connecting using the TADA client "
        "(option 4). Real Commodore 64/128 terminals are supported too "
        "(options 1-3).",
        "",
    ]
    await ctx.send(lines)

    while True:
        options = [
            ("1", "Commodore 64",  40, 25, "PETSCII"),
            ("2", "Commodore 128", 40, 25, "PETSCII"),
            ("3", "Commodore 128", 80, 25, "PETSCII"),
            ("4", "TADA Client",   80, 25, "ANSI"),
        ]
        t = Table(headers=["##", "Computer Type", "Screen Size", "Translation"],
                  border_style=border_style_for_ctx(ctx))

        for k in options:
            t.add_row([k[0], k[1], f"{k[2]} x {k[3]}", k[4]])
        await ctx.send(*t.render(width=ctx.player.client_settings.screen_columns))

        raw = await ctx.prompt("client", preamble_lines=lines)
        if raw is None:
            return False
        ans = raw.strip()
        if not ans:
            continue

        for key, label, cols, rows, encoding in options:
            if ans == key:
                cs = ctx.player.client_settings
                cs.screen_columns = cols
                cs.screen_rows    = rows
                # Translation is stored as a string here; network_context
                # resolves the actual codec when formatting output.
                cs.translation    = encoding
                await ctx.send(f"Client set to: {label}, {cols}x{rows} screen size")
                return True

        await ctx.send(f"|blue|Please enter a number between |white|1|blue| and |white|{len(options)}|blue|.")


# ---------------------------------------------------------------------------
# Step 2 — age
# ---------------------------------------------------------------------------

async def _choose_age(ctx) -> bool:
    """Prompt for age (15–50) and optionally a birthday."""
    preamble = [
        "",
        "How old is your character?",
        "Enter a number (15–50), or 'R' for a random age:",
    ]
    while True:
        raw = await ctx.prompt("age", preamble_lines=preamble)
        if raw is None:
            return False
        ans = raw.strip().lower()
        if not ans:
            continue
        if ans in ("quit", "q"):
            return False

        if ans == "r":
            # TODO: per-class age minimum-maximum limits
            while True:
                age = random.randint(15, 50)
                accepted = await input_yes_no(ctx, f"Random age: {age}. Accept?", default=True)
                if accepted is None:
                    return False
                if accepted:
                    break
        elif ans.isdigit():
            age = int(ans)
            help_msg = "Please enter a number between 15 and 50, or 'R' to choose a random age."
            if age < 15:
                apostrophe = "'"
                await ctx.send(f'"Oh, come off it! You{apostrophe}re not even old enough to handle a '
                               f'Staff yet."')
                continue
            elif age > 50:
                await ctx.send('"Hmm, we seem to be out of Senior Adventurer life '
                                'insurance policies right now. Come back tomorrow!"',
                                '',
                                f"{help_msg}")
                continue


        ctx.player.age = age
        await ctx.send(f"Age set to {age}.")

        # Optional birthday
        raw2 = await ctx.prompt(
            "T/A",
            preamble_lines=[f"Use [T]oday's date for birthday, or enter [A]nother date? (T/A)"],
        )
        if raw2 is None:
            return False
        choice = raw2.strip().lower()

        from characters import birthday_for_age

        if choice in ("t", "today", ""):
            ctx.player.birthday = birthday_for_age(age, date.today().month, date.today().day)
        else:
            # Month
            month_lines = ["", "Select birth month:"] + [
                f"  {i+1:2}.  {calendar.month_name[i+1]}" for i in range(12)
            ]
            raw_m = await ctx.prompt("month (1-12)", preamble_lines=month_lines)
            if raw_m is None:
                return False
            try:
                m = max(1, min(12, int(raw_m.strip())))
            except ValueError:
                m = date.today().month

            # Day
            days = calendar.monthrange(date.today().year, m)[1]
            raw_d = await ctx.prompt(f"day (1-{days})")
            if raw_d is None:
                return False
            try:
                d = max(1, min(days, int(raw_d.strip())))
            except ValueError:
                d = date.today().day

            ctx.player.birthday = birthday_for_age(age, m, d)

        await ctx.send(f"Birthday set to {ctx.player.birthday.strftime('%B %d')}.")
        return True


# ---------------------------------------------------------------------------
# Step 3 — gender
# ---------------------------------------------------------------------------

async def _choose_gender(ctx) -> bool:
    """Prompt for character gender."""
    try:
        from base_classes import Gender
    except ImportError:
        Gender = None

    preamble = ["", 'Verus squints myopically. "Is your character Male or Female?"']
    while True:
        raw = await ctx.prompt("M/F", preamble_lines=preamble)
        if raw is None:
            return False
        ans = raw.strip().lower()
        if ans in ("m", "male"):
            ctx.player.gender = Gender.MALE if Gender else "male"
            await ctx.send("Gender set to Male.")
            return True
        if ans in ("f", "female"):
            ctx.player.gender = Gender.FEMALE if Gender else "female"
            await ctx.send("Gender set to Female.")
            return True
        await ctx.send("Please enter 'M' for Male or 'F' for Female.")


# ---------------------------------------------------------------------------
# Step 4 — character name
# ---------------------------------------------------------------------------

async def _choose_name(ctx) -> bool:
    """Prompt for the in-world character name (distinct from login username)."""
    preamble = [
        "|reset|Choose a name for your character.",
        "|blue|Enter a name, or |white|'R'|blue| for a random one:",
    ]
    while True:
        raw = await ctx.prompt("name", preamble_lines=preamble)
        if raw is None:
            return False
        name = raw.strip()
        if not name:
            continue
        if name.lower() in ("quit", "q"):
            return False

        if name.lower() == "r":
            while True:
                name = _generate_random_name(ctx.player)
                if _username_taken(name.lower()):
                    continue  # collision -- silently reroll
                accepted = await input_yes_no(ctx, f"Random name chosen: {name}. Accept?", default=True)
                if accepted is None:
                    return False
                if accepted:
                    break

        # Character names share the same namespace as usernames.
        if _username_taken(name.lower()):
            await ctx.send(f"There is already someone named '{name}'.  Choose another.")
            continue

        ctx.player.name = name
        await ctx.send(f"Character name set to '{name}'.")
        return True


# ---------------------------------------------------------------------------
# Step 5 — class
# ---------------------------------------------------------------------------

async def _choose_class(ctx) -> int | None:
    """Prompt for character class.

    :return: int for character class, None for connection drop"""

    async def help(ctx, class_names):
        """Show some help on how to display class information."""
        # pick random class:
        random_class_num = random.randint(0, len(class_names) - 1)
        help = [f"Enter a number 1–{len(class_names)}, or 'I' and a number "
                "to show more information about that class.",
                "",
                f"Example: Type 'i{random_class_num}' for class info."
                "",
                f"<shows information about the {class_names[random_class_num]}...>",
                ]
        await ctx.send(help)

    class_names = [""]
    try:
        from base_classes import PlayerClass, PlayerClassText
        classes     = list(PlayerClass)
        class_names = [c.value for c in classes]
        class_texts = list(PlayerClassText)
    except ImportError:
        classes     = ["Fighter", "Mage", "Cleric", "Thief"]
        class_texts = ["Fighters fight", "Mages mage", "Clerics cleric", "Thieves thieve"]

    # Show class overview in non-expert mode
    if not ctx.player.is_expert:
        class_idx    = random.randint(0, len(class_names) - 1)
        class_number = class_idx + 1   # 1-based, matching what the player types
        overview = ["",
                    f'Verus says, "Choose a class by number in one of the following ways:"',
                    f'',
                    f"* Type a number, e.g., '{class_number}', to choose a class "
                    f"(in this case, {class_names[class_idx]}).",
                    f"* Type 'I' followed by the class number (e.g., 'I{class_number}'), "
                    "for information on that class:",
                    "",
                    f"{class_texts[class_idx]}",
                    "",
                   ]

        for i, name in enumerate(class_names):
            desc = str(class_texts[i]) if i < len(class_texts) else ""
            overview.append(f"  {i+1}. {name}" + (f" — {desc}" if desc else ""))
        await ctx.send(*overview)
    else:
        expert_list = ["", "Available classes:"]
        for i, name in enumerate(class_names):
            expert_list.append(f"  {i+1}. {name}")
        await ctx.send(*expert_list)

    while True:
        raw = await ctx.prompt("class")
        if raw is None:
            return False
        ans = raw.strip().lower()
        if ans in ['?', 'h', 'help']:
            await help(ctx, class_names)
        if not ans:
            continue

        # I# — show class info
        info_idx = _parse_info_request(ans)
        if info_idx is not None:
            if 1 <= info_idx <= len(class_texts):
                await ctx.send(str(class_texts[info_idx - 1]))
            else:
                await ctx.send(f'Verus reminds you, "Enter I followed by a number 1–{len(class_names)}."')
            continue

        # Numeric selection
        sel = _parse_selection(ans, len(class_names))
        if sel is not None:
            ctx.player.char_class = class_names[sel - 1]
            await ctx.send(f"Class set to {ctx.player.char_class}.")
            return True


# ---------------------------------------------------------------------------
# Step 6 — race
# ---------------------------------------------------------------------------

async def _choose_race(ctx) -> int | None:
    """Prompt for character race."""
    from tada_utilities import a_or_an

    async def help_msg(ctx, msg):
        await ctx.send(msg)

    try:
        from base_classes import PlayerRace, PlayerRaceText
        races      = list(PlayerRace)
        race_names = [r.value for r in races]
        race_texts = list(PlayerRaceText)
    except ImportError:
        races      = race_names = ["Human", "Elf", "Dwarf", "Halfling"]
        race_texts = []

    lines = [
        "",
        'Verus says: "Choose your race, or I# for info. ',
        'Some combinations of classes and races cannot be selected together."',
    ] + [f"  {i+1}. {r}" for i, r in enumerate(race_names)]

    # TODO: limit the available races shown to the player, based on the chosen race so they can't choose
    #   an invalid combination?

    while True:
        raw = await ctx.prompt("race", preamble_lines=lines)
        if raw is None:
            return False
        ans = raw.strip()
        if not ans:
            continue
        if ans in ['?', 'h', 'help']:
            await help_msg(ctx, 'Some combinations of classes and races cannot be selected together.')
            continue

        info_idx = _parse_info_request(ans)
        if info_idx is not None:
            if 1 <= info_idx <= len(race_texts):
                await ctx.send(str(race_texts[info_idx - 1]))
            else:
                await help_msg(ctx, f"Enter I followed by a number 1–{len(race_names)}.")
            continue

        sel = _parse_selection(ans, len(race_names))
        if sel is not None:
            # Store the real PlayerRace member (race_names above is only
            # its .value, used for the numbered menu labels) -- storing
            # race_names[sel-1] here instead stored a bare string rather
            # than the enum member itself; since StrEnum equality compares
            # against .value, that silently broke every
            # "in [PlayerRace.X, ...]" membership check downstream
            # (validate_class_race_combo(), natural alignment) for every
            # race choice, forever.
            ctx.player.char_race = races[sel - 1]
            ok, msg = validate_class_race_combo(ctx)
            if not ok:
                await ctx.send(msg)
                ctx.player.char_race = None   # reset so they can repick
                continue
            await ctx.send(f"Race set to {ctx.player.char_race}.")
            return True

        await ctx.send(f"Enter a number 1–{len(race_names)}, or I# for race info.")


# ---------------------------------------------------------------------------
# Step 7 — guild
# ---------------------------------------------------------------------------

# Keyed by Guild enum member: (letter, short_description)
_GUILD_INFO = {
    'C': (
        'Civilian',
        'The Path of Peace',
        [
            "Do you prefer a quieter existence, free from the entanglements of guild "
            "wars? As a Civilian, you walk a path of peace and prosperity.",
            "",
            "* You are safe from dueling by all but Outlaws, and may only duel Outlaws.",
            "* You may remain in the Shoppe while you sleep - a secure refuge.",
            "* Recommended for first-time players.",
        ],
    ),
    'M': (
        'Mark of the Claw',
        'Embrace the Wild Within',
        [
            "For the soul intertwined with nature, for the mystic who commands the "
            "untamed forces of the world, the Mark of the Claw calls.",
            "",
            "This guild is a sanctuary for Druids, Rangers, and mystical scholars — "
            "guardians of the natural balance, masters of forms both fey and fearsome.",
        ],
    ),
    'F': (
        'Iron Fist',
        'Dominate and Conquer',
        [
            "For those who seek undeniable power, for leaders who forge destiny through "
            "sheer will, the Iron Fist extends its grip.",
            "",
            "We are the architects of empire — tacticians, warlords, and those who bend "
            "others to their will.  Join us and reshape the Land under unyielding command!",
        ],
    ),
    'S': (
        'Mark of the Sword',
        'Forge Your Legend in Steel',
        [
            "For the unyielding spirit, for the warrior whose heart beats with the "
            "rhythm of battle, the Mark of the Sword awaits.",
            "",
            "A bastion of strength and honor, a brotherhood of Fighters and Knights "
            "who stand as the Land's shield.  Draw your blade and carve your saga!",
        ],
    ),
    'O': (
        'Outlaw',
        'The Path of Defiance',
        [
            "For the lone wolf, for the rebel who bows to no one — but be warned, "
            "this path is not for the faint of heart!",
            "",
            "As an Outlaw you thrive on defiance, making enemies of most others in "
            "the Land.  You are a target for many, but unique solo opportunities await.",
            "",
            "* Not recommended for first-time players.",
        ],
    ),
}


async def _choose_guild(ctx) -> bool:
    """Prompt for guild membership.

    Letter selects directly (C/M/F/S/O).
    I<letter> shows the full info blurb for that guild.
    """
    from base_classes import Guild
    from table import Table, Column
    from formatting import border_style_for_ctx
    from tada_utilities import a_or_an

    # Map letter → Guild enum
    _LETTER_TO_GUILD = {
        'C': Guild.CIVILIAN,
        'M': Guild.CLAW,
        'F': Guild.FIST,
        'S': Guild.SWORD,
        'O': Guild.OUTLAW,
    }

    # Overview preamble — sent as one batch so pagination fires if needed
    overview = [
        "",
        'Verus leans forward. "Wouldst thou join a Guild, remain a Civilian, or become an Outlaw?"',
        "",
        "Joining a Guild introduces dueling, territory control, and guild headquarters access.",
        "Civilians are safe from all dueling except by Outlaws.",
        "Outlaws stand alone — at war with everyone.",
        "",
    ]

    t = Table(headers=["Key", "Guild", "Theme"], border_style=border_style_for_ctx(ctx))
    for letter, (name, theme, _) in _GUILD_INFO.items():
        t.add_row([letter, name, theme])
    overview += t.render(width=ctx.player.client_settings.screen_columns)
    overview += ["", "Type a letter to join, or I<letter> for details  (e.g. IC, IM, IS …)", ""]
    await ctx.send(*overview)

    while True:
        raw = await ctx.prompt("guild")
        if raw is None:
            return False
        ans = raw.strip().lower()
        if not ans:
            continue
        if ans in ('q', 'quit'):
            return False

        # I<letter> — show info blurb
        if len(ans) == 2 and ans[0] == 'i' and ans[1].upper() in _GUILD_INFO:
            letter = ans[1].upper()
            name, theme, blurb = _GUILD_INFO[letter]
            await ctx.send(*([f"|yellow|{name}|reset| — {theme}", ""] + blurb + [""]))
            continue

        # Single letter — join that guild
        letter = ans.upper()
        if letter in _LETTER_TO_GUILD:
            guild = _LETTER_TO_GUILD[letter]
            ctx.player.guild = guild
            name = _GUILD_INFO[letter][0]
            if letter in ('C', 'O'):
                await ctx.send(f"You have chosen to be {a_or_an(name)}.")
            else:
                await ctx.send(f"You have chosen to join the {name}.")
            return True

        await ctx.send(f"Enter a letter (C/M/F/S/O) to choose, or I<letter> for info.")


# ---------------------------------------------------------------------------
# Step 8 — roll stats
# ---------------------------------------------------------------------------

_STAT_ORDER = [
    PlayerStat.STR, PlayerStat.DEX, PlayerStat.CON,
    PlayerStat.INT, PlayerStat.WIS, PlayerStat.EGY,
]


def _roll_one_stat() -> tuple[int, list[int]]:
    """Roll 4d6 drop lowest; return (total, all_four_rolls)."""
    rolls = sorted(random.randint(1, 6) for _ in range(4))
    return sum(rolls[1:]), rolls


_ROLL_EXPLANATION = [
    "Each attribute below is rolled with 4 six-sided dice; the lowest of",
    "the four is dropped and the remaining three are added together.",
]


async def _roll_stats(ctx) -> bool:
    """Roll stats and let the player accept or re-roll."""
    while True:
        stats   = {}
        details = []
        for stat in _STAT_ORDER:
            total, rolls = _roll_one_stat()
            stats[stat]  = total
            details.append(f"  {stat.name:<4} {total:2d}  (rolled {rolls}, dropped {min(rolls)})")

        lines = ["", *_ROLL_EXPLANATION, "", "Rolled stats:", ""] + details + [""]
        raw = await ctx.prompt(
            "Y/R",
            preamble_lines=lines + ["Accept these stats? ([Y]es / [R]e-roll)"],
        )
        if raw is None:
            return False
        ans = raw.strip().lower()
        if ans in ("y", "yes", ""):
            ctx.player.stats = stats
            before = dict(stats)
            apply_race_class_deltas(ctx.player)
            after = ctx.player.stats

            # apply_race_class_deltas() silently folds in race/class stat
            # deltas (e.g. Ogre STR +3, INT -2) -- without reporting them,
            # the accepted-vs-actual stats silently diverge and the only
            # way to notice is comparing before/after by hand.
            changed = [stat for stat in PlayerStat if before.get(stat, 0) != after.get(stat, 0)]
            if changed:
                race_name  = getattr(getattr(ctx.player, 'char_race',  None), 'name', None)
                class_name = getattr(getattr(ctx.player, 'char_class', None), 'name', None)
                who = ' / '.join(n.title() for n in (race_name, class_name) if n)
                adj_lines = [
                    f"  {stat.name:<4} {before.get(stat, 0):2d} -> {after[stat]:2d}"
                    f"  ({'+' if after[stat] - before.get(stat, 0) >= 0 else ''}"
                    f"{after[stat] - before.get(stat, 0)})"
                    for stat in changed
                ]
                await ctx.send([
                    "",
                    f"Applying {who} attribute bonuses/penalties:" if who
                    else "Applying attribute bonuses/penalties:",
                    *adj_lines,
                ])

            await ctx.send("Stats accepted.")
            return True
        if ans in ("r", "reroll", "re-roll"):
            continue
        await ctx.send("Enter 'Y' to accept or 'R' to re-roll.")


_MAX_QUOTE_LEN = 60


async def _choose_quote(ctx) -> bool:
    """SPUR.LOGON.S:410,618-624's creation-time "quote" step.

    Unlike the in-game QuoteCommand._write() (blank input = "No change..",
    a cancel), blank input here is an explicit choice to be silent -- SPUR
    prints "Ok, you will be silent.." and leaves the quote unset.
    """
    player = ctx.player
    preamble = [
        "",
        f"Enter quote now, {_MAX_QUOTE_LEN} char max. A $ in the quote will "
        "be replaced by the reading player's handle (leave a space, comma, "
        "etc, after the $). Leave blank to stay silent.",
    ]
    while True:
        raw = await ctx.prompt("Enter quote", preamble_lines=preamble)
        if raw is None:
            return False
        text = raw.strip()
        if len(text) > _MAX_QUOTE_LEN:
            await ctx.send("TOO LONG!")
            continue
        if not text:
            player.quote = None
            await ctx.send("Ok, you will be silent..")
            return True

        satisfied = await confirm_dollar_quote(ctx, text)
        if satisfied is None:
            return False
        if not satisfied:
            continue

        player.quote = text
        await ctx.send("Quote set.")
        return True


# ---------------------------------------------------------------------------
# Step 9 — final review
# ---------------------------------------------------------------------------

async def _final_review(ctx) -> bool:
    """Show a summary and let the player make last-minute edits."""
    p = ctx.player
    while True:
        lines = [
            "",
            f"  Character summary for {getattr(p, 'name', '?')}",
            "  " + "-" * 40,
            f"  Username : {getattr(p, 'name',       '?')}",
            f"  Age      : {getattr(p, 'age',        '?')}",
            f"  Gender   : {getattr(p, 'gender',     '?')}",
            f"  Class    : {getattr(p, 'char_class', '?')}",
            f"  Race     : {getattr(p, 'char_race',  '?')}",
            f"  Guild    : {getattr(p, 'guild',      '?')}",
            "",
            "  Stats:",
        ]
        for stat, val in getattr(p, "stats", {}).items():
            lines.append(f"    {stat}: {val}")

        quote_preview = format_quote(getattr(p, "quote", None), getattr(p, "name", "?"))
        lines += ["", f"  Quote    : {quote_preview if quote_preview else '(silent)'}"]

        ok, combo_msg = validate_class_race_combo(ctx)
        if not ok:
            lines += ["", f"  |red|WARNING: {combo_msg}|reset|",
                         "  |red|(Edit class or race before accepting.)|reset|"]

        lines += [
            "",
            "  Options:",
            "    1. Edit settings",
            "    2. Edit name",
            "    3. Edit age",
            "    4. Edit gender",
            "    5. Edit class",
            "    6. Edit race",
            "    7. Edit guild",
            "    8. Re-roll stats",
            "    9. Edit quote",
            ""
            "    Enter / Y — Accept and finish",
        ]

        raw = await ctx.prompt("edit / Y", preamble_lines=lines)
        if raw is None:
            return False
        ans = raw.strip().lower()

        if ans in ("", "y", "yes"):
            if not ok:
                await ctx.send("Please fix the class/race combination before accepting (options 5 or 6).")
                continue
            return True

        dispatch = {
            "1": _edit_settings,
            "2": _choose_name,
            "3": _choose_age,
            "4": _choose_gender,
            "5": _choose_class,
            "6": _choose_race,
            "7": _choose_guild,
            "8": _roll_stats,
            "9": _choose_quote,
        }
        # remap '7' to re-roll only when explicitly picking that option
        fn = dispatch.get(ans)
        if fn:
            await fn(ctx)   # re-run that step; loop back to summary afterwards
        else:
            await ctx.send(f"Enter a number 1–{len(dispatch)}, or press Enter to accept.")


# ---------------------------------------------------------------------------
# Confirm & persist
# ---------------------------------------------------------------------------

async def _confirm_creation(ctx, username: str, password: str) -> bool:
    """Persist credentials and player state. ctx.player is already a real Player."""
    player = ctx.player
    player.creation_done   = True
    player.unsaved_changes = True

    # Credential file — login only needs the password; full state lives in player-<id>.json
    udir = user_dir()
    udir.mkdir(parents=True, exist_ok=True)
    try:
        (udir / f"login-{username}.json").write_text(
            json.dumps({"password": hash_password(password)}, indent=2)
        )
    except Exception:
        log.exception("Failed to write credential file for %r", username)
        await ctx.send("An error occurred saving your character.  Please try again.")
        return False

    if not player.save(force=True):
        await ctx.send("An error occurred saving your character.  Please try again.")
        return False

    log.info("Created new player %r", username)
    return True


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _random_pronounceable_password() -> str:
    """Generate a random 10-character pronounceable password.

    Translated from BASIC (line 3178):
        v$="AEIOU" : c$="STTRSHSCBLFL" : n$="NTRSB"
    Pattern: CC-V CC-V CC-V N  (three consonant-digraph/vowel pairs + ending consonant)
    Examples: STABLITREN, SHOBLUFLES, TRAFLOSTEN
    """
    vowels   = "AEIOU"
    digraphs = "STTRSHSCBLFL"   # pairs: ST TR SH SC BL FL
    endings  = "NTRSB"

    def pick_digraph() -> str:
        idx = random.randint(0, len(digraphs) // 2 - 1)
        return digraphs[idx * 2 : idx * 2 + 2]

    return (
        pick_digraph() + random.choice(vowels) +
        pick_digraph() + random.choice(vowels) +
        pick_digraph() + random.choice(vowels) +
        random.choice(endings)
    )


def _parse_selection(ans: str, max_n: int) -> Optional[int]:
    """Return 1-based int if ans is a digit in range 1..max_n, else None."""
    if ans.isdigit():
        n = int(ans)
        if 1 <= n <= max_n:
            return n
    return None


def _parse_info_request(ans: str) -> Optional[int]:
    """Return 1-based int if ans matches 'I#' or 'i#', else None."""
    low = ans.lower()
    if len(low) == 2 and low[0] == "i" and low[1].isdigit():
        return int(low[1])
    return None


def _generate_random_name(player) -> str:
    """Return a random medieval-ish name appropriate to the player's gender."""
    try:
        from base_classes import Gender
        is_male = getattr(player, "gender", None) == Gender.MALE
    except ImportError:
        is_male = getattr(player, "gender", "male") in ("male", "m")

    male_names = [
        "Aldric", "Baldwin", "Cedric", "Dunstan", "Edric", "Falk", "Godwin",
        "Harold", "Ivo", "Jasper", "Kenric", "Lancel", "Merrick", "Osric",
        "Peregrin", "Quentin", "Roderick", "Sigurd", "Theobald", "Ulric", "Wulfric",
    ]
    female_names = [
        "Alina", "Beatrice", "Cecily", "Dawn", "Edith", "Gwen", "Jacqueline",
        "Matilda", "Rosamund", "Rhiannon", "Sybil",
    ]
    surnames = [
        "Cooper", "Smith", "Baker", "Fletcher", "Cartwright", "Sawyer", "Fuller",
        "Tanner", "Chandler", "Taylor", "Clarke", "Hayward", "Miller", "Harper",
        "Turner", "Marsh", "Langley", "Hawthorne", "Ashby", "Blackwood", "Stone",
        "Kingsley", "Oakenshield", "Ironmonger",
    ]

    first = random.choice(male_names if is_male else female_names)
    if random.random() < 0.75:
        return f"{first} {random.choice(surnames)}"
    return first


# ---------------------------------------------------------------------------
# Quick self-test  (python -m commands.new_player)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    async def _run():
        ctx              = MagicMock()
        ctx.send         = AsyncMock()
        ctx.player       = MagicMock()
        ctx.player.name  = ""
        ctx.player.stats = {}
        ctx.player.expert_mode = False
        ctx.player.client_settings = MagicMock(
            screen_columns=80, screen_rows=25
        )

        # Feed scripted answers for every prompt
        answers = iter([
            "",           # accept default settings
            "4",          # client: TADA
            "25",         # age
            "t",          # birthday: today
            "m",          # gender
            "testuser",   # char name
            "1",          # class: first option
            "1",          # race: first option
            "c",          # guild: Civilian
            "y",          # accept stats
            "y",          # accept summary
            "testuser",   # username (defaults to char name; typed here anyway)
            "pass1234",   # password
            "pass1234",   # confirm password
        ])
        ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, "y"))

        cmd    = NewPlayerCommand()
        result = await cmd.execute(ctx)
        assert result.success, f"Expected success, got: {result}"
        assert result.data.get("authenticated")
        print("✅ NewPlayerCommand self-test passed")
        print(f"   result.message = {result.message!r}")
        print(f"   result.data    = {result.data}")

    asyncio.run(_run())