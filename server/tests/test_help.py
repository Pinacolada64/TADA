import asyncio
import logging
import pytest

from commands.command_processor import CommandProcessor
from commands.base_command import BaseCommand, CommandResult


class DummyClient:
    pass


class DummyMove(BaseCommand):
    name = 'move'
    aliases = ['m']
    summary = 'Move around'

    def help_text(self):
        return 'Usage: move <dir>\nMoves your character.'

    async def execute(self, context, args):
        return CommandResult(success=True, message='moved')


class TestHelpCmd(BaseCommand):
    name = 'help'
    aliases = ['h', '?']

    async def execute(self, context, args=None):
        # Normalize args
        token = None
        rest = []
        if args:
            if isinstance(args, (list, tuple)):
                token = args[0].strip().lower() if len(args) > 0 else None
                rest = args[1:]
            else:
                token = str(args).strip().lower()

        proc = context.get('processor')

        # If asking for categories
        if token in ("categories", "category", "cat", "#cat", "#c"):
            grouped = proc.get_commands_by_category()
            cats = [c.name for c in grouped.keys()]
            lines = ["Available help categories:"] + [f"- {c}" for c in sorted(cats)]
            return CommandResult(success=True, message=lines)

        # If search requested: help search <term>
        if token in ("search", "find") and rest:
            term = " ".join(rest).lower()
            matches = []
            for cmd in proc.get_all_commands():
                if term in cmd.name.lower() or term in (getattr(cmd, 'summary', '') or '').lower():
                    matches.append(cmd.name)
            if not matches:
                return CommandResult(success=False, message=f"No commands found matching '{term}'")
            return CommandResult(success=True, message=[f"Commands matching '{term}':"] + matches)

        # If asking for a specific command
        if token:
            cmd_inst, _ = proc.find_command(token)
            if cmd_inst:
                # Prefer help_text()
                try:
                    if callable(getattr(cmd_inst, 'help_text', None)):
                        ht = cmd_inst.help_text()
                        return CommandResult(success=True, message=ht)
                except Exception:
                    pass
                # Fallback to docstring
                doc = getattr(getattr(cmd_inst, 'execute', None), '__doc__', None)
                if doc:
                    return CommandResult(success=True, message=doc.strip())
                return CommandResult(success=False, message=f'No detailed help available for {token}')
            else:
                return CommandResult(success=False, message=f"No help found for '{token}'")

        # General listing
        lines = ['Available commands:']
        grouped = proc.get_commands_by_category()
        for cat, cmds in grouped.items():
            lines.append(f"\n{getattr(cat,'name',str(cat))}:")
            for c in sorted(cmds, key=lambda x: x.name):
                summary = getattr(c, 'summary', '') or ''
                lines.append(f"  {c.name:<12} - {summary}")
        return CommandResult(success=True, message=lines)


def test_help_general_contains_categories():
    logging.basicConfig(level=logging.DEBUG)
    client = DummyClient()
    processor = CommandProcessor(client=client, context={'username': 'test', 'server': None})
    # Make the processor visible to commands via context
    processor.context['processor'] = processor

    # ensure our dummy move isn't overriding the auto-discovered one; register explicitly
    processor.register_command(DummyMove())
    # register a minimal help command that uses the processor via context
    help_cmd = TestHelpCmd()
    # provide processor reference in the context passed to commands
    help_context = {'processor': processor}
    help_cmd_context = help_context
    # store 'context' on command if used by command implementations
    processor.register_command(help_cmd)

    res = asyncio.run(processor.process_input('help'))
    assert isinstance(res, CommandResult)
    # message may be a list or string
    msg = res.message
    if isinstance(msg, list):
        joined = "\n".join(msg)
    else:
        joined = str(msg)
    assert 'Available commands' in joined or 'Available Commands by Category' in joined


def test_help_move_returns_detailed():
    client = DummyClient()
    processor = CommandProcessor(client=client, context={'username': 'test', 'server': None})
    processor.context['processor'] = processor
    processor.register_command(DummyMove())
    # register help command
    help_cmd = TestHelpCmd()
    processor.register_command(help_cmd)

    res = asyncio.run(processor.process_input('help move'))
    assert isinstance(res, CommandResult)
    # message for detailed help likely returns the help_text string
    msg = res.message
    if isinstance(msg, list):
        joined = "\n".join(msg)
    else:
        joined = str(msg)
    assert 'Usage: move' in joined or 'Moves your character' in joined


def test_help_categories_lists_categories():
    client = DummyClient()
    processor = CommandProcessor(client=client, context={'username': 'test', 'server': None})
    processor.context['processor'] = processor
    processor.register_command(DummyMove())
    processor.register_command(TestHelpCmd())

    res = asyncio.run(processor.process_input('help categories'))
    assert isinstance(res, CommandResult)
    msg = res.message
    if isinstance(msg, list):
        joined = "\n".join(msg)
    else:
        joined = str(msg)
    assert 'MISCELLANEOUS' in joined or 'GENERAL' in joined


def test_help_search_finds_move():
    client = DummyClient()
    processor = CommandProcessor(client=client, context={'username': 'test', 'server': None})
    processor.context['processor'] = processor
    processor.register_command(DummyMove())
    processor.register_command(TestHelpCmd())

    res = asyncio.run(processor.process_input('help search move'))
    assert isinstance(res, CommandResult)
    msg = res.message
    if isinstance(msg, list):
        joined = "\n".join(msg)
    else:
        joined = str(msg)
    assert 'move' in joined


def test_help_nonexistent_returns_error():
    client = DummyClient()
    processor = CommandProcessor(client=client, context={'username': 'test', 'server': None})
    processor.context['processor'] = processor
    processor.register_command(DummyMove())
    processor.register_command(TestHelpCmd())

    res = asyncio.run(processor.process_input('help unicorn'))
    assert isinstance(res, CommandResult)
    msg = res.message
    if isinstance(msg, list):
        joined = "\n".join(msg)
    else:
        joined = str(msg)
    assert 'No help found' in joined or 'No detailed help' in joined

