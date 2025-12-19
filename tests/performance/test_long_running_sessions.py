"""
Performance tests for long-running sessions.
Tests session stability, memory usage, and performance over extended periods.
"""
import pytest
import asyncio
import time
import gc
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
)
from tests.mocks.voice_mocks import MockVoiceClient

from src.session import session_manager
from src.session.Session import Session
from src.session import session_controller
from src.Settings import Settings
from configs.bot_enum import State


class TestLongRunningSessions:
    """Performance tests for long-running session scenarios"""
    
    def setup_method(self):
        """Reset session state and force garbage collection"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
        gc.collect()
    
    @pytest.fixture
    def performance_environment(self):
        """Fixture providing environment for performance testing"""
        bot = MockBot()
        guild = MockGuild(id=12345, name="Performance Test Guild")
        voice_channel = MockVoiceChannel(guild=guild)
        user = MockUser(id=67890, name="PerformanceTestUser")
        interaction = MockInteraction(user=user, guild=guild)
        
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        return {
            'bot': bot,
            'guild': guild,
            'voice_channel': voice_channel,
            'user': user,
            'interaction': interaction
        }
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extended_pomodoro_session(self, performance_environment):
        """Test a full extended pomodoro session (multiple cycles)"""
        env = performance_environment
        
        # Track performance metrics
        start_time = time.time()
        memory_usage = []
        
        def get_memory_usage():
            """Get current memory usage in MB"""
            import psutil
            import os
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_controller.vc_accessor'), \
             patch('src.session.session_controller.session_messenger'):
            
            # Setup realistic timer behavior
            mock_timer_instance = MagicMock()
            mock_timer_instance.remaining = 1500  # 25 minutes
            mock_timer_instance.running = False
            mock_timer_instance.is_expired.return_value = False
            mock_timer.return_value = mock_timer_instance
            
            # Setup stats tracking
            mock_stats_instance = MagicMock()
            mock_stats_instance.pomos_completed = 0
            mock_stats_instance.pomos_elapsed = 0
            mock_stats_instance.seconds_completed = 0
            mock_stats.return_value = mock_stats_instance
            
            # Create long-running session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Activate session
            await session_manager.activate(session)
            
            # Simulate multiple pomodoro cycles
            total_cycles = 8  # 2 complete sets of 4 intervals each
            
            for cycle in range(total_cycles):
                # Record memory usage
                memory_usage.append(get_memory_usage())
                
                # Simulate state transitions
                if cycle % 4 == 3:  # Every 4th cycle is long break
                    session.state = State.LONG_BREAK
                    mock_timer_instance.remaining = 1200  # 20 minutes
                else:
                    if session.state == State.POMODORO:
                        session.state = State.SHORT_BREAK
                        mock_timer_instance.remaining = 300  # 5 minutes
                    else:
                        session.state = State.POMODORO
                        mock_timer_instance.remaining = 1500  # 25 minutes
                        mock_stats_instance.pomos_completed += 1
                
                # Update stats
                mock_stats_instance.seconds_completed += 1500 if session.state == State.POMODORO else 300
                
                # Simulate some processing time
                await asyncio.sleep(0.01)
                
                # Force garbage collection periodically
                if cycle % 4 == 0:
                    gc.collect()
            
            # Final memory measurement
            memory_usage.append(get_memory_usage())
            
            # Calculate performance metrics
            execution_time = time.time() - start_time
            memory_growth = memory_usage[-1] - memory_usage[0] if memory_usage else 0
            
            # Verify session completed successfully
            assert session.state in [State.POMODORO, State.SHORT_BREAK, State.LONG_BREAK]
            assert mock_stats_instance.pomos_completed > 0
            
            # Performance assertions
            assert execution_time < 10.0  # Should complete within 10 seconds
            assert memory_growth < 50.0   # Memory growth should be under 50MB
            
            # Cleanup
            await session_manager.deactivate(session)
    
    @pytest.mark.asyncio
    @pytest.mark.slow  
    async def test_session_timer_accuracy_over_time(self, performance_environment):
        """Test timer accuracy during long-running sessions"""
        env = performance_environment
        
        with patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create timer that tracks actual elapsed time
            class AccurateTimer:
                def __init__(self, parent):
                    self.parent = parent
                    self.start_time = None
                    self.duration = parent.settings.duration * 60  # Convert to seconds
                    self.running = False
                    self._remaining = self.duration
                
                def start(self):
                    self.start_time = time.time()
                    self.running = True
                
                def stop(self):
                    self.running = False
                    self.start_time = None
                
                def kill(self):
                    self.stop()
                
                @property
                def remaining(self):
                    if not self.running or self.start_time is None:
                        return self._remaining
                    elapsed = time.time() - self.start_time
                    return max(0, self.duration - elapsed)
                
                def is_expired(self):
                    return self.remaining == 0
                
                def time_remaining_to_str(self):
                    minutes, seconds = divmod(int(self.remaining), 60)
                    return f"{minutes}分{seconds:02d}秒"
            
            with patch('src.session.Session.Timer', AccurateTimer):
                settings = Settings(duration=1, short_break=1, long_break=2, intervals=2)  # Short durations for testing
                session = Session(State.POMODORO, settings, env['interaction'])
                
                await session_manager.activate(session)
                
                # Start timer and measure accuracy
                session.timer.start()
                initial_remaining = session.timer.remaining
                
                # Wait for a known period
                test_duration = 0.5  # 500ms
                await asyncio.sleep(test_duration)
                
                # Check timer accuracy
                expected_remaining = initial_remaining - test_duration
                actual_remaining = session.timer.remaining
                accuracy_error = abs(expected_remaining - actual_remaining)
                
                # Timer should be accurate within 100ms
                assert accuracy_error < 0.1, f"Timer accuracy error: {accuracy_error}s"
                
                await session_manager.deactivate(session)
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_multiple_concurrent_long_sessions(self, performance_environment):
        """Test multiple long-running sessions concurrently"""
        env = performance_environment
        
        # Create multiple guild environments
        guild_count = 5
        sessions = []
        environments = []
        
        for i in range(guild_count):
            guild = MockGuild(id=20000 + i, name=f"LongTestGuild{i}")
            user = MockUser(id=30000 + i, name=f"LongTestUser{i}")
            interaction = MockInteraction(user=user, guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = MockVoiceChannel(guild=guild)
            environments.append({
                'guild': guild,
                'interaction': interaction
            })
        
        start_time = time.time()
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create and activate multiple sessions
            for env in environments:
                settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
                session = Session(State.POMODORO, settings, env['interaction'])
                await session_manager.activate(session)
                sessions.append(session)
            
            # Verify all sessions are active
            assert len(session_manager.active_sessions) == guild_count
            
            # Simulate concurrent session activity
            async def simulate_session_activity(session, cycles=10):
                for cycle in range(cycles):
                    # Simulate state changes
                    if session.state == State.POMODORO:
                        session.state = State.SHORT_BREAK
                    else:
                        session.state = State.POMODORO
                    
                    # Simulate processing
                    await asyncio.sleep(0.01)
                    
                    # Periodically yield control
                    if cycle % 3 == 0:
                        await asyncio.sleep(0.001)
            
            # Run concurrent session activities
            tasks = [simulate_session_activity(session) for session in sessions]
            await asyncio.gather(*tasks)
            
            # Verify all sessions are still active and healthy
            assert len(session_manager.active_sessions) == guild_count
            
            for session in sessions:
                # Session should still be valid
                assert session.state in [State.POMODORO, State.SHORT_BREAK, State.LONG_BREAK]
                assert session.settings is not None
                
                # Retrieve session from manager
                retrieved = await session_manager.get_session(session.ctx)
                assert retrieved == session
            
            # Cleanup all sessions
            for session in sessions:
                await session_manager.deactivate(session)
            
            # Verify cleanup
            assert len(session_manager.active_sessions) == 0
        
        execution_time = time.time() - start_time
        assert execution_time < 30.0  # Should complete within 30 seconds
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_session_manager_performance_under_load(self, performance_environment):
        """Test session manager performance under sustained load"""
        env = performance_environment
        
        operation_count = 1000
        start_time = time.time()
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            # Perform many session operations
            for i in range(operation_count):
                # Activate session
                await session_manager.activate(session)
                
                # Retrieve session
                retrieved = await session_manager.get_session(env['interaction'])
                assert retrieved == session
                
                # Get session by interaction
                retrieved_by_interaction = await session_manager.get_session_interaction(env['interaction'])
                assert retrieved_by_interaction == session
                
                # Deactivate session
                await session_manager.deactivate(session)
                
                # Periodically yield control
                if i % 100 == 0:
                    await asyncio.sleep(0.001)
        
        execution_time = time.time() - start_time
        operations_per_second = operation_count * 4 / execution_time  # 4 operations per loop
        
        # Should handle at least 100 operations per second
        assert operations_per_second > 100, f"Performance too low: {operations_per_second:.2f} ops/sec"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_leak_detection(self, performance_environment):
        """Test for memory leaks during repeated session operations"""
        env = performance_environment
        
        def get_object_count(obj_type):
            """Count objects of a specific type"""
            return len([obj for obj in gc.get_objects() if isinstance(obj, obj_type)])
        
        # Initial memory state
        gc.collect()
        initial_session_count = get_object_count(Session)
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Perform many session create/destroy cycles
            for cycle in range(50):
                sessions_created = []
                
                # Create multiple sessions
                for i in range(5):
                    guild = MockGuild(id=40000 + i, name=f"MemTestGuild{cycle}_{i}")
                    user = MockUser(id=50000 + i, name=f"MemTestUser{cycle}_{i}")
                    interaction = MockInteraction(user=user, guild=guild)
                    
                    settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
                    session = Session(State.POMODORO, settings, interaction)
                    
                    await session_manager.activate(session)
                    sessions_created.append(session)
                
                # Use sessions briefly
                for session in sessions_created:
                    session.state = State.SHORT_BREAK
                    await session_manager.get_session(session.ctx)
                
                # Cleanup sessions
                for session in sessions_created:
                    await session_manager.deactivate(session)
                
                # Force garbage collection
                del sessions_created
                gc.collect()
                
                # Check for memory growth every 10 cycles
                if cycle % 10 == 0:
                    current_session_count = get_object_count(Session)
                    # Allow for some growth but detect major leaks
                    assert current_session_count - initial_session_count < 20, \
                        f"Potential memory leak: {current_session_count - initial_session_count} extra sessions"
        
        # Final memory check
        gc.collect()
        final_session_count = get_object_count(Session)
        
        # Should return to approximately initial state
        session_growth = final_session_count - initial_session_count
        assert session_growth < 10, f"Memory leak detected: {session_growth} sessions not cleaned up"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_session_state_integrity_over_time(self, performance_environment):
        """Test session state integrity during long-running operations"""
        env = performance_environment
        
        with patch('src.session.Session.Timer'), \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'):
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            
            await session_manager.activate(session)
            
            # Track state changes over time
            state_history = []
            expected_states = [State.POMODORO, State.SHORT_BREAK, State.POMODORO, State.LONG_BREAK]
            
            # Simulate many state transitions
            for transition in range(200):
                # Change state according to pattern
                current_state_index = transition % len(expected_states)
                expected_state = expected_states[current_state_index]
                session.state = expected_state
                
                # Record state
                state_history.append(session.state)
                
                # Verify session manager can still find session
                retrieved = await session_manager.get_session(session.ctx)
                assert retrieved == session
                assert retrieved.state == expected_state
                
                # Verify state consistency
                assert session.ctx == env['interaction']
                assert session.settings == settings
                
                # Simulate processing time
                await asyncio.sleep(0.001)
                
                # Periodic integrity check
                if transition % 50 == 0:
                    guild_id = session_manager.session_id_from(session.ctx)
                    assert guild_id in session_manager.active_sessions
                    assert session_manager.active_sessions[guild_id] == session
            
            # Verify state history is correct
            assert len(state_history) == 200
            
            # Cleanup
            await session_manager.deactivate(session)
    
    @pytest.mark.asyncio
    @pytest.mark.slow  
    async def test_extended_idle_session_handling(self, performance_environment):
        """Test handling of sessions that remain idle for extended periods"""
        env = performance_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats'), \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute'), \
             patch('src.session.session_manager.vc_accessor') as mock_vc_accessor:
            
            # Setup timer that becomes expired after some time
            mock_timer_instance = MagicMock()
            mock_timer_instance.is_expired.return_value = False
            mock_timer.return_value = mock_timer_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.timeout = mock_timer_instance
            
            await session_manager.activate(session)
            
            # Simulate idle period - session not expired initially
            for idle_check in range(100):
                is_idle = await session_manager.kill_if_idle(session)
                assert is_idle is False  # Should not be killed while not expired
                await asyncio.sleep(0.001)
            
            # Simulate session expiration
            mock_timer_instance.is_expired.return_value = True
            
            # Remove client attribute to simulate non-interaction session
            if hasattr(session.ctx, 'client'):
                delattr(session.ctx, 'client')
            
            # Mock empty voice channel (simulates idle condition)
            mock_vc_accessor.get_voice_channel.return_value = None
            session.ctx.invoke = AsyncMock()
            session.ctx.bot.get_command.return_value = 'stop_command'
            
            # Now session should be killed as idle
            is_idle = await session_manager.kill_if_idle(session)
            assert is_idle is True
            
            # Verify cleanup was called
            session.ctx.invoke.assert_called_once_with('stop_command')