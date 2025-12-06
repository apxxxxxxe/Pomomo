"""
Tests for the Subscribe cog commands.
"""
import pytest
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
            
            # Verify auto_mute.handle_all was called
            mock_session.auto_mute.handle_all.assert_called_once_with(interaction)
            
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
            
            # Verify auto_mute.handle_all was called
            mock_session.auto_mute.handle_all.assert_called_once_with(interaction)
            
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