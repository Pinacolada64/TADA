"""commands/messaging.py — Shared utilities for whisper, page, and groups.

parse_targets()       — split a comma/space/quoted target string into a name list
expand_groups()       — replace #groupname tokens with stored member lists
find_online()         — map name list to live GameContext objects
online_player_names() — list all currently connected player names
known_player_names()  — list names from save files (online or not)
is_online()           — check whether a specific name is currently connected
player_exists()       — check online clients and save files; supports ? and * wildcards
find_players()        — return sorted names matching a pattern (? and * wildcards)
"""
import fnmatch
import shlex


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


def online_player_names(server) -> list[str]:
    """Return display names of all currently connected players."""
    names = []
    for client in server.clients.values():
        ctx  = getattr(client, 'ctx', None)
        name = getattr(getattr(ctx, 'player', None), 'name', '')
        if name:
            names.append(name)
    return names


def known_player_names() -> list[str]:
    """Return ids of all players that have a save file, online or not.

    Names are derived from the filename: run/server/player-<name>.json.
    """
    import glob
    import os
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None) or './run/server'
    except Exception:
        base = './run/server'
    names = []
    for path in glob.glob(os.path.join(str(base), 'player-*.json')):
        stem = os.path.basename(path)[len('player-'):-len('.json')]
        if stem:
            names.append(stem)
    return names


def is_online(server, name: str) -> bool:
    """Return True if a player with this name is currently connected."""
    needle = name.lower()
    return any(n.lower() == needle for n in online_player_names(server))


def find_players(server, pattern: str) -> list[str]:
    """Return sorted names matching pattern, checking online clients then save files.

    Supports shell-style wildcards: * matches any string, ? matches one character.
    Matching is case-insensitive.  Each name appears at most once.

    Examples:
        find_players(server, '*')       → all known players
        find_players(server, 'ral*')    → ['railbender'] (if that save file exists)
        find_players(server, 'r?lan')   → ['Rulan'] (if online or saved)
    """
    pat  = pattern.lower()
    seen: set[str] = set()
    results: list[str] = []

    for name in online_player_names(server):
        if fnmatch.fnmatch(name.lower(), pat):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                results.append(name)

    for name in known_player_names():
        if fnmatch.fnmatch(name.lower(), pat):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                results.append(name)

    return sorted(results, key=str.lower)


def player_exists(server, name: str) -> bool:
    """Return True if the name belongs to an online player or has a save file.

    Supports ? and * wildcards — returns True if any player matches.
    """
    if '*' in name or '?' in name:
        return bool(find_players(server, name))
    if is_online(server, name):
        return True
    needle = name.lower()
    return any(n.lower() == needle for n in known_player_names())
