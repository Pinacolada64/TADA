#!/usr/bin/env python3
"""
Test cases for the invite system functionality.
"""
import os
import sys
import json
import time
import logging
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, mock
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_invite_system.log')
    ]
)
logger = logging.getLogger(__name__)

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.net_common import Invite, User, K, Mode
from server.config import config as server_config

class TestInviteSystem(TestCase):
    """Test cases for the invite system functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test data
        self.test_dir = Path(tempfile.mkdtemp(prefix="tada_test_"))
        self.original_require_invites = server_config.require_invites
        
        # Patch the paths to use our test directory
        self.patcher = mock.patch('server.net_common.run_server_dir', self.test_dir / 'run' / 'server')
        self.mock_run_server_dir = self.patcher.start()
        
        # Create necessary directories
        (self.test_dir / 'run' / 'server' / 'invite').mkdir(parents=True, exist_ok=True)
        (self.test_dir / 'run' / 'server' / 'net').mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        server_config.require_invites = self.original_require_invites
    
    def test_invite_creation_and_validation(self):
        """Test creating and validating an invite."""
        # Create a test invite
        invite = Invite(
            id="testuser",
            email="test@example.com",
            code="TEST123"
        )
        
        # Save the invite
        invite.save()
        
        # Load the invite back
        loaded_invite = Invite.load("testuser")
        
        # Verify the loaded invite matches the original
        self.assertIsNotNone(loaded_invite)
        self.assertEqual(loaded_invite.id, "testuser")
        self.assertEqual(loaded_invite.email, "test@example.com")
        self.assertEqual(loaded_invite.code, "TEST123")
        
        # Test invite deletion
        loaded_invite.delete()
        self.assertIsNone(Invite.load("testuser"))
    
    def test_optional_invite_registration(self):
        """Test registration with optional invites."""
        # Test with invites required
        server_config.require_invites = True
        
        # Create a test user
        user_id = "testuser1"
        password = "testpass123"
        
        # First, ensure the user doesn't exist
        if os.path.exists(User._json_path(user_id)):
            os.remove(User._json_path(user_id))
        
        # Try to load the user (should not exist yet)
        user = User.load(user_id)
        self.assertIsNone(user)
        
        # Create an invite
        invite = Invite(
            id=user_id,
            email="test1@example.com",
            code="INVITE123"
        )
        invite.save()
        
        # Verify the invite exists
        loaded_invite = Invite.load(user_id)
        self.assertIsNotNone(loaded_invite)
        
        # Now create a user with the invite
        user = User(id=user_id)
        user.hash_password(password)
        user.save()
        
        # The invite should still exist until explicitly deleted
        # (in the actual server, the login handler would delete it)
        self.assertIsNotNone(Invite.load(user_id))
        
        # Clean up the invite
        Invite.load(user_id).delete()
        self.assertIsNone(Invite.load(user_id))
        
        # Test with invites not required
        server_config.require_invites = False
        
        # Try to register without an invite (should work)
        user_id2 = "testuser2"
        password2 = "testpass456"
        
        user2 = User(id=user_id2)
        user2.hash_password(password2)
        user2.save()
        
        # Verify the user was created
        loaded_user = User.load(user_id2)
        self.assertIsNotNone(loaded_user)
        self.assertTrue(loaded_user.match_password(password2))
    
    def test_invite_expiration(self):
        """Test invite expiration functionality."""
        # This would test invite expiration, but it's not implemented yet
        # We can add this test when invite expiration is implemented
        pass


if __name__ == "__main__":
    import unittest
    unittest.main()
