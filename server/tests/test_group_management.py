import unittest
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import after setting up the path
from server.group_management import Group
from server.player import Player, set_up_flags, set_up_silver
from server.base_classes import PlayerStat, Gender

class TestGroupManagement(unittest.TestCase):
    def setUp(self):
        # Create test groups "test_group" and "another_group" to test moving players between groups
        self.test_group = Group("test_group")
        self.another_group = Group("another_group")
        
        # Create players "Alice", "Bob", and "Nonexistent Player" to test moving players between groups
        self.alice = Player(name="Alice")
        self.bob = Player(name="Bob")
        self.nonexistent_player = Player(name="Nonexistent Player")
        
        # Initialize required attributes for players to test imports
        for player in [self.alice, self.bob, self.nonexistent_player]:
            # Initialize stats
            player.stats = {stat: 10 for stat in PlayerStat}
            # Initialize flags
            player.flags = set_up_flags()
            # Initialize silver
            player.silver = set_up_silver()
            # Set default gender
            player.gender = Gender.MALE

    def test_add_duplicate_player(self):
        expected = f"Player '{self.alice.name}' is already in group '{self.test_group.name}'."
        self.test_group.player_add(self.alice)
        self.assertEqual(self.test_group.player_add(self.alice), expected)

    def test_remove_nonexistent_player(self):
        # Test removing a player that doesn't exist in the group
        error_msg = self.test_group.player_remove(self.bob)
        self.assertEqual(error_msg, "Player 'Bob' is not in group 'test_group'.")
        
        error_msg = self.another_group.player_remove(self.alice)
        self.assertEqual(error_msg, "Player 'Alice' is not in group 'another_group'.")
        
        error_msg = self.test_group.player_remove(self.nonexistent_player)
        self.assertEqual(error_msg, "Player 'Nonexistent Player' is not in group 'test_group'.")

    def test_move_player_between_groups(self):
        # Add Alice to group 'test_group'
        self.test_group.player_add(self.alice)
        # Add Bob to group 'another_group'
        self.another_group.player_add(self.bob)

        # Test initial state
        self.assertIn(self.alice, self.test_group.members, "Alice should be in test_group initially")
        self.assertIn(self.bob, self.another_group.members, "Bob should be in another_group initially")
        self.assertNotIn(self.alice, self.another_group.members, "Alice should not be in another_group initially")
        self.assertNotIn(self.bob, self.test_group.members, "Bob should not be in test_group initially")

        # Move Alice from test_group to another_group
        result = self.test_group.move_player_between_groups(
            move_from=self.test_group,
            move_to=self.another_group,
            player=self.alice
        )
        self.assertIsNone(result, "Moving Alice should succeed")
        
        # Move Bob from another_group to test_group
        result = self.another_group.move_player_between_groups(
            move_from=self.another_group,
            move_to=self.test_group,
            player=self.bob
        )
        self.assertIsNone(result, "Moving Bob should succeed")
        
        # Verify the moves were successful
        self.assertNotIn(self.alice, self.test_group.members, "Alice should not be in test_group after move")
        self.assertIn(self.alice, self.another_group.members, "Alice should be in another_group after move")
        self.assertNotIn(self.bob, self.another_group.members, "Bob should not be in another_group after move")
        self.assertIn(self.bob, self.test_group.members, "Bob should be in test_group after move")
        
        # Test moving back to original groups
        result = self.another_group.move_player_between_groups(
            move_from=self.another_group,
            move_to=self.test_group,
            player=self.alice
        )
        self.assertIsNone(result, "Moving Alice back should succeed")
        
        result = self.test_group.move_player_between_groups(
            move_from=self.test_group,
            move_to=self.another_group,
            player=self.bob
        )
        self.assertIsNone(result, "Moving Bob back should succeed")
        
        # Verify the moves back were successful
        self.assertIn(self.alice, self.test_group.members, "Alice should be back in test_group")
        self.assertNotIn(self.alice, self.another_group.members, "Alice should not be in another_group")
        self.assertIn(self.bob, self.another_group.members, "Bob should be back in another_group")
        self.assertNotIn(self.bob, self.test_group.members, "Bob should not be in test_group")

    def test_group_rename_success(self):
        """Test successful group renaming."""
        new_name = "renamed_group"
        result = self.test_group.group_rename(new_name)
        self.assertIsNone(result, "group_rename should return None on success")
        self.assertEqual(self.test_group.name, new_name)
    
    def test_group_rename_empty_name(self):
        """Test renaming to an empty name raises ValueError."""
        with self.assertRaises(ValueError):
            self.test_group.group_rename("")
    
    def test_group_rename_same_name(self):
        """Test renaming to the same name returns error message."""
        current_name = self.test_group.name
        result = self.test_group.group_rename(current_name)
        self.assertEqual(
            result,
            f"Group '{current_name}' already exists.",
            "Should return error message when renaming to same name"
        )
        
    def test_group_rename_existing_group_name(self):
        """Test renaming to an existing group name returns error message."""
        # Create another group
        existing_group_name = "existing_group"
        self.test_group.group_add(existing_group_name)
        
        # Try to rename to existing group name
        result = self.test_group.group_rename(existing_group_name)
        self.assertIsNone(
            result,
            "Renaming to an existing group name should be allowed when it's the same group"
        )
        
    def test_group_rename(self):
        """Test renaming a group."""
        # Rename the test group
        new_name = "renamed_group"
        result = self.test_group.group_rename(new_name)
        
        self.assertIsNone(result, "Rename should succeed")
        self.assertEqual(self.test_group.name, new_name)

    def test_show_members(self):
        # Test empty group
        self.assertEqual(self.test_group.show_members(), "No members.")
        
        # Test with one member
        self.test_group.player_add(self.alice)
        self.assertEqual(self.test_group.show_members(), "Group 'test_group' Members: Alice")
        
        # Test with two members
        self.test_group.player_add(self.bob)
        expected = "Group 'test_group' Members: Alice and Bob"
        self.assertEqual(self.test_group.show_members(), expected)
        
        # Test with three members
        charlie = Player(name="Charlie")
        self.test_group.player_add(charlie)
        expected = "Group 'test_group' Members: Alice, Bob, and Charlie"
        self.assertEqual(self.test_group.show_members(), expected)

if __name__ == "__main__":
    unittest.main()
