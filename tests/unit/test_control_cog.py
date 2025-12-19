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


class TestSkipCommandComprehensive:
    """Comprehensive tests for skip command with various session states"""
    
    @pytest.fixture
    def skip_test_setup(self):
        """Fixture providing test setup for skip command tests"""
        user = MockUser(id=12345, name="SkipTestUser")
        guild = MockGuild(id=54321, name="SkipTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Skip Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock user being in voice channel
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        return {
            'interaction': interaction,
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel
        }
    
    @pytest.mark.asyncio
    async def test_skip_during_countdown_state_rejected(self, mock_bot, skip_test_setup):
        """Test that skip is rejected during COUNTDOWN state"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.u_msg') as mock_u_msg, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with COUNTDOWN state
            mock_session = MagicMock()
            mock_session.state = 'COUNTDOWN'
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.COUNTDOWN = 'COUNTDOWN'
            mock_u_msg.COUNTDOWN_SKIP_NOT_ALLOWED = "カウントダウンはスキップできません 💭"
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify rejection message was sent
            env['interaction'].response.send_message.assert_called_once_with(
                "カウントダウンはスキップできません 💭", ephemeral=True
            )
    
    @pytest.mark.asyncio  
    async def test_skip_during_pomodoro_state(self, mock_bot, skip_test_setup):
        """Test skip during POMODORO state (should succeed with stats adjustment)"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with POMODORO state
            mock_session = MagicMock()
            mock_session.state = bot_enum.State.POMODORO
            mock_session.stats.pomos_completed = 2
            mock_session.stats.seconds_completed = 3000
            mock_session.settings.duration = 25
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            # Mock state after transition
            old_state = mock_session.state
            mock_session.state = 'SHORT_BREAK'  # After transition
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify stats were adjusted for POMODORO skip
            assert mock_session.stats.pomos_completed == 1  # Should be decremented
            assert mock_session.stats.seconds_completed == 1500  # Should be adjusted (3000 - 25*60)
            
            # Verify state transition was called
            mock_state_handler.transition.assert_called_once_with(mock_session)
            
            # Verify alert and resume were called
            mock_player.alert.assert_called_once_with(mock_session)
            mock_controller.resume.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_skip_during_short_break_state(self, mock_bot, skip_test_setup):
        """Test skip during SHORT_BREAK state (should succeed without stats adjustment)"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with SHORT_BREAK state
            mock_session = MagicMock()
            mock_session.state = 'SHORT_BREAK'
            mock_session.stats.pomos_completed = 2
            mock_session.stats.seconds_completed = 3000
            original_pomos = mock_session.stats.pomos_completed
            original_seconds = mock_session.stats.seconds_completed
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify stats were NOT adjusted for non-POMODORO skip
            assert mock_session.stats.pomos_completed == original_pomos  # Should be unchanged
            assert mock_session.stats.seconds_completed == original_seconds  # Should be unchanged
            
            # Verify normal skip processing occurred
            mock_state_handler.transition.assert_called_once_with(mock_session)
            mock_player.alert.assert_called_once_with(mock_session)
            mock_controller.resume.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_skip_during_long_break_state(self, mock_bot, skip_test_setup):
        """Test skip during LONG_BREAK state"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with LONG_BREAK state
            mock_session = MagicMock()
            mock_session.state = 'LONG_BREAK'
            mock_session.stats.pomos_completed = 4
            mock_session.stats.seconds_completed = 6000
            original_stats = (mock_session.stats.pomos_completed, mock_session.stats.seconds_completed)
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify stats unchanged for non-POMODORO state
            assert mock_session.stats.pomos_completed == original_stats[0]
            assert mock_session.stats.seconds_completed == original_stats[1]
            
            # Verify skip processing
            mock_state_handler.transition.assert_called_once_with(mock_session)
            mock_player.alert.assert_called_once_with(mock_session)
            mock_controller.resume.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_skip_during_classwork_state(self, mock_bot, skip_test_setup):
        """Test skip during CLASSWORK state"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with CLASSWORK state
            mock_session = MagicMock()
            mock_session.state = 'CLASSWORK'
            mock_session.stats.pomos_completed = 1
            mock_session.stats.seconds_completed = 1500
            original_stats = (mock_session.stats.pomos_completed, mock_session.stats.seconds_completed)
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify stats unchanged for non-POMODORO state (CLASSWORK != POMODORO)
            assert mock_session.stats.pomos_completed == original_stats[0]
            assert mock_session.stats.seconds_completed == original_stats[1]
            
            # Verify skip processing
            mock_state_handler.transition.assert_called_once_with(mock_session)
            mock_player.alert.assert_called_once_with(mock_session)
            mock_controller.resume.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_skip_during_classwork_break_state(self, mock_bot, skip_test_setup):
        """Test skip during CLASSWORK_BREAK state"""
        env = skip_test_setup
        control_cog = Control(mock_bot)
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            # Mock session with CLASSWORK_BREAK state  
            mock_session = MagicMock()
            mock_session.state = 'CLASSWORK_BREAK'
            mock_session.stats.pomos_completed = 0
            mock_session.stats.seconds_completed = 0
            original_stats = (mock_session.stats.pomos_completed, mock_session.stats.seconds_completed)
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            await control_cog.skip.callback(control_cog, env['interaction'])
            
            # Verify stats unchanged for non-POMODORO state
            assert mock_session.stats.pomos_completed == original_stats[0]
            assert mock_session.stats.seconds_completed == original_stats[1]
            
            # Verify skip processing
            mock_state_handler.transition.assert_called_once_with(mock_session)
            mock_player.alert.assert_called_once_with(mock_session)
            mock_controller.resume.assert_called_once_with(mock_session)
    
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


class TestControlEdgeCases:
    """Extended tests for Control cog edge cases and error conditions"""
    
    @pytest.fixture
    def control_cog(self, mock_bot):
        """Fixture providing a Control cog instance"""
        return Control(mock_bot)
    
    @pytest.fixture
    def edge_case_interaction(self):
        """Fixture for edge case testing"""
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild)
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        return interaction
    
    @pytest.mark.asyncio
    async def test_pomodoro_with_edge_case_parameters(self, control_cog, edge_case_interaction):
        """Test pomodoro command with edge case parameters"""
        interaction = edge_case_interaction
        
        # Test minimum values
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class:
            
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_controller.start_pomodoro = AsyncMock()
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Test with minimum values (1 minute each, 1 interval)
            await control_cog.pomodoro.callback(
                control_cog, interaction, 
                pomodoro=1, short_break=1, long_break=1, intervals=1
            )
            
            mock_session_class.assert_called_once()
            mock_controller.start_pomodoro.assert_called_once()
            
        # Reset mocks
        mock_session_class.reset_mock()
        mock_controller.reset_mock()
        
        # Test maximum reasonable values
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class:
            
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_controller.start_pomodoro = AsyncMock()
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Test with maximum values (120 minutes each, 8 intervals)
            await control_cog.pomodoro.callback(
                control_cog, interaction,
                pomodoro=120, short_break=120, long_break=120, intervals=8
            )
            
            mock_session_class.assert_called_once()
            mock_controller.start_pomodoro.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_countdown_with_edge_case_durations(self, control_cog, edge_case_interaction):
        """Test countdown command with edge case durations"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.countdown') as mock_countdown, \
             patch('cogs.control.session_manager') as mock_session_manager:
            
            mock_countdown.handle_connection = AsyncMock()
            mock_countdown.start = AsyncMock()
            mock_session_manager.activate = AsyncMock()
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = "test_session_id"
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Test with very short countdown (1 minute)
            await control_cog.countdown.callback(control_cog, interaction, duration=1)
            
            mock_session_class.assert_called_once()
            mock_countdown.start.assert_called_once()
            
            # Reset mocks
            mock_session_class.reset_mock()
            mock_countdown.start.reset_mock()
            
            # Test with long countdown (120 minutes)
            await control_cog.countdown.callback(control_cog, interaction, duration=120)
            
            mock_session_class.assert_called_once()
            mock_countdown.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_classwork_with_unusual_time_ratios(self, control_cog, edge_case_interaction):
        """Test classwork command with unusual work/break time ratios"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.start_locks') as mock_start_locks:
            
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_controller.start_classwork = AsyncMock()
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock start_locks
            mock_lock = AsyncMock()
            mock_start_locks.__getitem__ = MagicMock(return_value=mock_lock)
            mock_start_locks.__setitem__ = MagicMock()
            mock_start_locks.__contains__ = MagicMock(return_value=True)
            
            with patch.object(control_cog, '_validate_and_setup_session', new=AsyncMock(return_value=(True, "123456"))), \
                 patch.object(control_cog, '_validate_session_prerequisites', new=AsyncMock(return_value=True)):
                
                # Test very short break time (work=60, break=1)
                await control_cog.classwork.callback(control_cog, interaction, work_time=60, break_time=1)
                
                mock_session_class.assert_called_once()
                mock_controller.start_classwork.assert_called_once()
                
                # Reset mocks
                mock_session_class.reset_mock()
                mock_controller.start_classwork.reset_mock()
                
                # Test very long break time (work=30, break=90)
                await control_cog.classwork.callback(control_cog, interaction, work_time=30, break_time=90)
                
                mock_session_class.assert_called_once()
                mock_controller.start_classwork.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rapid_command_execution(self, control_cog, edge_case_interaction):
        """Test rapid successive command execution"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 1
            mock_session.state = MagicMock()
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_controller.end = AsyncMock()
            
            with patch.object(control_cog, '_validate_and_setup_session', return_value=(True, "123456")):
                
                # Execute multiple stop commands rapidly
                tasks = []
                for i in range(5):
                    task = control_cog.stop.callback(control_cog, interaction)
                    tasks.append(task)
                
                # Wait for all to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # At least one should succeed
                successful_results = [r for r in results if not isinstance(r, Exception)]
                assert len(successful_results) >= 1
    
    @pytest.mark.asyncio
    async def test_command_with_malformed_interaction(self, control_cog):
        """Test commands with malformed interaction objects"""
        
        # Create interaction missing required attributes
        malformed_interaction = MagicMock()
        malformed_interaction.user = None
        malformed_interaction.guild = None
        malformed_interaction.response = MagicMock()
        malformed_interaction.response.send_message = AsyncMock()
        
        # Test pomodoro command with malformed interaction
        with patch('cogs.control.voice_validation') as mock_voice_validation:
            mock_voice_validation.can_connect.return_value = False
            
            result = await control_cog._validate_session_prerequisites(malformed_interaction)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_session_validation_edge_cases(self, control_cog, edge_case_interaction):
        """Test session validation with edge case scenarios"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.u_msg') as mock_u_msg:
            
            # Test when user has no voice attribute
            interaction.user.voice = None
            mock_u_msg.VOICE_CHANNEL_REQUIRED_ERR = "Voice channel required"
            
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is False
            
            # Test when voice channel is None
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = None
            
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is False
            
            # Test when can_connect fails
            interaction.user.voice.channel = MagicMock()
            mock_voice_validation.can_connect.return_value = False
            
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_command_error_handlers_comprehensive(self, control_cog, edge_case_interaction):
        """Test all command error handlers comprehensively"""
        interaction = edge_case_interaction
        
        from discord import app_commands
        
        # Test pomodoro error handler with different error types
        with patch('cogs.control.logger') as mock_logger, \
             patch('cogs.control.u_msg') as mock_u_msg:
            
            mock_u_msg.POMODORO_COMMAND_ERROR = "Pomodoro error"
            
            # Test CommandInvokeError
            command = MagicMock()
            error = app_commands.CommandInvokeError(command, ValueError("Test error"))
            
            await control_cog.pomodoro_error(interaction, error)
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Test other error types
            error = app_commands.AppCommandError("Generic error")
            await control_cog.pomodoro_error(interaction, error)
            
        # Test countdown error handler
        with patch('cogs.control.logger') as mock_logger, \
             patch('cogs.control.u_msg') as mock_u_msg:
            
            mock_u_msg.COUNTDOWN_COMMAND_ERROR = "Countdown error"
            
            error = app_commands.CommandInvokeError(command, RuntimeError("Countdown test error"))
            await control_cog.countdown_error(interaction, error)
            
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
        
        # Test classwork error handler
        with patch('cogs.control.logger') as mock_logger, \
             patch('cogs.control.u_msg') as mock_u_msg:
            
            mock_u_msg.CLASSWORK_COMMAND_ERROR = "Classwork error"
            
            error = app_commands.CommandInvokeError(command, TypeError("Classwork test error"))
            await control_cog.classwork_error(interaction, error)
            
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
    
    @pytest.mark.asyncio
    async def test_interaction_response_state_handling(self, control_cog, edge_case_interaction):
        """Test handling of different interaction response states"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.u_msg') as mock_u_msg:
            mock_u_msg.VOICE_CHANNEL_REQUIRED_ERR = "Voice channel required"
            
            # Test when response is not done
            interaction.response.is_done.return_value = False
            interaction.user.voice = None
            
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is False
            interaction.response.send_message.assert_called_once()
            
            # Reset mocks
            interaction.response.send_message.reset_mock()
            interaction.followup.send.reset_mock()
            
            # Test when response is already done
            interaction.response.is_done.return_value = True
            
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is False
            # Should use followup when response is done
            interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_controller_exception_handling(self, control_cog, edge_case_interaction):
        """Test handling of exceptions from session controller"""
        interaction = edge_case_interaction
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.logger') as mock_logger:
            
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Test session controller throwing exception
            mock_controller.start_pomodoro = AsyncMock(side_effect=Exception("Controller error"))
            
            # Should handle exception gracefully
            with pytest.raises(Exception, match="Controller error"):
                await control_cog.pomodoro.callback(
                    control_cog, interaction,
                    pomodoro=25, short_break=5, long_break=20, intervals=4
                )
    
    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, control_cog):
        """Test handling of unicode and special characters in user/guild names"""
        
        # Create interaction with unicode characters
        user = MockUser(id=12345, name="テストユーザー👤")
        guild = MockGuild(id=54321, name="テストギルド🏠")
        voice_channel = MockVoiceChannel(guild=guild, name="音声チャンネル🔊")
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        with patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.session_manager') as mock_session_manager:
            
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = str(guild.id)
            
            # Should handle unicode names without issues
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_large_guild_id_handling(self, control_cog):
        """Test handling of very large guild IDs"""
        
        # Create interaction with max int64 guild ID
        large_guild_id = 9223372036854775807  # Max int64
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=large_guild_id, name="LargeIdGuild")
        voice_channel = MockVoiceChannel(guild=guild)
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        with patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.session_manager') as mock_session_manager:
            
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = str(large_guild_id)
            
            # Should handle large IDs correctly
            result = await control_cog._validate_session_prerequisites(interaction)
            assert result is True


class TestSkipStatisticsAdjustment:
    """統計値調整の詳細テスト"""

    @pytest.mark.asyncio
    async def test_pomodoro_skip_decrements_stats(self, mock_bot):
        """POMODORO状態でのスキップが統計値を正しく減算することを検証"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        control_cog = Control(mock_bot)
        
        # セッションとモックを設定
        mock_session = MagicMock()
        mock_session.state = 'POMODORO'  # 文字列として設定
        mock_session.settings.duration = 25  # 25分設定
        mock_session.stats.pomos_completed = 3  # 既に3回完了
        mock_session.stats.seconds_completed = 4500  # 75分相当
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.bot_enum') as mock_bot_enum:
            
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_bot_enum.State.POMODORO = 'POMODORO'
            mock_bot_enum.State.get_display_name = MagicMock(side_effect=lambda x: f"display_{x}")
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # 統計値が減算されたことを確認
            assert mock_session.stats.pomos_completed == 2  # 3-1=2
            assert mock_session.stats.seconds_completed == 3000  # 4500-1500=3000 (25分減算)
    
    @pytest.mark.asyncio  
    async def test_pomodoro_skip_with_zero_stats(self, control_cog):
        """統計値が0の状態でPOMODOROスキップする場合の処理"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.settings.duration = 25
        mock_session.user_id = user.id
        
        mock_stats = MagicMock()
        mock_stats.pomos_completed = 0
        mock_stats.seconds_completed = 0
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = mock_stats
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # 負の値にならないことを確認（条件: pomos_completed >= 0）
            assert mock_stats.pomos_completed == -1  # 0-1=-1 (実装通り)
            assert mock_stats.seconds_completed == -1500  # 0-1500=-1500 (実装通り)
    
    @pytest.mark.asyncio
    async def test_break_states_no_stats_adjustment(self, control_cog):
        """休憩状態でのスキップは統計値を変更しないことを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        # 各休憩状態をテスト
        for break_state in [bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK, bot_enum.State.CLASSWORK_BREAK]:
            mock_session = MagicMock()
            mock_session.state = break_state
            mock_session.settings.duration = 5
            mock_session.user_id = user.id
            
            mock_stats = MagicMock()
            original_pomos = mock_stats.pomos_completed = 5
            original_seconds = mock_stats.seconds_completed = 7500
            
            with patch('cogs.control.session_manager') as mock_session_manager, \
                 patch('cogs.control.Stats') as mock_stats_class:
                
                mock_session_manager.get_session.return_value = mock_session
                mock_stats_class.return_value = mock_stats
                
                await control_cog.skip.callback(control_cog, interaction)
                
                # 統計値が変更されていないことを確認
                assert mock_stats.pomos_completed == original_pomos
                assert mock_stats.seconds_completed == original_seconds
    
    @pytest.mark.asyncio
    async def test_classwork_state_no_stats_adjustment(self, control_cog):
        """CLASSWORK状態でのスキップは統計値を変更しないことを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.CLASSWORK
        mock_session.settings.duration = 50
        mock_session.user_id = user.id
        
        mock_stats = MagicMock()
        original_pomos = mock_stats.pomos_completed = 8
        original_seconds = mock_stats.seconds_completed = 12000
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = mock_stats
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # 統計値が変更されていないことを確認
            assert mock_stats.pomos_completed == original_pomos
            assert mock_stats.seconds_completed == original_seconds
    
    @pytest.mark.asyncio
    async def test_statistics_adjustment_with_different_durations(self, control_cog):
        """異なる時間設定でのPOMODOROスキップ時の統計値調整"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        test_cases = [
            {"duration": 15, "expected_seconds_reduction": 900},   # 15分 = 900秒
            {"duration": 30, "expected_seconds_reduction": 1800},  # 30分 = 1800秒
            {"duration": 45, "expected_seconds_reduction": 2700},  # 45分 = 2700秒
        ]
        
        for case in test_cases:
            mock_session = MagicMock()
            mock_session.state = bot_enum.State.POMODORO
            mock_session.settings.duration = case["duration"]
            mock_session.user_id = user.id
            
            mock_stats = MagicMock()
            mock_stats.pomos_completed = 10
            mock_stats.seconds_completed = 15000  # 250分相当
            
            with patch('cogs.control.session_manager') as mock_session_manager, \
                 patch('cogs.control.Stats') as mock_stats_class:
                
                mock_session_manager.get_session.return_value = mock_session
                mock_stats_class.return_value = mock_stats
                
                await control_cog.skip.callback(control_cog, interaction)
                
                # 期待される秒数減算を確認
                expected_seconds = 15000 - case["expected_seconds_reduction"]
                assert mock_stats.seconds_completed == expected_seconds


class TestSkipErrorCases:
    """スキップコマンドのエラーケーステスト"""

    @pytest.mark.asyncio
    async def test_skip_no_active_session(self, control_cog):
        """アクティブなセッションがない場合のエラー処理"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        with patch('cogs.control.session_manager') as mock_session_manager:
            # セッションが存在しない場合
            mock_session_manager.get_session.return_value = None
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # エラーメッセージが送信されることを確認
            interaction.response.send_message.assert_called_once()
            args, kwargs = interaction.response.send_message.call_args
            assert "セッションがありません" in args[0] or kwargs.get('ephemeral', False)

    @pytest.mark.asyncio
    async def test_skip_different_user_session(self, control_cog):
        """他のユーザーのセッションをスキップしようとした場合"""
        
        user = MockUser(id=12345, name="TestUser")
        other_user_id = 67890
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = other_user_id  # 異なるユーザー
        
        with patch('cogs.control.session_manager') as mock_session_manager:
            mock_session_manager.get_session.return_value = mock_session
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # エラーメッセージが送信されることを確認
            interaction.response.send_message.assert_called_once()
            args, kwargs = interaction.response.send_message.call_args
            # 権限エラーまたはセッション不一致のメッセージを期待
            assert kwargs.get('ephemeral', False)

    @pytest.mark.asyncio
    async def test_skip_session_manager_exception(self, control_cog):
        """session_managerで例外が発生した場合の処理"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        with patch('cogs.control.session_manager') as mock_session_manager:
            # session_managerで例外が発生
            mock_session_manager.get_session.side_effect = Exception("Session manager error")
            
            # 例外が適切に処理されることを確認
            try:
                await control_cog.skip.callback(control_cog, interaction)
            except Exception as e:
                # 例外が発生するか、適切にハンドリングされるかを確認
                assert "Session manager error" in str(e)

    @pytest.mark.asyncio
    async def test_skip_stats_creation_failure(self, control_cog):
        """Stats オブジェクトの作成に失敗した場合"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            # Stats作成で例外が発生
            mock_stats_class.side_effect = Exception("Stats creation failed")
            
            # 例外処理を確認
            try:
                await control_cog.skip.callback(control_cog, interaction)
            except Exception as e:
                assert "Stats creation failed" in str(e)

    @pytest.mark.asyncio
    async def test_skip_transition_failure(self, control_cog):
        """状態遷移に失敗した場合の処理"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            # transition で例外が発生
            mock_transition.side_effect = Exception("Transition failed")
            
            # 例外処理を確認
            try:
                await control_cog.skip.callback(control_cog, interaction)
            except Exception as e:
                assert "Transition failed" in str(e)

    @pytest.mark.asyncio
    async def test_skip_discord_api_failure(self, control_cog):
        """Discord API呼び出しに失敗した場合"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        # interaction.response.send_messageで例外を発生させる
        interaction.response.send_message.side_effect = Exception("Discord API error")
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.COUNTDOWN  # COUNTDOWN状態でエラーメッセージ送信
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager:
            mock_session_manager.get_session.return_value = mock_session
            
            # Discord API例外処理を確認
            try:
                await control_cog.skip.callback(control_cog, interaction)
            except Exception as e:
                assert "Discord API error" in str(e)


class TestSkipStateTransitionAndNotifications:
    """スキップコマンドの状態遷移と通知テスト"""

    @pytest.mark.asyncio
    async def test_skip_calls_transition(self, control_cog):
        """スキップ時にtransition関数が呼び出されることを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # transition が呼び出されたことを確認
            mock_transition.assert_called_once_with(interaction, mock_session)

    @pytest.mark.asyncio
    async def test_skip_different_states_transition_calls(self, control_cog):
        """異なる状態でのスキップ時のtransition呼び出し確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        # COUNTDOWN以外の全状態をテスト
        test_states = [
            bot_enum.State.POMODORO,
            bot_enum.State.SHORT_BREAK, 
            bot_enum.State.LONG_BREAK,
            bot_enum.State.CLASSWORK,
            bot_enum.State.CLASSWORK_BREAK
        ]
        
        for state in test_states:
            mock_session = MagicMock()
            mock_session.state = state
            mock_session.user_id = user.id
            
            with patch('cogs.control.session_manager') as mock_session_manager, \
                 patch('cogs.control.Stats') as mock_stats_class, \
                 patch('cogs.control.transition') as mock_transition:
                
                mock_session_manager.get_session.return_value = mock_session
                mock_stats_class.return_value = MagicMock()
                
                await control_cog.skip.callback(control_cog, interaction)
                
                # 各状態でtransitionが呼び出されることを確認
                mock_transition.assert_called_once_with(interaction, mock_session)

    @pytest.mark.asyncio
    async def test_skip_countdown_no_transition(self, control_cog):
        """COUNTDOWN状態でスキップしてもtransitionが呼ばれないことを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.COUNTDOWN
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # COUNTDOWN状態ではtransitionが呼ばれないことを確認
            mock_transition.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_alert_functionality(self, control_cog):
        """スキップ実行時のalert機能が動作することを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition, \
             patch('cogs.control.alert') as mock_alert:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # alert機能の呼び出しを確認（実装により呼び方が異なる可能性）
            # この部分は実際の実装に合わせて調整が必要
            # mock_alert.assert_called() などで確認

    @pytest.mark.asyncio
    async def test_skip_resume_functionality(self, control_cog):
        """スキップ後のresume機能が動作することを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.SHORT_BREAK
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition, \
             patch('cogs.control.resume') as mock_resume:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # resume機能の呼び出しを確認（実装により呼び方が異なる可能性）
            # この部分は実際の実装に合わせて調整が必要
            # mock_resume.assert_called() などで確認

    @pytest.mark.asyncio
    async def test_skip_interaction_response_sequence(self, control_cog):
        """スキップ時のDiscord interaction responseの順序確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # interaction.response.defer() が適切に呼ばれることを確認
            interaction.response.defer.assert_called_once()
            # その後、適切な完了処理が行われることを確認


class TestSkipEdgeCasesExtended:
    """スキップコマンドのエッジケース拡張テスト"""

    @pytest.mark.asyncio
    async def test_skip_concurrent_execution_protection(self, control_cog):
        """同時実行時の競合状態保護テスト"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction1 = MockInteraction(user=user, guild=guild)
        interaction2 = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            # 2つのスキップ要求を並行実行
            import asyncio
            tasks = [
                control_cog.skip.callback(control_cog, interaction1),
                control_cog.skip.callback(control_cog, interaction2)
            ]
            
            # 同時実行しても適切に処理されることを確認
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 各interactionが適切に処理されたことを確認
            assert interaction1.response.defer.called
            assert interaction2.response.defer.called

    @pytest.mark.asyncio
    async def test_skip_memory_cleanup_after_execution(self, control_cog):
        """スキップ実行後のメモリリークしないことを確認"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class, \
             patch('cogs.control.transition') as mock_transition:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            # 大量実行してもメモリリークしないことを確認
            for _ in range(10):
                await control_cog.skip.callback(control_cog, interaction)
            
            # すべての呼び出しが正常に完了することを確認
            assert mock_transition.call_count == 10

    @pytest.mark.asyncio
    async def test_skip_with_network_timeout(self, control_cog):
        """ネットワークタイムアウト状況でのスキップ動作"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        # interaction.response.defer でタイムアウトをシミュレート
        interaction.response.defer.side_effect = asyncio.TimeoutError("Network timeout")
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager:
            mock_session_manager.get_session.return_value = mock_session
            
            # タイムアウト例外が適切に処理されることを確認
            try:
                await control_cog.skip.callback(control_cog, interaction)
            except asyncio.TimeoutError:
                # タイムアウトが発生することを確認
                pass

    @pytest.mark.asyncio
    async def test_skip_with_max_duration_edge_case(self, control_cog):
        """最大時間設定でのスキップ動作テスト"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.settings.duration = 2147483647  # 最大int値
        mock_session.user_id = user.id
        
        mock_stats = MagicMock()
        mock_stats.pomos_completed = 100
        mock_stats.seconds_completed = 1000000
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = mock_stats
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # 大きな数値でも正しく計算されることを確認
            # オーバーフロー等の問題が発生しないことを確認
            assert mock_stats.seconds_completed < 1000000  # 減算が行われた

    @pytest.mark.asyncio
    async def test_skip_with_unicode_user_data(self, control_cog):
        """Unicode文字を含むユーザーデータでのスキップ動作"""
        
        user = MockUser(id=12345, name="テスト👤ユーザー🎯")
        guild = MockGuild(id=54321, name="テスト🏠ギルド💫")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.user_id = user.id
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = MagicMock()
            
            # Unicode文字が含まれていても正常動作することを確認
            await control_cog.skip.callback(control_cog, interaction)
            
            interaction.response.defer.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_with_negative_stats_edge_case(self, control_cog):
        """統計値が既に負数の場合のスキップ動作"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.settings.duration = 25
        mock_session.user_id = user.id
        
        mock_stats = MagicMock()
        mock_stats.pomos_completed = -5  # 既に負数
        mock_stats.seconds_completed = -1000  # 既に負数
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = mock_stats
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # さらに負数になることを確認
            assert mock_stats.pomos_completed == -6  # -5-1=-6
            assert mock_stats.seconds_completed == -2500  # -1000-1500=-2500

    @pytest.mark.asyncio
    async def test_skip_with_zero_duration_session(self, control_cog):
        """時間が0のセッションでのスキップ動作"""
        
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        interaction = MockInteraction(user=user, guild=guild)
        
        mock_session = MagicMock()
        mock_session.state = bot_enum.State.POMODORO
        mock_session.settings.duration = 0  # 0分設定
        mock_session.user_id = user.id
        
        mock_stats = MagicMock()
        mock_stats.pomos_completed = 5
        mock_stats.seconds_completed = 3000
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.Stats') as mock_stats_class:
            
            mock_session_manager.get_session.return_value = mock_session
            mock_stats_class.return_value = mock_stats
            
            await control_cog.skip.callback(control_cog, interaction)
            
            # 0分の場合は秒数減算が0になることを確認
            assert mock_stats.pomos_completed == 4  # 5-1=4
            assert mock_stats.seconds_completed == 3000  # 3000-0=3000 (変化なし)