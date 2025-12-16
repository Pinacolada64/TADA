"""Tests for message handlers in TADA server."""
import sys
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch, call, Mock
from io import StringIO

"""
cd /home/ryan/Documents/c64/Windsurf/TADA/server && python3 -m unittest tests.test_message_handlers -v
"""
# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from message_handlers import (
    MessageRouter,
    message_router,
    handle_notification,
    handle_page,
    handle_system,
    handle_new_player,
    handle_player_created
)

class TestMessageRouter(unittest.TestCase):
    """Test the message routing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.router = MessageRouter()
        self.mock_client = MagicMock()
        self.mock_client.current_prompt = "test> "
    
    def test_register_handler(self):
        """Test that handlers can be registered."""
        @self.router.register_command("test_message")
        def test_handler(message, client):
            return "test"
            
        self.assertIn("test_message", self.router._handlers)
        self.assertEqual(
            self.router._handlers["test_message"].message_type,
            "test_message"
        )
    
    def test_handle_message_success(self):
        """Test successful message handling."""
        # Create a mock handler function
        def mock_handler_func(message, client):
            return "test"
            
        # Register the mock handler using the message_router's register method
        self.router.register_command("test")(mock_handler_func)
        
        test_message = {"type": "test", "data": "test data"}
        result = self.router.handle_message(test_message, self.mock_client)
        
        self.assertTrue(result)
    
    def test_handle_message_missing_type(self):
        """Test handling of messages without a type."""
        with self.assertLogs(level='WARNING'):
            result = self.router.handle_message({}, self.mock_client)
            self.assertFalse(result)
    
    def test_handle_message_no_handler(self):
        """Test handling of messages with no registered handler."""
        with self.assertLogs(level='DEBUG'):
            result = self.router.handle_message(
                {"type": "unknown"}, 
                self.mock_client
            )
            self.assertFalse(result)
    
    def test_handle_message_exception(self):
        """Test that exceptions in handlers are caught and logged."""
        def failing_handler(message, client):
            raise ValueError("Test error")
            
        self.router._handlers["failing"] = failing_handler
        
        with self.assertLogs(level='ERROR'):
            result = self.router.handle_message(
                {"type": "failing"}, 
                self.mock_client
            )
            self.assertFalse(result)


class TestMessageHandlers(unittest.TestCase):
    """Test individual message handlers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_client.current_prompt = "test> "
        
        # Redirect stdout for testing print statements
        self.held_output = io.StringIO()
        self.original_stdout = sys.stdout
        sys.stdout = self.held_output
    
    def tearDown(self):
        """Clean up after tests."""
        sys.stdout = self.original_stdout
    
    def test_handle_notification(self):
        """Test notification message handler."""
        test_message = {
            "type": "notification",
            "text": "Test notification"
        }
        
        # Reset the output buffer
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        
        # Set a test prompt
        self.mock_client.current_prompt = "test> "
        
        # Call the handler
        handle_notification(test_message, self.mock_client)
        
        # Get the captured output
        output = self.held_output.getvalue()
        
        # Check that the notification was printed to stdout
        self.assertIn("[Notification] Test notification", output)
        
        # The prompt should be preserved
        self.assertEqual(self.mock_client.current_prompt, "test> ")
        
        # The prompt should be printed after the notification
        self.assertIn("test> ", output)
    
    def test_handle_page(self):
        """Test page message handler."""
        test_message = {
            "type": "page",
            "from": "other_user",
            "text": "Test message"
        }
        
        handle_page(test_message, self.mock_client)
        
        output = self.held_output.getvalue()
        self.assertIn("Page from other_user", output)
        self.assertIn("Test message", output)
    
    def test_handle_system(self):
        """Test system message handler."""
        test_message = {
            "type": "system",
            "text": "System is going down in 5 minutes"
        }
        
        handle_system(test_message, self.mock_client)
        
        output = self.held_output.getvalue()
        self.assertIn("System is going down in 5 minutes", output)
    
    @patch('builtins.input', return_value='TestPlayer')
    def test_handle_new_player(self, mock_input):
        """Test new player creation flow."""
        # Setup the mock client with a send_message method
        self.mock_client.send_message = MagicMock()
        
        test_message = {
            "type": "new_player",
            "user_id": "testuser",
            "message": "Welcome!"
        }
        
        handle_new_player(test_message, self.mock_client)
        
        # Verify the welcome message was printed
        output = self.held_output.getvalue()
        self.assertIn("Welcome!", output)
        self.assertIn("Character Creation", output)
        
        # Verify the character creation message was sent
        self.mock_client.send_message.assert_called_once()
        args, _ = self.mock_client.send_message.call_args
        self.assertEqual(args[0]["type"], "command")
        self.assertEqual(args[0]["character"]["name"], "TestPlayer")
    
    def test_handle_player_created(self):
        """Test successful player creation handler."""
        test_message = {
            "type": "player_created",
            "user_id": "testuser",
            "room": "1",
            "message": "Welcome to the game!"
        }
        
        handle_player_created(test_message, self.mock_client)
        
        # Verify the welcome message and room info were printed
        output = self.held_output.getvalue()
        self.assertIn("Welcome to the game!", output)
        self.assertIn("You are in room 1", output)
        self.assertIn("Type 'help' for a list of commands", output)
        
        # Verify the prompt was updated
        self.assertEqual(self.mock_client.current_prompt, "testuser> ")


class TestMessageRouterIntegration(unittest.TestCase):
    """Integration tests for the message router with actual handlers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.router = message_router  # Use the global router with registered handlers
        self.mock_client = MagicMock()
        self.mock_client.current_prompt = "test> "
        
        # Redirect stdout for testing print statements
        self.held_output = io.StringIO()
        self.original_stdout = sys.stdout
        sys.stdout = self.held_output
    
    def tearDown(self):
        """Clean up after tests."""
        sys.stdout = self.original_stdout
    
    def test_notification_routing(self):
        """Test that notification messages are properly routed."""
        test_message = {
            "type": "notification",
            "text": "Test notification"
        }
        
        result = self.router.handle_message(test_message, self.mock_client)
        self.assertTrue(result)
        
        output = self.held_output.getvalue()
        self.assertIn("Test notification", output)


if __name__ == '__main__':
    unittest.main()
