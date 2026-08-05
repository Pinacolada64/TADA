"""ship/armory.py — the ship's armory (SPUR.SHIP.S `armory`/`weapons0`/`protect` section).

A narrower rack than the regular Merchant Shoppe's armory
(shoppe/armory.py, which this port already generalized to sell from the
*entire* weapons.json/objects.json catalog everywhere): SPUR.SHIP.S's own
copy of these sections only offers three energy weapons (weapons.json
#58-60: LIGHT SABRE, HAND PHASER, PLASMA RIFLE) and four sci-fi armor/
shield items (objects.json #113-116: battle armor, battle shield, power
armor, lazer shield) -- exactly the gear that matches this port's
existing energy-weapon ammo locker (ship/ammo_locker.py, #118-121).

Thin wrapper: reuses shoppe/armory.py's buy/sell/protection UI wholesale
via its new `item_ids` filter rather than duplicating that logic.
"""
from network_context import GameContext

# weapons.json #58-60 (SPUR.SHIP.S weapons0: position #1,34,x for x=58..60)
_WEAPON_IDS = {58, 59, 60}

# objects.json #113-116 (SPUR.SHIP.S protect: position #1,30,x for x=113..116)
_PROTECTION_IDS = {113, 114, 115, 116}


async def main(ctx: GameContext) -> None:
    """Ship's armory entry point — routes to protection or weaponry."""
    from shoppe.armory import main as armory_main
    await armory_main(ctx, item_ids=_WEAPON_IDS | _PROTECTION_IDS)


async def protection(ctx: GameContext) -> None:
    """Ship's sci-fi armor/shield rack (#113-116)."""
    from shoppe.armory import protection as protection_main
    await protection_main(ctx, item_ids=_PROTECTION_IDS)
