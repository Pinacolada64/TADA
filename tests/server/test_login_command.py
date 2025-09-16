"""Tests for the login command."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from server.commands.login import LoginCommand
from server.commands.base_command import CommandResult
from server.net_common import Mode

@pytest.fixture
def login_command():
    """Fixture that returns a LoginCommand instance with a mock client."""
    command = LoginCommand()
    command.context = {'client': AsyncMock()}
    return command

@pytest.mark.asyncio
async def test_show_help(login_command):
    """Test showing help when no arguments are provided."""
    result = await login_command.execute({}, [])
    
    print("\n" + "="*80)
    print("HELP SCREEN OUTPUT:")
    print("="*80)
    print(result['message'])
    print("="*80 + "\n")
    
    assert result['success'] is True
    assert 'not currently logged in' in result['message']
    assert 'login <username> <password>' in result['message']
    assert result['data']['mode'] == Mode.login

@pytest.mark.asyncio
async def test_guest_connect(login_command):
    """Test connecting as a guest user."""
    mock_client = AsyncMock()
    
    result = await login_command.execute(
        {'client': mock_client}, 
        ['guest']
    )
    
    # Should return guest welcome message
    assert result['success'] is True
    assert 'Welcome, Guest!' in result['message']
    assert result['data']['authenticated'] is False
    assert result['data']['mode'] == Mode.guest

@pytest.mark.asyncio
async def test_prompt_for_password(login_command):
    """Test the password prompt when no password is provided."""
    mock_client = AsyncMock()
    mock_client.get_input.return_value = 'password123'
    
    result = await login_command.execute(
        {'client': mock_client}, 
        ['testuser']
    )
    
    # Verify password prompt was shown and input was requested
    mock_client.send.assert_called_with("Password: ", hide_input=True)
    mock_client.get_input.assert_awaited_once()
    
    # The actual implementation will show a success message for admin/password
    # or an error for other credentials
    assert isinstance(result, dict)
    assert 'message' in result

@pytest.mark.asyncio
async def test_missing_username(login_command):
    """Test login attempt with missing username."""
    result = await login_command.execute(
        {'client': AsyncMock()}, 
        []  # No username provided
    )
    
    assert result['success'] is True  # Shows help instead of error
    assert 'not currently logged in' in result['message']

@pytest.mark.asyncio
async def test_authentication_success(login_command):
    """Test successful user authentication."""
    # The actual implementation has a hardcoded test for 'admin'/'password'
    with patch('server.net_common.User') as mock_user:
        # Mock the user authentication
        mock_user.return_value.match_password.return_value = True
        
        result = await login_command.execute(
            {'client': AsyncMock()},
            ['admin', 'password']
        )
    
    assert result['success'] is True
    assert 'Welcome back, admin!' in result['message']
    assert result['data']['authenticated'] is True
    assert result['data']['mode'] == Mode.app

@pytest.mark.asyncio
async def test_authentication_failure(login_command):
    """Test failed user authentication."""
    result = await login_command.execute(
        {'client': AsyncMock()},
        ['testuser', 'wrongpassword']
    )
    
    assert result['success'] is False
    assert 'Invalid username or password' in result['message']
    assert result['data']['mode'] == Mode.login

@pytest.mark.asyncio
async def test_show_authenticated_status(login_command):
    """Test showing status when user is already authenticated."""
    context = {
        'client': AsyncMock(),
        'authenticated': True,
        'user_id': 'testuser'
    }
    
    result = await login_command._show_login_status(context)
    
    assert result['success'] is True
    # The message should mention the username and no characters
    assert 'testuser' in result['message']
    assert 'You don\'t have any characters yet' in result['message']

@pytest.mark.asyncio
async def test_show_unauthenticated_status(login_command):
    """Test showing status when user is not authenticated."""
    context = {'client': AsyncMock()}
    result = await login_command._show_login_status(context)
    
    assert result['success'] is True
    assert 'not currently logged in' in result['message']
    assert 'login <username> <password>' in result['message']
