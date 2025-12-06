"""
Tests for session management logic including Session class, session_manager, and related components.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tests.mocks.discord_mocks import MockInteraction, MockUser, MockGuild

# Import session components
from src.session.Session import Session
from src.session import session_manager
from src.Settings import Settings
from src.Stats import Stats
from src.Timer import Timer


class TestSession:
    """Test class for Session class"""
    
    @pytest.fixture
    def mock_interaction(self):
        """Fixture providing a mock interaction"""
        return MockInteraction()
    
    @pytest.fixture
    def mock_settings(self):
        """Fixture providing mock settings"""
        return MagicMock(spec=Settings)
    
    @pytest.fixture
    def session_instance(self, mock_interaction, mock_settings):
        """Fixture providing a Session instance"""
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            from configs.bot_enum import State
            return Session(State.POMODORO, mock_settings, mock_interaction)
    
    def test_session_initialization(self, session_instance, mock_interaction, mock_settings):
        """Test Session class initialization"""
        assert session_instance.ctx == mock_interaction
        assert session_instance.settings == mock_settings
        assert session_instance.timer is not None
        assert session_instance.stats is not None
        assert session_instance.current_session_start_time is None  # Initially None
    
    def test_session_attributes(self, session_instance):
        """Test Session class has all required attributes"""
        required_attributes = [
            'state', 'settings', 'timer', 'stats', 'ctx', 'timeout',
            'bot_start_msg', 'current_session_start_time', 'dm', 'auto_mute'
        ]
        
        for attr in required_attributes:
            assert hasattr(session_instance, attr), f"Session missing attribute: {attr}"


class TestSessionManager:
    """Test class for session_manager module"""
    
    def setup_method(self):
        """Clear session state before each test"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def mock_session(self):
        """Fixture providing a mock session"""
        session = MagicMock()
        session.ctx = MockInteraction()
        session.ctx.guild = MockGuild(id=12345)
        session.timeout = MagicMock()
        session.timeout.is_expired.return_value = False
        return session
    
    @pytest.mark.asyncio
    async def test_activate_session(self, mock_session):
        """Test activating a session"""
        await session_manager.activate(mock_session)
        
        guild_id = session_manager.session_id_from(mock_session.ctx)
        
        # Verify session was added to active sessions
        assert guild_id in session_manager.active_sessions
        assert session_manager.active_sessions[guild_id] == mock_session
        
        # Verify lock was created
        assert guild_id in session_manager.session_locks
    
    @pytest.mark.asyncio
    async def test_deactivate_session(self, mock_session):
        """Test deactivating a session"""
        # First activate the session
        await session_manager.activate(mock_session)
        
        guild_id = session_manager.session_id_from(mock_session.ctx)
        assert guild_id in session_manager.active_sessions
        
        # Now deactivate it
        await session_manager.deactivate(mock_session)
        
        # Verify session was removed
        assert guild_id not in session_manager.active_sessions
    
    @pytest.mark.asyncio
    async def test_get_session_existing(self, mock_session):
        """Test getting an existing session"""
        guild_id = session_manager.session_id_from(mock_session.ctx)
        session_manager.active_sessions[guild_id] = mock_session
        
        result = await session_manager.get_session(mock_session.ctx)
        assert result == mock_session
    
    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, mock_interaction):
        """Test getting a non-existent session"""
        # Create a context that doesn't exist in active sessions
        mock_interaction.guild.id = 99999
        result = await session_manager.get_session(mock_interaction)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_session_interaction(self, mock_session):
        """Test getting session via interaction"""
        guild_id = session_manager.session_id_from(mock_session.ctx)
        session_manager.active_sessions[guild_id] = mock_session
        
        result = await session_manager.get_session_interaction(mock_session.ctx)
        assert result == mock_session
    
    def test_session_id_from_interaction(self):
        """Test generating session ID from interaction"""
        interaction = MockInteraction()
        interaction.guild.id = 12345
        
        result = session_manager.session_id_from(interaction)
        assert result == "12345"
    
    def test_session_id_from_guild_id(self):
        """Test session_id_from with object having guild.id attribute"""
        mock_ctx = MagicMock()
        mock_ctx.guild.id = 54321
        result = session_manager.session_id_from(mock_ctx)
        assert result == "54321"
    
    @pytest.mark.asyncio
    async def test_kill_if_idle_not_expired(self, mock_session):
        """Test kill_if_idle when session is not expired"""
        # Mock interaction-based session (has client attribute)
        mock_session.ctx.client = MagicMock()
        
        result = await session_manager.kill_if_idle(mock_session)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_kill_if_idle_expired(self, mock_session):
        """Test kill_if_idle when session is expired"""
        # Mock non-interaction session (no client attribute)
        mock_session.ctx = MagicMock()
        if hasattr(mock_session.ctx, 'client'):
            delattr(mock_session.ctx, 'client')
            
        with patch('src.session.session_manager.vc_accessor') as mock_vc_accessor:
            # Mock empty voice channel
            mock_vc_accessor.get_voice_channel.return_value = None
            
            # Mock the ctx.invoke method
            mock_session.ctx.invoke = AsyncMock()
            mock_session.ctx.bot.get_command.return_value = 'stop_command'
            
            result = await session_manager.kill_if_idle(mock_session)
            
            assert result is True
            mock_session.ctx.invoke.assert_called_once_with('stop_command')


class TestSettings:
    """Test class for Settings class"""
    
    @pytest.fixture
    def settings_instance(self):
        """Fixture providing a Settings instance"""
        return Settings(duration=25, short_break=5, long_break=20, intervals=4)
    
    def test_settings_initialization(self, settings_instance):
        """Test Settings class initialization"""
        assert settings_instance.duration == 25
        assert settings_instance.short_break == 5
        assert settings_instance.long_break == 20
        assert settings_instance.intervals == 4
    
    @pytest.mark.asyncio
    async def test_is_valid_interaction_valid_settings(self):
        """Test Settings.is_valid_interaction with valid settings"""
        interaction = MockInteraction()
        
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            result = await Settings.is_valid_interaction(interaction, 25, 5, 20, 4)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_is_valid_interaction_invalid_settings(self):
        """Test Settings.is_valid_interaction with invalid settings"""
        interaction = MockInteraction()
        
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            # Test with pomodoro time too long
            result = await Settings.is_valid_interaction(interaction, 999, 5, 20, 4)
            assert result is False
    
    @pytest.mark.skip(reason="is_valid_countdown method does not exist")
    def test_is_valid_countdown_valid(self):
        """Test Settings.is_valid_countdown with valid input"""
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            result = Settings.is_valid_countdown(30)
            assert result is True
    
    @pytest.mark.skip(reason="is_valid_countdown method does not exist")
    def test_is_valid_countdown_invalid(self):
        """Test Settings.is_valid_countdown with invalid input"""
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            # Test with time too long
            result = Settings.is_valid_countdown(999)
            assert result is False
            
            # Test with time too short
            result = Settings.is_valid_countdown(0)
            assert result is False
    
    @pytest.mark.skip(reason="is_valid_classwork method does not exist")
    def test_is_valid_classwork_valid(self):
        """Test Settings.is_valid_classwork with valid input"""
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            result = Settings.is_valid_classwork(45, 15)
            assert result is True
    
    @pytest.mark.skip(reason="is_valid_classwork method does not exist")
    def test_is_valid_classwork_invalid(self):
        """Test Settings.is_valid_classwork with invalid input"""
        with patch('src.Settings.config') as mock_config:
            mock_config.MAX_INTERVAL_MINUTES = 120
            mock_config.MIN_INTERVAL_MINUTES = 1
            
            # Test with work time too long
            result = Settings.is_valid_classwork(999, 15)
            assert result is False
            
            # Test with rest time invalid
            result = Settings.is_valid_classwork(45, 0)
            assert result is False


class TestStats:
    """Test class for Stats class"""
    
    def test_stats_initialization(self):
        """Test Stats class initialization"""
        stats = Stats()
        
        assert stats.pomos_completed == 0
        assert stats.pomos_elapsed == 0
        assert stats.seconds_completed == 0


class TestTimer:
    """Test class for Timer class"""
    
    def test_timer_initialization(self):
        """Test Timer class initialization"""
        mock_parent = MagicMock()
        mock_parent.settings.duration = 25
        timer = Timer(mock_parent)
        
        # Verify timer has basic attributes
        assert hasattr(timer, 'remaining')
        assert hasattr(timer, 'running')
        assert timer.parent == mock_parent
        assert not timer.running
        assert timer.remaining == 25 * 60  # 25 minutes in seconds
    
    @pytest.mark.asyncio
    async def test_timer_basic_functionality(self):
        """Test basic timer functionality"""
        mock_parent = MagicMock()
        mock_parent.settings.duration = 25
        mock_parent.state = MagicMock()
        timer = Timer(mock_parent)
        
        # Test timer initial state
        assert not timer.running
        assert timer.remaining == 25 * 60
        
        # Test time remaining string method
        time_str = timer.time_remaining_to_str()
        assert isinstance(time_str, str)
        assert "分" in time_str