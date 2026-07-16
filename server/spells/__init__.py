"""spells/ — magical effects, however they're currently triggered.

This codebase has no general spell-casting system yet (no `cast` command,
no targeting pipeline -- see items.py's Spell dataclass, which is a data
container only). Modules here hold effects that are conceptually spells
even when their only current trigger is an item (e.g. spells/charm.py's
CHARM POTION) rather than a cast command, so they have a home that won't
need to move once real spell-casting exists.
"""
