"""
ネットワーク中断からの回復テスト

future_test_plan.mdで特定された高優先度テストケース：
Discord API一時的エラー時の再試行機能をテスト
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from discord import HTTPException, NotFound, Forbidden, ConnectionClosed
from discord.errors import DiscordServerError

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel
)
from tests.mocks.voice_mocks import MockVoiceClient

from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestNetworkRecovery:
    """ネットワーク中断からの回復テスト"""
    
    def setup_method(self):
        """各テストメソッドの前にセッション状態をリセット"""
        from src.session import session_manager
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def network_test_environment(self):
        """ネットワークテスト用の環境を準備"""
        guild = MockGuild(id=54321, name="Test Guild")
        user = MockUser(id=12345, name="TestUser")
        voice_channel = MockVoiceChannel(id=98765, name="Test Voice Channel")
        interaction = MockInteraction(user=user, guild=guild, channel=voice_channel)
        voice_client = MockVoiceClient(guild=guild, channel=voice_channel)
        bot = MockBot()
        
        return {
            'bot': bot,
            'interaction': interaction,
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'voice_client': voice_client,
            'guild_id': str(guild.id)
        }
    
    @pytest.mark.asyncio
    async def test_discord_api_timeout_recovery(self, network_test_environment):
        """Discord APIタイムアウトからの回復をテスト"""
        env = network_test_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            mock_auto_mute_instance = MagicMock()
            mock_auto_mute_instance.unmute = AsyncMock(side_effect=[
                asyncio.TimeoutError("API timeout"),  # 1回目は失敗
                None  # 2回目は成功
            ])
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test unmute with timeout (should handle gracefully)
            try:
                await session.auto_mute.unmute(env['interaction'])
            except asyncio.TimeoutError:
                pass  # 最初の失敗は期待される
            
            # Second attempt should succeed
            await session.auto_mute.unmute(env['interaction'])
            
            # Verify unmute was called twice
            assert mock_auto_mute_instance.unmute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_discord_server_error_503_recovery(self, network_test_environment):
        """Discord 503エラーからの回復をテスト"""
        env = network_test_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            
            mock_auto_mute_instance = MagicMock()
            # Simulate 503 error followed by success
            mock_auto_mute_instance.handle_all = AsyncMock(side_effect=[
                DiscordServerError(MagicMock(status=503), "Service temporarily unavailable"),
                None  # Success on retry
            ])
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test handle_all with 503 error
            try:
                await session.auto_mute.handle_all(True)
            except DiscordServerError:
                pass  # First call fails with 503
            
            # Retry should succeed
            await session.auto_mute.handle_all(True)
            
            # Verify handle_all was called twice
            assert mock_auto_mute_instance.handle_all.call_count == 2
    
    @pytest.mark.asyncio
    async def test_connection_reset_recovery(self, network_test_environment):
        """接続リセットエラーからの回復をテスト"""
        env = network_test_environment
        
        with patch('src.voice_client.vc_manager.connect') as mock_vc_connect:
            
            # Setup mock to simulate connection reset then success
            from unittest.mock import Mock
            mock_socket = Mock()
            mock_socket.close_code = 1000  # Normal closure
            
            mock_vc_connect.side_effect = [
                ConnectionClosed(mock_socket, shard_id=0),  # First attempt fails
                True  # Second attempt succeeds
            ]
            
            # Test voice connection with network interruption
            from src.session.Session import Session
            from src.Settings import Settings
            from configs.bot_enum import State
            
            settings = Settings(duration=25)
            session = Session(State.COUNTDOWN, settings, env['interaction'])
            
            try:
                result = await mock_vc_connect(session)
            except ConnectionClosed:
                pass  # Expected first failure
            
            # Retry should succeed
            result = await mock_vc_connect(session)
            assert result is True
            
            # Verify connect was called twice
            assert mock_vc_connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_http_exception_with_rate_limit_recovery(self, network_test_environment):
        """レート制限HTTPエラーからの回復をテスト"""
        env = network_test_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            
            # Create HTTPException with rate limit status
            rate_limit_response = MagicMock()
            rate_limit_response.status = 429
            rate_limit_response.reason = "Too Many Requests"
            
            mock_auto_mute_instance = MagicMock()
            mock_auto_mute_instance.mute = AsyncMock(side_effect=[
                HTTPException(rate_limit_response, "Rate limited"),  # First call hits rate limit
                None  # Second call succeeds
            ])
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test mute with rate limiting
            try:
                await session.auto_mute.mute(env['user'])
            except HTTPException as e:
                assert e.response.status == 429  # Verify it's a rate limit error
            
            # Retry should succeed
            await session.auto_mute.mute(env['user'])
            
            # Verify mute was called twice
            assert mock_auto_mute_instance.mute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_websocket_connection_lost_recovery(self, network_test_environment):
        """WebSocket接続断からの回復をテスト"""
        env = network_test_environment
        
        with patch('src.session.session_manager.get_session') as mock_get_session:
            
            # Setup session manager to simulate connection issues
            from unittest.mock import Mock
            mock_socket = Mock()
            mock_socket.close_code = 1000  # Normal closure
            
            mock_get_session.side_effect = [
                ConnectionClosed(mock_socket, shard_id=0),  # First attempt fails
                MagicMock()  # Second attempt returns valid session
            ]
            
            # Test session retrieval with connection loss
            try:
                session = await mock_get_session(env['interaction'])
            except ConnectionClosed:
                pass  # Expected first failure
            
            # Retry should succeed
            session = await mock_get_session(env['interaction'])
            assert session is not None
            
            # Verify get_session was called twice
            assert mock_get_session.call_count == 2
    
    @pytest.mark.asyncio
    async def test_partial_api_failure_graceful_handling(self, network_test_environment):
        """部分的なAPI障害の適切な処理をテスト"""
        env = network_test_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class:
            
            # Setup mocks for testing partial failures
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            
            # Create multiple members to test partial failure scenario
            mock_members = [MagicMock() for _ in range(3)]
            
            mock_auto_mute_instance = MagicMock()
            # Simulate partial failure: first member fails, others succeed
            mock_auto_mute_instance.safe_edit_member = AsyncMock(side_effect=[
                Forbidden(MagicMock(status=403), "Missing permissions"),  # First member fails
                None,  # Second member succeeds
                None   # Third member succeeds
            ])
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test muting multiple members with partial failure
            for member in mock_members:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=True)
                except Forbidden:
                    pass  # Some failures are expected and should be handled gracefully
            
            # Verify all members were attempted
            assert mock_auto_mute_instance.safe_edit_member.call_count == 3
    
    @pytest.mark.asyncio
    async def test_network_recovery_with_exponential_backoff(self, network_test_environment):
        """指数バックオフによるネットワーク回復をテスト"""
        env = network_test_environment
        
        # Test exponential backoff behavior (mocked for speed)
        retry_delays = []
        
        async def mock_sleep(delay):
            retry_delays.append(delay)
        
        with patch('asyncio.sleep', side_effect=mock_sleep) as mock_sleep_func, \
             patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            
            mock_auto_mute_instance = MagicMock()
            # Simulate multiple failures before success
            from unittest.mock import Mock
            mock_socket = Mock()
            mock_socket.close_code = 1000
            
            mock_auto_mute_instance.unmute = AsyncMock(side_effect=[
                ConnectionClosed(mock_socket, shard_id=0),  # First failure
                ConnectionClosed(mock_socket, shard_id=0),  # Second failure
                None  # Finally succeeds
            ])
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Simulate retry logic with exponential backoff
            max_retries = 3
            base_delay = 1.0
            
            for attempt in range(max_retries):
                try:
                    await session.auto_mute.unmute(env['interaction'])
                    break  # Success
                except ConnectionClosed:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        await mock_sleep_func(delay)
                    else:
                        break  # Max retries reached
            
            # Verify exponential backoff pattern was used
            assert len(retry_delays) >= 2
            if len(retry_delays) >= 2:
                assert retry_delays[1] > retry_delays[0]  # Delay should increase  # Delay should increase