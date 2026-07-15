"""encounters/ — world NPC encounters that aren't tied to any one room's
static level data (see encounters/dwarf.py). Command/combat modules import
from here; this package does not import from commands/ or combat/, to
keep the dependency one-way (same convention as quests/).
"""
