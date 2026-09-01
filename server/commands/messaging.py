"""commands/messaging.py — Shared utilities for whisper, page, and groups.

parse_targets()       — split a comma/space/quoted target string into a name list
expand_groups()       — replace #groupname tokens with stored member lists
find_online()         — map name list to live GameContext objects
prompt_player_choice()  — display a numbered player list and return the user's pick
is_in_combat()          — whether a ctx's player is an active combat participant

online_player_names()/known_player_names()/is_online()/find_players()/
player_exists() moved to tada_utilities.py (2026-09-01) -- general
"does this player exist/who's online" lookups with callers well outside
messaging (bar/, commands/board/edit.py). Re-imported here just for
prompt_player_choice()'s own use below.
"""
import shlex

from tada_utilities import find_players, online_player_names


def parse_targets(targets_str: str) -> list[str]:
    """Parse a comma- or space-delimited, optionally quoted name list.

    Examples:
        "Alice"              → ['Alice']
        "Alice, Bob"         → ['Alice', 'Bob']
        'Alice Bob'          → ['Alice', 'Bob']
        '"Dark Lord",Alice'  → ['Dark Lord', 'Alice']
        "#friends"           → ['#friends']
    """
    normalized = targets_str.replace(',', ' ')
    try:
        tokens = shlex.split(normalized)
    except ValueError:
        # Unmatched quote — fall back to plain split
        tokens = normalized.split()
    return [t for t in tokens if t]


def expand_groups(player, targets: list[str]) -> tuple[list[str], list[str]]:
    """Replace #groupname tokens with the player's stored member lists.

    Returns (expanded_names, unknown_group_tokens).
    Tokens not starting with '#' are passed through unchanged.
    """
    cs      = getattr(player, 'command_settings', None)
    groups  = getattr(cs, 'groups', {})
    expanded: list[str] = []
    unknown:  list[str] = []
    for t in targets:
        if t.startswith('#'):
            key     = t[1:].lower()
            members = groups.get(key)
            if members is None:
                unknown.append(t)
            else:
                expanded.extend(members)
        else:
            expanded.append(t)
    return expanded, unknown


def find_online(ctx, target_names: list[str], *,
                same_room_only: bool = False) -> tuple[list, list]:
    """Resolve target names to live GameContext objects.

    Returns (found_ctxs, not_found_names).
    - Names matched case-insensitively against online players (excluding self).
    - Each ctx appears at most once even if the same name is listed twice.
    - If same_room_only=True, only clients in ctx.client's room are searched.
    """
    my_room = getattr(ctx.client, 'room', None) if same_room_only else None

    # Build a lower-name → ctx map for eligible online players
    online: dict[str, object] = {}
    for other_client in ctx.server.clients.values():
        if other_client is ctx.client:
            continue
        if same_room_only and getattr(other_client, 'room', None) != my_room:
            continue
        other_ctx = getattr(other_client, 'ctx', None)
        if other_ctx is None:
            continue
        name = getattr(getattr(other_ctx, 'player', None), 'name', '')
        if name:
            online[name.lower()] = other_ctx

    found:     list  = []
    seen:      set   = set()
    not_found: list[str] = []
    for name in target_names:
        key = name.lower()
        if key in online:
            tctx = online[key]
            if id(tctx) not in seen:
                seen.add(id(tctx))
                found.append(tctx)
        else:
            not_found.append(name)

    return found, not_found


async def prompt_player_choice(ctx, pattern: str = '*', *,
                               prompt_text: str = 'Choose a player') -> 'str | None':
    """Show a numbered, wildcard-filtered player list and prompt for a choice.

    Displays all players matching *pattern* (? and * wildcards), with online
    players marked *.  The user may enter a list number or type a name.
    Returns the chosen name, or None if the user cancels (empty input) or the
    list is empty.

    Typical usage:
        name = await prompt_player_choice(ctx, 'r*', prompt_text='Study whom')
        if name is None:
            return   # cancelled or no matches
    """
    matches = find_players(ctx.server, pattern)
    if not matches:
        await ctx.send(f'No players found matching "{pattern}".')
        return None

    online = {n.lower() for n in online_player_names(ctx.server)}
    lines  = [f'Players matching "{pattern}" (* = online):', '']
    for i, name in enumerate(matches, 1):
        marker = '*' if name.lower() in online else ' '
        lines.append(f'  {i:>3}.{marker} {name}')
    lines.append('')
    await ctx.send(lines)

    raw = await ctx.prompt(f'{prompt_text} (number or name, {ctx.player.client_settings.return_key} to cancel)')
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(matches):
            return matches[idx]
        await ctx.send(f'Please enter a number between 1 and {len(matches)}.')
        return None

    # Name typed directly — must be in the filtered list
    needle = raw.lower()
    for name in matches:
        if name.lower() == needle:
            return name
    await ctx.send(f'"{raw}" is not in the list.')
    return None


def is_in_combat(ctx) -> bool:
    """Whether ctx's player is currently an active combat participant.

    Used by commands/page.py to decide whether to queue a page (surfaced
    on the recipient's next prompt via network_context.py's prompt(),
    which flushes player.pending_pages) instead of delivering it
    immediately -- getting a wall of page text mid-exchange is a bad time.

    Checks ctx.server.active_combats[room].attackers, the same structure
    combat/engine.py's CombatSession already maintains -- being in the
    same room as a fight (a bystander) doesn't count, only actually
    fighting does.
    """
    active  = getattr(ctx.server, 'active_combats', None) or {}
    room    = getattr(ctx.client, 'room', None)
    session = active.get(room)
    if session is None:
        return False
    return ctx in getattr(session, 'attackers', [])
