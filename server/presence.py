"""presence.py — Virtual-location occupancy for non-room areas.

Areas currently using this:
    'elevator' — elevator car (shoppe/elevator.py)
    'shoppe'   — merchant annex (shoppe/main.py)
    'bar'      — Wall Bar & Grill (future)

Usage pattern
-------------
    from presence import enter_area, leave_area, broadcast_area

    async def main(ctx):
        player_name = ctx.player.name
        await enter_area(ctx, 'shoppe')
        try:
            ...interaction loop...
        finally:
            await leave_area(ctx, 'shoppe')
"""
import asyncio
import logging

log = logging.getLogger(__name__)

# Commands that change *where* the player is (room movement, teleport) are
# excluded from try_global_command(): a virtual area's own prompt loop has
# no way to notice the player has physically left and would just keep
# prompting for shop/bar options as if they were still standing there.
# Everything else (whereat, who, say, stats, inv, attack, ...) is safe to
# run in place -- worst case a command like 'attack' just reports there's
# nothing to fight.
_GLOBAL_COMMAND_DENYLIST = {'go', '#'}


async def try_global_command(ctx, raw: str) -> bool:
    """Attempt to dispatch *raw* as a normal game command from inside a
    virtual area's own prompt loop (Olly's, the Bar, the Bank, etc.).

    Every such area runs its own `while True: raw = await ctx.prompt(...)`
    loop with a small set of hardcoded single-key options, entirely
    bypassing CommandProcessor -- so things like 'whereat', 'who', 'say',
    'stats', or 'inv' are normally unusable while browsing a shop. Call
    this from an area's "unrecognized input" branch *before* showing its
    own "invalid choice" message; it runs the input through the same
    CommandProcessor the main game loop uses (commands print their own
    output via ctx.send(), same as always) and reports back whether
    anything actually matched.

    Returns True if a real command was found and dispatched (the area's
    loop should just re-prompt afterward), False if the input didn't match
    any global command either (the area should fall back to its own
    "invalid choice" message).
    """
    processor = getattr(getattr(ctx, 'client', None), 'command_processor', None)
    if processor is None or not raw or not raw.strip():
        return False

    token = raw.strip().split()[0]
    # '#37' (teleport shorthand, no space) resolves to the same '#' command
    # as a bare '#' -- match process_command()'s own splitting so the
    # denylist check sees the right canonical command.
    lookup_token = '#' if token.startswith('#') and len(token) > 1 else token
    cmd, _ = processor.find_command(lookup_token)
    if cmd is None or cmd.name in _GLOBAL_COMMAND_DENYLIST:
        return False

    await processor.process_input(raw, ctx=ctx)
    return True


def occupants(server, area: str) -> list:
    """Return all server-side clients currently in *area*.

    Matching is case-insensitive: enter_area() may store a display-friendly
    capitalization (e.g. 'Bar', for the whereat command's output) while
    other call sites broadcast/query using a lowercase area name ('bar').
    Both refer to the same area.
    """
    area_lower = area.lower()
    return [c for c in server.clients.values()
            if (getattr(c, 'virtual_location', None) or '').lower() == area_lower]


def others_present(ctx, area: str) -> list[str]:
    """Return names of other players in *area*, excluding the caller."""
    names = []
    for client in occupants(ctx.server, area):
        if client is ctx.client:
            continue
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        name   = getattr(player, 'name', None)
        if name:
            names.append(name)
    return names


async def broadcast_area(ctx, area: str, message: str) -> None:
    """Send *message* to every occupant of *area* except the sender."""
    for client in occupants(ctx.server, area):
        if client is ctx.client:
            continue
        peer_ctx = getattr(client, 'ctx', None)
        if peer_ctx:
            try:
                await peer_ctx.send(message)
            except Exception:
                log.warning('presence.broadcast_area: send failed for %s', client)


async def broadcast_open_room(ctx, message: str) -> None:
    """Send *message* to players in the same map room who are NOT in any virtual sub-area.

    Use this for entranceway events (e.g. "X steps up to the elevator") that
    should be visible to players standing in the open room but not to those
    already inside a sub-area (elevator, shoppe, bar, etc.).
    """
    my_room = getattr(ctx.client, 'room', None)
    for client in ctx.server.clients.values():
        if client is ctx.client:
            continue
        if getattr(client, 'room', None) != my_room:
            continue
        if getattr(client, 'virtual_location', None) is not None:
            continue
        peer_ctx = getattr(client, 'ctx', None)
        if peer_ctx:
            try:
                await peer_ctx.send(message)
            except Exception:
                log.warning('presence.broadcast_open_room: send failed for %s', client)


async def enter_area(ctx, area: str) -> None:
    """Mark this client as being in *area* and notify other occupants."""
    ctx.client.virtual_location = area
    name = getattr(ctx.player, 'name', '???')
    await broadcast_area(ctx, area, f'{name} steps into the {area}.')


async def leave_area(ctx, area: str) -> None:
    """Clear this client's virtual location and notify remaining occupants and the open room."""
    ctx.client.virtual_location = None
    name = getattr(ctx.player, 'name', '???')
    await broadcast_area(ctx, area, f'{name} steps out of the {area}.')
    await broadcast_open_room(ctx, f'{name} steps out of the {area}.')
