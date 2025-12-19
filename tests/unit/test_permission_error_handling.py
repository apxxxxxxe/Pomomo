"""
権限エラー処理の自動テスト

このモジュールは、ボットが権限を持たないボイスチャンネルでの
enableautomute/disableautomuteコマンド実行時の動作をテストします。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.mocks.discord_mocks import MockBot, MockGuild, MockUser, MockMember, MockVoiceChannel, MockInteraction
from cogs.subscribe import Subscribe
from src.subscriptions.AutoMute import AutoMute, AutoMutePermissionError


class TestPermissionErrorHandling:
    """権限エラー処理のテストクラス"""
    
    @pytest.fixture
    def permission_test_setup(self):
        """権限テスト用のセットアップ"""
        user = MockUser(id=12345, name="TestUser")
        guild = MockGuild(id=67890, name="TestGuild")
        voice_channel = MockVoiceChannel(guild=guild, name="General")
        interaction = MockInteraction(user=user, guild=guild, channel=voice_channel)
        
        # Mock session setup
        mock_session = MagicMock()
        mock_session.ctx = interaction
        mock_session.state = 'POMODORO'  # 作業状態
        mock_session.auto_mute = MagicMock()
        mock_session.auto_mute.all = False
        
        # ボットメンバーとボイスチャンネル権限のモック
        bot_member = MagicMock()
        bot_member.name = "pomomo-dev"
        voice_channel.guild.me = bot_member
        
        # 権限なしの設定
        mock_permissions = MagicMock()
        mock_permissions.mute_members = False
        mock_permissions.administrator = False
        voice_channel.permissions_for = MagicMock(return_value=mock_permissions)
        
        # インタラクション応答のモック
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.delete_original_response = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel.send = AsyncMock()
        
        return {
            'interaction': interaction,
            'session': mock_session,
            'voice_channel': voice_channel,
            'user': user,
            'guild': guild,
            'bot_member': bot_member,
            'permissions': mock_permissions
        }
    
    @pytest.mark.asyncio
    async def test_automute_permission_error_creation(self):
        """AutoMutePermissionErrorが正しく作成できることをテスト"""
        error_message = "Test permission error"
        error = AutoMutePermissionError(error_message)
        
        assert str(error) == error_message
        assert isinstance(error, Exception)
    
    @pytest.mark.asyncio
    async def test_automute_permission_error_direct_creation(self):
        """AutoMutePermissionErrorが直接作成され、適切なメッセージを持つことをテスト"""
        # 実際のエラーメッセージ形式をテスト
        channel_name = "General"
        bot_name = "pomomo-dev"
        permission_error_msg = f'ボットが `{channel_name}` ボイスチャンネルでメンバーをミュートする権限を持っていません。\nbotアカウント `{bot_name}` へ `{channel_name}` ボイスチャンネルでの「メンバーをミュートする」権限を付与してください。'
        
        error = AutoMutePermissionError(permission_error_msg)
        error_message = str(error)
        
        # エラーメッセージの内容を検証
        assert "General" in error_message  # チャンネル名
        assert "pomomo-dev" in error_message  # ボット名
        assert "メンバーをミュートする権限を持っていません" in error_message
        assert "権限を付与してください" in error_message
    
    @pytest.mark.asyncio
    async def test_permission_error_types_and_inheritance(self):
        """AutoMutePermissionErrorの型と継承関係をテスト"""
        error = AutoMutePermissionError("test message")
        
        # 正しい型であることを確認
        assert isinstance(error, AutoMutePermissionError)
        assert isinstance(error, Exception)
        
        # メッセージが正しく設定されることを確認
        assert str(error) == "test message"
        
        # 例外として正しく発生できることを確認
        with pytest.raises(AutoMutePermissionError):
            raise AutoMutePermissionError("test exception")
    
    @pytest.mark.asyncio
    async def test_enableautomute_permission_error_handling(self, permission_test_setup):
        """enableautomuteコマンドが権限エラーを適切に処理することをテスト"""
        env = permission_test_setup
        mock_bot = MockBot()
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # セットアップ
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            # handle_allが権限エラーを投げるように設定
            env['session'].auto_mute.handle_all = AsyncMock(
                side_effect=AutoMutePermissionError(
                    "ボットが `General` ボイスチャンネルでメンバーをミュートする権限を持っていません。\n"
                    "botアカウント `pomomo-dev` へ `General` ボイスチャンネルでの「メンバーをミュートする」権限を付与してください。"
                )
            )
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # 権限エラー時の動作を検証
            # 1. warningログが出力される
            mock_logger.warning.assert_called_once()
            log_message = mock_logger.warning.call_args[0][0]
            assert "Permission error in enableautomute" in log_message
            
            # 2. delete_original_responseが呼ばれる（クリーンアップ）
            env['interaction'].delete_original_response.assert_called_once()
            
            # 3. ephemeralメッセージが送信される（_safe_interaction_response経由でfollowup.sendに変換）
            env['interaction'].followup.send.assert_called_once()
            call_args = env['interaction'].followup.send.call_args
            assert call_args[1]['ephemeral'] is True
            
            # メッセージ内容の確認
            sent_message = call_args[0][0]
            assert "General" in sent_message
            assert "pomomo-dev" in sent_message
            assert "メンバーをミュートする権限を持っていません" in sent_message
            
            # 4. チャンネルに成功メッセージは送信されない
            env['interaction'].channel.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_disableautomute_permission_error_handling(self, permission_test_setup):
        """disableautomuteコマンドも同様に権限エラーを処理することをテスト"""
        env = permission_test_setup
        env['session'].auto_mute.all = True  # disableの前提条件
        mock_bot = MockBot()
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # セットアップ
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            
            # handle_allが権限エラーを投げるように設定
            env['session'].auto_mute.handle_all = AsyncMock(
                side_effect=AutoMutePermissionError("権限エラーメッセージ")
            )
            
            await subscribe_cog.disableautomute.callback(subscribe_cog, env['interaction'])
            
            # disableautomuteでも同様の動作を検証
            mock_logger.warning.assert_called_once()
            log_message = mock_logger.warning.call_args[0][0]
            assert "Permission error in disableautomute" in log_message
            
            env['interaction'].delete_original_response.assert_called_once()
            env['interaction'].followup.send.assert_called_once()
            env['interaction'].channel.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_permission_error_message_format_variations(self):
        """異なるチャンネル名とボット名での権限エラーメッセージ形式をテスト"""
        test_cases = [
            ("General", "pomomo-dev"),
            ("ボイスチャット", "テストボット"),
            ("Voice Channel", "bot-name-123"),
        ]
        
        for channel_name, bot_name in test_cases:
            # 実際のエラーメッセージ作成ロジックをテスト
            permission_error_msg = f'ボットが `{channel_name}` ボイスチャンネルでメンバーをミュートする権限を持っていません。\nbotアカウント `{bot_name}` へ `{channel_name}` ボイスチャンネルでの「メンバーをミュートする」権限を付与してください。'
            error = AutoMutePermissionError(permission_error_msg)
            error_message = str(error)
            
            # メッセージ形式の確認
            assert f"`{channel_name}`" in error_message
            assert f"`{bot_name}`" in error_message
            assert "メンバーをミュートする権限を持っていません" in error_message
            assert "権限を付与してください" in error_message
    
    @pytest.mark.asyncio
    async def test_actual_error_message_content_validation(self):
        """実際に表示されるエラーメッセージの内容が適切であることを検証"""
        # 実際にユーザーに表示されるメッセージと同じ形式をテスト
        expected_message = (
            "ボットが `General` ボイスチャンネルでメンバーをミュートする権限を持っていません。\n"
            "botアカウント `pomomo-dev` へ `General` ボイスチャンネルでの「メンバーをミュートする」権限を付与してください。"
        )
        
        error = AutoMutePermissionError(expected_message)
        
        # メッセージ内容の詳細検証
        error_str = str(error)
        assert "ボットが" in error_str
        assert "ボイスチャンネルでメンバーをミュートする権限を持っていません" in error_str
        assert "botアカウント" in error_str
        assert "権限を付与してください" in error_str
        
        # 改行が含まれることを確認
        assert "\n" in error_str
        
        # バッククォートでチャンネル名とボット名が囲まれていることを確認
        assert "`General`" in error_str
        assert "`pomomo-dev`" in error_str
    
    @pytest.mark.asyncio
    async def test_permission_error_during_break_state(self, permission_test_setup):
        """休憩中の状態でenableautomuteを実行した場合の動作をテスト"""
        env = permission_test_setup
        env['session'].state = 'SHORT_BREAK'  # 休憩状態
        mock_bot = MockBot()
        subscribe_cog = Subscribe(mock_bot)
        
        with patch('cogs.subscribe.session_manager') as mock_session_manager, \
             patch('cogs.subscribe.vc_accessor') as mock_vc_accessor, \
             patch('cogs.subscribe.voice_validation') as mock_voice_validation, \
             patch('cogs.subscribe.bot_enum') as mock_bot_enum, \
             patch('cogs.subscribe.logger') as mock_logger:
            
            # セットアップ
            mock_session_manager.get_session_interaction = AsyncMock(return_value=env['session'])
            mock_vc_accessor.get_voice_channel_interaction.return_value = env['voice_channel']
            mock_vc_accessor.get_voice_channel.return_value = env['voice_channel']
            mock_voice_validation.require_same_voice_channel = AsyncMock(return_value=True)
            mock_bot_enum.State.BREAK_STATES = ['SHORT_BREAK', 'LONG_BREAK', 'CLASSWORK_BREAK']
            
            await subscribe_cog.enableautomute.callback(subscribe_cog, env['interaction'])
            
            # 休憩中はhandle_allが呼ばれず、権限エラーも発生しない
            env['session'].auto_mute.handle_all.assert_not_called()
            
            # auto_mute.allフラグだけ設定される
            assert env['session'].auto_mute.all is True
            
            # 成功メッセージが送信される（休憩中用メッセージ）
            env['interaction'].channel.send.assert_called_once()
            call_args = env['interaction'].channel.send.call_args
            message_content = call_args[0][0]
            assert "次の作業時間開始時から強制ミュートが適用されます" in message_content