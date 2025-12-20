"""
永続化から復元されたセッション（ctx=None）の処理テスト
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from src.session.Session import Session
from src.Settings import Settings
from src.session import session_manager, session_controller
from tests.mocks.discord_mocks import MockBot, MockUser, MockGuild, MockTextChannel


class MockContext:
    """テスト用のコンテキストモック"""
    def __init__(self):
        self.guild = MockGuild()
        self.channel = MockTextChannel()
        self.bot = MockBot()
        
    async def send(self, content):
        return MockMessage()

class MockMessage:
    """テスト用のメッセージモック"""
    def __init__(self):
        pass
        
    async def add_reaction(self, emoji):
        pass


class TestSessionPersistenceRecovery:
    """永続化復元セッションのテストクラス"""
    
    @pytest.fixture
    def mock_settings(self):
        """モック設定"""
        return Settings(duration=25, short_break=5, long_break=15, intervals=4)
    
    @pytest.fixture
    def session_with_ctx(self, mock_settings):
        """通常のセッション（ctxあり）"""
        mock_ctx = MockContext()
        return Session("running", mock_settings, mock_ctx)
    
    @pytest.fixture
    def session_without_ctx(self, mock_settings):
        """永続化復元セッション（ctx=None）"""
        return Session("running", mock_settings, ctx=None)
    
    @pytest.mark.asyncio
    async def test_kill_if_idle_with_none_ctx(self, session_without_ctx):
        """session_manager.kill_if_idle でctx=Noneの場合のテスト"""
        # ctx=None の場合はFalseを返してスキップすること
        result = await session_manager.kill_if_idle(session_without_ctx)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_kill_if_idle_with_valid_ctx(self, session_with_ctx):
        """session_manager.kill_if_idle で正常なctxの場合のテスト"""
        # Mock voice client functions
        with patch('src.session.session_manager.vc_accessor') as mock_vc:
            mock_vc.get_voice_channel.return_value = True
            mock_vc.get_true_members_in_voice_channel.return_value = [1, 2]  # 2人いる
            
            # 通常のctxがある場合は処理が続行されること（timeout未到達なのでNone）
            result = await session_manager.kill_if_idle(session_with_ctx)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_session_controller_end_with_none_ctx(self, session_without_ctx):
        """session_controller.end でctx=Noneの場合のテスト"""
        with patch('src.session.session_controller.session_manager') as mock_sm, \
             patch('src.session.session_controller.goal_manager') as mock_gm, \
             patch('src.session.session_controller.logger') as mock_logger:
            
            mock_sm.deactivate = AsyncMock()
            mock_gm.remove_all_goals_for_guild.return_value = 0
            mock_gm.remove_non_goal_user_reactions_for_guild.return_value = 0
            
            # ctx=None でもエラーなく終了処理が実行されること
            await session_controller.end(session_without_ctx)
            
            # deactivateが呼ばれることを確認
            mock_sm.deactivate.assert_called_once_with(session_without_ctx)
            
            # "Ending session without context" ログが出力されることを確認
            mock_logger.info.assert_called_with("Ending session without context (recovered session)")
    
    @pytest.mark.asyncio
    async def test_session_controller_end_with_valid_ctx(self, session_with_ctx):
        """session_controller.end で正常なctxの場合のテスト"""
        with patch('src.session.session_controller.session_manager') as mock_sm, \
             patch('src.session.session_controller.goal_manager') as mock_gm, \
             patch('src.session.session_controller.vc_accessor') as mock_vc, \
             patch('src.session.session_controller.vc_manager') as mock_vm, \
             patch('src.session.session_controller.logger') as mock_logger:
            
            mock_sm.deactivate = AsyncMock()
            mock_gm.remove_all_goals_for_guild.return_value = 2
            mock_gm.remove_non_goal_user_reactions_for_guild.return_value = 1
            mock_vc.get_voice_client.return_value = True
            mock_vm.disconnect = AsyncMock()
            session_with_ctx.auto_mute.unmute = AsyncMock()
            
            # 通常のctxがある場合は全処理が実行されること
            await session_controller.end(session_with_ctx)
            
            # 各処理が呼ばれることを確認
            mock_sm.deactivate.assert_called_once_with(session_with_ctx)
            mock_gm.remove_all_goals_for_guild.assert_called_once_with(session_with_ctx.ctx.guild.id)
            mock_gm.remove_non_goal_user_reactions_for_guild.assert_called_once_with(session_with_ctx.ctx.guild.id)
            session_with_ctx.auto_mute.unmute.assert_called_once()
            mock_vm.disconnect.assert_called_once_with(session_with_ctx)
            
            # 正常なログが出力されることを確認
            mock_logger.info.assert_any_call(f"Ending session for guild {session_with_ctx.ctx.guild.id}")
    
    @pytest.mark.asyncio 
    async def test_kill_idle_sessions_task_with_none_ctx(self, session_without_ctx):
        """main.py の kill_idle_sessions タスクでctx=Noneの場合のテスト"""
        
        # モックセッションマネージャーを設定
        mock_active_sessions = {'123': session_without_ctx}
        
        with patch('src.session.session_manager.active_sessions', mock_active_sessions), \
             patch('src.session.session_manager.kill_if_idle') as mock_kill, \
             patch('main.logger') as mock_logger:
            
            mock_kill.side_effect = Exception("Test exception")
            
            # main.py の kill_idle_sessions 関数をインポート・実行
            from main import kill_idle_sessions
            
            await kill_idle_sessions()
            
            # エラーログが適切に出力されることを確認
            mock_logger.error.assert_called_with("Error killing idle session (no context): Test exception")
    
    @pytest.mark.asyncio
    async def test_kill_idle_sessions_task_with_valid_ctx(self, session_with_ctx):
        """main.py の kill_idle_sessions タスクで正常なctxの場合のテスト"""
        
        # モックセッションマネージャーを設定
        mock_active_sessions = {'456': session_with_ctx}
        
        with patch('src.session.session_manager.active_sessions', mock_active_sessions), \
             patch('src.session.session_manager.kill_if_idle') as mock_kill, \
             patch('main.logger') as mock_logger:
            
            mock_kill.side_effect = Exception("Test exception")
            
            # main.py の kill_idle_sessions 関数をインポート・実行
            from main import kill_idle_sessions
            
            await kill_idle_sessions()
            
            # エラーログが適切に出力されることを確認（guild IDが含まれる）
            expected_guild_id = session_with_ctx.ctx.guild.id
            mock_logger.error.assert_called_with(f"Error killing idle session {expected_guild_id}: Test exception")
    
    @pytest.mark.asyncio
    async def test_session_recovery_preserves_state(self, mock_settings):
        """永続化復元時にセッション状態が保持されることのテスト"""
        
        # 永続化復元をシミュレート
        session = Session("paused", mock_settings, ctx=None)
        session.stats.pomos_completed = 3
        session.timer.remaining = 15 * 60  # 15分残り
        
        # ctxがNoneでも基本的なセッション状態は保持されていることを確認
        assert session.state == "paused"
        assert session.stats.pomos_completed == 3
        assert session.timer.remaining == 15 * 60
        assert session.ctx is None
        
        # 新しいctxを設定可能であることを確認
        new_ctx = MockContext()
        session.ctx = new_ctx
        assert session.ctx == new_ctx
    
    @pytest.mark.asyncio
    async def test_session_manager_functions_handle_none_ctx(self, session_without_ctx):
        """session_manager の各関数がctx=Noneを適切に処理することのテスト"""
        
        # session_id_from でctx=Noneを渡すとエラーになることを確認
        with pytest.raises(AttributeError):
            session_manager.session_id_from(None)
        
        # update_session_persistence でctx=Noneのセッションは処理されないことを確認
        with patch('src.session.session_manager._persistence_enabled', True):
            # ctxがNoneなので何も実行されない
            await session_manager.update_session_persistence(session_without_ctx)
            # エラーが発生しないことを確認（上記が正常終了すればOK）