from __future__ import annotations
from typing import List, Dict, TYPE_CHECKING
from tada_utilities import oxford_comma_list, input_yes_no

if TYPE_CHECKING:
    from player import Player

"""
Group players together so they can be addressed by the group name instead of individually.
Used in page / whisper / mail / etc.

Also group management, maybe party management later, but Allies have some additional attributes
(lurk status, tactical position)
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
        self.members: List['Player'] = []
        self.groups: Dict[str, 'Group'] = {}

    def group_add(self, group_name: str) -> str | None:
        """
        Add a new subgroup.
        
        Args:
            group_name: Name of the group to add
            
        Returns:
            str: Error message if group already exists, None on success
            
        Raises:
            ValueError: If group_name is empty or invalid
        """
        if not group_name or not group_name.strip():
            raise ValueError("Group name cannot be empty")
            
        if group_name in self.groups:
            return f"Group '{group_name}' already exists."
            
        self.groups[group_name] = Group(group_name)
        return None

    def group_delete(self, group_name: str, force: bool = False) -> str | None:
        """
        Delete a subgroup.
        
        Args:
            group_name: Name of the group to delete
            force: If True, skip confirmation prompt
            
        Returns:
            str: Error message if deletion fails, None on success
            
        Raises:
            ValueError: If group_name is empty or invalid
        """
        if not group_name or not group_name.strip():
            raise ValueError("Group name cannot be empty")
            
        if group_name not in self.groups:
            return f"Group '{group_name}' does not exist."
            
        if not self.groups[group_name].is_empty():
            return f"Group '{group_name}' is not empty."
            
        if not force and not input_yes_no(f"Delete group '{group_name}'? (y/n)"):
            return "Deletion cancelled."
            
        del self.groups[group_name]
        return None

    def group_list(self, verbose: bool = True) -> list[str]:
        """List all groups in the player's group list, and which players are in each group."""
        if not self.groups:
            if verbose:
                print("No groups.")
            else:
                return []
        for group in self.groups:
            if verbose:
                print(f"Group '{group}' contains members:")
                print(f"{oxford_comma_list(self.groups[group].members)}")
            else:
                return list(self.groups.keys())
        return None

    def player_add(self, player: 'Player') -> str | None:
        """
        Add a player to this group.
        
        :return: Error message if player is already in the group, None otherwise
        """
        if player in self.members:
            return f"Player '{player.name}' is already in group '{self.name}'."
        self.members.append(player)
        return None

    def player_remove(self, player: 'Player') -> str | None:
        """
        Remove a player from this group.
        
        Args:
            player: The player to remove
            
        Returns:
            str: Error message if player is not in group, None on success
        """
        if player not in self.members:
            return f"Player '{player.name}' is not in group '{self.name}'."
            
        self.members.remove(player)
        return None

    def move_player_between_groups(self, move_from: 'Group', move_to: 'Group', player: 'Player') -> str | None:
        """
        Move a player between groups.
        
        Args:
            move_from: The source group to move the player from
            move_to: The target group to move the player to
            player: The player to move
            
        Returns:
            str: Error message if the move fails, None on success
            
        Raises:
            ValueError: If move_from or move_to are invalid
        """
        # Input validation
        if not isinstance(move_from, Group) or not isinstance(move_to, Group):
            raise ValueError("Source and destination must be Group objects")
            
        # Check if player is in move_from group
        if player not in move_from.members:
            return f"Player '{player.name}' is not in the group '{move_from.name}' to move from."

        # Check if move_to is the same as move_from
        if move_to == move_from:
            return "Cannot move player within the same group."

        # Check if player is already in move_to group
        if player in move_to.members:
            return f"Player '{player.name}' is already in the group '{move_to.name}' to move to."
            
        # Perform the move
        error = move_from.player_remove(player)
        if error:
            return error
            
        error = move_to.player_add(player)
        if error:
            # Try to revert the removal if add fails
            move_from.player_add(player)
            return f"Failed to move player: {error}"
            
        return None

    def group_rename(self, new_name: str) -> str | None:
        """
        Rename this group.
        
        Args:
            new_name: New name for the group
            
        Returns:
            str: Error message if rename fails, None on success
            
        Raises:
            ValueError: If new_name is empty or invalid
        """
        if not new_name or not new_name.strip():
            raise ValueError("Group name cannot be empty.")
            
        if new_name == self.name:
            return f"Group '{new_name}' already exists."
            
        self.name = new_name
        return None

    def is_empty(self) -> bool:
        """
        Check if this group is empty.
        
        Returns:
            bool: True if group has no members, False otherwise
        """
        return not bool(self.members)

    def show_members(self) -> str:
        """
        Show the members of this group.
        
        Returns:
            str: Formatted string showing group members or 'No members.' if empty
        """
        if not self.members:
            return "No members."
            
        # Extract player names for display
        member_names = [player.name for player in self.members]
        return f"Group '{self.name}' Members: {oxford_comma_list(member_names)}"
