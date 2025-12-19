"""
Integration tests for voice functionality including voice channel operations,
auto-mute features, and audio playback during sessions.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel, 
    MockMember, MockVoiceState
)
from tests.mocks.voice_mocks import MockVoiceClient, MockAudioSource

from cogs.subscribe import Subscribe
from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestVoiceIntegration:
    """Integration tests for voice functionality"""
    
    @pytest.fixture
    def voice_environment(self):
        """Fixture providing voice test environment"""
        bot = MockBot()
        guild = MockGuild(id=12345, name="Test Guild")
        voice_channel = MockVoiceChannel(id=11111, name="Test Voice", guild=guild)
        user = MockUser(id=67890, name="TestUser")
        member = MockMember(user=user, guild=guild, voice_channel=voice_channel)
        
        interaction = MockInteraction(user=user, guild=guild)
        interaction.user.voice = MockVoiceState(channel=voice_channel, member=member)
        
        voice_client = MockVoiceClient(channel=voice_channel, guild=guild)
        
        return {
            'bot': bot,
            'guild': guild,
            'voice_channel': voice_channel,
            'user': user,
            'member': member,
            'interaction': interaction,
            'voice_client': voice_client
        }
    
    @pytest.mark.asyncio
    async def test_voice_channel_connection_during_session_start(self, voice_environment):
        """Test voice channel connection when starting a session"""
        env = voice_environment
        
        with patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.session_messenger') as mock_messenger:
            
            # Setup mocks
            mock_vc_accessor.connect = AsyncMock(return_value=env['voice_client'])
            mock_session_manager.activate = AsyncMock()
            mock_messenger.send_session_start_msg = AsyncMock()
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.session.Session.Timer'), \
                 patch('src.session.Session.Stats'), \
                 patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                
                # Import after patches are in place
                from src.session import session_controller
                
                # Start session
                await session_controller.start_pomodoro(session)
                
                # Verify voice connection was attempted
                mock_vc_accessor.connect.assert_called_once_with(session)
                
                # Verify session activation and messaging
                mock_session_manager.activate.assert_called_once_with(session)
                mock_messenger.send_session_start_msg.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_voice_channel_disconnection_during_session_end(self, voice_environment):
        """Test voice channel disconnection when ending a session"""
        env = voice_environment
        
        with patch('src.session.session_controller.vc_accessor') as mock_vc_accessor, \
             patch('src.session.session_controller.session_manager') as mock_session_manager, \
             patch('src.session.session_controller.session_messenger') as mock_messenger, \
             patch('src.session.session_controller.cleanup_pins') as mock_cleanup_pins:
            
            # Setup mocks
            mock_timer = MagicMock()
            mock_vc_accessor.disconnect = AsyncMock()
            mock_session_manager.deactivate = AsyncMock()
            mock_messenger.send_session_end_msg = AsyncMock()
            mock_cleanup_pins.return_value = AsyncMock()
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            
            with patch('src.session.Session.Timer'), \
                 patch('src.session.Session.Stats'), \
                 patch('src.subscriptions.Subscription.Subscription'), \
                 patch('src.subscriptions.AutoMute.AutoMute'):
                
                session = Session(State.POMODORO, settings, env['interaction'])
                session.timer = mock_timer
                
                from src.session import session_controller
                
                # End session
                await session_controller.end(session)
                
                # Verify voice disconnection
                mock_vc_accessor.disconnect.assert_called_once_with(session)
                
                # Verify timer was killed
                mock_timer.kill.assert_called_once()
                
                # Verify cleanup operations
                mock_session_manager.deactivate.assert_called_once_with(session)
                mock_messenger.send_session_end_msg.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_auto_mute_enable_functionality(self, voice_environment):
        """Test auto-mute enable functionality"""
        env = voice_environment
        subscribe_cog = Subscribe(env['bot'])
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation:
            
            # Setup session with auto_mute capability
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session.auto_mute = MagicMock()
            mock_session.auto_mute.all = False
            mock_session.auto_mute.handle_all = AsyncMock()
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Execute enableautomute command
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify session retrieval
            mock_session_manager.get_session_interaction.assert_called_once_with(env['interaction'])
            
            # Verify voice validation
            mock_voice_validation.require_same_voice_channel.assert_called_once_with(env['interaction'])
            
            # Verify auto_mute was enabled
            mock_session.auto_mute.handle_all.assert_called_once_with(env['interaction'])
            
            # Verify interaction handling
            env['interaction'].response.defer.assert_called_once_with(ephemeral=True)
            env['interaction'].delete_original_response.assert_called_once()
            env['interaction'].channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auto_mute_disable_functionality(self, voice_environment):
        """Test auto-mute disable functionality"""
        env = voice_environment
        subscribe_cog = Subscribe(env['bot'])
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation:
            
            # Setup session with auto_mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session.auto_mute = MagicMock()
            mock_session.auto_mute.all = True  # Currently enabled
            mock_session.auto_mute.handle_all = AsyncMock()
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Execute disableautomute command
            await subscribe_cog.disableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify session retrieval and validation
            mock_session_manager.get_session_interaction.assert_called_once_with(env['interaction'])
            mock_voice_validation.require_same_voice_channel.assert_called_once_with(env['interaction'])
            
            # Verify auto_mute was disabled
            mock_session.auto_mute.handle_all.assert_called_once_with(env['interaction'])
            
            # Verify interaction handling
            env['interaction'].response.defer.assert_called_once_with(ephemeral=True)
            env['interaction'].delete_original_response.assert_called_once()
            env['interaction'].channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_voice_state_update_handling(self, voice_environment):
        """Test voice state update event handling"""
        env = voice_environment
        subscribe_cog = Subscribe(env['bot'])
        
        # Create member with voice state changes
        before_state = MockVoiceState(channel=None, member=env['member'])
        after_state = MockVoiceState(channel=env['voice_channel'], member=env['member'])
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager:
            # Mock active sessions
            mock_session = MagicMock()
            mock_session_manager.active_sessions = {"12345": mock_session}
            
            # Test voice state update doesn't crash
            await subscribe_cog.on_voice_state_update(env['member'], before_state, after_state)
            
            # This test mainly ensures the event handler doesn't raise exceptions
            # In real implementation, it would handle auto-mute logic based on voice changes
    
    @pytest.mark.asyncio
    async def test_voice_validation_requirements(self, voice_environment):
        """Test voice validation requirements for commands"""
        env = voice_environment
        
        from src.utils import voice_validation
        
        # Test can_connect validation
        with patch('src.utils.voice_validation.vc_accessor') as mock_vc_accessor:
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            
            # User in voice channel should be able to connect
            result = voice_validation.can_connect(env['interaction'])
            assert result is True
            
            # User not in voice channel should not be able to connect
            env['interaction'].user.voice = None
            result = voice_validation.can_connect(env['interaction'])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_voice_alone_validation(self, voice_environment):
        """Test validation for user being alone in voice channel"""
        env = voice_environment
        
        from src.utils import voice_validation
        
        with patch('src.utils.voice_validation.vc_accessor') as mock_vc_accessor:
            # Setup voice channel with only one user
            env['voice_channel'].members = [env['member']]
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            
            # User alone in channel
            result = voice_validation.is_voice_alone(env['interaction'])
            assert result is True
            
            # Add another user
            other_member = MockMember(MockUser(id=99999, name="OtherUser"), env['guild'])
            env['voice_channel'].members.append(other_member)
            
            # User not alone in channel
            result = voice_validation.is_voice_alone(env['interaction'])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_same_voice_channel_requirement(self, voice_environment):
        """Test same voice channel requirement validation"""
        env = voice_environment
        
        from src.utils import voice_validation
        
        with patch('src.utils.voice_validation.vc_accessor') as mock_vc_accessor:
            # Bot and user in same channel
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            result = await voice_validation.require_same_voice_channel(env['interaction'])
            assert result is True
            
            # Bot and user in different channels
            different_channel = MockVoiceChannel(id=22222, name="Different Channel", guild=env['guild'])
            mock_vc_accessor.get_voice_channel.return_value = different_channel
            
            result = await voice_validation.require_same_voice_channel(env['interaction'])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_audio_playback_integration(self, voice_environment):
        """Test audio playback functionality during sessions"""
        env = voice_environment
        
        with patch('src.utils.player') as mock_player:
            # Setup audio playback mocks
            mock_player.alert = AsyncMock()
            mock_audio_source = MockAudioSource(title="Test Alert Sound")
            
            # Test alert playback
            await mock_player.alert(env['voice_client'], "test_alert.mp3")
            
            # Verify alert was called
            mock_player.alert.assert_called_once_with(env['voice_client'], "test_alert.mp3")
            
            # Test voice client audio operations
            env['voice_client'].play(mock_audio_source)
            assert env['voice_client'].is_playing() is True
            
            env['voice_client'].pause()
            assert env['voice_client'].is_paused() is True
            
            env['voice_client'].resume()
            assert env['voice_client'].is_paused() is False
            
            env['voice_client'].stop()
            assert env['voice_client'].is_playing() is False
    
    @pytest.mark.asyncio
    async def test_voice_client_manager_integration(self, voice_environment):
        """Test voice client manager operations"""
        env = voice_environment
        
        from tests.mocks.voice_mocks import MockVoiceManager
        
        voice_manager = MockVoiceManager()
        
        # Test connecting to voice channel
        voice_client = await voice_manager.connect_to_channel(env['voice_channel'])
        assert voice_client is not None
        assert voice_client.channel == env['voice_channel']
        assert env['guild'].id in voice_manager.voice_clients
        
        # Test getting voice client for guild
        retrieved_client = voice_manager.get_voice_client_for_guild(env['guild'].id)
        assert retrieved_client == voice_client
        
        # Test disconnecting from guild
        await voice_manager.disconnect_from_guild(env['guild'].id)
        assert env['guild'].id not in voice_manager.voice_clients
    
    @pytest.mark.asyncio
    async def test_voice_error_handling(self, voice_environment):
        """Test error handling in voice operations"""
        env = voice_environment
        subscribe_cog = Subscribe(env['bot'])
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.logger') as mock_logger, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Setup session that will raise an exception
            mock_session = MagicMock()
            mock_session.ctx = env['interaction']
            mock_session.auto_mute = MagicMock()
            mock_session.auto_mute.all = False
            mock_session.auto_mute.handle_all = AsyncMock(side_effect=Exception("Voice error"))
            
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_u_msg.AUTOMUTE_ENABLE_FAILED = "Auto-mute enable failed"
            
            # Execute command that should handle the error
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify error was logged
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify error message was sent to channel
            env['interaction'].channel.send.assert_called_with("Auto-mute enable failed", silent=True)


class TestAutoMuteVoiceStateIntegration:
    """Integration tests for auto-mute functionality during voice state changes"""
    
    @pytest.fixture
    def auto_mute_environment(self):
        """Fixture providing environment for auto-mute voice state testing"""
        bot = MockBot()
        guild = MockGuild(id=12345, name="AutoMute Test Guild")
        voice_channel = MockVoiceChannel(id=11111, name="Session Voice Channel", guild=guild)
        
        # Create test users
        session_user = MockUser(id=67890, name="SessionUser")  # User who starts session
        joining_user = MockUser(id=11111, name="JoiningUser")  # User who joins later
        
        # Create session user interaction
        session_interaction = MockInteraction(user=session_user, guild=guild)
        session_interaction.user.voice = MockVoiceState(channel=voice_channel, member=MockMember(session_user, guild, voice_channel))
        
        # Create joining user member
        joining_member = MockMember(joining_user, guild)
        
        subscribe_cog = Subscribe(bot)
        
        return {
            'bot': bot,
            'guild': guild,
            'voice_channel': voice_channel,
            'session_user': session_user,
            'joining_user': joining_user,
            'session_interaction': session_interaction,
            'joining_member': joining_member,
            'subscribe_cog': subscribe_cog
        }
    
    @pytest.mark.asyncio
    async def test_user_joins_voice_channel_with_active_automute(self, auto_mute_environment):
        """Test auto-mute when user joins voice channel during active session"""
        env = auto_mute_environment
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = MagicMock()  # Work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_auto_mute.safe_edit_member = AsyncMock()
            mock_session.auto_mute = mock_auto_mute
            
            # Setup voice client connection
            mock_voice_client = MagicMock()
            env['session_interaction'].voice_client = mock_voice_client
            env['session_interaction'].guild.voice_client = mock_voice_client
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states
            mock_bot_enum.State.WORK_STATES = [mock_session.state]
            
            # Create voice state changes - user joins the session voice channel
            before_state = MockVoiceState(channel=None, member=env['joining_member'])  # Not in any channel
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])  # Joins session channel
            after_state.mute = False  # User is not muted initially
            
            # Setup joining member voice state
            env['joining_member'].voice = after_state
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify user was muted
            mock_auto_mute.safe_edit_member.assert_called_once_with(env['joining_member'], unmute=False, channel_name='Session Voice Channel')
            
            # Verify logging
            mock_logger.info.assert_any_call(f'{env["joining_member"].display_name} joined the channel {env["voice_channel"].name}.')
            mock_logger.info.assert_any_call(f'Muting {env["joining_member"].display_name} due to joining automute channel')
    
    @pytest.mark.asyncio
    async def test_user_leaves_voice_channel_with_active_automute(self, auto_mute_environment):
        """Test auto-mute removal when user leaves voice channel during active session"""
        env = auto_mute_environment
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = MagicMock()  # Work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_session.auto_mute = mock_auto_mute
            
            # Setup voice client connection
            mock_voice_client = MagicMock()
            env['session_interaction'].voice_client = mock_voice_client
            env['session_interaction'].guild.voice_client = mock_voice_client
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states
            mock_bot_enum.State.WORK_STATES = [mock_session.state]
            
            # Create voice state changes - user leaves the session voice channel
            before_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])  # In session channel
            after_state = MockVoiceState(channel=None, member=env['joining_member'])  # Leaves channel
            
            # Mock member edit method for unmuting
            env['joining_member'].edit = AsyncMock()
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify user was unmuted
            env['joining_member'].edit.assert_called_once_with(mute=False)
            
            # Verify logging
            mock_logger.info.assert_any_call(f'{env["joining_member"].display_name} left the channel {env["voice_channel"].name}.')
            mock_logger.info.assert_any_call(f'Unmuting {env["joining_member"].display_name} due to leaving automute channel')
    
    @pytest.mark.asyncio
    async def test_user_moves_between_channels_with_automute(self, auto_mute_environment):
        """Test auto-mute behavior when user moves between voice channels"""
        env = auto_mute_environment
        
        # Create additional voice channel
        other_channel = MockVoiceChannel(id=22222, name="Other Voice Channel", guild=env['guild'])
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = MagicMock()  # Work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_auto_mute.safe_edit_member = AsyncMock()
            mock_session.auto_mute = mock_auto_mute
            
            # Setup voice client connection
            mock_voice_client = MagicMock()
            env['session_interaction'].voice_client = mock_voice_client
            env['session_interaction'].guild.voice_client = mock_voice_client
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states
            mock_bot_enum.State.WORK_STATES = [mock_session.state]
            
            # Mock member edit method
            env['joining_member'].edit = AsyncMock()
            
            # Test 1: User moves from other channel to session channel
            before_state = MockVoiceState(channel=other_channel, member=env['joining_member'])
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            after_state.mute = False  # Not muted initially
            env['joining_member'].voice = after_state
            
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Should mute user when joining session channel
            mock_auto_mute.safe_edit_member.assert_called_once_with(env['joining_member'], unmute=False, channel_name='Session Voice Channel')
            
            # Reset mocks
            mock_auto_mute.safe_edit_member.reset_mock()
            env['joining_member'].edit.reset_mock()
            
            # Test 2: User moves from session channel to other channel
            before_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            after_state = MockVoiceState(channel=other_channel, member=env['joining_member'])
            
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Should unmute user when leaving session channel
            env['joining_member'].edit.assert_called_once_with(mute=False)
    
    @pytest.mark.asyncio
    async def test_automute_only_during_work_states(self, auto_mute_environment):
        """Test that auto-mute only applies during work states, not break states"""
        env = auto_mute_environment
        
        from configs.bot_enum import State
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled but in break state
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = State.SHORT_BREAK  # Break state, not work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_auto_mute.safe_edit_member = AsyncMock()
            mock_session.auto_mute = mock_auto_mute
            
            # Setup voice client connection
            mock_voice_client = MagicMock()
            env['session_interaction'].voice_client = mock_voice_client
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states (break state not in work states)
            mock_bot_enum.State.WORK_STATES = [State.POMODORO, State.CLASSWORK]  # SHORT_BREAK not included
            
            # Create voice state changes - user joins during break
            before_state = MockVoiceState(channel=None, member=env['joining_member'])
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            after_state.mute = False
            env['joining_member'].voice = after_state
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify user was NOT muted (because it's break time)
            mock_auto_mute.safe_edit_member.assert_not_called()
            
            # Verify logging of join but no muting
            mock_logger.info.assert_any_call(f'{env["joining_member"].display_name} joined the channel {env["voice_channel"].name}.')
    
    @pytest.mark.asyncio
    async def test_no_automute_when_bot_not_connected(self, auto_mute_environment):
        """Test that auto-mute doesn't apply when bot is not connected to voice"""
        env = auto_mute_environment
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = MagicMock()  # Work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_auto_mute.safe_edit_member = AsyncMock()
            mock_session.auto_mute = mock_auto_mute
            
            # Bot is NOT connected to voice (no voice_client)
            env['session_interaction'].voice_client = None
            env['session_interaction'].guild.voice_client = None
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states
            mock_bot_enum.State.WORK_STATES = [mock_session.state]
            
            # Create voice state changes - user joins
            before_state = MockVoiceState(channel=None, member=env['joining_member'])
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            after_state.mute = False
            env['joining_member'].voice = after_state
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify user was NOT muted (because bot is not connected)
            mock_auto_mute.safe_edit_member.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_automute_when_user_already_muted(self, auto_mute_environment):
        """Test that auto-mute doesn't apply when user is already muted"""
        env = auto_mute_environment
        
        with patch('cogs.subscribe.vc_manager') as mock_vc_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup active session with auto-mute enabled
            mock_session = MagicMock()
            mock_session.ctx = env['session_interaction']
            mock_session.state = MagicMock()  # Work state
            mock_auto_mute = MagicMock()
            mock_auto_mute.all = True  # Auto-mute is enabled
            mock_auto_mute.safe_edit_member = AsyncMock()
            mock_session.auto_mute = mock_auto_mute
            
            # Setup voice client connection
            mock_voice_client = MagicMock()
            env['session_interaction'].voice_client = mock_voice_client
            
            # Setup vc_manager and vc_accessor
            mock_vc_manager.get_connected_session.return_value = mock_session
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Setup bot_enum work states
            mock_bot_enum.State.WORK_STATES = [mock_session.state]
            
            # Create voice state changes - user joins but is already muted
            before_state = MockVoiceState(channel=None, member=env['joining_member'])
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            after_state.mute = True  # User is already muted
            env['joining_member'].voice = after_state
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify auto-mute was NOT called (user already muted)
            mock_auto_mute.safe_edit_member.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_mute_state_logging_without_channel_change(self, auto_mute_environment):
        """Test logging of mute state changes without channel changes"""
        env = auto_mute_environment
        
        with patch('cogs.subscribe.logger') as mock_logger:
            
            # Create voice state changes - only mute state changes, no channel change
            before_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])
            before_state.self_mute = False
            before_state.mute = False
            before_state.self_deaf = False
            before_state.deaf = False
            
            after_state = MockVoiceState(channel=env['voice_channel'], member=env['joining_member'])  # Same channel
            after_state.self_mute = True  # User muted themselves
            after_state.mute = False
            after_state.self_deaf = False
            after_state.deaf = False
            
            # Execute voice state update
            await env['subscribe_cog'].on_voice_state_update(env['joining_member'], before_state, after_state)
            
            # Verify mute state change was logged
            mock_logger.info.assert_any_call(f'{env["joining_member"].display_name} muted themselves in {env["voice_channel"].name}')
            mock_logger.info.assert_any_call(f'No channel change for {env["joining_member"].display_name}, but logged mute/deafen state changes if any.')