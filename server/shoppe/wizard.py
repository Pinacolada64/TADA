"""shoppe/wizard.py — The Wizard's cave spell shop (SPUR.SHOP.S wizard section)."""
import logging
import random

from network_context import GameContext
from presence import try_global_command

log = logging.getLogger(__name__)

_SPELL_MAX           = 10  # SPUR xs=10 gate
_SPELL_NON_ADEPT_MAX =  6  # SPUR if pc>2 then if xs>5 goto wiz2b

# SPUR wiz3: non-adepts (Fighter/Paladin/Ranger/Thief/Archer/Assassin/
# Knight) can actually fail to learn a spell -- gold is already spent by
# this point (SPUR: `gosub sub.gold` runs before any of this), and a
# failure grants nothing back. Wizards/Druids (pc<3) skip this roll
# entirely ("Your calling makes learning simple!"). Never ported until
# now -- this port previously let every class succeed unconditionally.
_LOW_INT_WARNING_THRESHOLD = 10   # SPUR: if pi<10
_FAIL_ROLL_RANGE           = 25   # SPUR: a=random(25)
_FAIL_ROLL_BASE            =  5   # SPUR: a=a+5
_DULL_RACE_PENALTY         =  3   # SPUR: b=3 for pr=2/7/8 (Ogre/Dwarf/Orc)

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
    {'number': 21, 'name': 'CONJURE FOOD',        'effect': 'F', 'magnitude': 0, 'cast_chance': 80, 'price':   90,
     'description': 'Conjures a random ration of food out of thin air.'},
    {'number': 22, 'name': 'CONJURE DRINK',       'effect': 'K', 'magnitude': 0, 'cast_chance': 80, 'price':   80,
     'description': 'Conjures a random ration of drink out of thin air.'},
    {'number': 23, 'name': 'RESURRECT',           'effect': 'V', 'magnitude': 0, 'cast_chance': 60, 'price':  500,
     'description': 'Brings a fallen party Ally back from the dead.'},
    {'number': 24, 'name': 'ENCHANT ARMOR',       'effect': 'Y', 'magnitude': 15, 'cast_chance': 65, 'price':  250,
     'description': 'Boosts your armor rating, up to your class/race cap.'},
    {'number': 25, 'name': 'ENCHANT SHIELD',      'effect': 'Z', 'magnitude': 15, 'cast_chance': 65, 'price':  220,
     'description': 'Boosts your shield rating, up to your class/race cap.'},
]


# Short label shown in the Effect column of the spell list table.
_EFFECT_LABELS: dict[str, str] = {
    'I': 'INT',     'S': 'STR',     'E': 'EGY',    'C': 'CON',
    'D': 'DEX',     'W': 'WIS',     'P': 'HP',     'M': 'Combat',
    'U': 'Level +', 'L': 'Level -', 'T': 'Bank',   'R': 'Teleport',
    'G': 'Summon',  'A': 'Aura',    'F': 'Food',   'K': 'Drink',
    'V': 'Revive',  'Y': 'Armor',   'Z': 'Shield',
}


# TADA addition: randomized pools for two lines that were previously fixed,
# matching the Wizard's established disembodied-voice tone.
_UNKNOWN_SPELL_LINES = [
    'I do not know that spell.',
    'That incantation is unfamiliar to me.',
    'No such spell exists in this cave.',
    'The scroll remains blank at that name.',
]

_TEACHING_LINES = [
    'Teaching spell..........',
    'The scroll glows faintly as knowledge flows into you..........',
    'Ancient words echo through the cave..........',
    'The voice murmurs syllables older than the dungeon itself..........',
]


_SPELLBOOK_PRICE = 50  # TADA addition -- not a SPUR-sourced price, see spellbook.py


async def _buy_spellbook(ctx: GameContext, player, inv, is_adept: bool) -> None:
    """Sell the player a Spell Book -- Wizards/Druids only, matching
    spellbook.py's _ADEPT_CLASSES gate (non-adepts cap at 6 spells kept
    loose in the main inventory, no book concept for them). Any spells
    already sitting loose in the main inventory move into the new book on
    purchase, since that's the whole point of buying one instead of just
    waiting for ensure_spellbook() to auto-grant one on the next learned
    spell."""
    import spellbook
    from base_classes import PlayerMoneyTypes
    from items import ItemCategory

    if not is_adept:
        await ctx.send("'Only my fellow Adepts have the discipline to keep a Spell Book,' the voice says.")
        return

    if spellbook.find_spellbook(player) is not None:
        await ctx.send('You already have a Spell Book.')
        return

    await ctx.send(f'A Spell Book costs {_SPELLBOOK_PRICE} silver.')
    raw = await ctx.prompt('Buy one?')
    if raw is None or raw.strip().upper() != 'Y':
        return

    if player.get_silver(PlayerMoneyTypes.IN_HAND) < _SPELLBOOK_PRICE:
        await ctx.send('Ye do not have enough silver.')
        return

    if inv is None or not inv.add(spellbook.make_spellbook_item()):
        await ctx.send('Your pack is full -- no room for the Spell Book!')
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, _SPELLBOOK_PRICE)

    book = spellbook.find_spellbook(player)
    moved = 0
    if book is not None and book.contents is not None:
        for spell_entry in list(inv.entries(category=str(ItemCategory.SPELL))):
            # Capture quantity *before* remove() -- it mutates spell_entry
            # in place, so reading spell_entry.quantity again afterward
            # (the previous order here) always read the post-removal
            # value, i.e. 0 for a non-stacked spell. Silently added 0
            # copies to the book instead of the spell actually carried --
            # same read-after-mutate bug as commands/give.py's
            # give-to-other-player branch (fixed earlier this session),
            # just masked here because Inventory.entries()/add() didn't
            # used to prune/reject zero-quantity entries either.
            qty = spell_entry.quantity
            inv.remove(spell_entry.item, quantity=qty)
            book.contents.add(spell_entry.item, quantity=qty)
            moved += 1

    player.unsaved_changes = True
    await ctx.send('You purchase a Spell Book.')
    if moved:
        plural = 's' if moved != 1 else ''
        verb   = 'are' if moved != 1 else 'is'
        await ctx.send(f'Your {moved} carried spell{plural} {verb} tucked safely into it.')


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
    import spellbook
    from base_classes import PlayerClass, PlayerMoneyTypes, PlayerRace, PlayerStat
    from items import Spell
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    player    = ctx.player
    inv       = getattr(player, 'inventory', None)
    pc        = getattr(player, 'char_class', None)
    pr        = getattr(player, 'char_race', None)
    is_wizard = pc == PlayerClass.WIZARD
    is_druid  = pc == PlayerClass.DRUID
    is_adept  = is_wizard or is_druid

    def _spell_count() -> int:
        return len(spellbook.spell_entries(player))

    def _has_spell(number: int) -> bool:
        return any(getattr(e.item, 'id_number', None) == number
                   for e in spellbook.spell_entries(player))

    def _adjusted_price(base: int) -> int:
        if is_wizard:
            return max(1, base // 2)       # SPUR: q4=q4/2
        if is_druid:
            return max(1, base * 2 // 3)   # SPUR: q4=q4*2:q4=q4/3
        return base

    def _spell_list_lines() -> list[str]:
        from formatting import border_style_for_ctx
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
            # Was hardcoded to the ASCII '+--+' default regardless of the
            # player's own terminal -- a PETSCII connection or an ANSI
            # player's PREFS border-style choice (single/double) were both
            # ignored. Same helper commands/list_locations.py already uses.
            border_style=border_style_for_ctx(ctx),
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

    # Show the spell list up front -- previously the first thing a player
    # saw was a bare "Learn which spell? (?=List, ...)" prompt, with the
    # actual list only reachable by already knowing to type '?' first.
    # Found live: an alpha tester (visiting the Wizard) never saw a single
    # spell name before being asked to pick one by number. '?' still
    # works afterward to show it again.
    await ctx.send(_spell_list_lines())

    while True:
        xs = _spell_count()

        # SPUR wiz2b: check caps before prompting
        if xs >= _SPELL_MAX:
            await ctx.send('I am sorry but ye have already learned ten spells.')
            return
        if not is_adept and xs >= _SPELL_NON_ADEPT_MAX:
            await ctx.send('Sorry, Non-Adepts can only learn six spells..')
            return

        raw = await ctx.prompt(
            'Learn which spell?',
            preamble_lines=[f'(?=List, i#=Info, BOOK=Buy Spell Book, [Q] Leave{shop_menu_hint(player)})'])
        if raw is None:
            return
        choice = raw.strip()
        if not choice or choice.upper() == 'Q':
            return
        if choice == '?':
            await ctx.send(_spell_list_lines())
            continue
        if choice.upper() == 'BOOK':
            await _buy_spellbook(ctx, player, inv, is_adept)
            continue
        if choice.upper() in ('I', 'T') and await handle_shop_key(ctx, choice.upper()):
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
            if await try_global_command(ctx, raw):
                continue
            await ctx.send('Enter a spell number, ? to list, i# for info, or [Q] Leave.')
            continue

        sp = next((s for s in SPELLS if s['number'] == num), None)
        if sp is None:
            await ctx.send(random.choice(_UNKNOWN_SPELL_LINES))
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
            await ctx.send('Ye do not have enough silver.')
            continue

        await ctx.send(random.choice(_TEACHING_LINES))

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)

        if is_adept:
            await ctx.send('Your calling makes learning simple!')
        else:
            # SPUR wiz3: non-adepts roll against Intelligence to actually
            # learn the spell -- silver already spent above, and a hard
            # failure below gets none of it back.
            intelligence = player.stats.get(PlayerStat.INT, 10) if player.stats else 10
            if intelligence < _LOW_INT_WARNING_THRESHOLD:
                await ctx.send('Thy intelligence may hinder thee from learning this spell.')

            dull_race = pr in (PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC)
            penalty   = _DULL_RACE_PENALTY if dull_race else 0
            roll      = random.randint(1, _FAIL_ROLL_RANGE) + _FAIL_ROLL_BASE + penalty

            if roll > intelligence:
                if random.randint(1, 10) < 3:
                    # A near-miss the voice lets slide -- still succeeds.
                    await ctx.send('After much study..')
                else:
                    await ctx.send("'Alas! My efforts to teach thee were in vain, "
                                    "maybe if thee were smarter..'")
                    if dull_race:
                        await ctx.send("'Your kind never did make good wizards,' the voice sniffs..")
                    continue

        spell = Spell(
            id_number        = sp['number'],
            name             = sp['name'],
            cast_chance      = sp['cast_chance'],
            effect_type      = sp['effect'],
            effect_magnitude = sp['magnitude'],
            charges          = 1,
            max_charges      = 1,
        )
        # Adepts' learned spells go in their Spell Book (auto-granted here
        # if they don't have one yet -- covers characters created before
        # this feature existed) so they stop competing with weapons/
        # armor/food for a slot in the smaller Wizard/Druid inventory.
        # Non-adepts (capped at 6 spells anyway, no book) keep the old
        # behavior: straight into the main inventory.
        book  = spellbook.ensure_spellbook(player) if is_adept else None
        added = book.contents.add(spell) if book is not None else (
            inv.add(spell) if inv else False
        )
        if not added:
            await ctx.send('Your pack is full — no room for the spell scroll!')
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -price)  # refund
            continue

        player.unsaved_changes = True
        await ctx.send('Spell taught! Use it wisely, for it may only be used ONCE!')
