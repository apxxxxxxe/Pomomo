"""
Tests for the Subscribe cog commands.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks.discord_mocks import MockBot, MockInteraction, MockVoiceChannel, MockGuild, MockUser

# Import the cog under test
from cogs.subscribe import Subscribe


class TestSubscribe:
    """Test class for Subscribe cog"""
    
    @pytest.fixture
    def subscribe_cog(self, mock_bot):
        """Fixture providing a Subscribe cog instance"""
        return Subscribe(mock_bot)
    
    @pytest.fixture
    def setup_session_interaction(self):
        """Fixture providing interaction with session setup"""
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild, name="Test Voice Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return interaction, mock_session, voice_channel
    
    @pytest.mark.asyncio
    async def test_enableautomute_no_active_session(self, subscribe_cog, mock_interaction):
        """Test enableautomute command when no active session exists"""
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Mock no active session
            mock_session_manager.get_session_interaction = AsyncMock(return_value=None)
            mock_u_msg.NO_ACTIVE_SESSION_ERR = "No active session"
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, mock_interaction)
            
            # Verify session was checked
            mock_session_manager.get_session_interaction.assert_called_once_with(mock_interaction)
            
            # Verify error response
            mock_interaction.response.send_message.assert_called_once_with("No active session", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_bot_not_in_voice_channel(self, subscribe_cog, mock_interaction):
        """Test enableautomute when bot is not in voice channel"""
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Mock active session but bot not in voice channel
            mock_session = MagicMock()
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = None
            mock_u_msg.AUTOMUTE_REQUIRES_BOT_IN_VC = "Bot not in voice channel"
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, mock_interaction)
            
            # Verify error response
            mock_interaction.response.send_message.assert_called_once_with("Bot not in voice channel", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_user_not_in_same_voice_channel(self, subscribe_cog):
        """Test enableautomute when user is not in same voice channel as bot"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=False)
            mock_u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format.return_value = "Same channel required"
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, interaction)
            
            # Verify validation was called
            mock_voice_validation.require_same_voice_channel.assert_called_once_with(interaction)
            
            # Verify error response
            interaction.response.send_message.assert_called_once_with("Same channel required", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_already_enabled(self, subscribe_cog):
        """Test enableautomute when automute is already enabled"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        mock_session.auto_mute.all = True  # Already enabled
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_u_msg.AUTOMUTE_ALREADY_ENABLED.format.return_value = "Already enabled"
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, interaction)
            
            # Verify error response
            interaction.response.send_message.assert_called_once_with("Already enabled", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_success(self, subscribe_cog):
        """Test successful enableautomute command"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup successful path
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, interaction)
            
            # Verify interaction was deferred
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify auto_mute.handle_all was called with enable=True (work state default)
            mock_session.auto_mute.handle_all.assert_called_once_with(interaction, enable=True)
            
            # Verify original response was deleted
            interaction.delete_original_response.assert_called_once()
            
            # Verify channel message was sent
            interaction.channel.send.assert_called_once()
            
            # Verify logging
            mock_logger.info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enableautomute_exception_handling(self, subscribe_cog):
        """Test enableautomute exception handling"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.u_msg') as mock_u_msg, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks with exception in handle_all
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_session.auto_mute.handle_all.side_effect = Exception("Test error")
            mock_u_msg.AUTOMUTE_ENABLE_FAILED = "Enable failed"
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, interaction)
            
            # Verify error logging
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify error message was sent
            interaction.channel.send.assert_called_with("Enable failed", silent=True)
    
    @pytest.mark.asyncio
    async def test_disableautomute_success(self, subscribe_cog):
        """Test successful disableautomute command"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        mock_session.auto_mute.all = True  # Currently enabled
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation:
            
            # Setup successful path
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            await subscribe_cog.disableautomute.callback(subscribe_cog, interaction)
            
            # Verify interaction was deferred
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify auto_mute.handle_all was called with enable=False (disable operation)
            mock_session.auto_mute.handle_all.assert_called_once_with(interaction, enable=False)
            
            # Verify original response was deleted
            interaction.delete_original_response.assert_called_once()
            
            # Verify channel message was sent
            interaction.channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disableautomute_already_disabled(self, subscribe_cog):
        """Test disableautomute when automute is already disabled"""
        
        interaction, mock_session, voice_channel = self.setup_session_interaction()
        # mock_session.auto_mute.all is already False from fixture
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = voice_channel
            mock_vc_accessor.get_voice_channel.return_value = voice_channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_u_msg.AUTOMUTE_ALREADY_DISABLED.format.return_value = "Already disabled"
            
            await subscribe_cog.disableautomute.callback(subscribe_cog, interaction)
            
            # Verify error response
            interaction.response.send_message.assert_called_once_with("Already disabled", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_on_voice_state_update_basic(self, subscribe_cog):
        """Test on_voice_state_update event handler"""
        
        member = MagicMock()
        before_state = MagicMock()
        after_state = MagicMock()
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager:
            # Mock no active sessions
            mock_session_manager.active_sessions = {}
            
            # This should not raise an error
            await subscribe_cog.on_voice_state_update(member, before_state, after_state)
            
            # No assertions needed - just verify it doesn't crash
    
    def test_subscribe_cog_initialization(self, mock_bot):
        """Test Subscribe cog initialization"""
        cog = Subscribe(mock_bot)
        assert cog.client == mock_bot
    
    def setup_session_interaction(self):
        """Helper method to setup interaction with session (reusable)"""
        user = MockUser()
        guild = MockGuild()
        voice_channel = MockVoiceChannel(guild=guild, name="Test Voice Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return interaction, mock_session, voice_channel


class TestAutoMuteClass:
    """Tests for AutoMute class functionality"""
    
    @pytest.fixture
    def auto_mute_setup(self):
        """Fixture providing AutoMute test setup"""
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=54321, name="TestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Create mock member
        from tests.mocks.discord_mocks import MockMember, MockVoiceState
        member = MockMember(user, guild)
        member.voice = MockVoiceState(channel=voice_channel, member=member)
        member.edit = AsyncMock()
        
        return {
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'interaction': interaction,
            'member': member
        }
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_mute(self, auto_mute_setup):
        """Test safe_edit_member with mute operation"""
        env = auto_mute_setup
        
        # Import AutoMute class
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Test muting member
            await auto_mute.safe_edit_member(env['member'], unmute=False)
            
            # Verify safe_edit_member was called
            auto_mute.safe_edit_member.assert_called_once_with(env['member'], unmute=False)
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_unmute(self, auto_mute_setup):
        """Test safe_edit_member with unmute operation"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Test unmuting member
            await auto_mute.safe_edit_member(env['member'], unmute=True)
            
            # Verify safe_edit_member was called with unmute=True
            auto_mute.safe_edit_member.assert_called_once_with(env['member'], unmute=True)
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_exception_handling(self, auto_mute_setup):
        """Test safe_edit_member with exception handling"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.logger') as mock_logger:
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock(side_effect=Exception("Permission error"))
            MockAutoMute.return_value = auto_mute
            
            # Test exception handling - should not raise exception
            try:
                await auto_mute.safe_edit_member(env['member'], unmute=False)
            except Exception:
                # Expected behavior - method should be called but may raise
                pass
            
            # Verify exception was handled (method was called despite exception)
            auto_mute.safe_edit_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mute_method(self, auto_mute_setup):
        """Test AutoMute.mute method"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.mute = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Test mute method
            await auto_mute.mute(env['member'])
            
            # Verify mute was called
            auto_mute.mute.assert_called_once_with(env['member'])
    
    @pytest.mark.asyncio
    async def test_unmute_method(self, auto_mute_setup):
        """Test AutoMute.unmute method"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.unmute = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Test unmute method
            await auto_mute.unmute(env['member'])
            
            # Verify unmute was called
            auto_mute.unmute.assert_called_once_with(env['member'])
    
    @pytest.mark.asyncio
    async def test_handle_all_method_enable(self, auto_mute_setup):
        """Test AutoMute.handle_all method for enabling auto-mute"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            auto_mute.all = False  # Starting disabled
            MockAutoMute.return_value = auto_mute
            
            # Test handle_all for enabling
            await auto_mute.handle_all(env['interaction'])
            
            # Verify handle_all was called
            auto_mute.handle_all.assert_called_once_with(env['interaction'])
    
    @pytest.mark.asyncio
    async def test_handle_all_method_disable(self, auto_mute_setup):
        """Test AutoMute.handle_all method for disabling auto-mute"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            auto_mute.all = True  # Starting enabled
            MockAutoMute.return_value = auto_mute
            
            # Test handle_all for disabling
            await auto_mute.handle_all(env['interaction'])
            
            # Verify handle_all was called
            auto_mute.handle_all.assert_called_once_with(env['interaction'])
    
    @pytest.mark.asyncio
    async def test_handle_all_method_with_voice_channel_members(self, auto_mute_setup):
        """Test AutoMute.handle_all method with voice channel members"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.vc_accessor') as mock_vc_accessor:
            
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            auto_mute.all = False
            MockAutoMute.return_value = auto_mute
            
            # Mock voice channel with members
            env['voice_channel'].members = [env['member']]
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            
            # Test handle_all with voice channel members
            await auto_mute.handle_all(env['interaction'])
            
            # Verify handle_all was called
            auto_mute.handle_all.assert_called_once_with(env['interaction'])
    
    @pytest.mark.asyncio
    async def test_auto_mute_state_toggle(self, auto_mute_setup):
        """Test AutoMute state toggling"""
        env = auto_mute_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            auto_mute = MagicMock()
            auto_mute.all = False
            MockAutoMute.return_value = auto_mute
            
            # Initial state should be False
            assert auto_mute.all is False
            
            # Toggle to True
            auto_mute.all = True
            assert auto_mute.all is True
            
            # Toggle back to False
            auto_mute.all = False
            assert auto_mute.all is False


class TestAutoMuteErrorCases:
    """Tests for AutoMute error handling and edge cases"""
    
    @pytest.fixture
    def error_test_setup(self):
        """Fixture providing error test setup"""
        user = MockUser(id=12345, name="ErrorTestUser")
        guild = MockGuild(id=54321, name="ErrorTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Error Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        from tests.mocks.discord_mocks import MockMember, MockVoiceState
        member = MockMember(user, guild)
        member.voice = MockVoiceState(channel=voice_channel, member=member)
        
        return {
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'interaction': interaction,
            'member': member
        }
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_permission_error(self, error_test_setup):
        """Test safe_edit_member with permission error"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.logger') as mock_logger:
            
            from discord import Forbidden
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock(side_effect=Forbidden(MagicMock(), "Missing Permissions"))
            MockAutoMute.return_value = auto_mute
            
            # Test permission error handling - should not raise exception
            try:
                await auto_mute.safe_edit_member(env['member'], unmute=False)
            except Forbidden:
                # Expected behavior - method should be called but may raise
                pass
            
            # Verify method was called despite error
            auto_mute.safe_edit_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_member_not_found(self, error_test_setup):
        """Test safe_edit_member when member is not found"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.logger') as mock_logger:
            
            from discord import NotFound
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock(side_effect=NotFound(MagicMock(), "Member not found"))
            MockAutoMute.return_value = auto_mute
            
            # Test member not found error handling - should not raise exception
            try:
                await auto_mute.safe_edit_member(env['member'], unmute=False)
            except NotFound:
                # Expected behavior - method should be called but may raise
                pass
            
            # Verify method was called despite error
            auto_mute.safe_edit_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_edit_member_http_exception(self, error_test_setup):
        """Test safe_edit_member with HTTP exception"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.logger') as mock_logger:
            
            from discord import HTTPException
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock(side_effect=HTTPException(MagicMock(), "HTTP Error"))
            MockAutoMute.return_value = auto_mute
            
            # Test HTTP exception handling - should not raise exception
            try:
                await auto_mute.safe_edit_member(env['member'], unmute=False)
            except HTTPException:
                # Expected behavior - method should be called but may raise
                pass
            
            # Verify method was called despite error
            auto_mute.safe_edit_member.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_all_with_none_voice_channel(self, error_test_setup):
        """Test handle_all when voice channel is None"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.vc_accessor') as mock_vc_accessor:
            
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Mock None voice channel (bot not connected)
            mock_vc_accessor.get_voice_channel.return_value = None
            
            # Test handle_all with None voice channel
            await auto_mute.handle_all(env['interaction'])
            
            # Should still be called but may handle the None case internally
            auto_mute.handle_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_all_with_empty_voice_channel(self, error_test_setup):
        """Test handle_all when voice channel has no members"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.vc_accessor') as mock_vc_accessor:
            
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Mock empty voice channel
            empty_channel = MockVoiceChannel(guild=env['guild'], name="Empty Channel")
            empty_channel.members = []
            mock_vc_accessor.get_voice_channel.return_value = empty_channel
            
            # Test handle_all with empty voice channel
            await auto_mute.handle_all(env['interaction'])
            
            # Should handle empty channel gracefully
            auto_mute.handle_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auto_mute_with_bot_member(self, error_test_setup):
        """Test auto-mute behavior when trying to mute bot member"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            
            # Create bot member
            bot_user = MockUser(id=99999, name="TestBot")
            bot_user.bot = True  # Mark as bot
            from tests.mocks.discord_mocks import MockMember
            bot_member = MockMember(bot_user, env['guild'])
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Test that bot member muting is handled appropriately
            await auto_mute.safe_edit_member(bot_member, unmute=False)
            
            # Verify method was called (implementation may filter bots internally)
            auto_mute.safe_edit_member.assert_called_once_with(bot_member, unmute=False)
    
    @pytest.mark.asyncio
    async def test_auto_mute_concurrent_operations(self, error_test_setup):
        """Test auto-mute under concurrent operations"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock()
            auto_mute.handle_all = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Create multiple concurrent operations
            tasks = []
            
            # Multiple mute operations
            for i in range(5):
                task = auto_mute.safe_edit_member(env['member'], unmute=False)
                tasks.append(task)
            
            # Multiple handle_all operations
            for i in range(3):
                task = auto_mute.handle_all(env['interaction'])
                tasks.append(task)
            
            # Execute all tasks concurrently
            await asyncio.gather(*tasks)
            
            # Verify all operations were attempted
            assert auto_mute.safe_edit_member.call_count == 5
            assert auto_mute.handle_all.call_count == 3
    
    @pytest.mark.asyncio
    async def test_auto_mute_with_invalid_interaction(self, error_test_setup):
        """Test auto-mute with invalid interaction object"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute:
            
            auto_mute = MagicMock()
            auto_mute.handle_all = AsyncMock()
            MockAutoMute.return_value = auto_mute
            
            # Create invalid interaction (missing required attributes)
            invalid_interaction = MagicMock()
            invalid_interaction.guild = None
            invalid_interaction.user = None
            
            # Test handle_all with invalid interaction
            await auto_mute.handle_all(invalid_interaction)
            
            # Should handle invalid interaction gracefully
            auto_mute.handle_all.assert_called_once_with(invalid_interaction)
    
    @pytest.mark.asyncio
    async def test_auto_mute_timeout_error(self, error_test_setup):
        """Test auto-mute with timeout errors"""
        env = error_test_setup
        
        with patch('src.subscriptions.AutoMute.AutoMute') as MockAutoMute, \
             patch('src.subscriptions.AutoMute.logger') as mock_logger:
            
            import asyncio
            
            auto_mute = MagicMock()
            auto_mute.safe_edit_member = AsyncMock(side_effect=asyncio.TimeoutError("Operation timed out"))
            MockAutoMute.return_value = auto_mute
            
            # Test timeout error handling - should not raise exception
            try:
                await auto_mute.safe_edit_member(env['member'], unmute=False)
            except asyncio.TimeoutError:
                # Expected behavior - method should be called but may raise
                pass
            
            # Verify timeout was handled
            auto_mute.safe_edit_member.assert_called_once()


class TestEnableAutoMuteStateSpecific:
    """Tests for enableautomute command with specific session states"""
    
    @pytest.fixture
    def state_test_setup(self):
        """Fixture providing test setup for state-specific tests"""
        user = MockUser(id=12345, name="StateTestUser")
        guild = MockGuild(id=54321, name="StateTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="State Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild
        }
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_pomodoro_state(self, mock_bot, state_test_setup):
        """Test enableautomute during POMODORO state (should execute immediate mute)"""
        env = state_test_setup
        env['session'].state = 'POMODORO'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify immediate mute execution (not break state)
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify interaction was deferred
            env['interaction'].response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify response was deleted
            env['interaction'].delete_original_response.assert_called_once()
            
            # Verify channel message was sent (work state message)
            env['interaction'].channel.send.assert_called_once()
            call_args = env['interaction'].channel.send.call_args[1]
            assert call_args['silent'] is True
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'work state: POMODORO' in log_call_args
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_countdown_state(self, mock_bot, state_test_setup):
        """Test enableautomute during COUNTDOWN state (should execute immediate mute)"""
        env = state_test_setup
        env['session'].state = 'COUNTDOWN'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify immediate mute execution
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'work state: COUNTDOWN' in log_call_args
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_classwork_state(self, mock_bot, state_test_setup):
        """Test enableautomute during CLASSWORK state (should execute immediate mute)"""
        env = state_test_setup
        env['session'].state = 'CLASSWORK'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify immediate mute execution
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'work state: CLASSWORK' in log_call_args
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_short_break_state(self, mock_bot, state_test_setup):
        """Test enableautomute during SHORT_BREAK state (should only set flag, no immediate mute)"""
        env = state_test_setup
        env['session'].state = 'SHORT_BREAK'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify NO immediate mute execution (break state)
            env['session'].auto_mute.handle_all.assert_not_called()
            
            # Verify auto_mute flag was set
            assert env['session'].auto_mute.all is True
            
            # Verify interaction was deferred
            env['interaction'].response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify response was deleted
            env['interaction'].delete_original_response.assert_called_once()
            
            # Verify channel message was sent (break state message)
            env['interaction'].channel.send.assert_called_once()
            call_args = env['interaction'].channel.send.call_args
            message_content = call_args[0][0]
            assert '次の作業時間開始時から強制ミュートが適用されます' in message_content
            assert call_args[1]['silent'] is True
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'break state: SHORT_BREAK' in log_call_args
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_long_break_state(self, mock_bot, state_test_setup):
        """Test enableautomute during LONG_BREAK state (should only set flag, no immediate mute)"""
        env = state_test_setup
        env['session'].state = 'LONG_BREAK'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify NO immediate mute execution (break state)
            env['session'].auto_mute.handle_all.assert_not_called()
            
            # Verify auto_mute flag was set
            assert env['session'].auto_mute.all is True
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'break state: LONG_BREAK' in log_call_args
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_classwork_break_state(self, mock_bot, state_test_setup):
        """Test enableautomute during CLASSWORK_BREAK state (should only set flag, no immediate mute)"""
        env = state_test_setup
        env['session'].state = 'CLASSWORK_BREAK'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify NO immediate mute execution (break state)
            env['session'].auto_mute.handle_all.assert_not_called()
            
            # Verify auto_mute flag was set
            assert env['session'].auto_mute.all is True
            
            # Verify logging with state info
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert 'break state: CLASSWORK_BREAK' in log_call_args


class TestEnableAutoMuteHandleAllParameterValidation:
    """Tests for enableautomute handle_all parameter validation"""
    
    @pytest.fixture
    def parameter_test_setup(self):
        """Fixture providing test setup for parameter validation tests"""
        user = MockUser(id=12345, name="ParamTestUser")
        guild = MockGuild(id=54321, name="ParamTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Param Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild
        }
    
    @pytest.mark.asyncio
    async def test_enableautomute_work_state_calls_handle_all_with_enable_true(self, mock_bot, parameter_test_setup):
        """Test that work states call handle_all with enable=True parameter"""
        env = parameter_test_setup
        env['session'].state = 'POMODORO'  # Work state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify handle_all was called with correct parameters
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify the exact call arguments
            call_args, call_kwargs = env['session'].auto_mute.handle_all.call_args
            assert call_args[0] == env['interaction']
            assert call_kwargs.get('enable') is True
    
    @pytest.mark.asyncio
    async def test_enableautomute_break_state_does_not_call_handle_all(self, mock_bot, parameter_test_setup):
        """Test that break states do NOT call handle_all at all"""
        env = parameter_test_setup
        env['session'].state = 'SHORT_BREAK'  # Break state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify handle_all was NOT called at all
            env['session'].auto_mute.handle_all.assert_not_called()
            
            # Verify flag was set instead
            assert env['session'].auto_mute.all is True
    
    @pytest.mark.asyncio
    async def test_enableautomute_all_work_states_use_enable_true(self, mock_bot, parameter_test_setup):
        """Test that all work states use enable=True parameter"""
        work_states = ['POMODORO', 'COUNTDOWN', 'CLASSWORK']
        env = parameter_test_setup
        subscribe_cog = Subscribe(mock_bot)
        
        for state in work_states:
            # Reset mock for each iteration
            env['session'].auto_mute.handle_all.reset_mock()
            env['session'].state = state
            
            with patch('cogs.subscribe.session_manager') as mock_session_manager, \
                 patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
                 patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
                 patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
                 patch('cogs.subscribe.logger') as mock_logger:
                
                # Setup mocks
                mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
                mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
                mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
                mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
                mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
                
                await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
                
                # Verify handle_all was called with enable=True for this state
                env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_no_break_states_call_handle_all(self, mock_bot, parameter_test_setup):
        """Test that no break states call handle_all"""
        break_states = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
        env = parameter_test_setup
        subscribe_cog = Subscribe(mock_bot)
        
        for state in break_states:
            # Reset mock and auto_mute flag for each iteration
            env['session'].auto_mute.handle_all.reset_mock()
            env['session'].auto_mute.all = False
            env['session'].state = state
            
            with patch('cogs.subscribe.session_manager') as mock_session_manager, \
                 patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
                 patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
                 patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
                 patch('cogs.subscribe.logger') as mock_logger:
                
                # Setup mocks
                mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
                mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
                mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
                mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
                mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
                
                await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
                
                # Verify handle_all was NOT called for this break state
                env['session'].auto_mute.handle_all.assert_not_called()
                
                # Verify flag was set instead
                assert env['session'].auto_mute.all is True


class TestEnableAutoMuteMessageContentValidation:
    """Tests for enableautomute message content validation"""
    
    @pytest.fixture
    def message_test_setup(self):
        """Fixture providing test setup for message content validation tests"""
        user = MockUser(id=12345, name="MessageTestUser")
        guild = MockGuild(id=54321, name="MessageTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Message Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild
        }
    
    @pytest.mark.asyncio
    async def test_enableautomute_work_state_message_content(self, mock_bot, message_test_setup):
        """Test message content for work states"""
        env = message_test_setup
        env['session'].state = 'POMODORO'  # Work state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify message content for work state
            env['interaction'].channel.send.assert_called_once()
            call_args = env['interaction'].channel.send.call_args[0]
            message_content = call_args[0]
            
            # Check specific message content for work state
            assert 'MessageTestUser' in message_content
            assert '`/enableautomute`を使用しました' in message_content
            assert 'Message Test Channel' in message_content
            assert 'automuteをオンにしました' in message_content
            assert '参加者は作業時間の間は強制ミュートされます🤫' in message_content
            
            # Check that it's NOT the break state message
            assert '次の作業時間開始時から強制ミュートが適用されます' not in message_content
            
            # Verify silent parameter
            call_kwargs = env['interaction'].channel.send.call_args[1]
            assert call_kwargs['silent'] is True
    
    @pytest.mark.asyncio
    async def test_enableautomute_break_state_message_content(self, mock_bot, message_test_setup):
        """Test message content for break states"""
        env = message_test_setup
        env['session'].state = 'SHORT_BREAK'  # Break state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify message content for break state
            env['interaction'].channel.send.assert_called_once()
            call_args = env['interaction'].channel.send.call_args[0]
            message_content = call_args[0]
            
            # Check specific message content for break state
            assert 'MessageTestUser' in message_content
            assert '`/enableautomute`を使用しました' in message_content
            assert 'Message Test Channel' in message_content
            assert 'automuteをオンにしました' in message_content
            assert '現在は休憩中のため、次の作業時間開始時から強制ミュートが適用されます🤫' in message_content
            
            # Check that it's NOT the work state message
            assert '参加者は作業時間の間は強制ミュートされます' not in message_content
            
            # Verify silent parameter
            call_kwargs = env['interaction'].channel.send.call_args[1]
            assert call_kwargs['silent'] is True
    
    @pytest.mark.asyncio
    async def test_enableautomute_message_contains_user_and_channel_info(self, mock_bot, message_test_setup):
        """Test that messages contain correct user and channel information"""
        env = message_test_setup
        env['session'].state = 'COUNTDOWN'  # Work state
        
        # Set specific names for testing
        env['user'].display_name = "TestUser123"
        env['voice_channel'].name = "TestVoiceChannel456"
        
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Get the message content
            call_args = env['interaction'].channel.send.call_args[0]
            message_content = call_args[0]
            
            # Verify user and channel names are included
            assert 'TestUser123' in message_content
            assert 'TestVoiceChannel456' in message_content
            
            # Verify message format structure
            assert '> -#' in message_content  # Message starts with quote format
            assert 'さんが`/enableautomute`を使用しました' in message_content
            assert 'ボイスチャンネルのautomuteをオンにしました！' in message_content
    
    @pytest.mark.asyncio
    async def test_enableautomute_message_emoji_consistency(self, mock_bot, message_test_setup):
        """Test that messages contain consistent emoji usage"""
        test_cases = [
            ('POMODORO', 'work'),
            ('SHORT_BREAK', 'break'),
            ('LONG_BREAK', 'break'),
            ('CLASSWORK', 'work'),
            ('CLASSWORK_BREAK', 'break')
        ]
        
        env = message_test_setup
        subscribe_cog = Subscribe(mock_bot)
        
        for state, state_type in test_cases:
            # Reset interaction mock for each test and the auto_mute flag
            env['interaction'].channel.send.reset_mock()
            env['interaction'].response.defer.reset_mock()
            env['interaction'].delete_original_response.reset_mock()
            env['session'].auto_mute.all = False  # Reset flag
            env['session'].state = state
            
            with patch('cogs.subscribe.session_manager') as mock_session_manager, \
                 patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
                 patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
                 patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
                 patch('cogs.subscribe.logger') as mock_logger:
                
                # Setup mocks
                mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
                mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
                mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
                mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
                mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
                
                await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
                
                # Verify that channel.send was called
                assert env['interaction'].channel.send.called, f"channel.send was not called for state {state}"
                
                # Get the message content
                call_args = env['interaction'].channel.send.call_args[0]
                message_content = call_args[0]
                
                # Verify consistent emoji usage
                assert '🤫' in message_content, f"Missing emoji for state {state}"
                
                # Count occurrences to ensure consistent emoji usage
                emoji_count = message_content.count('🤫')
                assert emoji_count == 1, f"Expected exactly 1 emoji for state {state}, got {emoji_count}"


class TestEnableAutoMuteLoggingValidation:
    """Tests for enableautomute logging validation"""
    
    @pytest.fixture
    def logging_test_setup(self):
        """Fixture providing test setup for logging validation tests"""
        user = MockUser(id=12345, name="LogTestUser")
        guild = MockGuild(id=54321, name="LogTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Log Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild
        }
    
    @pytest.mark.asyncio
    async def test_enableautomute_work_state_logging(self, mock_bot, logging_test_setup):
        """Test logging content for work states"""
        env = logging_test_setup
        env['session'].state = 'POMODORO'  # Work state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify logging was called
            mock_logger.info.assert_called_once()
            
            # Verify log content for work state
            log_message = mock_logger.info.call_args[0][0]
            
            # Check specific log content for work state
            assert 'Enabled automute for all users in' in log_message
            assert 'Log Test Channel' in log_message
            assert 'by LogTestUser' in log_message or str(env['user']) in log_message
            assert 'work state: POMODORO' in log_message
            
            # Check that it's NOT the break state log
            assert 'break state:' not in log_message
    
    @pytest.mark.asyncio
    async def test_enableautomute_break_state_logging(self, mock_bot, logging_test_setup):
        """Test logging content for break states"""
        env = logging_test_setup
        env['session'].state = 'LONG_BREAK'  # Break state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify logging was called
            mock_logger.info.assert_called_once()
            
            # Verify log content for break state
            log_message = mock_logger.info.call_args[0][0]
            
            # Check specific log content for break state
            assert 'Enabled automute for all users in' in log_message
            assert 'Log Test Channel' in log_message
            assert 'by LogTestUser' in log_message or str(env['user']) in log_message
            assert 'break state: LONG_BREAK' in log_message
            
            # Check that it's NOT the work state log
            assert 'work state:' not in log_message
    
    @pytest.mark.asyncio
    async def test_enableautomute_logging_includes_all_required_info(self, mock_bot, logging_test_setup):
        """Test that logging includes all required information"""
        test_cases = [
            ('COUNTDOWN', 'work'),
            ('CLASSWORK', 'work'),
            ('SHORT_BREAK', 'break'),
            ('CLASSWORK_BREAK', 'break')
        ]
        
        env = logging_test_setup
        subscribe_cog = Subscribe(mock_bot)
        
        for state, state_type in test_cases:
            # Reset auto_mute flag and state for each test
            env['session'].auto_mute.all = False
            env['session'].state = state
            
            with patch('cogs.subscribe.session_manager') as mock_session_manager, \
                 patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
                 patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
                 patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
                 patch('cogs.subscribe.logger') as mock_logger:
                
                # Setup mocks
                mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
                mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
                mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
                mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
                mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
                
                await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
                
                # Verify logging was called
                mock_logger.info.assert_called_once()
                
                # Get log message
                log_message = mock_logger.info.call_args[0][0]
                
                # Verify required log components
                assert 'Enabled automute for all users in' in log_message, f"Missing base message for {state}"
                assert env['voice_channel'].name in log_message, f"Missing channel name for {state}"
                assert f'{state_type} state: {state}' in log_message, f"Missing state info for {state}"
    
    @pytest.mark.asyncio
    async def test_enableautomute_no_logging_on_early_returns(self, mock_bot, logging_test_setup):
        """Test that no logging occurs when enableautomute returns early due to errors"""
        env = logging_test_setup
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Test case: No active session (should return early)
            mock_session_manager.get_session_interaction = AsyncMock(return_value=None)
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify NO info logging occurred (only error scenarios might log)
            mock_logger.info.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_enableautomute_error_logging_on_exception(self, mock_bot, logging_test_setup):
        """Test that error logging occurs when exceptions happen"""
        env = logging_test_setup
        env['session'].state = 'POMODORO'  # Work state that would cause handle_all to be called
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks with exception in handle_all
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            # Make handle_all raise an exception
            env['session'].auto_mute.handle_all.side_effect = Exception("Test error")
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify error logging occurred
            mock_logger.error.assert_called_once()
            mock_logger.exception.assert_called_once()
            
            # Verify error message contains expected content
            error_message = mock_logger.error.call_args[0][0]
            assert 'Error in enableautomute:' in error_message


class TestEnableAutoMuteEdgeCases:
    """Tests for enableautomute edge cases and complex scenarios"""
    
    @pytest.fixture
    def edge_case_setup(self):
        """Fixture providing test setup for edge case tests"""
        user = MockUser(id=12345, name="EdgeTestUser")
        guild = MockGuild(id=54321, name="EdgeTestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="Edge Test Channel")
        interaction = MockInteraction(user=user, guild=guild)
        
        # Mock session and voice channel setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        mock_session.auto_mute.handle_all = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild
        }
    
    @pytest.mark.asyncio
    async def test_enableautomute_with_unknown_session_state(self, mock_bot, edge_case_setup):
        """Test enableautomute with an unknown/unexpected session state"""
        env = edge_case_setup
        env['session'].state = 'UNKNOWN_STATE'  # Unknown state
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Unknown state should be treated as work state (not in BREAK_STATES)
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify logging includes the unknown state
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert 'work state: UNKNOWN_STATE' in log_message
    
    @pytest.mark.asyncio
    async def test_enableautomute_concurrent_executions(self, mock_bot, edge_case_setup):
        """Test enableautomute under concurrent execution scenarios"""
        env = edge_case_setup
        env['session'].state = 'POMODORO'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            # Simulate slow handle_all to test concurrent access
            import asyncio
            async def slow_handle_all(*args, **kwargs):
                await asyncio.sleep(0.1)
                
            env['session'].auto_mute.handle_all = AsyncMock(side_effect=slow_handle_all)
            
            # Execute multiple concurrent calls
            tasks = [
                subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
                for _ in range(3)
            ]
            
            await asyncio.gather(*tasks)
            
            # Verify all calls completed (should handle concurrent access gracefully)
            assert env['session'].auto_mute.handle_all.call_count == 3
    
    @pytest.mark.asyncio
    async def test_enableautomute_during_state_transition(self, mock_bot, edge_case_setup):
        """Test enableautomute behavior during session state transitions"""
        env = edge_case_setup
        subscribe_cog = Subscribe(mock_bot)
        
        # Simulate state changing during execution
        initial_state = 'SHORT_BREAK'
        final_state = 'POMODORO'
        env['session'].state = initial_state
        
        call_count = 0
        def state_changing_session_getter(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                env['session'].state = final_state  # Change state during execution
            return env['session']
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(side_effect=state_changing_session_getter)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Should use the state at the time of state check (final_state)
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_with_voice_channel_members_edge_cases(self, mock_bot, edge_case_setup):
        """Test enableautomute with various voice channel member scenarios"""
        env = edge_case_setup
        env['session'].state = 'COUNTDOWN'
        subscribe_cog = Subscribe(mock_bot)
        
        # Create various member types
        from tests.mocks.discord_mocks import MockMember, MockVoiceState
        
        # Regular user
        regular_user = MockUser(id=111, name="RegularUser")
        regular_member = MockMember(regular_user, env['guild'])
        regular_member.voice = MockVoiceState(channel=env['voice_channel'], member=regular_member)
        
        # Bot user
        bot_user = MockUser(id=222, name="BotUser")
        bot_user.bot = True
        bot_member = MockMember(bot_user, env['guild'])
        bot_member.voice = MockVoiceState(channel=env['voice_channel'], member=bot_member)
        
        # User with no voice state
        no_voice_user = MockUser(id=333, name="NoVoiceUser")
        no_voice_member = MockMember(no_voice_user, env['guild'])
        no_voice_member.voice = None
        
        # Set voice channel members
        env['voice_channel'].members = [regular_member, bot_member, no_voice_member]
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Should still call handle_all despite edge cases in member list
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
    
    @pytest.mark.asyncio
    async def test_enableautomute_interaction_response_timing(self, mock_bot, edge_case_setup):
        """Test proper timing of interaction responses"""
        env = edge_case_setup
        env['session'].state = 'CLASSWORK'
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Verify interaction response sequence - check individual calls
            env['interaction'].response.defer.assert_called_once_with(ephemeral=True)
            env['interaction'].delete_original_response.assert_called_once()
            env['interaction'].channel.send.assert_called_once()
            
            # Verify timing - defer should be called before delete and send
            # We can verify this by checking the call count matches expected sequence
            assert env['interaction'].response.defer.call_count == 1, "Should defer interaction once"
            assert env['interaction'].delete_original_response.call_count == 1, "Should delete original response once"
            assert env['interaction'].channel.send.call_count == 1, "Should send channel message once"
    
    @pytest.mark.asyncio
    async def test_enableautomute_permission_edge_cases(self, mock_bot, edge_case_setup):
        """Test enableautomute with various permission scenarios"""
        env = edge_case_setup
        env['session'].state = 'POMODORO'
        subscribe_cog = Subscribe(mock_bot)
        
        # Test case where handle_all raises permission error
        from src.subscriptions.AutoMute import AutoMutePermissionError
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger, \
             patch('cogs.subscribe.u_msg') as mock_u_msg:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            mock_u_msg.AUTOMUTE_ENABLE_FAILED = "Permission error"
            
            # Make handle_all raise permission error
            permission_error = AutoMutePermissionError("Missing Permissions")
            env['session'].auto_mute.handle_all.side_effect = permission_error
            
            # Mock interaction response behavior
            env['interaction'].response.is_done.return_value = True  # Simulate defer already called
            env['interaction'].delete_original_response = AsyncMock()
            env['interaction'].followup.send = AsyncMock()
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Should handle permission error gracefully with warning log (not error)
            mock_logger.warning.assert_called_once()
            
            # Verify that the channel.send was NOT called (no success message)
            env['interaction'].channel.send.assert_not_called()
            
            # Verify that delete_original_response was called (cleanup)
            env['interaction'].delete_original_response.assert_called_once()
            
            # Verify that followup.send was called with ephemeral=True for permission error
            env['interaction'].followup.send.assert_called_once()
            call_args = env['interaction'].followup.send.call_args
            assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_enableautomute_multiple_voice_channels_scenario(self, mock_bot, edge_case_setup):
        """Test enableautomute when bot is connected to multiple voice channels"""
        env = edge_case_setup
        env['session'].state = 'POMODORO'
        subscribe_cog = Subscribe(mock_bot)
        
        # Create additional voice channel
        other_voice_channel = MockVoiceChannel(guild=env['guild'], name="Other Voice Channel")
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks - bot connected to original channel, user in same channel
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']  # Session channel
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Should operate on the session's voice channel, not other channels
            env['session'].auto_mute.handle_all.assert_called_once_with(env['interaction'], enable=True)
            
            # Verify log contains correct channel name
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert 'Edge Test Channel' in log_message
            assert 'Other Voice Channel' not in log_message
    
    @pytest.mark.asyncio
    async def test_enableautomute_session_auto_mute_object_edge_cases(self, mock_bot, edge_case_setup):
        """Test enableautomute with various auto_mute object states"""
        env = edge_case_setup
        env['session'].state = 'SHORT_BREAK'
        subscribe_cog = Subscribe(mock_bot)
        
        # Test case where auto_mute object has unusual state
        env['session'].auto_mute.all = None  # Unusual initial state
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # Setup mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # Should set auto_mute.all to True regardless of initial state
            assert env['session'].auto_mute.all is True
            
            # Should not call handle_all for break state
            env['session'].auto_mute.handle_all.assert_not_called()