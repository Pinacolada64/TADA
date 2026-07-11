# combat_system.py

import logging
from datetime import timedelta  # Needed for advancing game clock

# Assuming GameClock and Player will be passed in from main.py
# We won't import them directly here to avoid circular dependencies.
# Instead, the CombatSystem will receive instances of them.

# Configure logging for this module
logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)10s | %(funcName)15s() | %(message)s')


class Monster:
    """
    Represents a hostile creature the p can fight.
    """

    def __init__(self, name, description, health, attack_power, loot_item=None):
        self.name = name
        self.description = description
        self.max_health = health  # Store max health for display purposes
        self.current_health = health
        self.attack_power = attack_power
        self.loot_item = loot_item  # An optional item dropped upon defeat
        logging.info(f"Monster '{self.name}' created (HP: {self.current_health}, ATK: {self.attack_power}).")

    def __str__(self):
        return self.name

    def is_alive(self):
        """Checks if the monster has health remaining."""
        return self.current_health > 0

    def take_damage(self, amount):
        """Reduces the monster's current health by the given amount."""
        self.current_health -= amount
        if self.current_health < 0:
            self.current_health = 0
        logging.debug(f"{self.name} took {amount} damage. Remaining HP: {self.current_health}.")
        print(f"The {self.name} takes {amount} damage!")
        if not self.is_alive():
            print(f"The {self.name} falls, defeated!")

    def get_attack_description(self):
        """Returns a string describing the monster's attack."""
        # This can be expanded for more variety
        return f"The {self.name} lunges and attacks!"


class CombatSystem:
    """
    Manages the turn-based combat between the p and a monster.
    Requires instances of Player and GameClock to function.
    """
    def __init__(self, game_clock):
        self.game_clock = game_clock
        self.in_combat = False
        self.current_monster = None
        logging.info("CombatSystem initialized.")

    def start_combat(self, player, monster):
        """Initiates a combat encounter."""
        if self.in_combat:
            print("You are already in combat!")
            logging.warning("Attempted to start combat while already in combat.")
            return False

        if not monster.is_alive():
            print(f"The {monster.name} is already defeated.")
            logging.warning(f"Attempted to start combat with a defeated monster: {monster.name}.")
            return False

        self.in_combat = True
        self.current_monster = monster
        logging.info(f"Combat started between Player '{player.name}' and Monster '{monster.name}'.")
        print(f"\n--- Combat Initiated with {monster.name.upper()} ---")
        print(monster.description)
        self.display_combat_status(player, monster)
        print("What do you do? (e.g., 'attack', 'flee')")
        return True

    def player_attack(self, player, monster):
        """Handles the p's attack turn."""
        if not self.in_combat or monster != self.current_monster:
            print("You are not currently in combat with that monster.")
            return

        if not player.is_alive():
            print("You are too weak to fight.")
            self.end_combat(player, monster)  # End combat if p somehow isn't alive
            return

        weapon = player.inventory
        logging.info("Weapon: {weapon}")
        print(f"You attack the {monster.name}!")
        player_damage = player.attack_power  # Simple damage for now

        # Future improvement: Add p weapon damage, critical hits, etc.
        # if p.equipped_weapon:
        #     player_damage += p.equipped_weapon.damage

        monster.take_damage(player_damage)
        self.game_clock.advance_time(minutes=2)  # Combat actions take time

        if not monster.is_alive():
            self.end_combat(player, monster)
        else:
            self.monster_attack(player, monster)  # Monster counter-attacks if still alive

    def monster_attack(self, player, monster):
        """Handles the monster's attack turn."""
        if not monster.is_alive():
            return  # Monster is defeated, no attack

        print(monster.get_attack_description())
        player.take_damage(monster.attack_power)
        self.game_clock.advance_time(minutes=1)  # Monster's turn also takes time

        if not player.is_alive():
            self.end_combat(player, monster)
        else:
            self.display_combat_status(player, monster)
            print("What do you do next? (e.g., 'attack')")  # Prompt for next p action

    def flee_combat(self, player, monster):
        """Allows the p to attempt to flee from combat."""
        # Simple flee logic for now. Could be improved with success chance.
        print("You attempt to flee from combat...")
        self.game_clock.advance_time(minutes=3)  # Fleeing takes time

        # For simplicity, let's make fleeing always successful for now.
        # You could add: if random.random() < flee_chance: ... else: monster_attack(p, monster)
        print("You manage to escape!")
        logging.info(f"Player '{player.name}' fled from '{monster.name}'.")
        self.end_combat(player, monster, fled=True)

    def display_combat_status(self, player, monster):
        """Displays the current health status of both combatants."""
        print(f"\n--- Combat Status ---")
        print(f"{player.name}: {player.current_health}/{player.max_health} HP")
        print(f"{monster.name}: {monster.current_health}/{monster.max_health} HP")
        print(f"---------------------")

    def end_combat(self, player, monster, fled=False):
        """Ends the combat encounter, handling victory, defeat, or fleeing."""
        self.in_combat = False
        self.current_monster = None
        logging.info("Combat ended.")

        if fled:
            print(f"You are no longer fighting the {monster.name}.")
        elif not player.is_alive():
            print("\n--- DEFEATED ---")
            print("You have been defeated...")
            print("Game Over.")
            # In a full game, you'd handle respawn, load last save, etc.
            exit()  # For now, just exit.
        elif not monster.is_alive():
            print(f"\n--- VICTORY! ---")
            print(f"You have defeated the {monster.name}!")
            # Remove monster from room
            player.current_room.remove_monster(monster)  # Need to add this to Room
            if monster.loot_item:
                print(f"The {monster.name} dropped a {monster.loot_item.name}!")
                player.current_room.add_item(monster.loot_item)  # Add loot to room
        print("\nCombat has ended.")
