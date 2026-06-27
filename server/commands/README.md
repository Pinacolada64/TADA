# Commands — How to register, write, and respond to a command

This README explains the current command system used by the server and shows how to:

- register a command (decorator-based)
- write a command class
- return outputs (CommandResult)
- implement interactive prompts (server-driven) so a command can prompt the connected client

This guide assumes you are working in `server/commands/`.

---

## 1) Command registration (auto-discovered)

We prefer decorator-based registration. The decorator `@command(...)` is defined in `commands/command_processor.py` and collects metadata for automatic discovery.

Example (recommended):

```py
from commands.base_command import Command, CommandResult
from commands.command_processor import command


@command(name='greet', aliases=['hello'], summary='Say hello')
class GreetCommand(Command):
    async def execute(self, context, args):
        name = args[0] if args else 'stranger'
        return CommandResult(success=True, message=f'Hello, {name}!')
```

- The decorator registers the class so `create_command_processor()` will instantiate and register it.
- The command class should inherit `BaseCommand` and implement `async def execute(self, context, args)`.
- `context` is the processor context and will contain `context['client']` (the Client instance) if the command is executed within a live connection.


## 2) Command result and shapes

Commands return `CommandResult` (dataclass) or a plain dict with the same keys. The fields used by the server are:

- `success` (bool) — whether the command succeeded
- `message` (str | list[str]) — the main return text shown to player(s)
- `error` (str) — a short error code
- `data` (dict) — additional structured data; server uses `data['changes']` or `data['authenticated']` etc.

Example:

```py
from commands.base_command import CommandResult
return CommandResult(success=True, message=['Line 1', 'Line 2'], data={'changes': {'mode': 'app'}})
```

If you return a dict instead of CommandResult, use the same key names.


## 3) Non-interactive vs interactive commands

- Non-interactive commands accept all needed arguments in `args` and immediately return a `CommandResult`.
- Interactive commands (server-driven prompts) may send a `Message` prompt to the client and wait for a single reply. This is implemented by the helper pattern used in `new_player.py`.

Important: interactive commands require the `Client` object to expose both `writer` and `reader` on `context['client']`.
The server (`simple_server.py`) sets `client.writer = writer` and `client.reader = reader` in the handshake so interactive commands can use them.


## 4) Prompt helper pattern (server-driven prompt)

The `NewPlayerCommand` demonstrates a safe way to prompt the connected client without blocking the whole server. The pattern:

1. Build a `Message` for the prompt:

```py
from net_common import Message, to_jsonb
msg = Message(lines=['What is your name?'], prompt='name> ')
writer.write(to_jsonb(msg) + b'\n')
await writer.drain()
```

2. Read a single JSON message reply from the client's reader:

```py
raw = await reader.readline()
obj = from_jsonb(raw)
# obj likely contains {'lines': ['the response'], 'prompt':'', ...}
response_line = obj.get('lines', [''])[0]
```

This pattern is encapsulated in `prompt_client()` in `new_player.py`. Use that helper or copy the logic — it keeps your command implementation small and readable.


## 5) Step-based interactive flows (example: `new` command)

`new` was implemented as an interactive, step-driven flow. High-level flow:

1. If `new <username> <password>` provided, run non-interactive branch (create user immediately).
2. Otherwise if `context['client']` has `reader`/`writer`, prompt sequence:
   - Choose username
   - Choose password
   - Choose gender
   - Choose name (or random)
   - Choose class
   - Choose race
   - Roll stats (4d6 drop lowest) with option to reroll
   - Confirmation

On success, the command returns a `CommandResult` with `data['player']` and `data['changes']` telling the server to switch mode and set `username`.
The server then sends a welcome in `Mode.app` and the player continues.


## 6) Writing tests for commands

- Create a `CommandProcessor` instance using `create_command_processor()` with a stub client object when testing non-interactive commands. Example:

```py
from commands.command_processor import create_command_processor
class DummyClient: pass
p = create_command_processor(DummyClient(), context={'username': None})
# now call p.process_input('new alice secret')
```

- For interactive flow tests, you need to simulate client-side `reader` and `writer` streams (in-memory pipes). Tests can use `asyncio` streams backed by `StreamReader`/`StreamWriter` pair via `asyncio.open_connection` against a local test server or use `asyncio.StreamReaderProtocol` wrappers; these are advanced but doable.


## 7) Best practices

- Keep command logic pure where possible: do I/O only when necessary and return structured `data` for server state changes.
- Use the decorator and the provided `CommandResult` dataclass for consistency.
- For interactive flows, separate the prompt UI (prompt_client) from the state machine (choose_gender, choose_class, etc.). It makes the code easier to test and reuse.


## 8) Example minimal command (non-interactive)

```py
from commands.base_command import Command, CommandResult
from commands.command_processor import command


@command('test', aliases=['t'], summary='Test command')
class TestCommand(Command):
    async def execute(self, context, args):
        return CommandResult(success=True, message='Test OK')
```

Place this in `commands/`, restart the server, and `help` should list it (or the inline help will show it even without restart if imported).


## 9) Troubleshooting

- If a command does not appear in the processor's list:
  - Ensure the module is imported (auto-discovery imports modules in `commands/` except those starting with `test` or `_`).
  - Ensure the class is decorated with `@command` or explicitly instantiated/registered in `create_command_processor`.

- If interactive prompting fails, confirm the running server assigned `client.reader` and `client.writer` and that the client responds with JSON messages (the TADA client and `simple_client.py` adhere to that contract).

---

If you'd like, I can also add a small example test harness that simulates an interactive client and runs through the `new` command flow automatically.

