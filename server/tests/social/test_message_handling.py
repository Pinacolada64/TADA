#!/usr/bin/env python3
import logging
from dataclasses import asdict

import sys
import os

# Add parent directory to path so that packages in the parent directory can be imported
# FIXME: Not sure why "import server.net_common" doesn't work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from net_common import Mode
from net_server import Message as ServerMessage

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('test')

def test_message_creation():
    """Test message creation and serialization"""
    print("\n=== Testing Message Creation ===")
    
    # Test 1: Basic message with default mode
    msg1 = ServerMessage(lines=["Test message"])
    print(f"Message 1: {asdict(msg1)}")
    assert msg1.mode == Mode.app, f"Expected Mode.app, got {msg1.mode}"
    
    # Test 2: Message with explicit mode
    msg2 = ServerMessage(lines=["Login required"], mode=Mode.login)
    print(f"Message 2: {asdict(msg2)}")
    assert msg2.mode == Mode.login, f"Expected Mode.login, got {msg2.mode}"
    
    # Test 3: Message with mode=None. net_common.Message's `mode` field uses
    # a default_factory (Mode.app), which Python's dataclasses only apply
    # when the argument is omitted entirely -- passing mode=None explicitly
    # bypasses it and stores None as-is (standard dataclass semantics, not
    # something __post_init__ normalizes). No production code ever
    # constructs Message(mode=None), so this just documents that behavior.
    msg3 = ServerMessage(lines=["Test with explicit None mode"], mode=None)
    print(f"Message 3: {asdict(msg3)}")
    assert msg3.mode is None, f"Expected None, got {msg3.mode}"
    
    # Test with invalid Mode:
    msg4 = ServerMessage(lines=["Test with invalid Mode"], mode="invalid")
    print(f"Message 4: {asdict(msg4)}")
    assert msg4.mode == "invalid", f"Expected Mode.app, got {msg4.mode}"
    
    # Test with choices:
    choices = {"key": "value"}
    msg5 = ServerMessage(lines=["Test with choices"], choices=choices)
    print(f"Message 5: {asdict(msg5)}")
    assert msg5.choices == choices, f"Expected choices {choices}, got {msg5.choices}"
    
    # Test with changes:
    changes = {"key": "value"}
    msg6 = ServerMessage(lines=["Test with changes"], changes=changes)
    print(f"Message 6: {asdict(msg6)}")
    assert msg6.changes == changes, f"Expected changes {changes}, got {msg6.changes}"
    
    # Test with prompt:
    prompt = "> "
    msg7 = ServerMessage(lines=["Test with prompt"], prompt=prompt)
    print(f"Message 7: {asdict(msg7)}")
    assert msg7.prompt == prompt, f"Expected prompt {prompt}, got {msg7.prompt}"
    
    # Test with error:
    error = "error"
    msg8 = ServerMessage(lines=["Test with error"], error=error)
    print(f"Message 8: {asdict(msg8)}")
    assert msg8.error == error, f"Expected error {error}, got {msg8.error}"
    
    # Test with error_line:
    error_line = "error_line"
    msg9 = ServerMessage(lines=["Test with error_line"], error_line=error_line)
    print(f"Message 9: {asdict(msg9)}")
    assert msg9.error_line == error_line, f"Expected error_line {error_line}, got {msg9.error_line}"
    
    print("✓ All message creation tests passed!")

def test_message_serialization():
    """Test message serialization and deserialization"""
    print("\n=== Testing Message Serialization ===")
    
    # Create a message
    original_msg = ServerMessage(
        lines=["Test message"],
        mode=Mode.login,
        changes={"key": "value"},
        choices={"key": "value"},
        prompt="> "
    )
    
    # Convert to dict and then to JSON bytes with length prefix
    json_data = asdict(original_msg)
    print(f"Original message as dict: {json_data}")
    
    # Convert to JSON string first
    import json
    json_str = json.dumps(json_data, default=str)  # Use str for non-serializable objects
    print(f"Serialized to JSON string: {json_str}")
    
    # Deserialize back to dict
    deserialized = json.loads(json_str)
    print(f"Deserialized: {deserialized}")
    
    # Create new message from deserialized data
    new_msg = ServerMessage(**deserialized)
    print(f"Reconstructed message: {asdict(new_msg)}")
    
    # Verify
    assert new_msg.lines == original_msg.lines
    assert new_msg.mode == original_msg.mode
    assert new_msg.changes == original_msg.changes
    assert new_msg.choices == original_msg.choices
    assert new_msg.prompt == original_msg.prompt
    assert new_msg.error == original_msg.error
    assert new_msg.error_line == original_msg.error_line
    
    print("✓ All serialization tests passed!")

if __name__ == "__main__":
    test_message_creation()
    test_message_serialization()
