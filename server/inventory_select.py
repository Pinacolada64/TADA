"""inventory_select.py — shared "pick an item of type X" plumbing.

Several commands (READY/UNREADY, and — as they migrate — USE/DROP/GIVE/…)
all do the same two-step dance:

  1. Gather a numbered list of the items a player can act on — sometimes
     just their own pack, sometimes their pack *plus* every party ally's
     pack (READY lets the player direct an ally's weapon; UNREADY mirrors
     it).
  2. Resolve a name the player typed, or run an interactive numbered
     prompt, down to exactly one of those items — with the same
     empty/one-match/ambiguous/cancel/bad-input handling every time.

This module factors both steps out. `gather_items()` is step 1;
`resolve_or_prompt()` is step 2. The command keeps all the domain logic
(STR gates, STORM-weapon tantrums, water rooms, …) — it just stops
re-implementing the list and the menu.

`_party_allies()` moved here from commands/ready.py so both READY and
UNREADY import it from one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from items import ItemCategory


# ---------------------------------------------------------------------------
# Party allies
# ---------------------------------------------------------------------------

def _party_allies(player) -> list:
    """Living party allies, in party order.

    Alpha-tester feedback: it made no sense for an ally to *automatically*
    ready a weapon the moment it was GIVEn to them (commands/give.py used
    to do exactly that). READY now also lists every weapon sitting in an
    ally's pack (bar/ally_data.py Ally.items) so the player decides who
    wields what, and when -- see gather_items(include_allies=True).
    """
    party = getattr(player, 'party', None)
    if not party:
        return []
    try:
        from bar.ally_data import Ally, AllyStatus
    except ImportError:
        return []
    out = []
    for m in getattr(party, 'members', None) or []:
        if not isinstance(m, Ally):
            continue
        if getattr(m, 'status', None) == AllyStatus.DEAD:
            continue
        out.append(m)
    return out


# Backwards-friendly public alias.
party_allies = _party_allies


# ---------------------------------------------------------------------------
# ItemChoice
# ---------------------------------------------------------------------------

@dataclass
class ItemChoice:
    """One selectable item, plus who owns it.

    owner is None for the player's own item, or the Ally who carries it.
    entry is the InventoryEntry the item came from when there is one
    (the player's Inventory, or an ally's `.items` list); it may be None
    for choices built straight from an item object (e.g. UNREADY's list of
    already-readied weapons). item is always the item object itself.
    """
    item: object
    entry: object = None
    owner: object = None
    readied: bool = False

    @property
    def is_ally(self) -> bool:
        return self.owner is not None

    @property
    def name(self) -> str:
        return getattr(self.item, 'name', '?') or '?'

    @property
    def owner_name(self) -> str:
        return getattr(self.owner, 'name', 'You') if self.owner is not None else 'You'


def same_item(a, b) -> bool:
    """True if *a* and *b* are the same item.

    Identity first, then id_number *within the same category* -- id_number
    is only unique per category (weapons/items/rations each number from 1;
    items.py:364), so an id-only compare would conflate weapon #17 with
    ration #17.
    """
    if a is b:
        return True
    if a is None or b is None:
        return False
    a_id, b_id = getattr(a, 'id_number', None), getattr(b, 'id_number', None)
    if a_id is None or a_id != b_id:
        return False
    return str(getattr(a, 'category', '')) == str(getattr(b, 'category', ''))


def owner_has_readied(owner, item) -> bool:
    """True if *item* is the weapon *owner* (player or Ally) has readied."""
    return same_item(getattr(owner, 'readied_weapon', None), item)


# ---------------------------------------------------------------------------
# gather_items -- step 1
# ---------------------------------------------------------------------------

def _matches(item, category, predicate) -> bool:
    if category is not None and str(getattr(item, 'category', '')) != str(category):
        return False
    if predicate is not None and not predicate(item):
        return False
    return True


def gather_items(
    player,
    *,
    category: Optional[str] = None,
    predicate: Optional[Callable[[object], bool]] = None,
    include_player: bool = True,
    include_allies: bool = False,
    allies: Optional[list] = None,
) -> list[ItemChoice]:
    """Return a numbered (by list position) list of ItemChoice.

    category   -- an ItemCategory (or its str) to keep; None keeps every
                  category.
    predicate  -- optional extra test, ANDed with *category*.
    include_player  -- include the player's own pack (default True).
    include_allies  -- also walk each living party ally's `.items`.
    allies     -- override the ally list (defaults to _party_allies()).

    Order: the player's own items first (inventory order), then each
    ally's items grouped by ally in party order -- the layout bare READY
    has shown since the ally-weapon feature landed.
    """
    out: list[ItemChoice] = []

    if include_player:
        inv = getattr(player, 'inventory', None)
        if inv is not None:
            for e in inv.entries():
                item = getattr(e, 'item', None)
                if item is None or not _matches(item, category, predicate):
                    continue
                out.append(ItemChoice(
                    item=item, entry=e, owner=None,
                    readied=owner_has_readied(player, item),
                ))

    if include_allies:
        for ally in (allies if allies is not None else _party_allies(player)):
            for e in getattr(ally, 'items', None) or []:
                item = getattr(e, 'item', None)
                if item is None or not _matches(item, category, predicate):
                    continue
                out.append(ItemChoice(
                    item=item, entry=e, owner=ally,
                    readied=owner_has_readied(ally, item),
                ))

    return out


# ---------------------------------------------------------------------------
# resolve_or_prompt -- step 2
# ---------------------------------------------------------------------------

_UNSET = object()


def _default_match(choice: ItemChoice, pattern: str) -> bool:
    return pattern in (choice.name or '').lower()


async def resolve_or_prompt(
    ctx,
    choices: list[ItemChoice],
    *,
    args,
    prompt_text: str,
    label_fn: Callable[[ItemChoice], str],
    match_fn: Optional[Callable[[ItemChoice, str], bool]] = None,
    group_fn: Optional[Callable[[ItemChoice], str]] = None,
    list_header: Optional[str] = None,
    ambiguous_header: str = 'Which one?',
    no_match_msg: Optional[Callable[[str], str]] = None,
    invalid_msg: str = 'Invalid selection.',
    auto_select_single: bool = False,
) -> Optional[ItemChoice]:
    """Resolve *choices* down to one, by name or by numbered prompt.

    args        -- the raw command args; when non-empty they're joined and
                   matched (case-insensitive, substring) against each
                   choice via *match_fn*.
    label_fn    -- choice -> the menu text after the "NN. " number.
    match_fn    -- choice, lowercased-pattern -> bool. Default: substring
                   match on the item name.
    group_fn    -- choice -> a section header. When given, the *full* list
                   (no name typed) is split into sections, each with its
                   header and a blank line, numbered continuously. The
                   narrowed-by-name list is always shown flat under
                   *ambiguous_header*.
    list_header -- header for the full flat list (ignored when *group_fn*
                   is set). None => no header line.
    no_match_msg -- pattern -> the "nothing matches" line. Default:
                   'Nothing matching "<pattern>".'
    auto_select_single -- when the list holds exactly one choice and no
                   name was typed, return it without drawing a menu
                   (UNREADY does this; bare READY still shows its one-line
                   menu).

    Returns the chosen ItemChoice, or None on: empty *choices*, no name
    match, ambiguous cancel, blank prompt (cancel), or bad input. A
    player-facing line is sent for every None case except a deliberate
    blank-line cancel.
    """
    if not choices:
        return None

    match_fn = match_fn or _default_match
    return_key = getattr(getattr(ctx, 'player', None), 'return_key', 'RETURN')

    # --- name given: filter, then 0/1/many ---------------------------------
    if args:
        pattern = ' '.join(args).lower()
        matches = [c for c in choices if match_fn(c, pattern)]
        if not matches:
            msg = (no_match_msg or (lambda q: f'Nothing matching "{q}".'))(' '.join(args))
            await ctx.send(msg)
            return None
        if len(matches) == 1:
            return matches[0]
        menu = choices_menu(matches, label_fn, header=ambiguous_header)
        await ctx.send(menu)
        return await _prompt_pick(ctx, matches, prompt_text, return_key, invalid_msg)

    # --- no name: the full list -----------------------------------------
    if auto_select_single and len(choices) == 1:
        return choices[0]

    if group_fn is not None:
        lines: list[str] = []
        n = 0
        last_key = _UNSET
        for c in choices:
            key = group_fn(c)
            if key != last_key:
                if lines:
                    lines.append('')
                lines.append(key)
                lines.append('')
                last_key = key
            n += 1
            lines.append(f'  {n:>2}. {label_fn(c)}')
        lines.append('')
        await ctx.send(lines)
    else:
        await ctx.send(choices_menu(choices, label_fn, header=list_header))

    return await _prompt_pick(ctx, choices, prompt_text, return_key, invalid_msg)


def choices_menu(
    choices: list[ItemChoice],
    label_fn: Callable[[ItemChoice], str],
    *,
    header: Optional[str] = None,
) -> list[str]:
    """A flat numbered menu block: optional header, blank, "  NN. label"
    rows, trailing blank. Matches the shape ctx.send() expects (one list
    element per line)."""
    lines: list[str] = []
    if header:
        lines += [header, '']
    for i, c in enumerate(choices, 1):
        lines.append(f'  {i:>2}. {label_fn(c)}')
    lines.append('')
    return lines


async def _prompt_pick(ctx, choices, prompt_text, return_key, invalid_msg):
    """Prompt "(1-N, <key> to cancel)" and map the reply to a choice."""
    raw = await ctx.prompt(
        preamble_lines=f'(1-{len(choices)}, {return_key} to cancel)',
        prompt_text=prompt_text,
    )
    if not raw or not raw.strip():
        return None
    try:
        pick = int(raw.strip()) - 1
        if not (0 <= pick < len(choices)):
            raise ValueError
    except ValueError:
        await ctx.send(invalid_msg)
        return None
    return choices[pick]
