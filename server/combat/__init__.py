"""combat — modular combat system.

Public API:
    enter_combat(ctx, monster)  — start/join a CombatSession
    join_combat(ctx)            — join an existing fight in the room
    CombatSession               — the fight object (for advanced use)
"""
from combat.engine import CombatSession, enter_combat, join_combat

__all__ = ['CombatSession', 'enter_combat', 'join_combat']
