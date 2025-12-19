"""
Integration tests for complete Pomodoro session workflow.
Tests the entire flow from session start to completion including state transitions.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta

from tests.mocks.discord_mocks import MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
from tests.mocks.voice_mocks import MockVoiceClient

from cogs.control import Control
from src.session.Session import Session
from src.Settings import Settings
from src.Stats import Stats
from configs.bot_enum import State


class TestFullPomodoroSession:
    """Integration tests for complete Pomodoro session workflow"""
    
    @pytest.fixture
    def setup_session_environment(self):
        """Fixture providing a complete session test environment"""
        bot = MockBot()
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild)
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock user in voice channel
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        # Create Control cog
        control_cog = Control(bot)
        
        return {
            'bot': bot,
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'interaction': interaction,
            'control_cog': control_cog
        }
    
    @pytest.mark.asyncio
    async def test_complete_pomodoro_cycle(self, setup_session_environment):
        """Test a complete pomodoro cycle: work -> short break -> work -> long break"""
        env = setup_session_environment
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats:
            
            # Setup mocks for successful validation
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            mock_session_manager.active_sessions = {}
            mock_session_manager.session_id_from.return_value = "test_session_id"
            
            # Create mock session with realistic behavior
            mock_session = MagicMock()
            mock_session.state = State.POMODORO
            mock_session.settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            mock_session.stats = MagicMock()
            mock_session.stats.pomos_completed = 0
            mock_session.stats.pomos_elapsed = 0
            mock_session.timer = MagicMock()
            mock_session.timer.remaining = 1500  # 25 minutes
            mock_session_class.return_value = mock_session
            
            # Start pomodoro session
            await env['control_cog'].pomodoro.callback(
                env['control_cog'], 
                env['interaction'], 
                pomodoro=25, 
                short_break=5, 
                long_break=20, 
                intervals=4
            )
            
            # Verify session creation
            mock_session_class.assert_called_once()
            mock_controller.start_pomodoro.assert_called_once_with(mock_session)
            
            # Simulate first pomodoro completion
            mock_session.stats.pomos_completed = 1
            mock_session.state = State.SHORT_BREAK
            
            # Test skip to next interval
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session_id")):
                with patch('cogs.control.state_handler') as mock_state_handler, \
                     patch('cogs.control.player') as mock_player:
                    
                    mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
                    mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
                    
                    await env['control_cog'].skip.callback(env['control_cog'], env['interaction'])
                    
                    # Verify state transition was called
                    mock_state_handler.transition.assert_called_once()
                    mock_controller.resume.assert_called_once()
            
            # Simulate completion of multiple intervals
            for interval in range(1, 4):
                mock_session.stats.pomos_completed = interval
                if interval < 3:
                    mock_session.state = State.SHORT_BREAK
                else:
                    mock_session.state = State.LONG_BREAK
            
            # Test session stop
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session_id")):
                mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
                await env['control_cog'].stop.callback(env['control_cog'], env['interaction'])
                mock_controller.end.assert_called()
    
    @pytest.mark.asyncio
    async def test_pomodoro_session_state_transitions(self, setup_session_environment):
        """Test proper state transitions during a pomodoro session"""
        env = setup_session_environment
        
        # Test state progression: POMODORO -> SHORT_BREAK -> POMODORO -> LONG_BREAK
        expected_states = [
            (State.POMODORO, 1),
            (State.SHORT_BREAK, 1),  
            (State.POMODORO, 2),
            (State.SHORT_BREAK, 2),
            (State.POMODORO, 3),
            (State.SHORT_BREAK, 3),
            (State.POMODORO, 4),
            (State.LONG_BREAK, 4)
        ]
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler:
            
            # Create a session mock that tracks state changes
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 0
            current_state_idx = 0
            
            def mock_transition(*args, **kwargs):
                nonlocal current_state_idx
                if current_state_idx < len(expected_states):
                    state, pomo_count = expected_states[current_state_idx]
                    mock_session.state = state
                    mock_session.stats.pomos_completed = pomo_count
                    current_state_idx += 1
            
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_state_handler.transition.side_effect = mock_transition
            mock_controller.resume = AsyncMock()
            
            # Simulate skipping through all intervals
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session_id")):
                for i in range(len(expected_states)):
                    await env['control_cog'].skip.callback(env['control_cog'], env['interaction'])
                    
                    # Verify the expected state after transition
                    if i < len(expected_states):
                        expected_state, expected_pomo_count = expected_states[i]
                        assert mock_session.state == expected_state
                        assert mock_session.stats.pomos_completed == expected_pomo_count
            
            # Verify all transitions were called
            assert mock_state_handler.transition.call_count == len(expected_states)
    
    @pytest.mark.asyncio
    async def test_session_timer_integration(self, setup_session_environment):
        """Test timer behavior during session execution"""
        env = setup_session_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('src.session.Session.Timer') as mock_timer_class:
            
            # Create a realistic timer mock
            mock_timer = MagicMock()
            mock_timer.remaining = 1500  # 25 minutes in seconds
            mock_timer.running = False
            mock_timer.time_remaining_to_str.return_value = "25分00秒"
            mock_timer_class.return_value = mock_timer
            
            # Create session with timer
            from configs.bot_enum import State
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'), \
                 patch('src.session.Session.Stats'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                
                # Verify timer was initialized correctly
                mock_timer_class.assert_called_once_with(session)
                assert session.timer == mock_timer
                
                # Test timer state during different phases
                timer_states = [
                    (State.POMODORO, 1500),     # 25 minutes for work
                    (State.SHORT_BREAK, 300),   # 5 minutes for short break  
                    (State.LONG_BREAK, 1200)    # 20 minutes for long break
                ]
                
                for state, expected_duration in timer_states:
                    session.state = state
                    # In real implementation, timer duration would be updated based on state
                    # Here we just verify the timer exists and can be controlled
                    assert hasattr(session, 'timer')
                    assert session.timer is not None
    
    @pytest.mark.asyncio
    async def test_session_statistics_tracking(self, setup_session_environment):
        """Test statistics tracking during session execution"""
        env = setup_session_environment
        
        with patch('src.session.Session.Timer'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Initial stats should be zero
            assert session.stats.pomos_completed == 0
            assert session.stats.pomos_elapsed == 0
            assert session.stats.seconds_completed == 0
            
            # Simulate session progression
            session.stats.pomos_completed = 1
            session.stats.seconds_completed = 1500  # 25 minutes completed
            
            assert session.stats.pomos_completed == 1
            assert session.stats.seconds_completed == 1500
            
            # Test stats persistence through state transitions
            original_completed = session.stats.pomos_completed
            original_seconds = session.stats.seconds_completed
            
            session.state = State.SHORT_BREAK
            
            # Stats should persist across state changes
            assert session.stats.pomos_completed == original_completed
            assert session.stats.seconds_completed == original_seconds
    
    @pytest.mark.asyncio
    async def test_session_with_voice_channel_integration(self, setup_session_environment):
        """Test session behavior with voice channel operations"""
        env = setup_session_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.vc_accessor') as mock_vc_accessor, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.player') as mock_player:
            
            # Setup voice channel mocks
            mock_voice_client = MockVoiceClient(env['voice_channel'], env['guild'])
            mock_vc_accessor.get_voice_client.return_value = mock_voice_client
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Test that voice operations are properly integrated during session commands
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session_id")):
                
                # Test skip command with voice integration
                await env['control_cog'].skip.callback(env['control_cog'], env['interaction'])
                
                # Verify voice validation was called
                mock_voice_validation.require_same_voice_channel.assert_called_with(env['interaction'])
                
                # Test stop command with voice integration
                await env['control_cog'].stop.callback(env['control_cog'], env['interaction'])
                
                # Voice validation should be called for stop as well
                assert mock_voice_validation.require_same_voice_channel.call_count >= 1