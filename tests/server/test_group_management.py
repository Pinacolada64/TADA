import unittest
from ..group_management import Group
from player import Player

class TestGroupManagement(unittest.TestCase):
    def setUp(self):
        self.test_group = Group("test_group")
        self.another_group = Group("another_group")
        self.alice = Player(name="Alice")
        self.bob = Player(name="Bob")
        self.nonexistent_player = Player(name="Nonexistent Player")
        
        # Create a subgroup for testing
        self.test_group.group_add("subgroup")

    def test_add_duplicate_player(self):
        self.test_group.player_add(self.alice)
        with self.assertRaises(ValueError):
            self.test_group.player_add(self.alice)

    def test_remove_nonexistent_player(self):
        with self.assertRaises(ValueError):
            self.test_group.player_remove(self.nonexistent_player)

    def test_move_player(self):
        # Add player to the main group
        self.test_group.player_add(self.alice)
        
        # Move player from main group to subgroup
        self.test_group.move_player_between_groups(
            source_group=self.test_group,
            target_group=self.test_group.groups["subgroup"],
            player=self.alice
        )
        
        # Verify the move
        self.assertIn(self.alice, self.test_group.groups["subgroup"].members)
        self.assertNotIn(self.alice, self.test_group.members)

    def test_group_rename(self):
        # Test renaming to a new name
        new_name = "renamed_group"
        self.test_group.group_rename(new_name)
        self.assertEqual(self.test_group.name, new_name)
        
        # Test renaming to empty name
        with self.assertRaises(ValueError):
            self.test_group.group_rename("")  # Should raise ValueError

        # Test renaming group to itself
        with self.assertRaises(ValueError):
            self.test_group.group_rename("test_group")  # Should raise ValueError

    def test_show_members(self):
        self.test_group.player_add(self.alice)
        self.test_group.player_add(self.bob)
        expected = "Group 'test_group' Members: Alice, Bob"
        self.assertEqual(self.test_group.show_members(), expected)

if __name__ == "__main__":
    unittest.main()
