"""tests/e2e/test_shared_monster_kill_e2e.py — live end-to-end check that
when several players fight one monster, it dies exactly once.

Three real socket clients log in to a real Server, all seeded in level 1
room 13 with its TROLL (strength lowered so the fight is short; starting
in the room means the TROLL doesn't attack on entry). Bot A starts the
fight with ATTACK and keeps swinging at the combat prompt; B and C join
with one ATTACK each, the bystander path (CombatSession.join()).

The race this guards: _monster_dies() marks the fight done first, so a
late ATTACK no longer finds the session, but it then awaits a series of
messages -- and the shadow-ally recruit's Y/N prompt to the killer --
before the kill used to be recorded for everyone. A bystander's ATTACK in
that window opened a second fight against a fresh full-HP copy of the
monster. The recruit roll is random, so here it's replaced by a stub that
always asks the killer and holds _monster_dies() open; everyone else
ATTACKs while the killer is held, then the killer answers and ATTACKs
too.

Checked server-side (fights opened, monster deaths) and from what each
client saw: exactly one fight, one death, one "You have slain", everyone
else told who killed it, and every late ATTACK refused with "already
dead". Run once with an ordinary TROLL and once with it flagged
re_animates, which never goes into dead_monsters, so only
player.slain_here can stop the late ATTACKs.
"""
import asyncio
import time

import pytest

from conftest import perform_login, seed_test_account

# Starts a real Server + real sockets -- slow, excluded from local
# default runs (pyproject.toml addopts -m "not e2e"); CI overrides with
# -m "".
pytestmark = pytest.mark.e2e

_PASSWORD = 'e2epass'
_ROOM = 13            # level 1 CAVERN HEAD, home of monster #3 (TROLL)
_TROLL = 3
_TROLL_HP = 4         # monster HP comes from 'strength' (combat/engine.py _monster_hp())
_MAX_SWINGS = 80


@pytest.mark.parametrize('re_animates', [False, True], ids=['ordinary', 're_animates'])
def test_monster_shared_by_three_players_dies_once(tmp_path, re_animates):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    names = ['e2eparty_a', 'e2eparty_b', 'e2eparty_c']
    from player import Player
    for name in names:
        seed_test_account(name, _PASSWORD, map_room=_ROOM)
        seeded = Player(name=name, id=name)
        seeded.hit_points = 500          # the TROLL can't end the test early
        seeded.unsaved_changes = True
        assert seeded.save(force=True)

    import combat.engine as engine
    from net_common import Message, Mode
    from simple_server import Server

    server = Server('127.0.0.1', 0, 0)
    troll = next(m for m in server.monsters if m.get('number') == _TROLL)
    troll['strength'] = _TROLL_HP
    troll.setdefault('flags', {})['re_animates'] = re_animates

    # Server-side counters: _run_loop runs once per fight opened (only the
    # fight's leader runs it), _monster_dies once per death.
    fights, deaths = [], []
    real_run_loop, real_dies = engine.CombatSession._run_loop, engine.CombatSession._monster_dies

    async def counting_run_loop(self, ctx, **kw):
        fights.append(ctx.player.name)
        return await real_run_loop(self, ctx, **kw)

    async def counting_dies(self, ctx, **kw):
        deaths.append(ctx.player.name)
        return await real_dies(self, ctx, **kw)

    engine.CombatSession._run_loop = counting_run_loop
    engine.CombatSession._monster_dies = counting_dies

    # Stand-in for the shadow-ally recruit (encounters/monster.py
    # try_shadow_ally(), called from _monster_dies() after the kill): always
    # ask the killer, holding _monster_dies() open until they answer.
    import encounters.monster as encounter
    real_shadow = encounter.try_shadow_ally

    async def always_ask(ctx):
        await ctx.prompt('Join you? [Y/N]')
    encounter.try_shadow_ally = always_ask
    seen = {name: [] for name in names}
    late = {}

    async def scenario():
        from simple_client import receive_message, send_message

        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        conns = {}
        for name in names:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            assert await perform_login(reader, writer, name, _PASSWORD)
            conns[name] = (reader, writer)

        async def drain(name, *, quiet=0.4, max_wait=3.0):
            """Collect one client's lines until a prompt arrives and then
            `quiet` seconds pass. ctx.prompt() text lands in "prompt",
            never "lines". Returns (joined text, last prompt)."""
            reader = conns[name][0]
            lines, prompt = [], ''
            deadline = time.time() + max_wait
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(receive_message(reader), timeout=quiet)
                except asyncio.TimeoutError:
                    if prompt:
                        break
                    continue
                if not msg:
                    break
                lines.extend(str(x) for x in (msg.get('lines') or []))
                if msg.get('prompt'):
                    prompt = str(msg['prompt'])
            text = ' '.join(' '.join(lines).split())   # undo server word-wrap
            seen[name].append(text)
            return text, prompt

        async def say(name, text):
            await send_message(conns[name][1], Message(lines=[text], mode=Mode.app))

        async def until_main(name, text=''):
            """Keep reading until this client is back at the main prompt --
            one fixed-length drain can come up short on a slow run."""
            for _ in range(5):
                more, prompt = await drain(name)
                text += ' ' + more
                if prompt.rstrip().endswith('main>'):
                    break
            return text.strip()

        for name in names:
            await drain(name)

        a, b, c = names
        prompts = {}
        # A opens the fight; B and C join it with one bystander swing each
        # (either swing may already be the kill).
        await say(a, 'attack')
        _, prompts[a] = await drain(a)
        assert prompts[a].rstrip().endswith('Command>'), f'A never got the combat prompt: {prompts[a]!r}'
        for name in (b, c):
            await say(name, 'attack')
            _, prompts[name] = await drain(name)

        # A keeps swinging until the fight is over for A.
        for _ in range(_MAX_SWINGS):
            if not prompts[a].rstrip().endswith('Command>'):
                break
            await say(a, 'a')
            _, prompts[a] = await drain(a)

        def held(name):
            return 'Join you?' in prompts[name]

        killer_held = [n for n in names if held(n)]
        assert len(killer_held) == 1, f'expected one killer at the recruit prompt: {prompts}'
        killer = killer_held[0]

        # The race: everyone else ATTACKs while the killer is still inside
        # _monster_dies(), held at the recruit prompt.
        for name in names:
            if name != killer:
                await drain(name, max_wait=1.0)
                await say(name, 'attack')
                late[name] = await until_main(name)

        # Then the killer declines the recruit and ATTACKs too.
        await say(killer, 'n')
        await until_main(killer)
        await say(killer, 'attack')
        late[killer] = await until_main(killer)
        # The bystanders' "is slain!" notices only go out once the killer
        # is released from _monster_dies() -- pick them up now.
        for name in names:
            if name != killer:
                await drain(name, max_wait=1.0)
        await asyncio.sleep(0.5)

        for _, writer in conns.values():
            writer.close()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(asyncio.wait_for(scenario(), timeout=60))
    finally:
        engine.CombatSession._run_loop = real_run_loop
        engine.CombatSession._monster_dies = real_dies
        encounter.try_shadow_ally = real_shadow

    everything = {name: ' '.join(texts) for name, texts in seen.items()}
    assert len(deaths) == 1, f'TROLL died {len(deaths)} times: {deaths}'
    assert fights == [names[0]], f'fights opened: {fights} (a late ATTACK started a new one)'

    # The killer reads "You have slain"; everyone else in the room hears
    # "<killer> slays the TROLL!", and the other fighters also get "The
    # TROLL is slain!" (combat/engine.py _monster_dies()).
    killers = [n for n in names if 'You have slain the TROLL!' in everything[n]]
    assert len(killers) == 1, f'"You have slain" seen by {killers}'
    for name in names:
        if name != killers[0]:
            assert f'{killers[0]} slays the TROLL!' in everything[name], \
                f'{name} never told who killed it: {everything[name][-400:]!r}'
            assert 'The TROLL is slain!' in everything[name], \
                f'{name} never told the TROLL died: {everything[name][-400:]!r}'

    for name, text in late.items():
        assert 'The TROLL is already dead.' in text, \
            f'{name} late ATTACK: {text!r}; steps: {[t[-250:] for t in seen[name]]}'
        assert 'Combat begins' not in text, f'{name} late ATTACK opened a fight: {text!r}'


def test_leader_disconnecting_hands_the_wounded_monster_on(tmp_path):
    """The fight's leader drops mid-fight while another player is in it:
    that player's next ATTACK takes over the same, already wounded TROLL
    ("You take the lead against the TROLL!") instead of opening a fresh
    full-HP fight, as it used to when the leader's session was dropped."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    names = ['e2elead_a', 'e2elead_b']
    from player import Player
    for name in names:
        seed_test_account(name, _PASSWORD, map_room=_ROOM)
        seeded = Player(name=name, id=name)
        seeded.hit_points = 500
        seeded.unsaved_changes = True
        assert seeded.save(force=True)

    import combat.engine as engine
    import re
    from net_common import Message, Mode
    from simple_server import Server

    server = Server('127.0.0.1', 0, 0)
    troll = next(m for m in server.monsters if m.get('number') == _TROLL)
    troll['strength'] = 40              # survives A's first few swings

    loops = []
    real_run_loop = engine.CombatSession._run_loop

    async def counting_run_loop(self, ctx, **kw):
        loops.append((ctx.player.name, kw.get('resumed', False)))
        return await real_run_loop(self, ctx, **kw)
    engine.CombatSession._run_loop = counting_run_loop
    result = {}

    async def scenario():
        from simple_client import receive_message, send_message

        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]
        conns = {}
        for name in names:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            assert await perform_login(reader, writer, name, _PASSWORD)
            conns[name] = (reader, writer)

        async def drain(name, *, quiet=0.4, max_wait=3.0):
            reader = conns[name][0]
            lines, prompt = [], ''
            deadline = time.time() + max_wait
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(receive_message(reader), timeout=quiet)
                except asyncio.TimeoutError:
                    if prompt:
                        break
                    continue
                if not msg:
                    break
                lines.extend(str(x) for x in (msg.get('lines') or []))
                if msg.get('prompt'):
                    prompt = str(msg['prompt'])
            return ' '.join(' '.join(lines).split()), prompt

        async def say(name, text):
            await send_message(conns[name][1], Message(lines=[text], mode=Mode.app))

        a, b = names
        for name in names:
            await drain(name)
        await say(a, 'attack')
        text, prompt = await drain(a)
        await say(b, 'attack')                  # B joins A's fight
        await drain(b)
        # A swings until the TROLL is visibly hurt, then drops mid-fight.
        hp_seen = None
        for _ in range(_MAX_SWINGS):
            hps = re.findall(r'TROLL HP:(\d+)', text)
            if hps and int(hps[-1]) < 40 and prompt.rstrip().endswith('Command>'):
                hp_seen = int(hps[-1])
                break
            await say(a, 'a')
            text, prompt = await drain(a)
        assert hp_seen is not None, 'never got the TROLL below full HP'
        result['hp_before'] = hp_seen
        conns[a][1].transport.abort()
        await asyncio.sleep(0.5)
        await drain(b, max_wait=1.0)

        await say(b, 'attack')
        result['b_text'], result['b_prompt'] = await drain(b)
        conns[b][1].transport.abort()
        await asyncio.sleep(0.5)
        result['active_after'] = dict(server.active_combats)

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(asyncio.wait_for(scenario(), timeout=60))
    finally:
        engine.CombatSession._run_loop = real_run_loop

    b_text = result['b_text']
    assert 'You take the lead against the TROLL!' in b_text, b_text[-400:]
    assert 'Combat begins' not in b_text, b_text[-400:]
    assert result['b_prompt'].rstrip().endswith('Command>')
    # B's first combat prompt shows the TROLL exactly as A left it.
    assert f'TROLL HP:{result["hp_before"]})' in b_text, (result['hp_before'], b_text[-400:])
    assert loops == [('e2elead_a', False), ('e2elead_b', True)], loops
    # Both gone: the fight ended and came out of active_combats.
    assert result['active_after'] == {}, result['active_after']
