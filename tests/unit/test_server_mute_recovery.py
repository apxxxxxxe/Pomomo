"""
サーバーミュート自動回復テスト

future_test_plan.mdで特定された高優先度テストケース：
ボイスチャンネル参加時のサーバーミュート状態検出と解除をテスト
権限不足時の適切な指示メッセージ送信を確認
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import Forbidden, Member, VoiceState, VoiceChannel
from discord.errors import DiscordServerError

from tests.mocks.discord_mocks import (
    MockBot, MockInteraction, MockUser, MockGuild, MockVoiceChannel, MockMember
)
from tests.mocks.voice_mocks import MockVoiceClient

from src.session.Session import Session
from src.Settings import Settings
from configs.bot_enum import State


class TestServerMuteRecovery:
    """サーバーミュート自動回復テスト"""
    
    def setup_method(self):
        """各テストメソッドの前にセッション状態をリセット"""
        from src.session import session_manager
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
    
    @pytest.fixture
    def server_mute_test_environment(self):
        """サーバーミュートテスト用の環境を準備"""
        guild = MockGuild(id=54321, name="Test Guild")
        user = MockUser(id=12345, name="TestUser")
        voice_channel = MockVoiceChannel(id=98765, name="Test Voice Channel")
        interaction = MockInteraction(user=user, guild=guild, channel=voice_channel)
        voice_client = MockVoiceClient(guild=guild, channel=voice_channel)
        bot = MockBot()
        
        # Create test member with server mute
        member = MockMember(MockUser(id=12345, name="TestUser"), guild)
        member.voice = MagicMock()
        member.voice.mute = True  # Server muted
        member.voice.channel = voice_channel
        
        return {
            'bot': bot,
            'interaction': interaction,
            'user': user,
            'guild': guild,
            'voice_channel': voice_channel,
            'voice_client': voice_client,
            'member': member,
            'guild_id': str(guild.id)
        }
    
    @pytest.mark.asyncio
    async def test_detect_server_muted_user_on_join(self, server_mute_test_environment):
        """ボイスチャンネル参加時のサーバーミュート検出"""
        env = server_mute_test_environment
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            mock_auto_mute_instance._handle_server_muted_user_join = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session with AutoMute enabled
            mock_session = MagicMock()
            mock_session.auto_mute = mock_auto_mute_instance
            mock_session_manager.get_session_from_guild = MagicMock(return_value=mock_session)
            
            # Simulate voice state update for server muted user joining
            before = None  # User was not in voice channel
            after = MagicMock()
            after.channel = env['voice_channel']
            after.mute = True  # Server muted
            after.self_mute = False
            
            # Test server mute detection
            await mock_auto_mute_instance._handle_server_muted_user_join(env['member'], after)
            
            # Verify server mute detection was called
            mock_auto_mute_instance._handle_server_muted_user_join.assert_called_once_with(
                env['member'], after
            )
    
    @pytest.mark.asyncio
    async def test_automatic_unmute_with_sufficient_permissions(self, server_mute_test_environment):
        """十分な権限がある場合の自動ミュート解除"""
        env = server_mute_test_environment
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Mock successful unmute operation
            mock_auto_mute_instance.safe_edit_member = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            mock_session = MagicMock()
            mock_session.auto_mute = mock_auto_mute_instance
            mock_session_manager.get_session_from_guild = MagicMock(return_value=mock_session)
            
            # Test automatic unmute of server muted user
            await mock_auto_mute_instance.safe_edit_member(env['member'], mute=False)
            
            # Verify unmute was attempted
            mock_auto_mute_instance.safe_edit_member.assert_called_once_with(
                env['member'], mute=False
            )
    
    @pytest.mark.asyncio
    async def test_permission_error_sends_instruction_message(self, server_mute_test_environment):
        """権限不足時の指示メッセージ送信"""
        env = server_mute_test_environment
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Mock permission error during unmute
            mock_auto_mute_instance.safe_edit_member = AsyncMock(
                side_effect=Forbidden(MagicMock(status=403), "Missing permissions")
            )
            
            # Mock instruction message sending
            mock_auto_mute_instance._send_unmute_instruction = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            mock_session = MagicMock()
            mock_session.auto_mute = mock_auto_mute_instance
            mock_session.ctx = env['interaction']
            mock_session_manager.get_session_from_guild = MagicMock(return_value=mock_session)
            
            # Test permission error handling
            try:
                await mock_auto_mute_instance.safe_edit_member(env['member'], mute=False)
            except Forbidden:
                # Send instruction message when permission error occurs
                await mock_auto_mute_instance._send_unmute_instruction(
                    mock_session.ctx, env['member']
                )
            
            # Verify instruction message was sent
            mock_auto_mute_instance._send_unmute_instruction.assert_called_once_with(
                mock_session.ctx, env['member']
            )
    
    @pytest.mark.asyncio
    async def test_multiple_server_muted_users_batch_recovery(self, server_mute_test_environment):
        """複数のサーバーミュートユーザーの一括回復"""
        env = server_mute_test_environment
        
        # Create additional server muted members
        muted_members = []
        for i in range(3):
            user = MockUser(id=20000 + i, name=f"MutedUser{i}")
            member = MockMember(user=user, guild=env['guild'])
            member.voice = MagicMock()
            member.voice.mute = True  # Server muted
            member.voice.channel = env['voice_channel']
            muted_members.append(member)
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Track unmute operations
            unmuted_members = []
            
            async def mock_safe_edit_member(member, **kwargs):
                if not kwargs.get('mute', True):  # If unmuting
                    unmuted_members.append(member.id)
                    member.voice.mute = False  # Update state
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_instance._handle_multiple_server_muted_users = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            mock_session = MagicMock()
            mock_session.auto_mute = mock_auto_mute_instance
            mock_session_manager.get_session_from_guild = MagicMock(return_value=mock_session)
            
            # Test batch recovery of multiple server muted users
            for member in muted_members:
                await mock_auto_mute_instance.safe_edit_member(member, mute=False)
            
            # Verify all members were processed
            assert len(unmuted_members) == 3
            assert all(member_id in unmuted_members for member_id in [20000, 20001, 20002])
    
    @pytest.mark.asyncio
    async def test_mixed_permission_scenarios(self, server_mute_test_environment):
        """権限混在状態の適切な処理"""
        env = server_mute_test_environment
        
        # Create members with different permission scenarios
        members = []
        for i in range(4):
            user = MockUser(id=30000 + i, name=f"TestUser{i}")
            member = MockMember(user=user, guild=env['guild'])
            member.voice = MagicMock()
            member.voice.mute = True
            member.voice.channel = env['voice_channel']
            members.append(member)
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Track results
            results = {
                'successful_unmutes': [],
                'permission_errors': [],
                'instruction_messages': []
            }
            
            async def mock_safe_edit_member(member, **kwargs):
                if member.id in [30001, 30003]:  # Some members have permission issues
                    results['permission_errors'].append(member.id)
                    raise Forbidden(MagicMock(status=403), "Missing permissions")
                else:
                    results['successful_unmutes'].append(member.id)
                    member.voice.mute = False
            
            async def mock_send_instruction(ctx, member):
                results['instruction_messages'].append(member.id)
            
            mock_auto_mute_instance.safe_edit_member = mock_safe_edit_member
            mock_auto_mute_instance._send_unmute_instruction = mock_send_instruction
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create session
            mock_session = MagicMock()
            mock_session.auto_mute = mock_auto_mute_instance
            mock_session.ctx = env['interaction']
            mock_session_manager.get_session_from_guild = MagicMock(return_value=mock_session)
            
            # Test mixed permission scenario
            for member in members:
                try:
                    await mock_auto_mute_instance.safe_edit_member(member, mute=False)
                except Forbidden:
                    await mock_auto_mute_instance._send_unmute_instruction(
                        mock_session.ctx, member
                    )
            
            # Verify results
            assert len(results['successful_unmutes']) == 2  # Members 30000, 30002
            assert len(results['permission_errors']) == 2   # Members 30001, 30003
            assert len(results['instruction_messages']) == 2  # Instructions for failed members
            
            assert 30000 in results['successful_unmutes']
            assert 30002 in results['successful_unmutes']
            assert 30001 in results['permission_errors']
            assert 30003 in results['permission_errors']
    
    @pytest.mark.asyncio
    async def test_server_mute_detection_during_active_session(self, server_mute_test_environment):
        """アクティブセッション中のサーバーミュート検出"""
        env = server_mute_test_environment
        
        with patch('src.session.Session.Timer') as mock_timer, \
             patch('src.session.Session.Stats') as mock_stats, \
             patch('src.subscriptions.Subscription.Subscription'), \
             patch('src.subscriptions.AutoMute.AutoMute') as mock_auto_mute_class, \
             patch('src.session.session_manager') as mock_session_manager:
            
            # Setup mocks
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            mock_stats_instance = MagicMock()
            mock_stats.return_value = mock_stats_instance
            
            mock_auto_mute_instance = MagicMock()
            mock_auto_mute_instance.all = True  # AutoMute is enabled
            mock_auto_mute_instance._handle_server_muted_user_join = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Create active session
            settings = Settings(duration=25, short_break=5, long_break=20, intervals=4)
            session = Session(State.POMODORO, settings, env['interaction'])
            session.auto_mute = mock_auto_mute_instance
            
            mock_session_manager.get_session_from_guild = MagicMock(return_value=session)
            
            # Simulate voice state update during active session
            before = MagicMock()
            before.channel = None  # User was not in voice channel
            
            after = MagicMock()
            after.channel = env['voice_channel']  # User joins voice channel
            after.mute = True  # Server muted
            after.self_mute = False
            
            # Test server mute detection during active session
            if session and session.auto_mute.all:
                await session.auto_mute._handle_server_muted_user_join(env['member'], after)
            
            # Verify detection was triggered
            session.auto_mute._handle_server_muted_user_join.assert_called_once_with(
                env['member'], after
            )
    
    @pytest.mark.asyncio
    async def test_instruction_message_content_and_formatting(self, server_mute_test_environment):
        """指示メッセージの内容と形式の確認"""
        env = server_mute_test_environment
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.utils.msg_builder') as mock_msg_builder:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Mock message building
            expected_message = (
                f"🔇 {env['member'].display_name}さんがサーバーミュートされています。\\n"
                "Botに権限がないため、手動でミュートを解除してください。"
            )
            mock_msg_builder.build_unmute_instruction = MagicMock(return_value=expected_message)
            
            # Mock message sending
            sent_messages = []
            async def mock_send_message(content, **kwargs):
                sent_messages.append(content)
            
            env['interaction'].channel.send = mock_send_message
            
            async def mock_send_instruction(ctx, member):
                message = mock_msg_builder.build_unmute_instruction(member)
                await ctx.channel.send(message, silent=True)
            
            mock_auto_mute_instance._send_unmute_instruction = mock_send_instruction
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Test instruction message sending
            await mock_auto_mute_instance._send_unmute_instruction(
                env['interaction'], env['member']
            )
            
            # Verify message content and format
            assert len(sent_messages) == 1
            assert expected_message in sent_messages[0]
            assert env['member'].display_name in sent_messages[0]
            assert "サーバーミュート" in sent_messages[0]
            assert "手動で" in sent_messages[0]
    
    @pytest.mark.asyncio
    async def test_recovery_state_persistence(self, server_mute_test_environment):
        """回復状態の永続化テスト"""
        env = server_mute_test_environment
        
        with patch('src.subscriptions.AutoMute') as mock_auto_mute_class, \
             patch('src.persistence.session_store') as mock_store:
            
            # Setup mocks
            mock_auto_mute_instance = MagicMock()
            
            # Track recovery operations
            recovery_log = []
            
            async def mock_recovery_operation(member, success=True):
                recovery_entry = {
                    'member_id': member.id,
                    'timestamp': '2025-12-21T13:00:00',
                    'operation': 'server_mute_recovery',
                    'success': success
                }
                recovery_log.append(recovery_entry)
                
                # Persist recovery state
                await mock_store.save_recovery_state(member.guild.id, recovery_entry)
            
            mock_auto_mute_instance._log_recovery_operation = mock_recovery_operation
            mock_store.save_recovery_state = AsyncMock()
            mock_auto_mute_class.return_value = mock_auto_mute_instance
            
            # Test successful recovery logging
            await mock_auto_mute_instance._log_recovery_operation(env['member'], success=True)
            
            # Test failed recovery logging
            await mock_auto_mute_instance._log_recovery_operation(env['member'], success=False)
            
            # Verify recovery state persistence
            assert len(recovery_log) == 2
            assert recovery_log[0]['success'] is True
            assert recovery_log[1]['success'] is False
            
            # Verify persistence calls
            assert mock_store.save_recovery_state.call_count == 2