import asyncio
import types
import pytest

import menu_system
from menu_system import Menu, MenuItem


def test_async_get_user_choice_client_style(monkeypatch):
    async def _run():
        sent = []

        async def fake_send(writer, msg):
            sent.append(msg.lines if hasattr(msg, 'lines') else str(msg))

        # First call to receive returns '1' to choose first item
        async def fake_receive(reader):
            if not hasattr(fake_receive, 'called'):
                fake_receive.called = True
                return {'lines': ['1']}
            return {'lines': ['']}

        monkeypatch.setattr(menu_system, 'send_message', fake_send)
        monkeypatch.setattr(menu_system, 'receive_message', fake_receive)

        client_like = types.SimpleNamespace()
        class DummyWriter:
            def write(self, data):
                pass
            async def drain(self):
                return
        class DummyReader:
            pass

        client_like.writer = DummyWriter()
        client_like.reader = DummyReader()
        client_like.return_key = 'Enter'
        client_like.client_settings = {'screen_columns': 80}

        m = Menu(title='TestMenu', columns=1)
        m.add_item(MenuItem(text='First option', shortcuts='1', action=lambda: None))
        m.add_item(MenuItem(text='Second option', shortcuts='2', action=None))

        chosen = await menu_system.async_get_user_choice(client_like, m, 1)
        assert chosen is not None
        assert chosen.text == 'First option'
        assert isinstance(sent, list) and sent

    asyncio.run(_run())


def test_async_get_user_choice_reader_writer_style(monkeypatch):
    async def _run():
        # Test alternate calling style: (reader, writer, client, menu, stack_depth)
        sent = []

        async def fake_send(writer, msg):
            sent.append(msg.lines if hasattr(msg, 'lines') else str(msg))

        async def fake_receive(reader):
            if not hasattr(fake_receive, 'called'):
                fake_receive.called = True
                return {'lines': ['1']}
            return {'lines': ['']}

        monkeypatch.setattr(menu_system, 'send_message', fake_send)
        monkeypatch.setattr(menu_system, 'receive_message', fake_receive)

        class DummyWriter:
            def write(self, data):
                pass
            async def drain(self):
                return
        class DummyReader:
            pass

        client_like = types.SimpleNamespace()
        client_like.writer = DummyWriter()
        client_like.reader = DummyReader()
        client_like.return_key = 'Enter'

        m = Menu(title='TestMenu', columns=1)
        m.add_item(MenuItem(text='One', shortcuts='1', action=lambda: None))

        # call with reader, writer, client, menu, stack_depth
        chosen = await menu_system.async_get_user_choice(client_like.reader, client_like.writer, client_like, m, 1)
        assert chosen is not None
        assert chosen.text == 'One'

    asyncio.run(_run())
