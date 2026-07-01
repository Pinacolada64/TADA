"""shoppe/clan.py — Clan/Guild registration office (SPUR.SHOP.S clan section)."""
import logging
import os

from network_context import GameContext

log = logging.getLogger(__name__)

# Cost to change affiliation (SPUR: xu=1000 for Civilian, xu=2000 otherwise)
_FEE_CIVILIAN = 1000
_FEE_OTHER    = 2000

# Honor deducted when deserting a guild (SPUR vk=vk-vw where vw=100)
_DESERT_HONOR_PENALTY = 100

# (menu_number, display_label, Guild value, SPUR sigil)
_OPTIONS = [
    (1, 'Mark of the Claw',  'CLAW',     r'\|/'),
    (2, 'Mark of the Sword', 'SWORD',    '-}----'),
    (3, 'The Iron Fist',     'FIST',     '==[]'),
    (4, 'Civilian',          'CIVILIAN', None),
    (5, 'Outlaw',            'OUTLAW',   None),
]

_GUILD_NAMES = {
    'CLAW':     'Mark of the Claw',
    'SWORD':    'Mark of the Sword',
    'FIST':     'The Iron Fist',
    'CIVILIAN': 'Civilian',
    'OUTLAW':   'Outlaw',
}


def _load_clans_text() -> list[str]:
    """Read the SPUR clans menu text from SPUR-data/clans.txt."""
    path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'SPUR-data', 'clans.txt')
    )
    try:
        with open(path) as fh:
            return [line.rstrip('\n') for line in fh]
    except Exception:
        # Fallback if file is missing
        log.warning('Could not load clans.txt; using built-in fallback')
        return [
            '',
            'Indicate if you wish to join a Clan:',
            '',
            r'1) Join Mark of the Claw \|/',
            '2) Join Mark of the Sword -}----',
            '3) Join The Iron Fist ==[]',
            '4) Become a Civilian.',
            '5) Become an Outlaw.',
            '',
        ]


def _guild_key(player) -> str:
    """Return the simple key string for the player's current guild."""
    from base_classes import Guild
    g = getattr(player, 'guild', Guild.CIVILIAN)
    # Map Guild enum values to our short keys
    mapping = {
        Guild.CLAW:     'CLAW',
        Guild.SWORD:    'SWORD',
        Guild.FIST:     'FIST',
        Guild.CIVILIAN: 'CIVILIAN',
        Guild.OUTLAW:   'OUTLAW',
    }
    return mapping.get(g, 'CIVILIAN')


async def main(ctx: GameContext) -> None:
    """Clan/Guild registration. (SPUR.SHOP.S clan section)"""
    from base_classes import Guild, PlayerMoneyTypes

    player    = ctx.player
    cur_key   = _guild_key(player)
    is_guild  = cur_key in ('CLAW', 'SWORD', 'FIST')

    # Fee: 1000 from Civilian, 2000 from Outlaw or deserting a guild (SPUR xu)
    if cur_key == 'CIVILIAN':
        fee      = _FEE_CIVILIAN
        from_msg = 'Change from Civilian.'
    elif cur_key == 'OUTLAW':
        fee      = _FEE_OTHER
        from_msg = 'Change from Outlaw.'
    else:
        fee      = _FEE_OTHER
        from_msg = 'Desert a Guild!'

    await ctx.send([
        '',
        'A stern-faced registrar eyes you from behind a heavy desk.',
        f'Current affiliation: {_GUILD_NAMES[cur_key]}',
        '',
    ])

    # Show the clans menu text from SPUR-data/clans.txt
    await ctx.send(_load_clans_text())

    while True:
        in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)

        await ctx.send([
            f'There is a fee of {fee} silver to {from_msg}',
            f'(You have {in_hand}s in hand.)',
        ])
        if is_guild:
            await ctx.send(f'(Plus {_DESERT_HONOR_PENALTY} honor penalty for deserting your Guild!)')

        raw = await ctx.prompt('Which? (1-5, Q to leave, ? to re-list)')
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            await ctx.send('No change..')
            return
        if choice == '?':
            await ctx.send(_load_clans_text())
            continue

        try:
            n = int(choice)
        except ValueError:
            await ctx.send('Enter 1 through 5, Q to leave.')
            continue

        opt = next((o for o in _OPTIONS if o[0] == n), None)
        if opt is None:
            await ctx.send('Enter 1 through 5 please.')
            continue

        _, label, guild_key, sigil = opt

        # Can't join the guild you're already in
        if guild_key == cur_key:
            await ctx.send(f"You're already {_GUILD_NAMES[guild_key]}.")
            continue

        # Check funds
        in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if in_hand < fee:
            await ctx.send(f'Ye do not have enough silver (need {fee}, have {in_hand}).')
            continue

        # Confirm
        sigil_str = f' {sigil}' if sigil else ''
        raw = await ctx.prompt(f"Join {label}{sigil_str}? (Y/N)")
        if raw is None or raw.strip().upper() != 'Y':
            continue

        # Honor penalty for deserting an active guild (SPUR: vk=vk-vw)
        if is_guild:
            honor_loss = min(_DESERT_HONOR_PENALTY, int(getattr(player, 'honor', 0) or 0))
            player.honor = int(getattr(player, 'honor', 0) or 0) - honor_loss
            await ctx.send(f'({honor_loss} honor penalty for deserting your Guild!)')

        # Deduct fee and set new guild (SPUR: gosub sub.gold; vv=...)
        player.subtract_silver(PlayerMoneyTypes.IN_HAND, fee)

        guild_map = {
            'CLAW':     Guild.CLAW,
            'SWORD':    Guild.SWORD,
            'FIST':     Guild.FIST,
            'CIVILIAN': Guild.CIVILIAN,
            'OUTLAW':   Guild.OUTLAW,
        }
        player.guild = guild_map[guild_key]
        from flags import PlayerFlags
        if guild_key in ('CLAW', 'SWORD', 'FIST'):
            player.set_flag(PlayerFlags.GUILD_MEMBER)
        else:
            player.clear_flag(PlayerFlags.GUILD_MEMBER)
        player.unsaved_changes = True

        # "JOINED" vs "REJOINED": first-time guild joiner gets a waiting-for-GM note
        # (SPUR: zt$="REJOINED " if flags set, else zt$="JOINED ")
        was_civilian_or_outlaw = cur_key in ('CIVILIAN', 'OUTLAW')
        if guild_key in ('CLAW', 'SWORD', 'FIST'):
            action = 'JOINED' if was_civilian_or_outlaw else 'REJOINED'
            await ctx.send([
                f'Welcome to the {label}!{sigil_str}',
                '',
            ])
            if action == 'JOINED':
                await ctx.send('Access to the Guild sub & HQ is given by the GuildMaster.')
            else:
                await ctx.send('Welcome back! You now have access to HQ!')
        elif guild_key == 'CIVILIAN':
            await ctx.send("Ok, your status is: Civilian")
        elif guild_key == 'OUTLAW':
            await ctx.send("Ok, you're an OUTLAW!")

        await ctx.send('AutoDuel is OFF')
        return
