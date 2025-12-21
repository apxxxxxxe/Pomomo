"""
Tests for the Info cog commands.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import app_commands

from tests.mocks.discord_mocks import MockBot, MockInteraction

# Import the cog under test
from cogs.info import Info


class TestInfo:
    """Test class for Info cog"""
    
    @pytest.fixture
    def info_cog(self, mock_bot):
        """Fixture providing an Info cog instance"""
        return Info(mock_bot)
    
    @pytest.mark.asyncio
    async def test_help_command_with_valid_embed(self, info_cog, mock_interaction):
        """Test help command when msg_builder returns a valid embed"""
        
        with patch('cogs.info.msg_builder') as mock_msg_builder:
            # Mock a valid embed being returned
            mock_embed = MagicMock()
            mock_msg_builder.help_embed.return_value = mock_embed
            
            await info_cog.help.callback(info_cog, mock_interaction, command="")
            
            # Verify msg_builder was called with correct command
            mock_msg_builder.help_embed.assert_called_once_with("")
            
            # Verify response was sent with the embed
            mock_interaction.response.send_message.assert_called_once_with(embed=mock_embed, ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_command_with_specific_command(self, info_cog, mock_interaction):
        """Test help command with a specific command parameter"""
        
        with patch('cogs.info.msg_builder') as mock_msg_builder:
            # Mock a valid embed being returned
            mock_embed = MagicMock()
            mock_msg_builder.help_embed.return_value = mock_embed
            
            await info_cog.help.callback(info_cog, mock_interaction, command="pomodoro")
            
            # Verify msg_builder was called with specific command
            mock_msg_builder.help_embed.assert_called_once_with("pomodoro")
            
            # Verify response was sent with the embed
            mock_interaction.response.send_message.assert_called_once_with(embed=mock_embed, ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_command_with_no_embed(self, info_cog, mock_interaction):
        """Test help command when msg_builder returns None (no embed)"""
        
        with patch('cogs.info.msg_builder') as mock_msg_builder, \
             patch('cogs.info.u_msg') as mock_u_msg:
            
            # Mock no embed being returned
            mock_msg_builder.help_embed.return_value = None
            mock_u_msg.HELP_COMMAND_ERROR = "Help command error"
            
            await info_cog.help.callback(info_cog, mock_interaction, command="invalid_command")
            
            # Verify msg_builder was called
            mock_msg_builder.help_embed.assert_called_once_with("invalid_command")
            
            # Verify error response was sent
            mock_interaction.response.send_message.assert_called_once_with("Help command error", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_error_handler_command_invoke_error_response_not_done(self, info_cog, mock_interaction):
        """Test help error handler with CommandInvokeError when response is not done"""
        
        with patch('cogs.info.u_msg') as mock_u_msg, \
             patch('cogs.info.logger') as mock_logger:
            
            mock_u_msg.HELP_COMMAND_ERROR = "Help command error"
            mock_interaction.response.is_done.return_value = False
            
            # Create a CommandInvokeError
            command = MagicMock()
            error = app_commands.CommandInvokeError(command, Exception("Test error"))
            
            await info_cog.help_error(mock_interaction, error)
            
            # Verify logging occurred
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify response was sent
            mock_interaction.response.send_message.assert_called_once_with("Help command error", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_error_handler_command_invoke_error_response_done(self, info_cog, mock_interaction):
        """Test help error handler with CommandInvokeError when response is already done"""
        
        with patch('cogs.info.u_msg') as mock_u_msg, \
             patch('cogs.info.logger') as mock_logger:
            
            mock_u_msg.HELP_COMMAND_ERROR = "Help command error"
            mock_interaction.response.is_done.return_value = True
            
            # Create a CommandInvokeError
            command = MagicMock()
            error = app_commands.CommandInvokeError(command, Exception("Test error"))
            
            await info_cog.help_error(mock_interaction, error)
            
            # Verify logging occurred
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify followup was sent instead of response
            mock_interaction.followup.send.assert_called_once_with("Help command error", ephemeral=True)
            mock_interaction.response.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_help_error_handler_other_error_types(self, info_cog, mock_interaction):
        """Test help error handler with other error types"""
        
        with patch('cogs.info.u_msg') as mock_u_msg, \
             patch('cogs.info.logger') as mock_logger:
            
            mock_u_msg.HELP_COMMAND_ERROR = "Help command error"
            mock_interaction.response.is_done.return_value = False
            
            # Create a different type of error
            error = app_commands.AppCommandError("Some other error")
            
            await info_cog.help_error(mock_interaction, error)
            
            # Verify logging occurred
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
            
            # Verify response was sent
            mock_interaction.response.send_message.assert_called_once_with("Help command error", ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_error_handler_exception_in_handler(self, info_cog, mock_interaction):
        """Test help error handler when an exception occurs in the error handler itself"""
        
        with patch('cogs.info.u_msg') as mock_u_msg, \
             patch('cogs.info.logger') as mock_logger:
            
            mock_u_msg.HELP_COMMAND_ERROR = "Help command error"
            # Make the response methods raise an exception
            mock_interaction.response.is_done.side_effect = Exception("Handler error")
            
            error = app_commands.AppCommandError("Original error")
            
            await info_cog.help_error(mock_interaction, error)
            
            # Verify the handler error was logged
            mock_logger.error.assert_called()
            mock_logger.exception.assert_called()
    
    def test_info_cog_initialization(self, mock_bot):
        """Test Info cog initialization"""
        cog = Info(mock_bot)
        assert cog.client == mock_bot
    
    @pytest.mark.asyncio
    async def test_help_command_with_empty_string_parameter(self, info_cog, mock_interaction):
        """Test help command with empty string parameter (default behavior)"""
        
        with patch('cogs.info.msg_builder') as mock_msg_builder:
            mock_embed = MagicMock()
            mock_msg_builder.help_embed.return_value = mock_embed
            
            # Test with explicit empty string
            await info_cog.help.callback(info_cog, mock_interaction, command="")
            
            # Verify msg_builder was called with empty string
            mock_msg_builder.help_embed.assert_called_once_with("")
            
            # Verify response was sent with the embed
            mock_interaction.response.send_message.assert_called_once_with(embed=mock_embed, ephemeral=True)
    
    @pytest.mark.asyncio
    async def test_help_command_integration(self, info_cog, mock_interaction):
        """Integration test for help command with realistic mock data"""
        
        with patch('cogs.info.msg_builder') as mock_msg_builder:
            # Create a more realistic mock embed
            mock_embed = MagicMock()
            mock_embed.title = "Help"
            mock_embed.description = "Available commands"
            mock_msg_builder.help_embed.return_value = mock_embed
            
            await info_cog.help.callback(info_cog, mock_interaction, command="start")
            
            # Verify the flow worked correctly
            mock_msg_builder.help_embed.assert_called_once_with("start")
            mock_interaction.response.send_message.assert_called_once_with(embed=mock_embed, ephemeral=True)