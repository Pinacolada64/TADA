"""tests/social/test_follow_me.py

FOLLOW ME / STAY (guild_follow.py, commands/follow.py, commands/stay.py):
SPUR.MISC5.S's "come" + SPUR.MISC4.S's "stay", ported as a hybrid --
online guildmates follow live, logged-off guildmates parked in the room
are carried and dropped off (their saved location rewritten).
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import guild_follow
from base_classes import Guild, RoomAlignment
from commands.follow import FollowCommand
from commands.stay import StayCommand
from flags import PlayerFlags


class FakePlayer:
    def __init__(self, pid, guild=Guild.CLAW, follow=True, unconscious=False, level=1, room=5):
        self.id = pid
        self.name = pid.title()
        self.guild = guild
        self.map_level = level
        self.map_room = room
        self.unsaved_changes = False
        self._flags = {PlayerFlags.GUILD_FOLLOW_MODE: follow, PlayerFlags.UNCONSCIOUS: unconscious}

    def query_flag(self, flag):
        return self._flags.get(flag, False)

    def toggle_flag(self, flag):
        self._flags[flag] = not self._flags.get(flag, False)
        return self._flags[flag], None


class FakeServer:
    def __init__(self, rooms=None):
        self.clients = {}
        self.game_map = SimpleNamespace(get_room=lambda lvl, no: (rooms or {}).get((lvl, no)))
        self._show_room = AsyncMock()
        self._leave_combat_on_move = lambda ctx, room: None


def add_ctx(server, player, answers=()):
    client = SimpleNamespace(room=player.map_room, virtual_location=None, map_level=player.map_level)
    ctx = SimpleNamespace(player=player, client=client, server=server,
                          send=AsyncMock(), prompt=AsyncMock(side_effect=list(answers) or None))
    if not answers:
        ctx.prompt = AsyncMock(return_value='')
    client.ctx = ctx
    server.clients[player.id] = client
    return ctx


def sent_text(ctx) -> str:
    out = []
    for call in ctx.send.await_args_list:
        arg = call.args[0]
        out.extend(arg if isinstance(arg, list) else [arg])
    return '\n'.join(out)


def write_offline(tmp, pid, *, guild='Mark of the Claw', follow=True, unconscious=False, level=1, room=5):
    data = {
        'id': pid, 'name': pid.title(), 'guild': guild, 'map_level': level, 'map_room': room,
        'flags': {
            'Guild Follow Mode': {'name': 'Guild Follow Mode', 'status': follow},
            'Unconscious': {'name': 'Unconscious', 'status': unconscious},
        },
    }
    (Path(tmp) / f'player-{pid}.json').write_text(json.dumps(data))


class _TmpRunDir(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = self._tmp.name
        patcher = patch('net_common.run_server_dir', self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class TestFollowMe(_TmpRunDir):

    async def test_civilian_rejected(self):
        server = FakeServer()
        ctx = add_ctx(server, FakePlayer('lead', guild=Guild.CIVILIAN))
        res = await FollowCommand().execute(ctx, 'me')
        self.assertFalse(res.success)
        self.assertIn('Only guild members may use this command.', sent_text(ctx))

    async def test_nobody_here(self):
        server = FakeServer()
        ctx = add_ctx(server, FakePlayer('lead'))
        await FollowCommand().execute(ctx, 'me')
        self.assertIn('Nobody here!', sent_text(ctx))

    async def test_recruits_willing_online_guildmate(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'), answers=['Y'])
        mate = add_ctx(server, FakePlayer('mate'))
        await FollowCommand().execute(lead, 'me')
        self.assertEqual(mate.player.guild_following, 'lead')
        self.assertIn('Mate agrees to follow you..', sent_text(lead))
        self.assertIn('Lead leads the way', sent_text(mate))

    async def test_other_guild_stares(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        add_ctx(server, FakePlayer('rival', guild=Guild.FIST))
        await FollowCommand().execute(lead, 'me')
        text = sent_text(lead)
        self.assertIn("Rival stares at you, and doesn't move.", text)
        self.assertIn('Nobody wants to follow!', text)
        lead.prompt.assert_not_awaited()

    async def test_follow_mode_off_refuses(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'), answers=['Y'])
        mate = add_ctx(server, FakePlayer('mate', follow=False))
        await FollowCommand().execute(lead, 'me')
        self.assertIn("Mate doesn't want to follow..", sent_text(lead))
        self.assertIsNone(getattr(mate.player, 'guild_following', None))

    async def test_declining_prompt_skips(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'), answers=['n'])
        mate = add_ctx(server, FakePlayer('mate'))
        await FollowCommand().execute(lead, 'me')
        self.assertIsNone(getattr(mate.player, 'guild_following', None))

    async def test_unconscious_not_carried_yet(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'), answers=['Y'])
        add_ctx(server, FakePlayer('mate', unconscious=True))
        await FollowCommand().execute(lead, 'me')
        self.assertIn("Mate is unconscious! You can't carry them yet.", sent_text(lead))

    async def test_carries_offline_guildmate_in_room(self):
        write_offline(self.tmp, 'sleeper')
        write_offline(self.tmp, 'elsewhere', room=9)
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'), answers=['Y'])
        await FollowCommand().execute(lead, 'me')
        self.assertEqual(lead.player.carried_followers, [{'id': 'sleeper', 'name': 'Sleeper'}])

    async def test_offline_carried_by_someone_else_is_skipped(self):
        write_offline(self.tmp, 'sleeper')
        server = FakeServer()
        other = add_ctx(server, FakePlayer('other', room=77))
        other.player.carried_followers = [{'id': 'sleeper', 'name': 'Sleeper'}]
        lead = add_ctx(server, FakePlayer('lead'))
        await FollowCommand().execute(lead, 'me')
        self.assertIn('Nobody here!', sent_text(lead))

    async def test_follower_cannot_lead(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        me = add_ctx(server, FakePlayer('me'))
        me.player.guild_following = 'lead'
        res = await FollowCommand().execute(me, 'me')
        self.assertFalse(res.success)
        self.assertIn("You're following Lead yourself!", sent_text(me))

    async def test_toggle_off_breaks_away(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        mate = add_ctx(server, FakePlayer('mate', follow=True))
        mate.player.guild_following = 'lead'
        await FollowCommand().execute(mate)
        self.assertIsNone(mate.player.guild_following)
        self.assertIn('Mate stops following you.', sent_text(lead))


class TestBringFollowers(unittest.IsolatedAsyncioTestCase):

    async def test_follower_in_room_moves_with_leader(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        mate = add_ctx(server, FakePlayer('mate'))
        mate.player.guild_following = 'lead'
        await guild_follow.bring_followers(lead, from_level=1, from_room=5, to_level=1, to_room=6, direction='n')
        self.assertEqual((mate.client.room, mate.player.map_room), (6, 6))
        self.assertIn('You follow Lead north.', sent_text(mate))
        server._show_room.assert_awaited_once_with(mate)

    async def test_follower_elsewhere_loses_track(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        mate = add_ctx(server, FakePlayer('mate', room=9))
        mate.player.guild_following = 'lead'
        await guild_follow.bring_followers(lead, from_level=1, from_room=5, to_level=1, to_room=6, direction='n')
        self.assertEqual(mate.client.room, 9)
        self.assertIsNone(mate.player.guild_following)
        self.assertIn('You lose track of Lead.', sent_text(mate))

    async def test_cross_level_move_updates_level(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        mate = add_ctx(server, FakePlayer('mate'))
        mate.player.guild_following = 'lead'
        await guild_follow.bring_followers(lead, from_level=1, from_room=5, to_level=2, to_room=1, direction='d')
        self.assertEqual((mate.player.map_level, mate.client.room), (2, 1))


class TestStay(_TmpRunDir):

    async def test_nobody_following(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        await StayCommand().execute(lead)
        self.assertIn('Nobody is following!', sent_text(lead))

    async def test_drops_carried_and_releases_live(self):
        write_offline(self.tmp, 'sleeper', room=1)
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead', level=2, room=33))
        mate = add_ctx(server, FakePlayer('mate', level=2, room=33))
        mate.player.guild_following = 'lead'
        lead.player.carried_followers = [{'id': 'sleeper', 'name': 'Sleeper'}]
        await StayCommand().execute(lead)
        data = json.loads((Path(self.tmp) / 'player-sleeper.json').read_text())
        self.assertEqual((data['map_level'], data['map_room']), (2, 33))
        self.assertEqual(data['followed_leader_name'], 'Lead')
        self.assertEqual(lead.player.carried_followers, [])
        self.assertIsNone(mate.player.guild_following)
        self.assertIn('Lead tells you to stay here.', sent_text(mate))
        self.assertIn('Sleeper stays here.', sent_text(lead))

    async def test_carried_follower_who_logged_in_is_skipped(self):
        write_offline(self.tmp, 'sleeper', room=1)
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead', room=33))
        add_ctx(server, FakePlayer('sleeper', room=1))
        lead.player.carried_followers = [{'id': 'sleeper', 'name': 'Sleeper'}]
        await StayCommand().execute(lead)
        data = json.loads((Path(self.tmp) / 'player-sleeper.json').read_text())
        self.assertEqual(data['map_room'], 1)

    async def test_other_guild_turf_blocks(self):
        write_offline(self.tmp, 'sleeper', room=1)
        turf = SimpleNamespace(alignment=RoomAlignment.FIST, flags=[])
        server = FakeServer(rooms={(1, 5): turf})
        lead = add_ctx(server, FakePlayer('lead'))
        lead.player.carried_followers = [{'id': 'sleeper', 'name': 'Sleeper'}]
        res = await StayCommand().execute(lead)
        self.assertFalse(res.success)
        self.assertIn('A strange force prevents you from dropping off followers!', sent_text(lead))
        self.assertEqual(len(lead.player.carried_followers), 1)

    def test_drop_off_blocked_rules(self):
        claw = FakePlayer('lead', guild=Guild.CLAW)
        room = lambda align=RoomAlignment.NEUTRAL, flags=(): SimpleNamespace(alignment=align, flags=list(flags))
        self.assertFalse(guild_follow.drop_off_blocked(claw, room()))
        self.assertFalse(guild_follow.drop_off_blocked(claw, room(RoomAlignment.CLAW)))
        self.assertTrue(guild_follow.drop_off_blocked(claw, room(RoomAlignment.SWORD)))
        self.assertTrue(guild_follow.drop_off_blocked(claw, room(RoomAlignment.FREE_FIRE)))
        self.assertTrue(guild_follow.drop_off_blocked(claw, room(flags=['water'])))


class TestLogoff(_TmpRunDir):

    async def test_leader_logoff_drops_off_and_releases(self):
        write_offline(self.tmp, 'sleeper', room=1)
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead', room=12))
        mate = add_ctx(server, FakePlayer('mate', room=12))
        mate.player.guild_following = 'lead'
        lead.player.carried_followers = [{'id': 'sleeper', 'name': 'Sleeper'}]
        await guild_follow.drop_off_on_logoff(lead)
        data = json.loads((Path(self.tmp) / 'player-sleeper.json').read_text())
        self.assertEqual(data['map_room'], 12)
        self.assertIsNone(mate.player.guild_following)
        self.assertIn('Lead has left the realm', sent_text(mate))

    async def test_follower_logoff_tells_leader(self):
        server = FakeServer()
        lead = add_ctx(server, FakePlayer('lead'))
        mate = add_ctx(server, FakePlayer('mate'))
        mate.player.guild_following = 'lead'
        await guild_follow.drop_off_on_logoff(mate)
        self.assertIn('Mate is no longer following you.', sent_text(lead))


class TestFollowedLeaderPersistence(_TmpRunDir):

    def test_followed_leader_name_round_trips(self):
        from player import Player
        p = Player(id='roundtrip', name='Roundtrip')
        p.followed_leader_name = 'Lead'
        p.save(force=True)
        q = Player(id='roundtrip', name='Roundtrip')
        q._load()
        self.assertEqual(q.followed_leader_name, 'Lead')

    def test_session_fields_not_saved(self):
        from player import Player
        p = Player(id='sess', name='Sess')
        p.guild_following = 'lead'
        p.carried_followers = [{'id': 'x', 'name': 'X'}]
        p.save(force=True)
        data = json.loads((Path(self.tmp) / 'player-sess.json').read_text())
        self.assertNotIn('guild_following', data)
        self.assertNotIn('carried_followers', data)


if __name__ == '__main__':
    unittest.main()
