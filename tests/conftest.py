import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Add bot directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockGuild, MockUser, 
    MockVoiceChannel, MockTextChannel, MockMember
)
from tests.mocks.voice_mocks import MockVoiceClient


@pytest.fixture
def mock_bot():
    """Fixture providing a mocked Discord bot"""
    return MockBot()


@pytest.fixture
def mock_guild():
    """Fixture providing a mocked Discord guild"""
    return MockGuild()


@pytest.fixture
def mock_user():
    """Fixture providing a mocked Discord user"""
    return MockUser()


@pytest.fixture
def mock_voice_channel():
    """Fixture providing a mocked Discord voice channel"""
    return MockVoiceChannel()


@pytest.fixture
def mock_text_channel():
    """Fixture providing a mocked Discord text channel"""
    return MockTextChannel()


@pytest.fixture
def mock_member(mock_user, mock_guild):
    """Fixture providing a mocked Discord member"""
    return MockMember(user=mock_user, guild=mock_guild)


@pytest.fixture
def mock_interaction(mock_user, mock_guild, mock_text_channel):
    """Fixture providing a mocked Discord interaction"""
    return MockInteraction(
        user=mock_user,
        guild=mock_guild,
        channel=mock_text_channel
    )


@pytest.fixture
def mock_voice_client():
    """Fixture providing a mocked Discord voice client"""
    return MockVoiceClient()


@pytest.fixture
def mock_session_manager():
    """Fixture providing a mocked session manager"""
    with patch('src.session.session_manager') as mock_manager:
        mock_manager.active_sessions = {}
        mock_manager.get_session = MagicMock(return_value=None)
        mock_manager.add_session = AsyncMock()
        mock_manager.remove_session = AsyncMock()
        mock_manager.kill_if_idle = AsyncMock()
        yield mock_manager


@pytest.fixture
def mock_voice_client_manager():
    """Fixture providing a mocked voice client manager"""
    with patch('src.voice_client.vc_manager') as mock_vc_manager:
        mock_vc_manager.connect = AsyncMock()
        mock_vc_manager.disconnect = AsyncMock()
        mock_vc_manager.get_voice_client = MagicMock(return_value=None)
        yield mock_vc_manager


@pytest.fixture
def mock_env_variables():
    """Fixture providing mocked environment variables"""
    with patch.dict('os.environ', {'DISCORD_TOKEN': 'test_token'}):
        yield


@pytest.fixture(autouse=True)
def setup_test_environment(mock_env_variables):
    """Auto-used fixture to set up test environment"""
    # Clear any existing bot instances and session data
    with patch('bot.main.bot') as mock_bot:
        mock_bot.user = MockUser(name="TestBot")
        yield


@pytest.fixture
async def async_fixture_example():
    """Example of how to create async fixtures"""
    # Setup
    await asyncio.sleep(0)  # Simulate async setup
    yield "test_data"
    # Cleanup
    await asyncio.sleep(0)  # Simulate async cleanup


@pytest.fixture
def no_discord_api():
    """Fixture to ensure no real Discord API calls are made"""
    with patch('discord.Client.start'), \
         patch('discord.VoiceClient.connect'), \
         patch('discord.VoiceClient.disconnect'):
        yield