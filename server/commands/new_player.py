"""commands/new_player.py

New player creation flow.

`NewPlayerCommand` is the entry point — it is auto-discovered by
CommandProcessor and available in Mode.LOGIN.  It drives the player
through a linear series of prompts (prologue → username/password →
client settings → age → gender → name → class → race → guild →
stat roll → review → confirm) using only ctx.send() and ctx.prompt().

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
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from base_classes import PlayerRace
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from create_character import validate_class_race_combo
from network_context import GameContext

log = logging.getLogger(__name__)

# Room where newly created players are placed after finishing creation.
# This is a "hole" in map level 1 — no normal room occupies slot 5.
CREATION_ROOM = 5

# Where per-user credential files live.
_USER_DIR = Path("run") / "server" / "net"


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
            "username, password, client settings, age, gender, name, class, "
            "race, guild, and stat roll.  Your faithful servant Verus will "
            "assist you through the process."
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

        return await main_flow(ctx,
                               prefill_username=prefill_username,
                               prefill_password=prefill_password)


# ---------------------------------------------------------------------------
# main_flow — sequencer
# ---------------------------------------------------------------------------

async def main_flow(ctx,
                    prefill_username: Optional[str] = None,
                    prefill_password: Optional[str] = None) -> CommandResult:
    """Run the full creation sequence.  Returns a CommandResult."""

    await _prologue(ctx)

    # --- username & password ---
    username = await _choose_username(ctx, prefill=prefill_username)
    if not username:
        return CommandResult.fail("Character creation abandoned.", error="abandoned")

    password = await _choose_password(ctx, prefill=prefill_password)
    if not password:
        return CommandResult.fail("Character creation abandoned.", error="abandoned")

    # Initialise a bare Player stub on ctx so later steps can write to it.
    # The real Player object is created/persisted in _confirm_creation().
    ctx.player.name = username

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
        _final_review,
    ]
    for step in steps:
        ok = await step(ctx)
        if not ok:
            return CommandResult.fail("Character creation abandoned.", error="abandoned")

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
        "{yellow}Welcome to {white}'Totally Awesome Dungeon Adventure'{yellow}, "
        "or {white}TADA{yellow} for short!",
        "",
        "Before you begin your adventure, let's set up your character.",
        "You'll be guided through a series of steps to create your unique",
        "persona in this world.  Your faithful servant {light_green}Verus{yellow} will assist you.",
        "",
        "If you need help at any point, type {white}'help'{yellow}, {white}'h'{yellow}, or {white}'?'{yellow}.",
        # TODO: "Type 'helpstaff' to summon a live helper.",
        # TODO: "Type 'chat #join newplayers' to join the new-player chat channel.",
        "",
    ]
    await ctx.send(prologue)
    return True

# ---------------------------------------------------------------------------
# Username & password
# ---------------------------------------------------------------------------

async def _choose_username(ctx, prefill: Optional[str] = None) -> Optional[str]:
    """Prompt for a username; return it or None on disconnect/quit."""
    if prefill:
        username = prefill.strip().lower()
        if _username_taken(username):
            await ctx.send(f"The name '{username}' is already taken.  Please choose another.")
            prefill = None
        else:
            return username

    # TODO: capture this from CommodoreServer account name
    while True:
        raw = await ctx.prompt(
            "Choose a username",
            preamble_lines=["", " ('quit' or 'q' abandons choosing a user name.)",
                            "Your name must be at least 3 characters.",
                            "Choose a username (letters and numbers only).",
                            ""],
        )
        if raw is None:
            return None
        username = raw.strip().lower()
        if not username:
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
                "Choose a password, or 'R' for a random pronounceable one:",
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
                    "Y/N",
                    preamble_lines=[f"Your random password is: {pw}", "Is this OK?"],
                )
                if ans is None:
                    return None
                if ans.strip().lower() in ("y", "yes", ""):
                    return pw
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
    return (_USER_DIR / f"login-{username}.json").exists()


# ---------------------------------------------------------------------------
# Step 1 — user preferences / client settings
# ---------------------------------------------------------------------------

async def _edit_settings(ctx) -> bool:
    """Edit things like Debug Mode, Expert Mode, etc."""
    # text color
    # tutorial mode, maybe (include command-line practice? 'tutorial #loud' -> 'LOUD TUTORIAL!'
    #    partial matching on base commands (wh = whisper, can't be just 'w' -- short for 'west')
    #    movement, other things...

    expert_mode = ["If you have played this game before, you can enable Expert Mode, if you wish. "
                   "If enabled, Expert mode bypasses displaying in-depth instructions or information "
                   "about commands or features in the game."
                  ]
    await ctx.send(expert_mode)

async def _choose_client_settings(ctx) -> bool:
    """Let the player declare their terminal type so we can set screen dimensions,
    translation options, etc."""
    from table import Table

    lines = [
        "",
        "Which client are you connecting from?",
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
        t = Table(headers=["##", "Computer Type", "Screen Size", "Translation"])

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

        await ctx.send(f"{blue}Please enter a number between {white}1{blue} and {white}{len(options)}{blue}.")


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
            age = random.randint(15, 50)
        elif ans.isdigit() and 15 <= int(ans) <= 50:
            age = int(ans)
        else:
            await ctx.send("Please enter a number between 15 and 50, or 'R' for random.")
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

        if choice in ("t", "today", ""):
            ctx.player.birthday = datetime.now()
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

            ctx.player.birthday = datetime(date.today().year, m, d)

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
        "{reset}Choose a name for your character.",
        "{blue}Enter a name, or {white}'R'{blue} for a random one:",
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
            name = _generate_random_name(ctx.player)
            await ctx.send(f"Random name chosen: {name}")

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

    apostrophe = "'"
    class_names = [""]
    try:
        from base_classes import PlayerClass, PlayerClassText
        classes     = list(PlayerClass)
        class_names = [c.name for c in classes]
        class_texts = list(PlayerClassText)
    except ImportError:
        classes     = ["Fighter", "Mage", "Cleric", "Thief"]
        class_texts = ["Fighters fight", "Mages mage", "Clerics cleric", "Thieves thieve"]

    # Show class overview in non-expert mode
    if not ctx.player.expert_mode: # getattr(ctx.player, "expert_mode", False):
        overview = ["",
                    f'Verus says: "Choose a class by number in one of the following ways:",'
                    f'',
                    f'* Type {apostrophe}6{apostrophe}) to choose a {class_names[6]}, '
                    f'* Type {apostrophe}I{apostrophe}"'
                    f'"or {apostrophe}I{apostrophe} followed by the class number "'
                    f'"(e.g., {apostrophe}i5{apostrophe})  for info."',
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
            # TODO: check for valid class/race combinations
            if isinstance(ctx.player.char_race, PlayerRace):
                # this indicates they are editing during the final edit step,
                # therefore perform the class/race check
                pass
            continue

        # I# — show class info
        info_idx = _parse_info_request(ans)
        if info_idx is not None:
            if 1 <= info_idx <= len(class_texts):
                await ctx.send(str(class_texts[info_idx - 1]))
            else:
                await ctx.send(f"Enter I followed by a number 1–{len(class_names)}.")
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
    async def help_msg(ctx, msg):
        await ctx.send(msg)

    try:
        from base_classes import PlayerRace, PlayerRaceText
        races      = list(PlayerRace)
        race_names = [r.name for r in races]
        race_texts = list(PlayerRaceText)
    except ImportError:
        race_names = ["Human", "Elf", "Dwarf", "Halfling"]
        race_texts = []

    lines = [
        "",
        'Verus says: "Choose your race, or I# for info."',
        "",
    ] + [f"  {i+1}. {r}" for i, r in enumerate(race_names)]

    help_text = 'Some combinations of classes and races cannot be selected together.'

    # TODO: limit the available races shown to the player, based on the chosen race so they can't choose
    #   an invalid combination?
    # something like:
    valid_class_and_race = validate_class_race_combo(ctx)  # from create_character.py: returns bool

    while True:
        raw = await ctx.prompt("race", preamble_lines=lines)
        if raw is None:
            return False
        ans = raw.strip()
        if not ans:
            continue
        if ans in ['?', 'h', 'help']:
            help_msg(ctx, help_text)

        info_idx = _parse_info_request(ans)
        if info_idx is not None:
            if 1 <= info_idx <= len(race_texts):
                await ctx.send(str(race_texts[info_idx - 1]))
            else:
                await help_msg(ctx, f"Enter I followed by a number 1–{len(race_names)}.")
            continue

        sel = _parse_selection(ans, len(race_names))
        if sel is not None:
            # TODO: validate class/race combo (create_character.py does this)
            ctx.player.char_race = race_names[sel - 1]
            await ctx.send(f"Race set to {ctx.player.char_race}.")
            return True

        await ctx.send(f"Enter a number 1–{len(race_names)}, or I# for race info.")


# ---------------------------------------------------------------------------
# Step 7 — guild
# ---------------------------------------------------------------------------

_GUILDS = [
    ("C", "Civilian"),
    ("M", "Mark of the Claw"),
    ("F", "Iron Fist"),
    ("S", "Mark of the Sword"),
    ("O", "Outlaw"),
]

async def _choose_guild(ctx) -> int | None:
    """Prompt for guild membership."""
    lines = [
        "",
        "Wouldst thou join a guild, remain a civilian, or become an Outlaw?",
        "Choose an affiliation:",
        "",
    ] + [f"  {i+1}. {name}  ({short})" for i, (short, name) in enumerate(_GUILDS)]

    while True:
        raw = await ctx.prompt("guild", preamble_lines=lines)
        if raw is None:
            return None  # lost connection
        ans = raw.strip().lower()
        if not ans:
            continue

        # Numeric
        sel = _parse_selection(ans, len(_GUILDS))
        if sel is not None:
            ctx.player.guild = _GUILDS[sel - 1][1]
            await ctx.send(f"Guild set to {ctx.player.guild}.")
            return ctx

        # Short letter
        for short, name in _GUILDS:
            if ans in (short.lower(), name.lower()):
                ctx.player.guild = name
                await ctx.send(f"Guild set to {name}.")
                return ctx

        await ctx.send(f"Please enter a number 1–{len(_GUILDS)}, or a letter: "
                       f"({', '.join(s for s, _ in _GUILDS)}).")


# ---------------------------------------------------------------------------
# Step 8 — roll stats
# ---------------------------------------------------------------------------

_STAT_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def _roll_one_stat() -> tuple[int, list[int]]:
    """Roll 4d6 drop lowest; return (total, all_four_rolls)."""
    rolls = sorted(random.randint(1, 6) for _ in range(4))
    return sum(rolls[1:]), rolls


async def _roll_stats(ctx) -> bool:
    """Roll stats and let the player accept or re-roll."""
    while True:
        stats   = {}
        details = []
        for stat in _STAT_ORDER:
            total, rolls = _roll_one_stat()
            stats[stat]  = total
            details.append(f"  {stat}: {total:2d}  (rolled {rolls}, dropped {min(rolls)})")

        lines = ["", "Rolled stats:", ""] + details + [""]
        raw = await ctx.prompt(
            "Y/R",
            preamble_lines=lines + ["Accept these stats? ([Y]es / [R]e-roll)"],
        )
        if raw is None:
            return False
        ans = raw.strip().lower()
        if ans in ("y", "yes", ""):
            ctx.player.stats = stats
            await ctx.send("Stats accepted.")
            return True
        if ans in ("r", "reroll", "re-roll"):
            continue
        await ctx.send("Enter 'Y' to accept or 'R' to re-roll.")


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
            "    Enter / Y — Accept and finish",
        ]

        raw = await ctx.prompt("edit / Y", preamble_lines=lines)
        if raw is None:
            return False
        ans = raw.strip().lower()

        if ans in ("", "y", "yes", "7"):  # '7' is accept in the menu shown
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
    """Write the credential file and mark creation complete."""
    _USER_DIR.mkdir(parents=True, exist_ok=True)
    cred_file = _USER_DIR / f"login-{username}.json"
    try:
        cred_file.write_text(json.dumps({
            "password":     password,
            "char_name":    getattr(ctx.player, "name",       username),
            "char_class":   getattr(ctx.player, "char_class", ""),
            "char_race":    getattr(ctx.player, "char_race",  ""),
            "guild":        getattr(ctx.player, "guild",      ""),
            "stats":        getattr(ctx.player, "stats",      {}),
            "age":          getattr(ctx.player, "age",        0),
            "gender":       str(getattr(ctx.player, "gender", "")),
            "created":      datetime.now().isoformat(),
        }, indent=2))
    except Exception:
        log.exception("Failed to write credential file for %r", username)
        await ctx.send("An error occurred saving your character.  Please try again.")
        return False

    ctx.player.creation_done = True
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
            "testuser",   # username
            "pass1234",   # password
            "pass1234",   # confirm password
            "4",          # client: TADA
            "25",         # age
            "t",          # birthday: today
            "m",          # gender
            "testuser",   # char name
            "1",          # class: first option
            "1",          # race: first option
            "1",          # guild: first option
            "y",          # accept stats
            "y",          # accept summary
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