# TADA

(work in progress)

"Totally Awesome Dungeon Adventure" (TADA) is a re-implementation of the Apple BBS game "The Land of Spur" (TLoS). Instead of being a single-player, one-at-a-time, multi-user-dungeon as it was in the dial-up BBS days, TADA has a real Python game server (`server/`) that multiple players connect to at once, from either a real Commodore 64 client or an ANSI terminal client.

TLoS was written in a scripting language called _Advanced Communications Operating System_ (ACOS). It had limitations and quirks, as any programming language does. One such quirk is that by default, it can only handle two-byte signed integers between `-32768` and `+32767`. Naturally, this is a bit restrictive when dealing with adventure game statistics such as the amount of gold carried upon your person, or similar things. (There is a cumbersome, repeated workaround in the code for this: splitting large values into two bytes/variables of most- and least-significant multiples of 1000.) The server-side rewrite addresses this with ordinary Python integers, and the original C64 client work (see `text-listings/` below) addressed it with 24-bit values of `1`-`16,777,216`--a much more comfortable range--using routines written by FuzzyFox of "AutoGraph," a graphics converter for the C64, fame.

## Server architecture

`server/` is an asyncio-based Python game server and its clients, replacing TLoS's single-player GBBS BASIC model with real multiplayer:

* `net_server.py` runs the async server (connection handling, invite/login handshake); `net_client.py`/`net_common.py` define the shared wire protocol (JSON-serialized messages).
* Player commands live in `commands/` (dozens of modules--movement, combat, loot, prayer, admin, preferences, etc.) dispatched through a central command processor.
* Gameplay systems are split into their own packages: `combat/` (the fight engine), `ally_events/` (ally gold-finding, hunger, death-saves, farewells--ported line-by-line from named SPUR BASIC routines), `encounters/`, `logon_events/`, `quests/`, `guild_hq/`, `shoppe/`, `bar/`, `street/`, plus `board.py`, `mail.py`, and `news.py` for BBS-style social features.
* `characters.py`, `player.py`, and `base_classes.py` define the character/stat model (races, classes, alignment, size); room and item data live as `level_*.json`/`objects.json`/`monsters.json`, converted from SPUR's original compressed GBBS message-database files.
* `terminal.py` translates the same game output per client type--PETSCII, ANSI, or plain text--so one server serves every client below.
* Newer subsystems: `sid_engine/` (streams SID music to the C64 client) and `petscii_editor/` (in-game PETSCII banner/screen editor).

## Commodore 64 client

A custom 6502 client (`assembly-language/client/`) talks to the server over a SwiftLink cartridge, with an NMI-driven receive buffer and IRQ-driven SID playback and task dispatch (see `assembly-language/client/CLIENT_MECHANICS.md`). Notable features:

* Native PETSCII display, including an in-game visual banner/screen editor (server-side in `server/petscii_editor/`, with a matching client-side overlay) for authoring 40x25 PETSCII art.
* Streaming SID music playback: the server encodes SID register writes as frames (`server/sid_engine/`) which the client plays back through an IRQ-driven routine.
* Loadable overlay modules rather than a monolithic client--individual features load as separate `.prg` overlays through a jump table, keeping any one load small.

## ANSI client

For players without a real (or emulated) Commodore 64, `server/tada_client.py` is a `prompt_toolkit`-based terminal client with a scrollable output pane, status bar, and dedicated input line, rendering the server's ANSI escape sequences and color. `server/simple_client.py` is a lighter alternative using `colorama` for ANSI color. Both talk to the same server as the C64 client--`terminal.py`'s ANSI translation path is just another output mode alongside PETSCII.

## Directory structure:
`SPUR-code/`: Modules for TLoS.

`SPUR-data/`: Data files for study, part of TLoS.

`assembly-language/`: C64 6510 assembly projects, including the TADA C64 client: $c500 code, parser, works in progress, or code testing.

`programming-notes/`: Notes on both TLoS and TADA.

`scripts/`: Build, automation, and test scripts for both M$-DO$ and Linux.

`server/`: Python client and server, a work in progress. Help wanted.

`text-listings/`: The original C64/modBASIC TADA modules, from before the Python server rewrite--kept for reference and as source material for porting flavor text and game logic. See [text-listings/README.md](text-listings/README.md) for a breakdown of its subdirectories and the C64 assembly language routines behind it.

`text/`: Text captures from TLoS, miscellaneous notes.

## Want to play the original game?
It's telnettable: telnet://dura-bbs.net:6359

[Screenshots of the game](https://www.mobygames.com/game/37226/land-of-spur/screenshots/apple2/) are available on MobyGames.
