"""shoppe/wizard.py — The Wizard's cave spell shop (SPUR.SHOP.S wizard section)."""
import logging

from network_context import GameContext

log = logging.getLogger(__name__)

_SPELL_MAX           = 10  # SPUR xs=10 gate
_SPELL_NON_ADEPT_MAX =  6  # SPUR if pc>2 then if xs>5 goto wiz2b

# Hardcoded from SPUR-data/spells.txt (21 records; last is dummy sentinel).
# Fields: number, name, effect_type, effect_magnitude, cast_chance, price
# effect_type codes: S=Str W=Wis D=Dex C=Con E=Egy I=Int T=Transfer
#   P=Player-HP M=Monster L=LevelDown U=LevelUp R=Shop G=SPUR A=Aura
SPELLS: list[dict] = [
    {'number':  1, 'name': 'ESP',                 'effect': 'I', 'magnitude': 4, 'cast_chance': 70, 'price':  100,
     'description': 'Boosts Intelligence, sharpening your mind and magical aptitude.'},
    {'number':  2, 'name': 'WHEATIES',            'effect': 'S', 'magnitude': 6, 'cast_chance': 70, 'price':  150,
     'description': 'Grants a surge of Strength — what champions eat for breakfast.'},
    {'number':  3, 'name': 'HAPPY FEET',          'effect': 'E', 'magnitude': 6, 'cast_chance': 50, 'price':  100,
     'description': 'Restores Energy, putting a spring back in your step.'},
    {'number':  4, 'name': 'KILL',                'effect': 'M', 'magnitude': 6, 'cast_chance': 60, 'price':  140,
     'description': 'Deals direct damage to a monster in combat.'},
    {'number':  5, 'name': 'ELEVATOR UP',         'effect': 'U', 'magnitude': 7, 'cast_chance': 70, 'price':  800,
     'description': 'Transports you up one dungeon level without the elevator.'},
    {'number':  6, 'name': 'KNOWLEDGE',           'effect': 'W', 'magnitude': 4, 'cast_chance': 70, 'price':   75,
     'description': 'Increases Wisdom, improving judgment and resistance to magic.'},
    {'number':  7, 'name': 'DESTROYER',           'effect': 'M', 'magnitude': 8, 'cast_chance': 70, 'price':  250,
     'description': 'A devastating monster attack — hits harder than KILL.'},
    {'number':  8, 'name': 'SLAUGHTER',           'effect': 'M', 'magnitude': 4, 'cast_chance': 90, 'price':  100,
     'description': 'High-accuracy monster attack. Less power than KILL, but rarely misses.'},
    {'number':  9, 'name': 'DEPOSIT',             'effect': 'T', 'magnitude': 4, 'cast_chance': 80, 'price':   50,
     'description': 'Instantly transfers your gold to the bank from anywhere in the dungeon.'},
    {'number': 10, 'name': 'WELL-BEING',          'effect': 'C', 'magnitude': 9, 'cast_chance': 70, 'price':  170,
     'description': 'Improves Constitution, boosting health and stamina.'},
    {'number': 11, 'name': 'BALANCE',             'effect': 'D', 'magnitude': 4, 'cast_chance': 60, 'price':   80,
     'description': 'Sharpens Dexterity, making you nimbler in combat and harder to hit.'},
    {'number': 12, 'name': 'ELEVATOR DOWN',       'effect': 'L', 'magnitude': 5, 'cast_chance': 80, 'price': 1000,
     'description': 'Transports you down one dungeon level without the elevator.'},
    {'number': 13, 'name': 'ENDURANCE',           'effect': 'P', 'magnitude': 8, 'cast_chance': 70, 'price':  140,
     'description': 'Restores hit points — handy in a tight spot.'},
    {'number': 14, 'name': 'TRANSPORT TO SHOPPE', 'effect': 'R', 'magnitude': 8, 'cast_chance': 80, 'price':  250,
     'description': 'Teleports you directly to the Merchant Shoppe from anywhere in the dungeon.'},
    {'number': 15, 'name': 'SUMMON SPUR',         'effect': 'G', 'magnitude': 7, 'cast_chance': 90, 'price': 2000,
     'description': 'Powerful summoning spell that calls forth the spirit of SPUR itself.'},
    {'number': 16, 'name': 'DISPEL POISON',       'effect': 'A', 'magnitude': 5, 'cast_chance': 90, 'price':  100,
     'description': 'Aura spell that neutralizes poison affecting the caster.'},
    {'number': 17, 'name': 'APPLE A DAY',         'effect': 'A', 'magnitude': 7, 'cast_chance': 90, 'price':  100,
     'description': 'Healing aura that slowly restores health over time.'},
    {'number': 18, 'name': 'DRUID HEALTH',        'effect': 'A', 'magnitude': 9, 'cast_chance': 90, 'price':  200, 'druid_only': True,
     'description': 'Druid-only aura. Channels nature to significantly restore hit points.'},
    {'number': 19, 'name': "WIZARD'S GLOW",       'effect': 'A', 'magnitude': 9, 'cast_chance': 90, 'price':  200, 'wizard_only': True,
     'description': "Wizard-only aura. Surrounds the caster in magical light, enhancing all spell effects."},
    {'number': 20, 'name': 'BOOTS OF SPEED',      'effect': 'A', 'magnitude': 9, 'cast_chance': 50, 'price': 2000,
     'description': 'Aura spell that dramatically increases movement and combat speed. Rare and expensive.'},
]


# Short label shown in the Effect column of the spell list table.
_EFFECT_LABELS: dict[str, str] = {
    'I': 'INT',     'S': 'STR',     'E': 'EGY',    'C': 'CON',
    'D': 'DEX',     'W': 'WIS',     'P': 'HP',     'M': 'Combat',
    'U': 'Level +', 'L': 'Level -', 'T': 'Bank',   'R': 'Teleport',
    'G': 'Summon',  'A': 'Aura',
}


def _parse_info_request(ans: str) -> 'int | None':
    """Return spell number if ans matches i<number> (e.g. i3, i15), else None."""
    low = ans.lower()
    if low.startswith('i') and len(low) > 1 and low[1:].isdigit():
        return int(low[1:])
    return None


async def main(ctx: GameContext) -> None:
    """Learn spells. Wizards pay half, Druids two-thirds. Max 10 spells (6 for non-adepts).
    (SPUR.SHOP.S wizard section)
    """
    from base_classes import PlayerClass, PlayerMoneyTypes
    from items import Spell

    player    = ctx.player
    inv       = getattr(player, 'inventory', None)
    pc        = getattr(player, 'char_class', None)
    is_wizard = pc == PlayerClass.WIZARD
    is_druid  = pc == PlayerClass.DRUID
    is_adept  = is_wizard or is_druid

    def _spell_count() -> int:
        return len(inv.entries('Spell')) if inv else 0

    def _has_spell(number: int) -> bool:
        return bool(inv.find(item_id=number, category='Spell')) if inv else False

    def _adjusted_price(base: int) -> int:
        if is_wizard:
            return max(1, base // 2)       # SPUR: q4=q4/2
        if is_druid:
            return max(1, base * 2 // 3)   # SPUR: q4=q4*2:q4=q4/3
        return base

    def _spell_list_lines() -> list[str]:
        from table import Table, Column, Align
        try:
            width = ctx.player.client_settings.screen_columns
        except AttributeError:
            width = 78

        t = Table(
            headers=[
                Column('#',      align=Align.RIGHT,  min_width=2),
                Column('Name',                       min_width=10),
                Column('Effect',                     min_width=6),
                Column('Cost',   align=Align.RIGHT,  min_width=4),
            ],
            title='Available Spells  (i# for description)',
            border=True,
        )
        for sp in SPELLS:
            tag   = ' *' if sp.get('wizard_only') else (' †' if sp.get('druid_only') else '')
            known = ' ✓' if _has_spell(sp['number']) else ''
            price = _adjusted_price(sp['price'])
            t.add_row([
                str(sp['number']),
                sp['name'] + tag + known,
                _EFFECT_LABELS.get(sp['effect'], sp['effect']),
                f"{price}s",
            ])
        t.set_footer('* Wizard only   † Druid only   ✓ known')
        return [''] + t.render(width=width) + ['']

    await ctx.send([
        '',
        'You enter the cave of the Wizard, a dis-embodied voice asks.....',
        '"Are you here to learn a spell?"',
        '',
    ])
    raw = await ctx.prompt('Y/N')
    if raw is None or raw.strip().upper() != 'Y':
        await ctx.send('Return when you are ready.')
        return

    await ctx.send(['A scroll appears before you, and the voice pronounces...', ''])

    if is_wizard:
        await ctx.send('Psst! Fellow wizard!! Half price for you!')
    elif is_druid:
        await ctx.send('Psst! Fellow Adept! 2/3 price for you!')

    while True:
        xs = _spell_count()

        # SPUR wiz2b: check caps before prompting
        if xs >= _SPELL_MAX:
            await ctx.send('I am sorry but ye have already learned ten spells.')
            return
        if not is_adept and xs >= _SPELL_NON_ADEPT_MAX:
            await ctx.send('Sorry, Non-Adepts can only learn six spells..')
            return

        raw = await ctx.prompt('Learn which spell? (?=List, i#=Info, Q to leave)')
        if raw is None:
            return
        choice = raw.strip()
        if not choice or choice.upper() == 'Q':
            return
        if choice == '?':
            await ctx.send(_spell_list_lines())
            continue

        info_num = _parse_info_request(choice)
        if info_num is not None:
            sp_info = next((s for s in SPELLS if s['number'] == info_num), None)
            if sp_info:
                known = ' (known)' if _has_spell(sp_info['number']) else ''
                price = _adjusted_price(sp_info['price'])
                await ctx.send([
                    '',
                    f"  Spell {sp_info['number']}: {sp_info['name']}{known}",
                    f"  Effect  : {_EFFECT_LABELS.get(sp_info['effect'], sp_info['effect'])}",
                    f"  Cost    : {price}s",
                    f"  {sp_info['description']}",
                    '',
                ])
            else:
                await ctx.send(f'No spell number {info_num}.')
            continue

        try:
            num = int(choice)
        except ValueError:
            await ctx.send('Enter a spell number, ? to list, i# for info, or Q to leave.')
            continue

        sp = next((s for s in SPELLS if s['number'] == num), None)
        if sp is None:
            await ctx.send('I do not know that spell.')
            continue

        # Class restrictions (SPUR: x=19 Wizard only; x=18 Druid only)
        if sp.get('wizard_only') and not is_wizard:
            await ctx.send("'Sorry, this spell for Wizards only'")
            continue
        if sp.get('druid_only') and not is_druid:
            await ctx.send("'Sorry, this spell for Druids only'")
            continue

        if _has_spell(sp['number']):
            await ctx.send(f"You already know {sp['name']}.")
            continue

        price   = _adjusted_price(sp['price'])
        in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)

        await ctx.send(f"You have chosen {sp['name']} for {price} silver.")
        raw = await ctx.prompt('Is this correct?')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        if in_hand < price:
            await ctx.send('Ye do not have enough gold.')
            continue

        await ctx.send('Teaching spell..........')

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)

        spell = Spell(
            id_number        = sp['number'],
            name             = sp['name'],
            cast_chance      = sp['cast_chance'],
            effect_type      = sp['effect'],
            effect_magnitude = sp['magnitude'],
            charges          = 1,
            max_charges      = 1,
        )
        if inv is None or not inv.add(spell, charges=1):
            await ctx.send('Your pack is full — no room for the spell scroll!')
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -price)  # refund
            continue

        player.unsaved_changes = True
        await ctx.send('Spell taught, use it wisely, for it may only be used ONCE!')

        if is_adept:
            await ctx.send('Your calling makes learning simple!')
