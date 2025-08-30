from player import Player
from tada_utilities import input_yes_no
from typing import Set, List, Dict

"""
Group players togeher so they can be addressed by the group name instead of individually.
Used in page / whisper / mail / etc.

Also group management, maybe party management later, but with some additional attributes
(lurk, tactical position)
"""

class Group:
    """
    Group of players.

    Attributes:
        name (str): The name of the group.
        members (List[Player]): The list of players in the group.
        groups (Dict[str, 'Group']): The dictionary of subgroups.
    """
    def __init__(self, name: str):
        self.name = name
        self.members: List[Player] = []
        self.groups: Dict[str, 'Group'] = {}

    def group_add(self, group_name: str) -> None:
        """Add a new subgroup."""
        if group_name in self.groups:
            raise ValueError(f"Group '{group_name}' already exists.")
        self.groups[group_name] = Group(group_name)

    def group_delete(self, group_name: str) -> None:
        """Delete a subgroup."""
        if group_name not in self.groups:
            raise ValueError(f"Group '{group_name}' does not exist.")
        if not self.groups[group_name].is_empty():
            raise ValueError(f"Group '{group_name}' is not empty.")
        if not input_yes_no(f"Are you sure you want to delete group '{group_name}'? (y/n)"):
            return
        del self.groups[group_name]

    def group_list(self):
        """List all subgroups."""
        if not self.groups:
            return "No subgroups."
        for group in self.groups:
            print(f"Group '{group}' contains members:")
            for member in self.groups[group].members:
                print(", ".join(member.name))
        return list(self.groups.keys())
    
    def player_add(self, player: Player) -> None:
        """Add a player to this group."""
        if player in self.members:
            raise ValueError(f"Player '{player.name}' is already in group '{self.name}'.")
        self.members.append(player)

    def player_remove(self, player: Player) -> None:
        """Remove a player from this group."""
        if player not in self.members:
            raise ValueError(f"Player '{player.name}' is not in group '{self.name}'.")
        self.members.remove(player)
        print(f"Player '{player.name}' removed from group '{self.name}'.")

    def move_player_between_groups(self, source_group: 'Group', target_group: 'Group', player: Player) -> None:
        """Move a player between groups."""
        if player not in source_group.members:
            raise ValueError(f"Player '{player.name}' is not in source group '{source_group.name}'.")
        if not self.group_exists(target_group):
            raise ValueError(f"Target group '{target_group.name}' does not exist.")
        if target_group == source_group:
            raise ValueError(f"Target group '{target_group.name}' has the same name as the source group.")

        source_group.player_remove(player)
        target_group.player_add(player)

    def group_rename(self, new_name: str) -> None:
        """Rename this group."""
        if not new_name:
            raise ValueError("Group name cannot be empty.")
        if new_name in self.groups:
            raise ValueError(f"Group '{new_name}' already exists.")
        self.name = new_name

    def group_exists(self, group_name: str) -> bool:
        """Check if a subgroup exists."""
        return group_name in self.groups

    def player_exists(self, player: Player) -> bool:
        """Check if a player is in this group."""
        return player in self.members

    def is_empty(self) -> bool:
        """Check if this group is empty."""
        return not bool(self.members) and not bool(self.groups)

    def show_members(self) -> str:
        """Show the members of this group."""
        member_names = [player.name for player in self.members]
        return f"Group '{self.name}' Members: {', '.join(member_names)}"

def main():
    # define some players and groups
    alice_setup = {"name": "Alice", "groups": ["group1", "group2"]}
    bob_setup = {"name": "Bob", "groups": ["group1"]}
    charlie_setup = {"name": "Charlie", "groups": ["group2"]}
    
    # define some groups
    group1 = Group("group1")
    group2 = Group("group2")
    
    # add players to groups
    group1.player_add(Player(**alice_setup))
    group1.player_add(Player(**bob_setup))
    group2.player_add(Player(**charlie_setup))
    
    # test group rename
    group1.group_rename("new_group1")   # should pass
    group1.group_rename("new_group1")   # should fail
    
    # test group delete
    group1.group_delete("new_group1")   # should pass
    group1.group_delete("new_group1")   # should fail
    
    # test group list
    group1.group_list()
    
    # test group add
    group1.group_add("subgroup")
    group1.group_add("subgroup")
    
    # test group remove
    try:
        group1.group_remove("subgroup")
    except ValueError as e:
        print(e)
    # group1.group_remove("subgroup")

if __name__ == "__main__":
    main()
