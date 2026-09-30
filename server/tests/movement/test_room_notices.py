"""tests/movement/test_room_notices.py

Movement tells the room left and the room reached (room_notices.py,
simple_server.py's _move()), and "same room" means same level as well as
same room number -- GameContext.send_room() and _describe_room_parts()'s
"X is here" list used to compare the number alone, so every broadcast
leaked into the same-numbered room on every other level.

Run with:
    python -m pytest tests/movement/test_room_notices.py -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Gender, Map, Room
from network_context import GameContext, PETSCIINetworkContext
from room_notices import (arrival_line, balk_dismount_line, beam_in_line,
                          beam_out_line, departure_line, dismount_line,
                          location_of, mount_line, the)
from simple_server import Server


def _player(name='Ryan', gender=Gender.MALE, party=(), level=1):
    return SimpleNamespace(name=name, gender=gender, party=list(party),
                           map_level=level)


class TestLines(unittest.TestCase):

    def test_solo_compass(self):
        p = _player()
        self.assertEqual(departure_line(p, 'n'), 'Ryan moves north.')
        self.assertEqual(arrival_line(p, 'n'), 'Ryan enters from the south.')
        self.assertEqual(arrival_line(p, 'w'), 'Ryan enters from the east.')

    def test_full_direction_words(self):
        p = _player()
        self.assertEqual(departure_line(p, 'north'), 'Ryan moves north.')
        self.assertEqual(arrival_line(p, 'Down'), 'Ryan arrives from above.')
        self.assertIsNone(departure_line(p, 'sideways'))

    def test_solo_up_down(self):
        p = _player()
        self.assertEqual(departure_line(p, 'u'), 'Ryan moves up.')
        self.assertEqual(arrival_line(p, 'u'), 'Ryan arrives from below.')
        self.assertEqual(arrival_line(p, 'd'), 'Ryan arrives from above.')

    def test_party_uses_pronoun_and_plural_verbs(self):
        ann = _player('Ann', Gender.FEMALE, party=['Fat Olaf'])
        self.assertEqual(departure_line(ann, 'e'), 'Ann and her party move east.')
        self.assertEqual(arrival_line(ann, 'e'), 'Ann and her party enter from the west.')
        self.assertEqual(arrival_line(ann, 'd'), 'Ann and her party arrive from above.')
        bob = _player('Bob', Gender.MALE, party=['Fat Olaf'])
        self.assertEqual(departure_line(bob, 's'), 'Bob and his party move south.')


    def test_beam_lines_solo_and_party(self):
        ryan = _player()
        ann = _player('Ann', Gender.FEMALE, party=['Fat Olaf'])
        self.assertEqual(beam_out_line(ryan), 'Ryan shimmers and fades away!')
        self.assertEqual(beam_in_line(ryan), 'Ryan shimmers into view!')
        self.assertEqual(beam_out_line(ann, malfunction=True),
                         'Ann and her party flicker erratically and vanish!')
        self.assertEqual(beam_in_line(ann, malfunction=True),
                         'Ann and her party flicker into view, looking dazed.')

    def test_the_does_not_double_articles(self):
        self.assertEqual(the('leather armor'), 'the leather armor')
        self.assertEqual(the('The Howling'), 'The Howling')
        self.assertEqual(the('An Old Map'), 'An Old Map')
        self.assertEqual(the('Anvil'), 'the Anvil')

    def test_names_phrase(self):
        from room_notices import names_phrase
        self.assertEqual(names_phrase(['Frodo']), 'Frodo')
        self.assertEqual(names_phrase(['Frodo', 'Sam']), 'Frodo and Sam')
        self.assertEqual(names_phrase(['Frodo', 'Sam', 'Pippin']), 'Frodo, Sam and Pippin')

    def test_group_lines(self):
        from room_notices import (carry_line, group_arrival_line, group_departure_line,
                                  leader_departure_line, you_carry_line)
        rulan = _player('Rulan')
        two = ['Frodo', 'Sam']
        self.assertEqual(group_departure_line(rulan, 'n', two),
                         'Rulan leaves north, with Frodo and Sam following.')
        self.assertEqual(leader_departure_line('n', two),
                         'You leave north, with Frodo and Sam following.')
        self.assertEqual(group_arrival_line(rulan, 'n', two),
                         'Rulan arrives from the south, with Frodo and Sam following.')
        self.assertEqual(group_departure_line(rulan, 'u', ['Frodo']),
                         'Rulan goes up, with Frodo following.')
        self.assertEqual(leader_departure_line('d', ['Frodo']),
                         'You go down, with Frodo following.')
        self.assertEqual(group_arrival_line(rulan, 'u', ['Frodo']),
                         'Rulan arrives from below, with Frodo following.')
        ann = _player('Ann', Gender.FEMALE, party=['Fat Olaf'])
        self.assertEqual(group_departure_line(ann, 'e', ['Frodo']),
                         'Ann and her party leave east, with Frodo following.')
        # nobody conscious following: the plain lines, and nothing for the leader
        self.assertEqual(group_departure_line(rulan, 'n', []), 'Rulan moves north.')
        self.assertEqual(group_arrival_line(rulan, 'n', []), 'Rulan enters from the south.')
        self.assertIsNone(leader_departure_line('n', []))
        self.assertEqual(carry_line(rulan, ['Bilbo']), 'Rulan carries Bilbo, who is unconscious.')
        self.assertEqual(carry_line(rulan, ['Bilbo', 'Sam']),
                         'Rulan carries Bilbo and Sam, who are unconscious.')
        self.assertEqual(you_carry_line(['Bilbo']), 'You carry Bilbo, who is unconscious.')
        self.assertIsNone(carry_line(rulan, []))

    def test_mount_lines(self):
        ann = _player('Ann', Gender.FEMALE)
        self.assertEqual(mount_line(ann, 'Blaze'), 'Ann climbs onto Blaze.')
        self.assertEqual(dismount_line(ann, 'Blaze'), 'Ann dismounts Blaze.')
        self.assertEqual(dismount_line(ann), 'Ann dismounts.')
        self.assertEqual(balk_dismount_line(ann),
                         "Ann's horse balks at the water, and she dismounts.")


def _map() -> Map:
    m = Map()
    rooms = {
        1: Room(number=1, name='Lobby', desc='', exits={'south': 13}),
        13: Room(number=13, name='Cavern Head', desc='', exits={'north': 1}),
    }
    m.levels[1] = rooms
    m.rooms = rooms
    return m


class TestMoveNotifies(unittest.IsolatedAsyncioTestCase):

    async def test_departure_before_move_arrival_after(self):
        server = Server('127.0.0.1', 0, 0)
        server.game_map = _map()
        ctx = MagicMock()
        ctx.client.room = 1
        ctx.player = _player()
        ctx.player.map_room = 1
        ctx.send = AsyncMock()
        rooms_at_send = []

        async def send_room(line, exclude_self=False):
            rooms_at_send.append((ctx.client.room, line, exclude_self))
        ctx.send_room = send_room

        with patch.object(Server, '_show_room_then_encounter', new=AsyncMock()), \
             patch('visited_rooms.mark_visited'):
            # every post-move encounter hook is a no-op for this player
            for mod, fn in (('encounters.desert', 'try_desert_sweat'),
                            ('ally_events', 'try_ally_find_silver'),
                            ('wild_horse_events', 'try_wandering_horse_encounter'),
                            ('encounters.dwarf', 'try_steal'),
                            ('encounters.little_girl', 'try_encounter'),
                            ('encounters.meteor', 'try_encounter'),
                            ('encounters.ringwraith', 'try_wraith_stalks'),
                            ('encounters.galadriel', 'try_encounter'),
                            ('encounters.djinn_sighting', 'try_encounter'),
                            ('ally_events.starvation', 'try_encounter'),
                            ('spells.charm', 'try_charm_join_offer')):
                patch(f'{mod}.{fn}', new=AsyncMock()).start()
            patch('encounters.dwarf.maybe_relocate').start()
            try:
                await server._move(ctx, 's')
            finally:
                patch.stopall()

        self.assertEqual(rooms_at_send, [
            (1, 'Ryan moves south.', True),
            (13, 'Ryan enters from the north.', True),
        ])

    async def test_group_moves_as_one_with_follow_me(self):
        """A FOLLOW ME leader moves as one group (guild_follow.py): the room
        left and the room reached each get one line naming the followers,
        plus a "carries ... unconscious" line; the leader reads its own
        version; followers get only "You follow ...", after they've been
        moved -- and aren't sent the group lines."""
        from flags import PlayerFlags
        server = Server('127.0.0.1', 0, 0)
        server.game_map = _map()

        def person(name, room, *, following=None, unconscious=False):
            player = _player(name)
            player.id = name.lower()
            player.map_room = room
            player.guild_following = following
            player.carried_followers = []
            player.quote = None
            player.query_flag = lambda flag, u=unconscious: u and flag == PlayerFlags.UNCONSCIOUS
            client = SimpleNamespace(room=room, presence_area=None, virtual_location=None)
            got = []

            async def send(*lines):
                for line in lines:
                    got.extend(line if isinstance(line, list) else [line])
            ctx = SimpleNamespace(player=player, client=client, server=server, send=send)
            client.ctx = ctx
            return ctx, got

        leader, leader_got = person('Rulan', 1)
        leader.player.carried_followers = [{'id': 'pippin', 'name': 'Pippin'}]
        frodo, frodo_got = person('Frodo', 1, following='rulan')
        sam, sam_got = person('Sam', 1, following='rulan', unconscious=True)
        left, left_got = person('Watcher', 1)
        reached, reached_got = person('Rival', 13)
        server.clients = {i: c.client for i, c in enumerate((leader, frodo, sam, left, reached))}

        with patch.object(Server, '_show_room_then_encounter', new=AsyncMock()), \
             patch.object(Server, '_show_room', new=AsyncMock()), \
             patch('visited_rooms.mark_visited'):
            for mod, fn in (('encounters.desert', 'try_desert_sweat'),
                            ('ally_events', 'try_ally_find_silver'),
                            ('wild_horse_events', 'try_wandering_horse_encounter'),
                            ('encounters.dwarf', 'try_steal'),
                            ('encounters.little_girl', 'try_encounter'),
                            ('encounters.meteor', 'try_encounter'),
                            ('encounters.ringwraith', 'try_wraith_stalks'),
                            ('encounters.galadriel', 'try_encounter'),
                            ('encounters.djinn_sighting', 'try_encounter'),
                            ('ally_events.starvation', 'try_encounter'),
                            ('spells.charm', 'try_charm_join_offer')):
                patch(f'{mod}.{fn}', new=AsyncMock()).start()
            patch('encounters.dwarf.maybe_relocate').start()
            try:
                await server._move(leader, 's')
            finally:
                patch.stopall()

        self.assertEqual(leader_got, ['You leave south, with Frodo and Pippin following.',
                                      'You carry Sam, who is unconscious.'])
        self.assertEqual(left_got, ['Rulan leaves south, with Frodo and Pippin following.',
                                    'Rulan carries Sam, who is unconscious.'])
        self.assertEqual(reached_got, ['Rulan arrives from the north, with Frodo and Pippin following.',
                                       'Rulan carries Sam, who is unconscious.'])
        self.assertEqual(frodo_got, ['You follow Rulan south.'])
        self.assertEqual(sam_got, ['You follow Rulan south.'])
        self.assertEqual((frodo.client.room, sam.client.room, leader.client.room), (13, 13, 13))

    async def test_failed_move_says_nothing_to_the_room(self):
        server = Server('127.0.0.1', 0, 0)
        server.game_map = _map()
        ctx = MagicMock()
        ctx.client.room = 1
        ctx.player = _player()
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        await server._move(ctx, 'e')          # no east exit
        ctx.send_room.assert_not_called()
        self.assertEqual(ctx.client.room, 1)


def _client(room, level, name, area=None, activity=None):
    player = _player(name, level=level)
    player.query_flag = lambda flag: False    # _describe_room_parts reads
    player.quote = None                       # these for each bystander
    other_ctx = SimpleNamespace(player=player, send=AsyncMock())
    return SimpleNamespace(room=room, ctx=other_ctx, presence_area=area,
                           virtual_location=area or activity)


class TestSendRoomLevels(unittest.IsolatedAsyncioTestCase):
    """Both working send_room() implementations -- JSON (GameContext)
    and PETSCII -- only reach the sender's level."""

    async def _run(self, cls):
        me = _client(13, 1, 'Ryan')
        same = _client(13, 1, 'Ann')
        other_level = _client(13, 2, 'Bob')
        other_room = _client(14, 1, 'Cid')
        clients = {'a': me, 'b': same, 'c': other_level, 'd': other_room}
        fake_self = SimpleNamespace(player=me.ctx.player, client=me,
                                    server=SimpleNamespace(clients=clients))
        await cls.send_room(fake_self, 'hello', exclude_self=True)
        me.ctx.send.assert_not_called()
        same.ctx.send.assert_awaited_once_with('hello')
        other_level.ctx.send.assert_not_called()
        other_room.ctx.send.assert_not_called()

    async def test_json_context(self):
        await self._run(GameContext)

    async def test_petscii_context(self):
        await self._run(PETSCIINetworkContext)

    def test_location_of_defaults_to_level_1(self):
        bare = SimpleNamespace(room=5, ctx=SimpleNamespace(player=None))
        self.assertEqual(location_of(bare), (1, 5, None))

    async def _say(self, cls, speaker, *listeners):
        clients = {str(i): c for i, c in enumerate((speaker,) + listeners)}
        fake_self = SimpleNamespace(player=speaker.ctx.player, client=speaker,
                                    server=SimpleNamespace(clients=clients))
        await cls.send_room(fake_self, 'hello', exclude_self=True)

    async def test_virtual_areas_hear_only_their_own(self):
        """The Shoppe shares room 1's number with the lobby above it."""
        for cls in (GameContext, PETSCIINetworkContext):
            lobby = _client(1, 1, 'Ryan')
            shopper = _client(1, 1, 'Ann', area='Shoppe')
            reader = _client(1, 1, 'Bob', activity='Reading news')  # not a place
            await self._say(cls, lobby, shopper, reader)
            shopper.ctx.send.assert_not_called()
            reader.ctx.send.assert_awaited_once_with('hello')

            lobby = _client(1, 1, 'Ryan')
            shopper = _client(1, 1, 'Ann', area='Shoppe')
            other = _client(1, 1, 'Cid', area='Shoppe')
            await self._say(cls, shopper, lobby, other)
            lobby.ctx.send.assert_not_called()
            other.ctx.send.assert_awaited_once_with('hello')

    async def test_area_broadcasts_stay_on_one_level(self):
        """There's a Shoppe on each of levels 1-5 -- the name isn't a place."""
        from presence import broadcast_area, others_present
        me = _client(1, 1, 'Ryan', area='Shoppe')
        same = _client(1, 1, 'Ann', area='Shoppe')
        other_level = _client(1, 3, 'Bob', area='Shoppe')
        ctx = SimpleNamespace(player=me.ctx.player, client=me,
                              server=SimpleNamespace(clients={'m': me, 's': same, 'o': other_level}))
        await broadcast_area(ctx, 'Shoppe', 'hi')
        same.ctx.send.assert_awaited_once_with('hi')
        other_level.ctx.send.assert_not_called()
        self.assertEqual(others_present(ctx, 'Shoppe'), ['Ann'])


class TestOccupantListLevels(unittest.TestCase):

    def test_is_here_list_skips_other_levels(self):
        server = Server('127.0.0.1', 0, 0)
        m = _map()
        m.levels[2] = {13: Room(number=13, name='Elsewhere', desc='', exits={})}
        server.game_map = m
        viewer = _client(13, 1, 'Ryan')
        viewer.ctx.player.client_settings = MagicMock()
        server.clients = {'v': viewer, 'a': _client(13, 1, 'Ann'),
                          'b': _client(13, 2, 'Bob')}
        text = '\n'.join(sum(server._describe_room_parts(viewer), []))
        self.assertIn('Ann', text)
        self.assertNotIn('Bob', text)


if __name__ == '__main__':
    unittest.main()
