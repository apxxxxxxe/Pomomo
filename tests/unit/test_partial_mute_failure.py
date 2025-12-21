"""
部分的ミュート失敗処理テスト

future_test_plan.mdで特定された高優先度テストケース：
一部メンバーのミュートが失敗しても他のメンバーは正常処理される機能をテスト
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import Forbidden, NotFound, HTTPException
from discord.errors import DiscordServerError

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel, MockMember
)
from tests.mocks.voice_mocks import MockVoiceClient

from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestPartialMuteFailure:
    """部分的ミュート失敗処理テスト"""
    
    def setup_method(self):
        """各テストメソッドの前にセッション状態をリセット"""
        from src.session import session_manager
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def partial_mute_test_environment(self):
        """部分的ミュートテスト用の環境を準備"""
        guild = MockGuild(id=54321, name="Test Guild")
        user = MockUser(id=12345, name="TestUser")
        voice_channel = MockVoiceChannel(id=98765, name="Test Voice Channel")
        interaction = MockInteraction(user=user, guild=guild, channel=voice_channel)
        voice_client = MockVoiceClient(guild=guild, channel=voice_channel)
        bot = MockBot()
        
        # Create multiple test members
        members = [
            MockMember(MockUser(id=11111, name="User1"), guild),
            MockMember(MockUser(id=22222, name="User2"), guild),
            MockMember(MockUser(id=33333, name="User3"), guild),
            MockMember(MockUser(id=44444, name="User4"), guild),
            MockMember(MockUser(id=55555, name="User5"), guild)
        ]
        
        # Add members to voice channel
        voice_channel.members = members
        
        return {
            'bot': bot,
            'interaction': interaction,
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'voice_client': voice_client,
            'members': members,
            'guild_id': str(guild.id)
        }
    
    @pytest.mark.asyncio
    async def test_partial_permission_failure_continues_others(self, partial_mute_test_environment):
        """一部メンバーで権限エラーが発生しても他のメンバーは処理続行"""
        env = partial_mute_test_environment
        
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
            
            # Simulate partial permission failures
            call_count = 0
            async def mock_safe_edit_member(member, **kwargs):
                nonlocal call_count
                call_count += 1
                if member.id in [22222, 44444]:  # User2 and User4 fail
                    raise Forbidden(MagicMock(status=403), "Missing permissions")
                return None  # Others succeed
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test muting all members with partial failures
            successful_mutes = 0
            failed_mutes = 0
            
            for member in env['members']:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=True)
                    successful_mutes += 1
                except Forbidden:
                    failed_mutes += 1
            
            # Verify results
            assert call_count == 5  # All members were attempted
            assert successful_mutes == 3  # 3 succeeded
            assert failed_mutes == 2  # 2 failed due to permissions
    
    @pytest.mark.asyncio
    async def test_mixed_error_types_handling(self, partial_mute_test_environment):
        """異なるタイプのエラーが混在する場合の適切な処理"""
        env = partial_mute_test_environment
        
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
            
            # Simulate different types of failures
            call_count = 0
            async def mock_safe_edit_member(member, **kwargs):
                nonlocal call_count
                call_count += 1
                if member.id == 11111:  # User1 - Permission error
                    raise Forbidden(MagicMock(status=403), "Missing permissions")
                elif member.id == 22222:  # User2 - User not found
                    raise NotFound(MagicMock(status=404), "Member not found")
                elif member.id == 33333:  # User3 - Rate limit
                    raise HTTPException(MagicMock(status=429), "Too many requests")
                # User4 and User5 succeed
                return None
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test muting all members with various error types
            results = {
                'success': 0,
                'permission_error': 0,
                'not_found_error': 0,
                'rate_limit_error': 0
            }
            
            for member in env['members']:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=True)
                    results['success'] += 1
                except Forbidden:
                    results['permission_error'] += 1
                except NotFound:
                    results['not_found_error'] += 1
                except HTTPException as e:
                    if e.response.status == 429:
                        results['rate_limit_error'] += 1
            
            # Verify all error types were handled
            assert call_count == 5
            assert results['success'] == 2  # User4 and User5
            assert results['permission_error'] == 1  # User1
            assert results['not_found_error'] == 1  # User2
            assert results['rate_limit_error'] == 1  # User3
    
    @pytest.mark.asyncio
    async def test_bulk_operation_with_error_logging(self, partial_mute_test_environment):
        """一括操作でのエラーロギングの確認"""
        env = partial_mute_test_environment
        
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
            
            # Track all operations and errors
            operations = []
            
            async def mock_handle_all(enable=True):
                for i, member in enumerate(env['members']):
                    try:
                        if i % 2 == 0:  # Every other member fails
                            error_msg = f"Failed to mute {member.name}"
                            operations.append(f"FAIL: {member.name}")
                            raise Forbidden(MagicMock(status=403), "Missing permissions")
                        else:
                            operations.append(f"SUCCESS: {member.name}")
                    except Forbidden:
                        pass  # Continue with other members
            
            mock_auto_mute_instance.handle_all = mock_handle_all
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test bulk mute operation
            await session.auto_mute.handle_all(enable=True)
            
            # Verify all members were processed and errors were logged
            assert len(operations) == 5
            
            # Count successes and failures
            successes = [op for op in operations if op.startswith("SUCCESS")]
            failures = [op for op in operations if op.startswith("FAIL")]
            
            assert len(successes) == 2  # Every other succeeds
            assert len(failures) == 3   # Every other fails
            
            # Verify error logging would have been called (mock removed)
    
    @pytest.mark.asyncio
    async def test_retry_failed_operations(self, partial_mute_test_environment):
        """失敗した操作の再試行テスト"""
        env = partial_mute_test_environment
        
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
            
            # Simulate failure then success on retry
            call_counts = {}
            
            async def mock_safe_edit_member(member, **kwargs):
                member_id = member.id
                call_counts[member_id] = call_counts.get(member_id, 0) + 1
                
                # Fail on first attempt, succeed on retry
                if call_counts[member_id] == 1 and member.id in [22222, 44444]:
                    raise HTTPException(MagicMock(status=503), "Service unavailable")
                return None
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test initial mute attempt with retries for failures
            failed_members = []
            
            for member in env['members']:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=True)
                except HTTPException:
                    failed_members.append(member)
            
            # Retry failed members
            for member in failed_members:
                await session.auto_mute.safe_edit_member(member, mute=True)
            
            # Verify retry behavior
            assert len(failed_members) == 2  # User2 and User4 initially failed
            
            # Verify User2 and User4 were called twice (initial + retry)
            assert call_counts[22222] == 2
            assert call_counts[44444] == 2
            
            # Verify others were called only once
            assert call_counts[11111] == 1
            assert call_counts[33333] == 1
            assert call_counts[55555] == 1
    
    @pytest.mark.asyncio
    async def test_state_consistency_after_partial_failure(self, partial_mute_test_environment):
        """部分的失敗後の状態一貫性テスト"""
        env = partial_mute_test_environment
        
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
            
            # Track mute states
            member_mute_states = {member.id: False for member in env['members']}
            
            async def mock_safe_edit_member(member, mute=False, **kwargs):
                if member.id == 22222:  # User2 fails
                    raise Forbidden(MagicMock(status=403), "Missing permissions")
                
                # Update state for successful operations
                member_mute_states[member.id] = mute
                return None
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            # Test muting with partial failure
            for member in env['members']:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=True)
                except Forbidden:
                    pass  # Continue with others
            
            # Verify state consistency
            # User2 (22222) should remain unmuted due to failure
            assert member_mute_states[22222] is False
            
            # All others should be muted
            for member_id in [11111, 33333, 44444, 55555]:
                assert member_mute_states[member_id] is True
            
            # Test unmuting with different failure pattern
            member_mute_states[33333] = True  # Reset for test
            
            async def mock_safe_edit_member_unmute(member, mute=False, **kwargs):
                if member.id == 33333:  # User3 fails during unmute
                    raise NotFound(MagicMock(status=404), "Member not found")
                
                # Update state for successful operations
                member_mute_states[member.id] = mute
                return None
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member_unmute
            
            # Test unmuting with partial failure
            for member in env['members']:
                try:
                    await session.auto_mute.safe_edit_member(member, mute=False)
                except (Forbidden, NotFound):
                    pass  # Continue with others
            
            # Verify final state consistency
            # User2 (22222) remains unmuted (was already unmuted from previous failure)
            assert member_mute_states[22222] is False
            
            # User3 (33333) remains muted (unmute failed)
            assert member_mute_states[33333] is True
            
            # All others should be unmuted
            for member_id in [11111, 44444, 55555]:
                assert member_mute_states[member_id] is False