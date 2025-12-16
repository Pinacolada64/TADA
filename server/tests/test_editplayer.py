import asyncio
import types

from commands.editplayer import EditPlayerCommand
from flags import PlayerFlags


def test_editplayer_toggle_self():
    # Create a fake player with minimal API
    class FakePlayer:
        def __init__(self):
            self.flags = {}
            self.name = 'tester'
        def toggle_flag(self, flag, verbose=False):
            # flip boolean or set True
            v = self.flags.get(flag)
            if isinstance(v, bool):
                self.flags[flag] = not v
            else:
                self.flags[flag] = True
        def query_flag(self, flag):
            v = self.flags.get(flag)
            if isinstance(v, bool):
                return v
            return bool(getattr(v, 'status', False))

    player = FakePlayer()
    # create a context mapping where get_player_from_context will find player
    context = {'player': player, 'client': types.SimpleNamespace(player=player)}
    cmd = EditPlayerCommand()
    # toggle ADMIN
    res = asyncio.run(cmd.execute(context, ['ADMIN']))
    assert res.success
    assert res.data.get('flag') in ('ADMIN', 'Admin', 'admin', PlayerFlags.ADMIN.name)
    # Now the flag should be present and True
    assert player.flags.get(PlayerFlags.ADMIN) is True or player.query_flag(PlayerFlags.ADMIN) is True


def test_editplayer_unknown_flag():
    class FakePlayer:
        def __init__(self):
            self.flags = {}
            self.name = 'tester'
        def query_flag(self, flag):
            return False
    player = FakePlayer()
    context = {'player': player, 'client': types.SimpleNamespace(player=player)}
    cmd = EditPlayerCommand()
    res = asyncio.run(cmd.execute(context, ['FOO']))
    assert not res.success
    assert res.error == 'bad_flag'

