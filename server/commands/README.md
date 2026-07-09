# Commands — How to register, write, and test a command

This README explains the command system as it actually works today: how a
command gets discovered and registered, what a command class looks like,
how it talks to the player, and how to test it.

`commands/example_commands.py` (the `colors`, `test`, and `table` commands)
is a working, up-to-date reference — when in doubt, read that file.

This guide assumes you are working in `server/commands/`.

---

## 1) Command registration — auto-discovery, no decorator

There is no `@command(...)` decorator. `CommandProcessor.discover()`
(`commands/command_processor.py`) walks every module in `commands/`,
imports it, and registers **any concrete `Command` subclass that has a
non-empty `name` class attribute and is defined directly in that module**
(classes merely imported into a module, like `from commands.base_command
import Command`, are skipped). One command class per file is the
convention, but nothing enforces it.

There is no special naming rule for which files get scanned — every
importable module in `commands/` is walked, including one named
`test_something.py`. Keep test files in `tests/`, not `commands/`.

```py
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory


class GreetCommand(Command):
    name    = 'greet'
    aliases = ['hello']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Say hello.',
        category = HelpCategory.COMMUNICATION,
        usage    = [('greet <name>', 'Greet someone by name.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        name = args[0] if args else 'stranger'
        await ctx.send(f'Hello, {name}!')
        return CommandResult.ok()
```

- Subclass `Command` (`commands/base_command.py`) and implement
  `async def execute(self, ctx, *args) -> CommandResult`.
- `ctx` is a `GameContext` (`network_context.py`) — see §3.
- `discover()` catches and logs failures per-module and per-class (bad
  import, duplicate name/alias, exception in `__init__`) so one broken
  command file never takes the rest down with it.


## 2) Class attributes

| Attribute | Type          | Required? | Notes |
|-----------|---------------|-----------|-------|
| `name`    | `str`         | yes       | Primary command word, case-insensitive. |
| `aliases` | `list[str]`   | no        | Alternate names; default `[]`. |
| `modes`   | `set[Mode]`   | no        | Default `{Mode.GAME}`. See `Mode` below. |
| `help`    | `Help`        | no, but expected | See §4 — every real command has one. |

### `Mode` (`commands/base_command.py`)

Gates whether a command is dispatchable in the player's current connection
state:

- `Mode.LOGIN` — before authentication (`connect`, `new`, `quit`)
- `Mode.GAME`  — authenticated and in the game world (the default)
- `Mode.ADMIN` — requires administrative privileges
- `Mode.ANY`   — no restriction (`help`, `quit`)

A command can list more than one, e.g. `modes = {Mode.LOGIN, Mode.GAME}`
for something usable both pre- and post-login (see `commands/more_prompt.py`).


## 3) `ctx` — talking to the player

Commands never touch sockets, `reader`/`writer`, or raw JSON directly.
Everything goes through the `GameContext` passed as `ctx`
(`network_context.py`):

- `await ctx.send(*lines)` — send one or more lines (or a `list[str]`) to
  the player. Handles pagination automatically based on
  `PlayerFlags.MORE_PROMPT`.
- `await ctx.send_room(*lines, exclude_self=False)` — broadcast to
  everyone else in the same room.
- `await ctx.prompt(prompt_text='', preamble_lines=None) -> str | None` —
  send an optional preamble, then block *this command's coroutine* (not
  the whole server — other connections keep running concurrently) for a
  single-line reply. Returns `None` on disconnect; always check for that
  before using the result.
- `ctx.player` — the `Player` instance.
- `ctx.client` — the `Client` (room, connection state, etc.).

Multi-step interactive flows are just `await ctx.prompt(...)` calls in a
loop, checking each answer as it comes back. See `commands/quote.py`'s
`QuoteCommand._write()` or `commands/new_player.py`'s step functions for
real examples — there's no separate "prompt helper" abstraction to learn
beyond `ctx.prompt()` itself.


## 4) `Help` and `HelpCategory` (`commands/help.py`)

Every real command in this codebase declares a `help = Help(...)`
attribute — the `help`/`table` commands and the login-time "help
categories" listing all read it. Fields:

```py
help = Help(
    summary     = 'One-line summary shown in listings.',
    description = 'Longer explanation shown by `help <command>`.',
    category    = HelpCategory.COMMUNICATION,   # groups commands in listings
    usage       = [('say <message>', 'Speak aloud.')],
    examples    = [('say Hello!', 'Greet everyone nearby.')],
    notes       = ['Shouting reaches adjacent rooms.'],
)
```

All fields except `category` default to empty/placeholder values, so a
minimal `Help(summary=..., category=...)` is fine to start with.
`HelpCategory` is an `Enum` in `commands/help.py` (not `command_types.py`
— that file no longer exists); see it for the current category list and
one-line descriptions.


## 5) `CommandResult` (`commands/base_command.py`)

```py
@dataclass
class CommandResult:
    success: bool
    message: str = ''
    error:   str = ''
    data:    dict = field(default_factory=dict)
```

Use the classmethods rather than constructing it by hand:

```py
return CommandResult.ok()                       # success, no message
return CommandResult.ok('Done.')                # success, with a message
return CommandResult.fail('Not enough gold.')   # failure
return CommandResult.fail('Not enough gold.', error='insufficient_funds')
```

`message` is a single string, not `str | list[str]` — send multi-line
output to the player via `ctx.send(*lines)` as you go; `CommandResult`'s
`message` is a short final status, and is often left empty (`ok()`) when
the command already sent everything it needed to via `ctx.send`.


## 6) Testing a command

The common pattern: build a small fake (or real) `ctx` and call
`SomeCommand().execute(ctx, *args)` directly — no `CommandProcessor`
needed for a single command's unit tests. See `tests/test_more_prompt.py`
or `tests/test_quote.py` for two real, current examples. Shape:

```py
import unittest
from unittest.mock import AsyncMock
from commands.your_command import YourCommand

class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)   # queued ctx.prompt() replies, in order
        self.sent = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.extend(a) if isinstance(a, list) else self.sent.append(a)

    async def prompt(self, prompt_text='', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None   # None == disconnect


class TestYourCommand(unittest.IsolatedAsyncioTestCase):
    async def test_basic(self):
        ctx = _FakeCtx(['some input'], player=your_test_player)
        result = await YourCommand().execute(ctx)
        self.assertTrue(result.success)
```

For registration/dispatch-level tests (does discovery find your command,
does it respect `modes`, alias collisions, etc.) use
`create_command_processor()` (`commands/command_processor.py`) instead,
which runs real `discover()` against the actual `commands/` package:

```py
from commands.command_processor import create_command_processor

processor = create_command_processor()
cmd, is_alias = processor.find_command('greet')
```


## 7) Best practices

- One command class per file, named after the command (`commands/quote.py`
  → `QuoteCommand`), matching the rest of the package.
- Keep `execute()` focused on I/O and dispatch; push real logic into plain
  functions/helpers in the same module so it's testable without a `ctx` at
  all where possible.
- Always set `help` — it costs nothing and both `help <command>` and the
  categorized `help` listing depend on it.
- Don't forget `modes` if a command shouldn't be available everywhere —
  the default `{Mode.GAME}` is usually right, but login-time or
  admin-only commands need to say so explicitly.


## 8) Troubleshooting

- **Command doesn't show up**: check the server log for `discover()`
  warnings — a duplicate `name`/alias, an exception in `__init__`, or an
  import error in that module will all be logged and the command silently
  skipped rather than crashing the server.
- **Command class defined but not registered**: confirm it's actually
  defined in that file (not just imported) and that `name` is set and
  non-empty — both are required by `discover()`'s filter.
- **Live server, code already changed**: use the admin `reload` command
  (`commands/reload.py`) to re-import specific modules and rebuild
  connected clients' command tables without a restart — but reload every
  module that changed, including anything the command imports that also
  changed (a stale dependency module can cause confusing import errors on
  reload; a full restart is simpler when in doubt).
