"""
Integration tests for session lifecycle management.
Tests session creation, activation, management, and cleanup.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta

from tests.mocks.discord_mocks import MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
from tests.mocks.voice_mocks import MockVoiceClient

from src.session import session_manager
from src.session.Session import Session
from src.session import session_controller
from src.Settings import Settings
from configs.bot_enum import State


class TestSessionLifecycle:
    """Integration tests for complete session lifecycle"""
    
    def setup_method(self):
        """Reset session state before each test"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def session_environment(self):
        """Fixture providing session test environment"""
        bot = MockBot()
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild)
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        return {
            'bot': bot,
            'interaction': interaction,
            'voice_channel': voice_channel,
            'guild_id': str(guild.id)
        }
    
    @pytest.mark.asyncio
    async def test_session_creation_and_activation(self, session_environment):
        """Test session creation and activation process"""
        env = session_environment
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Verify session is not initially active
            guild_id = session_manager.session_id_from(env['interaction'])
            assert guild_id not in session_manager.active_sessions
            
            # Activate session
            await session_manager.activate(session)
            
            # Verify session is now active
            assert guild_id in session_manager.active_sessions
            assert session_manager.active_sessions[guild_id] == session
            assert guild_id in session_manager.session_locks
            
            # Verify session can be retrieved
            retrieved_session = await session_manager.get_session(env['interaction'])
            assert retrieved_session == session
            
            retrieved_session_by_interaction = await session_manager.get_session_interaction(env['interaction'])
            assert retrieved_session_by_interaction == session
    
    @pytest.mark.asyncio
    async def test_session_deactivation_and_cleanup(self, session_environment):
        """Test session deactivation and cleanup process"""
        env = session_environment
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create and activate session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            await session_manager.activate(session)
            
            guild_id = session_manager.session_id_from(env['interaction'])
            
            # Verify session is active
            assert guild_id in session_manager.active_sessions
            
            # Deactivate session
            await session_manager.deactivate(session)
            
            # Verify session is no longer active
            assert guild_id not in session_manager.active_sessions
            
            # Verify session cannot be retrieved
            retrieved_session = await session_manager.get_session(env['interaction'])
            assert retrieved_session is None
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_with_controller(self, session_environment):
        """Test complete session lifecycle using session controller"""
        env = session_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_messenger') as mock_messenger:
            
            # Setup mocks
            mock_timer.return_value = MagicMock()
            mock_stats.return_value = MagicMock()
            mock_vc_accessor.connect = AsyncMock()
            mock_messenger.send_session_start_msg = AsyncMock()
            mock_session_manager.activate = AsyncMock()
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Test session start through controller
            await session_controller.start_pomodoro(session)
            
            # Verify session was activated
            mock_session_manager.activate.assert_called_once_with(session)
            
            # Verify voice connection was attempted
            mock_vc_accessor.connect.assert_called_once_with(session)
            
            # Verify start message was sent
            mock_messenger.send_session_start_msg.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_session_end_lifecycle(self, session_environment):
        """Test session ending and cleanup"""
        env = session_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_messenger') as mock_messenger, \
             patch('src.session.session_controller.cleanup_pins') as mock_cleanup_pins:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_stats_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats.return_value = mock_stats_instance
            mock_session_manager.deactivate = AsyncMock()
            mock_vc_accessor.disconnect = AsyncMock()
            mock_messenger.send_session_end_msg = AsyncMock()
            mock_cleanup_pins.return_value = AsyncMock()
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.timer = mock_timer_instance
            session.stats = mock_stats_instance
            
            # Test session end through controller
            await session_controller.end(session)
            
            # Verify timer was stopped
            mock_timer_instance.kill.assert_called_once()
            
            # Verify voice was disconnected
            mock_vc_accessor.disconnect.assert_called_once_with(session)
            
            # Verify end message was sent
            mock_messenger.send_session_end_msg.assert_called_once_with(session)
            
            # Verify session was deactivated
            mock_session_manager.deactivate.assert_called_once_with(session)
            
            # Verify pins were cleaned up
            cleanup_func = mock_cleanup_pins.return_value
            cleanup_func.assert_called_once_with(session.ctx)
    
    @pytest.mark.asyncio
    async def test_multiple_session_management(self, session_environment):
        """Test managing multiple sessions simultaneously"""
        env = session_environment
        
        # Create multiple guild environments
        guilds = []
        interactions = []
        for i in range(3):
            guild = MockGuild(id=54321 + i, name=f"Test Guild {i}")
            user = MockUser(id=12345 + i, name=f"TestUser{i}")
            interaction = MockInteraction(user=user, guild=guild)
            guilds.append(guild)
            interactions.append(interaction)
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            sessions = []
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            # Create and activate multiple sessions
            for interaction in interactions:
                session = Session(State.POMODORO, settings, interaction)
                await session_manager.activate(session)
                sessions.append(session)
            
            # Verify all sessions are active
            assert len(session_manager.active_sessions) == 3
            
            # Verify each session can be retrieved by its interaction
            for i, (session, interaction) in enumerate(zip(sessions, interactions)):
                retrieved_session = await session_manager.get_session(interaction)
                assert retrieved_session == session
                
                guild_id = session_manager.session_id_from(interaction)
                assert guild_id in session_manager.active_sessions
            
            # Deactivate sessions one by one
            for i, session in enumerate(sessions):
                await session_manager.deactivate(session)
                assert len(session_manager.active_sessions) == (2 - i)
            
            # Verify all sessions are deactivated
            assert len(session_manager.active_sessions) == 0
    
    @pytest.mark.asyncio
    async def test_session_idle_detection_and_cleanup(self, session_environment):
        """Test idle session detection and automatic cleanup"""
        env = session_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_manager.vc_accessor') as mock_vc_accessor:
            
            # Setup timer mock to simulate idle session
            mock_timer_instance = MagicMock()
            mock_timer_instance.is_expired.return_value = True
            mock_timer.return_value = mock_timer_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.timeout = mock_timer_instance
            
            # Remove client attribute to simulate non-interaction session
            session.ctx = MagicMock()
            if hasattr(session.ctx, 'client'):
                delattr(session.ctx, 'client')
            
            # Mock empty voice channel (simulates idle condition)
            mock_vc_accessor.get_voice_channel.return_value = None
            session.ctx.invoke = AsyncMock()
            session.ctx.bot.get_command.return_value = 'stop_command'
            
            # Test idle detection
            result = await session_manager.kill_if_idle(session)
            
            # Verify session was considered idle and cleanup was initiated
            assert result is True
            session.ctx.invoke.assert_called_once_with('stop_command')
    
    @pytest.mark.asyncio
    async def test_session_resume_functionality(self, session_environment):
        """Test session resume functionality"""
        env = session_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.run_interval') as mock_run_interval:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_run_interval.return_value = AsyncMock()
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.timer = mock_timer_instance
            
            # Test resume functionality
            await session_controller.resume(session)
            
            # Verify timer was started
            mock_timer_instance.start.assert_called_once()
            
            # Verify interval runner was started
            run_interval_func = mock_run_interval.return_value
            run_interval_func.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_session_state_persistence(self, session_environment):
        """Test that session state persists correctly throughout lifecycle"""
        env = session_environment
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Set initial state
            initial_state = State.POMODORO
            session.state = initial_state
            session.stats.pomos_completed = 1
            session.stats.seconds_completed = 500
            
            # Activate session
            await session_manager.activate(session)
            
            # Retrieve session and verify state persistence
            retrieved_session = await session_manager.get_session(env['interaction'])
            assert retrieved_session.state == initial_state
            assert retrieved_session.stats.pomos_completed == 1
            assert retrieved_session.stats.seconds_completed == 500
            
            # Change state and verify persistence
            new_state = State.SHORT_BREAK
            retrieved_session.state = new_state
            retrieved_session.stats.pomos_completed = 2
            
            # Get session again and verify changes persisted
            retrieved_again = await session_manager.get_session(env['interaction'])
            assert retrieved_again.state == new_state
            assert retrieved_again.stats.pomos_completed == 2
            assert retrieved_again is retrieved_session  # Should be same object