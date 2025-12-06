"""
Tests for the Control cog commands.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from tests.mocks.discord_mocks import MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
from tests.mocks.voice_mocks import MockVoiceClient

# Import the cog under test
from cogs.control import Control


class TestControl:
    """Test class for Control cog"""
    
    @pytest.fixture
    def control_cog(self, mock_bot):
        """Fixture providing a Control cog instance"""
        return Control(mock_bot)
    
    @pytest.fixture
    def setup_interaction(self):
        """Fixture providing a properly configured interaction"""
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild)
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock user being in voice channel
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        return interaction
    
    @pytest.mark.asyncio
    async def test_pomodoro_command_valid_parameters(self, control_cog, setup_interaction):
        """Test pomodoro command with valid parameters"""
        interaction = setup_interaction
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class:
            
            # Mock Settings validation
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            
            # Mock session controller
            mock_controller.start_pomodoro = AsyncMock()
            
            # Mock session creation
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Execute command
            await control_cog.pomodoro.callback(control_cog, interaction, pomodoro=25, short_break=5, long_break=20, intervals=4)
            
            # Verify settings validation was called
            mock_settings.is_valid_interaction.assert_called_once()
            
            # Verify interaction was deferred
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify session was created
            mock_session_class.assert_called_once()
            
            # Verify session controller was called
            mock_controller.start_pomodoro.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_pomodoro_command_invalid_settings(self, control_cog, setup_interaction):
        """Test pomodoro command with invalid settings"""
        interaction = setup_interaction
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.u_msg') as mock_msg, \
             patch('cogs.control.config') as mock_config:
            
            # Mock Settings validation failure
            mock_settings.is_valid_interaction = AsyncMock(return_value=False)
            mock_msg.INVALID_DURATION_ERR.format.return_value = "Invalid duration"
            mock_config.MAX_INTERVAL_MINUTES = 120
            
            # Execute command
            await control_cog.pomodoro.callback(control_cog, interaction, pomodoro=999, short_break=5, long_break=20, intervals=4)
            
            # Verify settings validation was called
            mock_settings.is_valid_interaction.assert_called_once()
            
            # Verify error response was sent
            interaction.response.send_message.assert_called_once_with("Invalid duration", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_pomodoro_command_no_voice_channel(self, control_cog, mock_interaction):
        """Test pomodoro command when user is not in voice channel"""
        # Setup interaction with user not in voice channel
        mock_interaction.user.voice = None
        
        with patch('cogs.control.voice_validation') as mock_voice_validation:
            mock_voice_validation.can_connect.return_value = False
            
            # Mock the validation method to return False
            with patch.object(control_cog, '_validate_session_prerequisites', return_value=False):
                await control_cog.pomodoro.callback(control_cog, mock_interaction)
                
                # Verify validation was called
                control_cog._validate_session_prerequisites.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_stop_command_active_session(self, control_cog, setup_interaction):
        """Test stop command with active session"""
        interaction = setup_interaction
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Mock active session
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 1
            mock_session.state = MagicMock()
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_controller.end = AsyncMock()
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Mock the validation method to return True
            with patch.object(control_cog, '_validate_and_setup_session', return_value=(True, "123456")):
                await control_cog.stop.callback(control_cog, interaction)
                
                # Verify session was retrieved
                mock_session_manager.get_session_interaction.assert_called_once()
                
                # Verify session was stopped
                mock_controller.end.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_command_no_active_session(self, control_cog, setup_interaction):
        """Test stop command with no active session"""
        interaction = setup_interaction
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.u_msg') as mock_msg:
            
            # Mock no active session
            mock_session_manager.get_session_interaction = AsyncMock(return_value=None)
            mock_msg.NO_SESSION_TO_STOP = "No active session"
            
            # Mock the validation method to return True
            with patch.object(control_cog, '_validate_and_setup_session', return_value=(True, "123456")):
                await control_cog.stop.callback(control_cog, interaction)
                
                # Verify session was retrieved
                mock_session_manager.get_session_interaction.assert_called_once()
                
                # Verify error response
                interaction.followup.send.assert_called_once_with("No active session", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_skip_command_active_session(self, control_cog, setup_interaction):
        """Test skip command with active session"""
        interaction = setup_interaction
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player:
            
            # Mock active session
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 1
            mock_session.state = MagicMock()  # Will be used for state comparison
            mock_session.settings.duration = 25
            mock_session.stats.seconds_completed = 1500
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_controller.resume = AsyncMock()
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            
            # Mock the validation method to return True
            with patch.object(control_cog, '_validate_and_setup_session', return_value=(True, "123456")):
                await control_cog.skip.callback(control_cog, interaction)
                
                # Verify session was retrieved
                mock_session_manager.get_session_interaction.assert_called_once()
                
                # Verify state transition was called
                mock_state_handler.transition.assert_called_once()
                
                # Verify session was resumed
                mock_controller.resume.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_countdown_command_valid_parameters(self, control_cog, setup_interaction):
        """Test countdown command with valid parameters"""
        interaction = setup_interaction
        
        with patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.countdown') as mock_countdown, \
             patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_messenger') as mock_messenger, \
             patch('cogs.control.vc_accessor') as mock_vc_accessor:
            
            # Mock countdown and session manager
            mock_countdown.handle_connection = AsyncMock()
            mock_countdown.start = AsyncMock()
            mock_session_manager.activate = AsyncMock()
            mock_messenger.send_countdown_msg = AsyncMock()
            
            # Mock session creation
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock session manager to ensure no active sessions
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = "test_session_id"
            
            await control_cog.countdown.callback(control_cog, interaction, duration=10)
            
            # Verify session was created
            mock_session_class.assert_called_once()
            
            # Verify countdown was started
            mock_countdown.start.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_classwork_command_valid_parameters(self, control_cog, setup_interaction):
        """Test classwork command with valid parameters"""
        interaction = setup_interaction
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.start_locks') as mock_start_locks:
            
            # Mock Settings validation
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            
            # Mock start_locks
            mock_lock = AsyncMock()
            mock_start_locks.__getitem__ = MagicMock(return_value=mock_lock)
            mock_start_locks.__setitem__ = MagicMock()
            mock_start_locks.__contains__ = MagicMock(return_value=True)
            
            # Mock session controller
            mock_controller.start_classwork = AsyncMock()
            
            # Mock session creation
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock the validation methods
            with patch.object(control_cog, '_validate_and_setup_session', new=AsyncMock(return_value=(True, "123456"))), \
                 patch.object(control_cog, '_validate_session_prerequisites', new=AsyncMock(return_value=True)):
                
                await control_cog.classwork.callback(control_cog, interaction, work_time=45, break_time=15)
                
                # Verify settings validation was called
                mock_settings.is_valid_interaction.assert_called_once()
                
                # Verify interaction was deferred
                interaction.response.defer.assert_called_once_with(ephemeral=True)
                
                # Verify session was created
                mock_session_class.assert_called_once()
                
                # Verify session controller was called
                mock_controller.start_classwork.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_validate_session_prerequisites_success(self, control_cog, setup_interaction):
        """Test _validate_session_prerequisites with valid conditions"""
        interaction = setup_interaction
        
        with patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.session_manager') as mock_session_manager:
            
            # Mock voice validation success
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Mock no existing session
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = "test_session_id"
            
            result = await control_cog._validate_session_prerequisites(interaction)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_session_prerequisites_voice_failure(self, control_cog, setup_interaction):
        """Test _validate_session_prerequisites with voice validation failure"""
        interaction = setup_interaction
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.u_msg') as mock_msg:
            
            # Mock no existing session
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = "test_session_id"
            
            # Remove user from voice channel to simulate voice failure
            interaction.user.voice = None
            mock_msg.VOICE_CHANNEL_REQUIRED_ERR = "Voice channel required"
            
            result = await control_cog._validate_session_prerequisites(interaction)
            
            assert result is False
            interaction.response.send_message.assert_called_once_with("Voice channel required", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_validate_session_prerequisites_existing_session(self, control_cog, setup_interaction):
        """Test _validate_session_prerequisites with existing session"""
        interaction = setup_interaction
        
        with patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.u_msg') as mock_msg:
            
            # Mock voice validation success
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Mock existing session
            mock_existing_session = MagicMock()
            mock_session_manager.session_id_from.return_value = "test_session_id"
            mock_session_manager.active_sessions = {"test_session_id": mock_existing_session}
            mock_msg.ACTIVE_SESSION_EXISTS_ERR = "Session already started"
            
            result = await control_cog._validate_session_prerequisites(interaction)
            
            assert result is False
            interaction.response.send_message.assert_called_once_with(mock_msg.ACTIVE_SESSION_EXISTS_ERR, ephemeral=True)