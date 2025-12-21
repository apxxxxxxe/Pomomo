"""
Scenario tests for concurrent access and race conditions.
Tests behavior when multiple users perform actions simultaneously.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
)

from cogs.control import Control
from src.session import session_manager
from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestConcurrentAccess:
    """Scenario tests for concurrent access patterns"""
    
    def setup_method(self):
        """Reset session state before each test"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def concurrent_environment(self):
        """Fixture providing environment for concurrent testing"""
        bot = MockBot()
        guild = MockGuild(id=12345, name="Test Guild")
        voice_channel = MockVoiceChannel(guild=guild)
        
        # Create multiple users
        users = []
        interactions = []
        for i in range(5):
            user = MockUser(id=10000 + i, name=f"User{i}")
            interaction = MockInteraction(user=user, guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            users.append(user)
            interactions.append(interaction)
        
        control_cog = Control(bot)
        
        return {
            'bot': bot,
            'guild': guild,
            'voice_channel': voice_channel,
            'users': users,
            'interactions': interactions,
            'control_cog': control_cog
        }
    
    @pytest.mark.asyncio
    async def test_concurrent_pomodoro_start_attempts(self, concurrent_environment):
        """Test multiple users trying to start pomodoro simultaneously"""
        env = concurrent_environment
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Setup mocks for successful validation
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            
            # Mock session manager to track session creation
            session_creation_count = 0
            original_sessions = {}
            
            def mock_session_id_from(interaction):
                return str(interaction.guild.id)
            
            def mock_active_sessions_get(key, default=None):
                return original_sessions.get(key, default)
            
            def mock_active_sessions_setitem(key, value):
                nonlocal session_creation_count
                if key not in original_sessions:
                    session_creation_count += 1
                original_sessions[key] = value
            
            def mock_active_sessions_contains(key):
                return key in original_sessions
            
            mock_session_manager.session_id_from.side_effect = mock_session_id_from
            mock_session_manager.active_sessions.__getitem__ = mock_active_sessions_get
            mock_session_manager.active_sessions.__setitem__ = mock_active_sessions_setitem
            mock_session_manager.active_sessions.__contains__ = mock_active_sessions_contains
            
            # Create mock sessions
            mock_sessions = []
            for i in range(len(env['interactions'])):
                mock_session = MagicMock()
                mock_session.ctx = env['interactions'][i]
                mock_sessions.append(mock_session)
            
            mock_session_class.side_effect = mock_sessions
            mock_controller.start_pomodoro = AsyncMock()
            
            # Create concurrent tasks
            async def start_pomodoro_task(interaction):
                try:
                    await env['control_cog'].pomodoro.callback(
                        env['control_cog'],
                        interaction,
                        pomodoro=25,
                        short_break=5,
                        long_break=20,
                        intervals=4
                    )
                    return True
                except Exception:
                    return False
            
            # Execute concurrent tasks
            tasks = [start_pomodoro_task(interaction) for interaction in env['interactions']]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify only one session was created (first wins)
            assert session_creation_count <= 1
            
            # At least one task should succeed
            successful_tasks = [r for r in results if r is True]
            assert len(successful_tasks) >= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_session_commands_same_guild(self, concurrent_environment):
        """Test concurrent commands on the same active session"""
        env = concurrent_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation, \
             patch('cogs.control.state_handler') as mock_state_handler, \
             patch('cogs.control.player') as mock_player:
            
            # Create an active session
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 1
            mock_session.state = State.POMODORO
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_controller.end = AsyncMock()
            mock_controller.resume = AsyncMock()
            mock_state_handler.transition = AsyncMock()
            mock_player.alert = AsyncMock()
            
            # Mock validation methods
            async def mock_validate_and_setup(interaction):
                return (True, str(interaction.guild.id))
            
            with patch.object(env['control_cog'], '_validate_and_setup_session', side_effect=mock_validate_and_setup):
                
                # Create concurrent command tasks
                async def skip_task(interaction):
                    try:
                        await env['control_cog'].skip.callback(env['control_cog'], interaction)
                        return "skip_success"
                    except Exception:
                        return "skip_error"
                
                async def stop_task(interaction):
                    try:
                        await env['control_cog'].stop.callback(env['control_cog'], interaction)
                        return "stop_success"
                    except Exception:
                        return "stop_error"
                
                # Execute concurrent skip and stop commands
                tasks = [
                    skip_task(env['interactions'][0]),
                    skip_task(env['interactions'][1]),
                    stop_task(env['interactions'][2])
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify commands were executed (order may vary due to concurrency)
                assert len(results) == 3
                successful_results = [r for r in results if isinstance(r, str) and "_success" in r]
                assert len(successful_results) >= 1  # At least one should succeed
    
    @pytest.mark.asyncio
    async def test_concurrent_different_guild_sessions(self, concurrent_environment):
        """Test concurrent sessions in different guilds"""
        env = concurrent_environment
        
        # Create interactions for different guilds
        guilds = []
        guild_interactions = []
        for i in range(3):
            guild = MockGuild(id=20000 + i, name=f"Guild{i}")
            user = MockUser(id=30000 + i, name=f"User{i}")
            interaction = MockInteraction(user=user, guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = MockVoiceChannel(guild=guild)
            guilds.append(guild)
            guild_interactions.append(interaction)
        
        with patch('cogs.control.Settings') as mock_settings, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.Session') as mock_session_class, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Setup mocks
            mock_settings.is_valid_interaction = AsyncMock(return_value=True)
            mock_voice_validation.can_connect.return_value = True
            mock_voice_validation.is_voice_alone.return_value = True
            mock_controller.start_pomodoro = AsyncMock()
            
            # Mock sessions for different guilds
            mock_sessions = []
            for interaction in guild_interactions:
                mock_session = MagicMock()
                mock_session.ctx = interaction
                mock_sessions.append(mock_session)
            
            mock_session_class.side_effect = mock_sessions
            
            # Create concurrent tasks for different guilds
            async def start_guild_session(interaction):
                try:
                    await env['control_cog'].pomodoro.callback(
                        env['control_cog'],
                        interaction,
                        pomodoro=25,
                        short_break=5,
                        long_break=20,
                        intervals=4
                    )
                    return f"success_{interaction.guild.id}"
                except Exception as e:
                    return f"error_{interaction.guild.id}_{e}"
            
            # Execute concurrent tasks for different guilds
            tasks = [start_guild_session(interaction) for interaction in guild_interactions]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All tasks should succeed since they're in different guilds
            successful_results = [r for r in results if isinstance(r, str) and "success_" in r]
            assert len(successful_results) == len(guild_interactions)
            
            # Verify sessions were created (using mocked session creation)
            assert len(successful_results) == len(guild_interactions), f"Expected {len(guild_interactions)} successful sessions, got {len(successful_results)}"
            
            # Verify session controller was called for each guild
            assert mock_controller.start_pomodoro.call_count == len(guild_interactions)
    
    @pytest.mark.asyncio
    async def test_session_lock_contention(self, concurrent_environment):
        """Test session lock behavior under contention"""
        env = concurrent_environment
        
        # Test with real session_manager lock mechanisms
        guild_id = str(env['guild'].id)
        
        # Create multiple tasks that try to acquire locks
        lock_acquisition_order = []
        lock_acquisition_times = {}
        
        async def acquire_lock_task(task_id):
            import time
            start_time = time.time()
            
            # Simulate lock acquisition
            if guild_id not in session_manager.session_locks:
                session_manager.session_locks[guild_id] = asyncio.Lock()
            
            async with session_manager.session_locks[guild_id]:
                lock_acquisition_order.append(task_id)
                lock_acquisition_times[task_id] = time.time() - start_time
                
                # Simulate some work while holding the lock
                await asyncio.sleep(0.01)
                
                return f"completed_{task_id}"
        
        # Execute concurrent lock acquisition tasks
        tasks = [acquire_lock_task(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all tasks completed
        assert len(results) == 5
        assert all("completed_" in result for result in results)
        
        # Verify locks were acquired in some order (serialized)
        assert len(lock_acquisition_order) == 5
        assert len(set(lock_acquisition_order)) == 5  # All unique task IDs
    
    @pytest.mark.asyncio
    async def test_concurrent_auto_mute_operations(self, concurrent_environment):
        """Test concurrent auto-mute enable/disable operations"""
        env = concurrent_environment
        
        from cogs.subscribe import Subscribe
        subscribe_cog = Subscribe(env['bot'])
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation:
            
            # Create mock session with auto_mute functionality
            mock_session = MagicMock()
            mock_session.ctx = env['interactions'][0]
            mock_session.auto_mute = MagicMock()
            mock_session.auto_mute.all = False
            
            # Track auto_mute operations
            auto_mute_operations = []
            
            async def mock_handle_all(interaction, enable=None):
                auto_mute_operations.append(f"handle_all_{interaction.user.id}")
                await asyncio.sleep(0.01)  # Simulate operation time
                if enable is not None:
                    mock_session.auto_mute.all = enable
                else:
                    mock_session.auto_mute.all = not mock_session.auto_mute.all
            
            mock_session.auto_mute.handle_all = mock_handle_all
            
            # Setup other mocks
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # Create concurrent auto-mute tasks
            async def enable_auto_mute_task(interaction):
                try:
                    await subscribe_cog.enableautomute.callback(subscribe_cog, interaction)
                    return f"enable_success_{interaction.user.id}"
                except Exception:
                    return f"enable_error_{interaction.user.id}"
            
            async def disable_auto_mute_task(interaction):
                try:
                    await subscribe_cog.disableautomute.callback(subscribe_cog, interaction)
                    return f"disable_success_{interaction.user.id}"
                except Exception:
                    return f"disable_error_{interaction.user.id}"
            
            # Execute concurrent auto-mute operations
            tasks = [
                enable_auto_mute_task(env['interactions'][0]),
                enable_auto_mute_task(env['interactions'][1]),
                disable_auto_mute_task(env['interactions'][2])
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify operations completed
            assert len(results) == 3
            
            # Verify auto_mute operations were called
            assert len(auto_mute_operations) >= 1
    
    @pytest.mark.asyncio
    async def test_high_frequency_command_execution(self, concurrent_environment):
        """Test system behavior under high-frequency command execution"""
        env = concurrent_environment
        
        with patch('cogs.control.session_manager') as mock_session_manager, \
             patch('cogs.control.session_controller') as mock_controller, \
             patch('cogs.control.voice_validation') as mock_voice_validation:
            
            # Create active session
            mock_session = MagicMock()
            mock_session.stats.pomos_completed = 1
            mock_session.state = State.POMODORO
            mock_session_manager.get_session_interaction = AsyncMock(return_value=mock_session)
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_controller.end = AsyncMock()
            
            # Mock validation
            with patch.object(env['control_cog'], '_validate_and_setup_session', return_value=(True, "test_session")):
                
                # Create high-frequency tasks
                async def rapid_stop_task(interaction, task_id):
                    try:
                        await env['control_cog'].stop.callback(env['control_cog'], interaction)
                        return f"stop_success_{task_id}"
                    except Exception:
                        return f"stop_error_{task_id}"
                
                # Execute many rapid commands
                tasks = []
                for i in range(20):
                    # Use different interactions to avoid interaction-specific locks
                    interaction_index = i % len(env['interactions'])
                    tasks.append(rapid_stop_task(env['interactions'][interaction_index], i))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify all tasks completed (some may error due to rapid execution)
                assert len(results) == 20
                
                # At least some should succeed
                successful_results = [r for r in results if isinstance(r, str) and "_success" in r]
                assert len(successful_results) >= 1
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_under_concurrency(self, concurrent_environment):
        """Test proper resource cleanup under concurrent operations"""
        env = concurrent_environment
        
        # Track resource allocation and cleanup
        allocated_resources = set()
        cleaned_resources = set()
        
        class MockResourceSession:
            def __init__(self, session_id):
                self.session_id = session_id
                allocated_resources.add(session_id)
                self.timer = MagicMock()
                self.stats = MagicMock()
            
            def cleanup(self):
                cleaned_resources.add(self.session_id)
        
        with patch('src.session.session_manager.deactivate') as mock_deactivate:
            
            async def mock_deactivate_func(session):
                session.cleanup()
                # Simulate cleanup work
                await asyncio.sleep(0.01)
            
            mock_deactivate.side_effect = mock_deactivate_func
            
            # Create multiple sessions and clean them up concurrently
            sessions = []
            for i in range(10):
                session = MockResourceSession(f"session_{i}")
                sessions.append(session)
                
                # Add to session_manager (simulate activation)
                guild_id = f"guild_{i}"
                session_manager.active_sessions[guild_id] = session
            
            # Concurrent cleanup tasks
            cleanup_tasks = [session_manager.deactivate(session) for session in sessions]
            await asyncio.gather(*cleanup_tasks)
            
            # Verify all resources were allocated and cleaned up
            assert len(allocated_resources) == 10
            assert len(cleaned_resources) == 10
            assert allocated_resources == cleaned_resources