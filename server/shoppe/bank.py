"""shoppe/bank.py — Ye Bank of SPUR (SPUR.SHOP.S bank section)."""
import json
import logging

from network_context import GameContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transfer helper — works for online and offline target players
# ---------------------------------------------------------------------------

def _get_online_player(server, name: str):
    """Return the live Player object for an online player, or None."""
    needle = name.lower()
    for client in server.clients.values():
        ctx_ = getattr(client, 'ctx', None)
        p    = getattr(ctx_, 'player', None)
        if p and getattr(p, 'name', '').lower() == needle:
            return p
    return None


async def _transfer_silver_to(server, target_name: str, amount: int) -> bool:
    """Add *amount* to target player's IN_BANK.  Returns True on success.

    Updates the in-memory Player if they're online; otherwise edits their JSON
    save file directly so the change survives their next login.
    """
    from base_classes import PlayerMoneyTypes
    from player import Player

    target = _get_online_player(server, target_name)
    if target is not None:
        target.subtract_silver(PlayerMoneyTypes.IN_BANK, -amount)  # negative = add
        target.unsaved_changes = True
        return True

    # Offline: read JSON, update, write back
    path = Player._json_path(target_name.lower())
    try:
        with open(path) as fh:
            data = json.load(fh)
        silver = data.get('silver', {})
        silver[PlayerMoneyTypes.IN_BANK] = int(silver.get(PlayerMoneyTypes.IN_BANK, 0)) + amount
        data['silver'] = silver
        with open(path, 'w') as fh:
            json.dump(data, fh, indent=2)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        log.exception('_transfer_silver_to: failed for %s', target_name)
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Deposit, withdraw, or transfer silver between players. (SPUR.SHOP.S bank section)"""
    from base_classes import PlayerMoneyTypes
    from commands.messaging import prompt_player_choice

    player = ctx.player

    while True:
        in_bank = player.get_silver(PlayerMoneyTypes.IN_BANK)
        in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
        level   = int(getattr(player, 'xp_level', 1) or 1)

        await ctx.send([
            '',
            '[ Ye Bank of SPUR ]',
            f'  In Account : {in_bank} silver',
            f'  In hand    : {in_hand} silver',
            '',
        ])

        raw = await ctx.prompt('[D]eposit, [W]ithdraw, [T]ransfer, or Q to leave')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return

        if cmd == 'D':
            raw = await ctx.prompt('[ Deposit ] - How much?')
            if not raw or not raw.strip():
                return
            try:
                amount = int(raw.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid amount!')
                continue
            if in_hand < amount:
                await ctx.send("You don't have that much!")
                continue
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, amount)
            player.subtract_silver(PlayerMoneyTypes.IN_BANK, -amount)
            player.unsaved_changes = True

        elif cmd == 'W':
            raw = await ctx.prompt('[ Withdraw ] - How much?')
            if not raw or not raw.strip():
                return
            try:
                amount = int(raw.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid amount!')
                continue
            if in_bank < amount:
                await ctx.send("You don't have that much!")
                continue
            player.subtract_silver(PlayerMoneyTypes.IN_BANK, amount)
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -amount)
            player.unsaved_changes = True

        elif cmd == 'T':
            if level < 2:
                await ctx.send('Must be at least level 2 to transfer silver.')
                continue

            target_name = await prompt_player_choice(ctx, '*', prompt_text='Transfer to whom')
            if target_name is None:
                continue
            if target_name.lower() == player.name.lower():
                await ctx.send("You can't transfer silver to yourself.")
                continue

            raw = await ctx.prompt('Give how much?')
            if not raw or not raw.strip():
                continue
            try:
                amount = int(raw.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid amount!')
                continue

            in_bank = player.get_silver(PlayerMoneyTypes.IN_BANK)
            if in_bank < amount:
                await ctx.send("You don't have that much in your account!")
                continue

            ok = await _transfer_silver_to(ctx.server, target_name, amount)
            if ok:
                player.subtract_silver(PlayerMoneyTypes.IN_BANK, amount)
                player.unsaved_changes = True
                await ctx.send(f'Silver transferred to {target_name}.')
            else:
                await ctx.send(f'Transfer failed — could not find account for {target_name}.')

        else:
            await ctx.send('D)eposit, W)ithdraw, T)ransfer, or Q to leave.')
