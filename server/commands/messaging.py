"""commands/messaging.py — Shared utilities for whisper and page.

parse_targets()  — split a comma/space/quoted target string into a name list
expand_groups()  — replace #groupname tokens with stored member lists
find_online()    — map name list to live GameContext objects
"""
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
