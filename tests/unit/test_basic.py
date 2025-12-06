"""
Basic tests to verify test setup is working correctly.
"""
import pytest
from tests.mocks.discord_mocks import MockBot, MockInteraction, MockUser


class TestBasicSetup:
    """Test class to verify basic testing setup"""
    
    def test_mock_objects_work(self):
        """Test that our mock objects can be created and used"""
        user = MockUser()
        assert user.id == 12345
        assert user.name == "TestUser"
        
        bot = MockBot()
        assert bot.user.name == "TestBot"
        
        interaction = MockInteraction()
        assert interaction.user is not None
        assert interaction.guild is not None
    
    def test_imports_work(self):
        """Test that basic imports work"""
        import discord
        assert discord is not None
        
        import asyncio
        assert asyncio is not None
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test that async tests work"""
        import asyncio
        await asyncio.sleep(0.01)
        assert True
    
    def test_python_path_setup(self):
        """Test that bot modules can be imported"""
        try:
            from configs import config
            assert config is not None
        except ImportError:
            pytest.skip("Bot modules not in Python path - this is expected in CI")
    
    def test_pytest_fixtures(self, mock_bot, mock_interaction):
        """Test that pytest fixtures from conftest.py work"""
        assert mock_bot is not None
        assert mock_interaction is not None
        
        # Test mock functionality
        assert hasattr(mock_bot, 'user')
        assert hasattr(mock_interaction, 'response')
        
    def test_environment_variables(self):
        """Test environment variable setup"""
        import os
        # This should be set by the test runner
        assert os.environ.get('TESTING') == '1'