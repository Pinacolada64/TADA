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


def _same_place(ctx, client) -> bool:
    """*client* is on the caller's level and in the caller's room: an area
    name alone isn't a place -- there's a Shoppe on each of levels 1-5."""
    from room_notices import room_of
    player = getattr(ctx, 'player', None)
    here = (int(getattr(player, 'map_level', 1) or 1), getattr(ctx.client, 'room', None))
    return room_of(client) == here


def others_present(ctx, area: str) -> list[str]:
    """Return names of other players in *area*, excluding the caller."""
    names = []
    for client in occupants(ctx.server, area):
        if client is ctx.client or not _same_place(ctx, client):
            continue
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        name   = getattr(player, 'name', None)
        if name:
            names.append(name)
    return names


async def broadcast_area(ctx, area: str, message: str) -> None:
    """Send *message* to every occupant of *area* (on the sender's level,
    in the sender's room) except the sender."""
    for client in occupants(ctx.server, area):
        if client is ctx.client or not _same_place(ctx, client):
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

    Same room means same level too (room_notices.location_of()) -- room
    numbers repeat on every level, and after an elevator ride the
    Shoppe's "steps out" used to reach room 1 on every level.
    """
    from room_notices import room_of
    player = getattr(ctx, 'player', None)
    here = (int(getattr(player, 'map_level', 1) or 1), getattr(ctx.client, 'room', None))
    for client in ctx.server.clients.values():
        if client is ctx.client:
            continue
        if room_of(client) != here:
            continue
        if getattr(client, 'virtual_location', None) is not None:
            continue
        peer_ctx = getattr(client, 'ctx', None)
        if peer_ctx:
            try:
                await peer_ctx.send(message)
            except Exception:
                log.warning('presence.broadcast_open_room: send failed for %s', client)


async def broadcast_nearby(ctx, message: str) -> None:
    """*message* to whoever can see the player right now: the occupants of
    the virtual area they're standing in (the Shoppe, when they step up to
    its elevator), or the open room if they aren't in one."""
    current = getattr(ctx.client, 'virtual_location', None)
    if current:
        await broadcast_area(ctx, current, message)
    else:
        await broadcast_open_room(ctx, message)


# Areas named after their owner read without an article ("steps out of
# Jake's Stable"); everything else gets one ("steps out of the Shoppe",
# "the Allies' Guild", "the Thieves Guild HQ").
_NO_ARTICLE = {"jake's stable"}


def _area_phrase(area: str) -> str:
    return area if area.lower() in _NO_ARTICLE else f'the {area}'


async def enter_area(ctx, area: str) -> None:
    """Mark this client as being in *area* and notify other occupants.

    Areas nest -- the elevator is inside the Shoppe -- so the area being
    left behind is remembered (the same save/restore text_editor.py and
    news.py do around their own virtual_location) and leave_area() puts
    it back."""
    outer = getattr(ctx.client, 'area_outer', None)
    if not isinstance(outer, dict):
        outer = {}
        ctx.client.area_outer = outer
    outer[area.lower()] = getattr(ctx.client, 'virtual_location', None)
    ctx.client.virtual_location = area
    ctx.client.presence_area = area     # where send_room() reaches (room_notices.location_of)
    name = getattr(ctx.player, 'name', '???')
    await broadcast_area(ctx, area, f'{name} steps into {_area_phrase(area)}.')


async def leave_area(ctx, area: str) -> None:
    """Put this client back where they were before enter_area() -- the
    enclosing area, or the open room -- and tell the area left and the
    place they're back in. Leaving the elevator only tells the Shoppe;
    only leaving the outermost area tells the open room."""
    outer = getattr(ctx.client, 'area_outer', None)
    previous = outer.pop(area.lower(), None) if isinstance(outer, dict) else None
    ctx.client.virtual_location = previous
    ctx.client.presence_area = previous
    name = getattr(ctx.player, 'name', '???')
    left = f'{name} steps out of {_area_phrase(area)}.'
    await broadcast_area(ctx, area, left)
    if previous:
        await broadcast_area(ctx, previous, left)
    else:
        await broadcast_open_room(ctx, left)
