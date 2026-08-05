"""tests/test_pronoun_token_substitution.py

Unit tests for %-token substitution (tada_utilities.substitute_tokens) and
its wiring into every outbound line/prompt of GameContext.send()/prompt()
(network_context.py), keyed to the recipient. Generalizes what used to be
ally_events/farewell.py-only %-token parsing to any player-facing text.

Run with:
    python -m pytest tests/test_pronoun_token_substitution.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from base_classes import Gender, PlayerClass, PlayerRace
from network_context import GameContext
from tada_utilities import substitute_tokens


class _FakeSubject:
    def __init__(self, name='Alice', gender=Gender.FEMALE,
                 char_class=PlayerClass.WIZARD, char_race=PlayerRace.ELF):
        self.name = name
        self.gender = gender
        self.char_class = char_class
        self.char_race = char_race


class TestSubstituteTokens(unittest.TestCase):

    def test_name_and_pronoun_tokens(self):
        subject = _FakeSubject()
        result = substitute_tokens('%n draws %p sword; %s is ready.', subject)
        self.assertEqual(result, "Alice draws her sword; she is ready.")

    def test_all_pronoun_types(self):
        subject = _FakeSubject(gender=Gender.MALE)
        result = substitute_tokens('%s %o %p %P %r', subject)
        self.assertEqual(result, 'he him his his himself')

    def test_class_and_race_tokens(self):
        subject = _FakeSubject()
        result = substitute_tokens('%n is an %e %c.', subject)
        self.assertEqual(result, 'Alice is an Elf Wizard.')

    def test_literal_percent_escape(self):
        subject = _FakeSubject()
        self.assertEqual(substitute_tokens('100%% done', subject), '100% done')

    def test_unrecognized_token_passes_through(self):
        subject = _FakeSubject()
        self.assertEqual(substitute_tokens('50% off, %q?', subject), '50% off, %q?')

    def test_trailing_percent_does_not_raise(self):
        subject = _FakeSubject()
        self.assertEqual(substitute_tokens('Success %', subject), 'Success %')

    def test_no_percent_returns_original_string_object(self):
        subject = _FakeSubject()
        text = 'no tokens here'
        self.assertIs(substitute_tokens(text, subject), text)

    def test_missing_gender_falls_back_to_empty_pronoun(self):
        subject = _FakeSubject()
        del subject.gender
        self.assertEqual(substitute_tokens('%s arrives.', subject), ' arrives.')


class TestGameContextSubstitutesForRecipient(unittest.IsolatedAsyncioTestCase):
    """ctx.send()/ctx.prompt() run every line/prompt through
    substitute_tokens() keyed to ctx.player -- always the recipient
    (per Ryan 8/3/26), distinct from ally_events/farewell.py's own
    ally-targeted substitution, which resolves before ctx.send() ever
    sees the text."""

    def _make_ctx(self, player) -> GameContext:
        ctx = GameContext(player=player, reader=None, writer=None,
                           server=None, client=None)
        ctx._paginate = AsyncMock()
        ctx._send_formatted = AsyncMock()
        return ctx

    async def test_send_substitutes_against_recipient(self):
        player = _FakeSubject(name='Bob', gender=Gender.MALE)
        player.client_settings = type('CS', (), {
            'screen_rows': 10, 'screen_columns': 80,
        })()
        player.query_flag = lambda flag: False

        ctx = self._make_ctx(player)
        await ctx.send('%n draws %p sword.')

        sent = ctx._send_formatted.call_args.args[0]
        self.assertIn('Bob draws his sword.', sent)

    async def test_prompt_text_substitutes_against_recipient(self):
        player = _FakeSubject(name='Carol', gender=Gender.FEMALE)
        player.client_settings = type('CS', (), {
            'screen_rows': 10, 'screen_columns': 80,
        })()
        player.query_flag = lambda flag: False
        player.pending_pages = None

        ctx = self._make_ctx(player)
        ctx.server = type('Srv', (), {'send_message': AsyncMock()})()
        ctx.reader = type('Rdr', (), {'readline': AsyncMock(return_value=b'')})()

        await ctx.prompt('%n, are %s ready?')

        msg = ctx.server.send_message.call_args.args[1]
        self.assertIn('Carol, are she ready?', msg.prompt)


if __name__ == '__main__':
    unittest.main()
