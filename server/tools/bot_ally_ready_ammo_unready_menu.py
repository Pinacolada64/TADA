#!/usr/bin/env python3
"""tools/bot_ally_ready_ammo_unready_menu.py -- live end-to-end check of two
polish features on feature/ally-ready-unready-polish:

  1. READY <ally> onto a projectile/energy weapon with no rounds loaded now
     tells the player:
         <ally> has no ammunition loaded for the <weapon>.
         (<ally> will need ammunition before it fires.)   <- no matching ammo
         (GIVE <ally> the <ammo> to load it.)             <- matching ammo in pack

  2. Bare UNREADY, when an ally also has a weapon readied, lists every
     readied weapon in the party ("Weapons readied:" -> "1. You: X",
     "2. <ally>: Y") and lets the player pick which to repack. A solo
     player with only their own weapon readied still gets SPUR's direct
     repack, no menu.

Runs as 'test' (admin, carries a CROSSBOW; allies GANDALF THE GREY /
SAMWISE / ATHENA share the room, variously armed). JSON wire protocol,
port 34083.

Read discipline (CLAUDE.md "Bot scripts"): the login flood and the ally
chatter arrive as many messages over several seconds, so every read drains
until the stream goes quiet (no message for `quiet`s), not until the first
prompt -- reading to first-prompt leaves the bot one message behind for
the whole run. Prompts are '[HH:MM AM] main> ' etc. -- matched by
substring, never ==. A reply that ends on a numbered menu is always
resolved (answer or blank-cancel) before the next command.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HOST, PORT = '127.0.0.1', 34083
USER, PASSWORD = 'test', 'test'


async def _send_raw(w, obj):
    w.write(json.dumps(obj).encode() + b'\n')
    await w.drain()


async def _recv(r, timeout):
    try:
        raw = await asyncio.wait_for(r.readline(), timeout=timeout)
        return json.loads(raw.strip()) if raw else None
    except (asyncio.TimeoutError, json.JSONDecodeError):
        return None


def _prompt_of(msgs):
    return next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')


def _text_of(msgs):
    return '\n'.join(str(l) for m in msgs for l in (m.get('lines') or []))


def _is_menu(prompt: str) -> bool:
    p = prompt.lower()
    return ('which' in p and p.rstrip().endswith('>')) or 'cancel)' in p \
        or bool(re.search(r'\(1-\d+', p))


def _menu_rows(text):
    """[(who, weapon)] from '  N. who: weapon' lines ('You' for the player)."""
    rows = []
    for m in re.finditer(r'^\s*(\d+)\.\s+(.+?):\s+(.+?)\s*(?:\(readied\)\s*)?$',
                         text, re.M):
        rows.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
    return rows


class Bot:
    def __init__(self, r, w):
        self.r, self.w = r, w

    async def drain(self, overall=12.0, quiet=1.3):
        """Read until `quiet`s pass with no message (or `overall`s total).
        Auto-dismiss '-- More'/'-- End' pages along the way."""
        loop = asyncio.get_event_loop()
        hard = loop.time() + overall
        msgs = []
        while loop.time() < hard:
            m = await _recv(self.r, timeout=quiet)
            if m is None:
                break
            msgs.append(m)
            pl = (m.get('prompt') or '').lower()
            if '-- more' in pl or '-- end' in pl:
                await _send_raw(self.w, {'lines': [''], 'mode': 'game'})
        return msgs

    async def cmd(self, line, *, menu=None, mode='game', echo=True, overall=12.0):
        if echo:
            print(f'\n  -> {line!r}')
        await _send_raw(self.w, {'lines': [line], 'mode': mode})
        msgs = await self.drain(overall=overall)
        text, prompt = _text_of(msgs), _prompt_of(msgs)
        if echo:
            for ln in text.splitlines():
                print(f'     {ln}')
            if prompt:
                print(f'     [{prompt}]')
        if _is_menu(prompt):
            reply = '' if menu is None else str(menu)
            if echo:
                print(f'  -> (menu) {reply!r}')
            await _send_raw(self.w, {'lines': [reply], 'mode': 'game'})
            m2 = await self.drain(overall=overall)
            t2, p2 = _text_of(m2), _prompt_of(m2)
            if echo:
                for ln in t2.splitlines():
                    print(f'     {ln}')
                if p2:
                    print(f'     [{p2}]')
            return (t2, p2) if menu is not None else (text + '\n' + t2, p2)
        return text, prompt

    async def login(self):
        init = await _recv(self.r, timeout=5.0)
        if not init:
            return False
        await _send_raw(self.w, {'server_id':  init.get('server_id',  'test_server'),
                                 'server_key': init.get('server_key', 'test_key')})
        for _ in range(40):
            msgs = await self.drain(overall=6.0)
            p = _prompt_of(msgs)
            if p.endswith('login> '):
                break
            if 'terminal type' in p.lower():
                await _send_raw(self.w, {'lines': ['A'], 'mode': 'login'})
            if not msgs:
                if not p.endswith('login> '):
                    return False
                break
        txt, _ = await self.cmd(f'connect {USER} {PASSWORD}', mode='login', overall=15.0)
        return not ('incorrect' in txt.lower() or 'is already connected' in txt.lower())

    async def unready_all(self):
        """Repack every readied weapon in the party."""
        for _ in range(10):
            txt, _ = await self.cmd('unready', echo=False)
            low = txt.lower()
            if 'no weapon readied' in low:
                return True
            rows = _menu_rows(txt)
            if 'weapons readied:' in low and len(rows) >= 2:
                # menu shown & auto-cancelled; repack row 1 explicitly
                await self.cmd('unready', menu=1, echo=False)
                continue
            # otherwise a single candidate was repacked directly; loop again
        return False


async def main():
    r, w = await asyncio.open_connection(HOST, PORT)
    bot = Bot(r, w)
    if not await bot.login():
        print('!! login failed'); return

    results = []
    def check(label, ok, detail=''):
        results.append((label, bool(ok), detail))
        print(f'   [{"PASS" if ok else "FAIL"}] {label}')

    print('\n=== reset: repack every readied weapon ===')
    ok = await bot.unready_all()
    txt, _ = await bot.cmd('unready')
    check('reset -> "No weapon readied!"', 'no weapon readied' in txt.lower(), txt)

    # ---------- Feature 1: ammo warning ----------
    print('\n=== Feature 1: READY an ally onto a ranged weapon ===')
    lst, _ = await bot.cmd('ready')                 # player + ally weapon list
    await _send_raw(w, {'lines': [''], 'mode': 'game'})   # cancel the READY menu
    await bot.drain(overall=4.0)

    RANGED = re.compile(r'BOW|CROSSBOW|SLING|BLOWGUN|MAGNUM|RIFLE|PISTOL|UZI|'
                        r'THROWER|BLASTER|RAY GUN|LASER|PHASER', re.I)
    ranged = next(((who, wpn) for _n, who, wpn in _menu_rows(lst)
                   if who != 'You' and RANGED.search(wpn)), None)

    warn = ''
    if ranged:
        who, wpn = ranged
        warn, _ = await bot.cmd(f'ready {who.split()[0]}')
    else:
        allies = [who for _n, who, _wp in _menu_rows(lst) if who != 'You']
        if allies:
            await bot.cmd(f'give crossbow to {allies[0].split()[0]}')
            warn, _ = await bot.cmd(f'ready {allies[0].split()[0]}')
            ranged = (allies[0], 'CROSSBOW')

    warn_flat = ' '.join(warn.split())   # server wraps lines at ~40 cols
    check('Feature 1: an ally + ranged weapon was available', ranged is not None,
          str(_menu_rows(lst)))
    if ranged:
        check('ally readies the weapon', re.search(r'readies the', warn_flat, re.I) is not None, warn)
        check('warns "has no ammunition loaded for the <weapon>"',
              re.search(r'has no ammunition loaded for the', warn_flat, re.I) is not None, warn)
        check('non-expert hint (GIVE .. to load it / will need ammunition ..)',
              re.search(r'(GIVE .* to load it|will need ammunition before it fires)',
                        warn_flat, re.I) is not None, warn)

    # ---------- Feature 2: bare UNREADY menu ----------
    print('\n=== Feature 2: bare UNREADY lists all readied weapons ===')
    pt, _ = await bot.cmd('ready crossbow', menu=1)         # arm the player (own CROSSBOW)
    player_armed = 'crossbow readied' in pt.lower()

    txt, _ = await bot.cmd('unready')                        # menu auto-cancelled
    rows = _menu_rows(txt)
    check('shows "Weapons readied:"', 'weapons readied:' in txt.lower(), txt)
    check('menu has >= 2 rows', len(rows) >= 2, str(rows))
    check('menu has the player row "You: ..."',
          any(who == 'You' for _n, who, _wp in rows) or not player_armed, str(rows))
    check('menu has an ally row', any(who != 'You' for _n, who, _wp in rows), str(rows))

    ally_row = next(((n, who) for n, who, _wp in rows if who != 'You'), None)
    if ally_row:
        n, who = ally_row
        rtxt, _ = await bot.cmd('unready', menu=int(n))
        check(f'picking row {n} repacks {who}',
              re.search(rf'{re.escape(who)} repacks the', rtxt, re.I) is not None, rtxt)

    # ---------- Feature 2b: solo -> direct repack ----------
    print('\n=== Feature 2b: only the player armed -> direct repack, no menu ===')
    await bot.unready_all()
    await bot.cmd('ready crossbow', menu=1)
    txt, _ = await bot.cmd('unready')
    check('solo UNREADY: "You repack the ..." and no menu',
          'you repack the' in txt.lower() and 'weapons readied:' not in txt.lower(), txt)

    print('\n=== Results ===')
    ok_all = all(ok for _, ok, _ in results)
    for label, ok, _ in results:
        print(f'  [{"PASS" if ok else "FAIL"}] {label}')
    print('\nALL CHECKS PASSED' if ok_all else '\nSOME CHECKS FAILED -- see transcript above')
    print('\n=== JSON ===')
    print(json.dumps([{'label': l, 'ok': ok, 'detail': d} for l, ok, d in results]))

    await bot.cmd('quit', echo=False, overall=3.0)
    w.close()


if __name__ == '__main__':
    asyncio.run(main())
