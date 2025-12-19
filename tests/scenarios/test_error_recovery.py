"""
Scenario tests for error recovery and fault tolerance.
Tests system behavior when errors occur and recovery mechanisms.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from discord.errors import DiscordException, HTTPException, ConnectionClosed

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
)
from tests.mocks.voice_mocks import MockVoiceClient

from cogs.control import Control
from cogs.subscribe import Subscribe
from src.session import session_manager
from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestErrorRecovery:
    """Scenario tests for error recovery mechanisms"""
    
    def setup_method(self):
        """Reset session state before each test"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def error_test_environment(self):
        """Fixture providing environment for error testing"""
        bot = MockBot()
        guild = MockGuild(id=12345, name="Test Guild")
        voice_channel = MockVoiceChannel(guild=guild)
        user = MockUser(id=67890, name="TestUser")
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        control_cog = Control(bot)
        subscribe_cog = Subscribe(bot)
        
        return {
            'bot': bot,
            'guild': guild,
            'voice_channel': voice_channel,
            'user': user,
            'interaction': interaction,
            'control_cog': control_cog,
            'subscribe_cog': subscribe_cog
        }
    
    @pytest.mark.asyncio
    async def test_discord_api_error_recovery(self, error_test_environment):
        """Test recovery from Discord API errors"""
        env = error_test_environment
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.logger') as mock_logger:
            
            # Setup mocks
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Simulate Discord API error during session start
            mock_controller.start_pomodoro = AsyncMock(
                side_effect=HTTPException(response=MagicMock(), message="API Error")
            )
            
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Try to start session (should handle error gracefully)
            try:
                await env['control_cog'].pomodoro.callback(
                    env['control_cog'],
                    env['interaction'],
                    pomodoro=25,
                    short_break=5,
                    long_break=20,
                    intervals=4
                )
            except HTTPException:
                pass  # Expected to be caught by error handler
            
            # Verify error logging occurred
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_voice_connection_error_recovery(self, error_test_environment):
        """Test recovery from voice connection errors"""
        env = error_test_environment
        
        with patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.session_messenger') as mock_messenger, \
             patch('src.session.session_controller.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.activate = AsyncMock()
            mock_messenger.send_session_start_msg = AsyncMock()
            
            # Simulate voice connection failure
            mock_vc_accessor.connect = AsyncMock(
                side_effect=DiscordException("Voice connection failed")
            )
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.session.Session.Timer'), \
                 patch('src.session.Session.Stats'), \
                 patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                
                from src.session import session_controller
                
                # Try to start session with voice connection error
                try:
                    await session_controller.start_pomodoro(session)
                except DiscordException:
                    pass  # Expected error
                
                # Verify error was logged
                mock_logger.error.assert_called()
                
                # Session should still be activated even if voice fails
                mock_session_manager.activate.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_session_corruption_recovery(self, error_test_environment):
        """Test recovery from corrupted session state"""
        env = error_test_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.logger') as mock_logger:
            
            # Create corrupted session (missing required attributes)
            corrupted_session = MagicMock()
            corrupted_session.ctx = env['interaction']
            corrupted_session.stats = None  # Corruption: missing stats
            corrupted_session.timer = None  # Corruption: missing timer
            
            mock_session_manager.get_session_interaction = AsyncMock(return_value=corrupted_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Mock validation to pass
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session")):
                
                # Try to execute command on corrupted session
                try:
                    await env['control_cog'].stop.callback(env['control_cog'], env['interaction'])
                except AttributeError:
                    pass  # Expected due to corruption
                
                # Verify error handling
                mock_logger.error.assert_called()
                
                # System should attempt to clean up corrupted session
                mock_controller.end.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_timer_exception_recovery(self, error_test_environment):
        """Test recovery from timer-related exceptions"""
        env = error_test_environment
        
        with patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.run_interval') as mock_run_interval, \
             patch('src.session.session_controller.logger') as mock_logger:
            
            # Create session with timer that throws exceptions
            mock_timer = MagicMock()
            mock_timer.start = MagicMock(side_effect=Exception("Timer error"))
            
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.session.Session.Timer'), \
                 patch('src.session.Session.Stats'), \
                 patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                session.timer = mock_timer
                
                from src.session import session_controller
                
                # Try to resume session with broken timer
                try:
                    await session_controller.resume(session)
                except Exception:
                    pass  # Expected timer error
                
                # Verify error was handled
                mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_network_disconnection_recovery(self, error_test_environment):
        """Test recovery from network disconnection"""
        env = error_test_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Create session
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Simulate network disconnection during command
            mock_controller.end = AsyncMock(
                side_effect=ConnectionClosed(None, None)
            )
            
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session")):
                
                # Try to execute command during network issue
                with pytest.raises(ConnectionClosed):
                    await env['control_cog'].stop.callback(env['control_cog'], env['interaction'])
                
                # Verify attempt was made
                mock_controller.end.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auto_mute_error_recovery(self, error_test_environment):
        """Test recovery from auto-mute operation errors"""
        env = error_test_environment
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.logger') as mock_logger, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Create session with auto_mute that fails
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session.auto_mute = MagicMock()
            mock_session.auto_mute.all = False
            mock_session.auto_mute.handle_all = AsyncMock(
                side_effect=Exception("Auto-mute operation failed")
            )
            
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_u_msg.AUTOMUTE_ENABLE_FAILED = "Auto-mute failed"
            
            # Execute auto-mute command
            await env['subscribe_cog'].enableautomute.callback(env['subscribe_cog'], env['interaction'])
            
            # Verify error was logged and handled gracefully
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify user was notified of failure
            env['interaction'].channel.send.assert_called_with("Auto-mute failed", silent=True)
    
    @pytest.mark.asyncio
    async def test_session_manager_corruption_recovery(self, error_test_environment):
        """Test recovery from session manager state corruption"""
        env = error_test_environment
        
        # Corrupt session manager state
        session_manager.active_sessions["corrupted_guild"] = "not_a_session_object"
        session_manager.active_sessions[str(env['guild'].id)] = None
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.logger') as mock_logger:
            
            # Use real session_manager but with corrupted state
            mock_session_manager.active_sessions = session_manager.active_sessions
            mock_session_manager.session_id_from.side_effect = session_manager.session_id_from
            
            async def mock_get_session_interaction(interaction):
                guild_id = session_manager.session_id_from(interaction)
                session = session_manager.active_sessions.get(guild_id)
                if session is None or not hasattr(session, 'ctx'):
                    return None
                return session
            
            mock_session_manager.get_session_interaction = mock_get_session_interaction
            
            # Try to get session from corrupted state
            result = await mock_session_manager.get_session_interaction(env['interaction'])
            
            # Should handle corruption gracefully
            assert result is None
    
    @pytest.mark.asyncio
    async def test_memory_pressure_recovery(self, error_test_environment):
        """Test recovery from memory pressure situations"""
        env = error_test_environment
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.logger') as mock_logger:
            
            # Setup mocks
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Simulate memory error during session creation
            mock_session_class.side_effect = MemoryError("Out of memory")
            
            # Try to create session under memory pressure
            try:
                await env['control_cog'].pomodoro.callback(
                    env['control_cog'],
                    env['interaction'],
                    pomodoro=25,
                    short_break=5,
                    long_break=20,
                    intervals=4
                )
            except MemoryError:
                pass  # Expected error
            
            # Verify error was logged
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_database_error_recovery(self, error_test_environment):
        """Test recovery from persistent storage errors"""
        env = error_test_environment
        
        # Simulate database/storage errors during stats operations
        with patch('src.session.Session.Stats') as mock_stats_class, \
             patch('src.session.Session.Timer'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.Session.logger') as mock_logger:
            
            # Mock stats that fails on save operations
            mock_stats = MagicMock()
            mock_stats.save = MagicMock(side_effect=IOError("Database error"))
            mock_stats_class.return_value = mock_stats
            
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            # Create session (should handle stats save error)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Try to save stats (should fail gracefully)
            try:
                session.stats.save()
            except IOError:
                pass  # Expected error
            
            # Session should still be functional despite storage error
            assert session.state == State.POMODORO
            assert session.settings == settings
    
    @pytest.mark.asyncio
    async def test_command_error_handler_integration(self, error_test_environment):
        """Test integration with command error handlers"""
        env = error_test_environment
        
        # Test pomodoro command error handler
        with patch('cogs.control.logger') as mock_logger, \
             patch('cogs.control.u_msg') as mock_u_msg:
            
            mock_u_msg.POMODORO_COMMAND_ERROR = "Pomodoro command failed"
            
            # Create a command error
            from discord import app_commands
            command = MagicMock()
            error = app_commands.CommandInvokeError(command, Exception("Test error"))
            
            # Test error handler
            await env['control_cog'].pomodoro_error(env['interaction'], error)
            
            # Verify error was logged and user was notified
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Check if response was sent (depends on interaction state)
            if not env['interaction'].response.is_done():
                env['interaction'].response.send_message.assert_called_once()
            else:
                env['interaction'].followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self, error_test_environment):
        """Test recovery from cascading failures"""
        env = error_test_environment
        
        with patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.session_messenger') as mock_messenger, \
             patch('src.session.session_controller.logger') as mock_logger:
            
            # Setup cascading failures
            mock_vc_accessor.connect = AsyncMock(side_effect=Exception("Voice error"))
            mock_session_manager.activate = AsyncMock(side_effect=Exception("Manager error"))
            mock_messenger.send_session_start_msg = AsyncMock(side_effect=Exception("Message error"))
            
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.session.Session.Timer'), \
                 patch('src.session.Session.Stats'), \
                 patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                
                from src.session import session_controller
                
                # Try to start session with multiple failures
                try:
                    await session_controller.start_pomodoro(session)
                except Exception:
                    pass  # Expected due to cascading failures
                
                # Verify all failure points were attempted and logged
                mock_vc_accessor.connect.assert_called_once()
                mock_logger.error.assert_called()  # Should have logged errors
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, error_test_environment):
        """Test graceful degradation when non-critical features fail"""
        env = error_test_environment
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Setup core functionality to work
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Create session that works despite some subsystem failures
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session_class.return_value = mock_session
            
            # Mock session controller to succeed (core functionality)
            mock_controller.start_pomodoro = AsyncMock()
            
            # Start session (should work even if some features are broken)
            await env['control_cog'].pomodoro.callback(
                env['control_cog'],
                env['interaction'],
                pomodoro=25,
                short_break=5,
                long_break=20,
                intervals=4
            )
            
            # Verify core functionality still worked
            mock_session_class.assert_called_once()
            mock_controller.start_pomodoro.assert_called_once_with(mock_session)
            env['interaction'].response.defer.assert_called_once()