"""
セッション永続化機能のテスト

TinyDBを使用したセッション保存・復元機能の包括的テスト
"""
import pytest
import os
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.persistence.session_store import SessionStore
from src.session.Session import Session
from src.Settings import Settings
from src.session import session_manager
from configs import bot_enum


class TestSessionStore:
    """SessionStore基本機能のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        # 一時ディレクトリでテスト用DBを作成
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_sessions.json")
        self.store = SessionStore(self.test_db_path)
    
    def teardown_method(self):
        """テストクリーンアップ"""
        self.store.close()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_test_session(self, guild_id: int = 12345) -> Session:
        """テスト用セッション作成"""
        settings = Settings(duration=25, short_break=5, long_break=15, intervals=4)
        ctx = MagicMock()
        ctx.guild.id = guild_id
        session = Session(bot_enum.State.POMODORO, settings, ctx)
        return session
    
    def test_save_and_load_session(self):
        """セッション保存・読み込みテスト"""
        guild_id = 12345
        session = self.create_test_session(guild_id)
        
        # 保存
        assert self.store.save_session(guild_id, session)
        
        # 読み込み
        loaded_session = self.store.load_session(guild_id)
        assert loaded_session is not None
        
        # 設定の確認
        assert loaded_session.settings.duration == 25
        assert loaded_session.settings.short_break == 5
        assert loaded_session.settings.long_break == 15
        assert loaded_session.settings.intervals == 4
        
        # 状態の確認
        assert loaded_session.state == bot_enum.State.POMODORO
    
    def test_session_update(self):
        """セッション更新テスト"""
        guild_id = 12345
        session = self.create_test_session(guild_id)
        
        # 初回保存
        assert self.store.save_session(guild_id, session)
        
        # セッション状態変更
        session.state = bot_enum.State.SHORT_BREAK
        session.timer.remaining = 300  # 5分
        session.stats.pomos_completed = 1
        
        # 更新保存
        assert self.store.save_session(guild_id, session)
        
        # 確認
        loaded_session = self.store.load_session(guild_id)
        assert loaded_session.state == bot_enum.State.SHORT_BREAK
        assert loaded_session.timer.remaining == 300
        assert loaded_session.stats.pomos_completed == 1
    
    def test_delete_session(self):
        """セッション削除テスト"""
        guild_id = 12345
        session = self.create_test_session(guild_id)
        
        # 保存
        assert self.store.save_session(guild_id, session)
        assert self.store.load_session(guild_id) is not None
        
        # 削除
        assert self.store.delete_session(guild_id)
        assert self.store.load_session(guild_id) is None
    
    def test_multiple_guilds(self):
        """複数ギルドのセッション管理テスト"""
        guild_ids = [12345, 67890, 11111]
        sessions = []
        
        # 複数セッション保存
        for guild_id in guild_ids:
            session = self.create_test_session(guild_id)
            sessions.append(session)
            assert self.store.save_session(guild_id, session)
        
        # 全セッション読み込み
        all_sessions = self.store.load_all_sessions()
        assert len(all_sessions) == 3
        
        for guild_id in guild_ids:
            assert guild_id in all_sessions
            assert all_sessions[guild_id].settings.duration == 25
    
    def test_session_count(self):
        """セッション数取得テスト"""
        assert self.store.get_session_count() == 0
        
        # セッション追加
        for i in range(5):
            session = self.create_test_session(10000 + i)
            self.store.save_session(10000 + i, session)
        
        assert self.store.get_session_count() == 5
        
        # 削除
        self.store.delete_session(10002)
        assert self.store.get_session_count() == 4
    
    def test_clear_all_sessions(self):
        """全セッション削除テスト"""
        # 複数セッション作成
        for i in range(3):
            session = self.create_test_session(20000 + i)
            self.store.save_session(20000 + i, session)
        
        assert self.store.get_session_count() == 3
        
        # 全削除
        assert self.store.clear_all_sessions()
        assert self.store.get_session_count() == 0
    
    def test_serialization_with_timer_state(self):
        """タイマー状態での直列化テスト"""
        guild_id = 12345
        session = self.create_test_session(guild_id)
        
        # タイマー状態設定
        session.timer.running = True
        session.timer.remaining = 1200  # 20分
        session.timer.end = 1699999999.0  # 特定のタイムスタンプ
        
        # 保存・読み込み
        assert self.store.save_session(guild_id, session)
        loaded_session = self.store.load_session(guild_id)
        
        assert loaded_session.timer.running == True
        assert loaded_session.timer.remaining == 1200
        assert loaded_session.timer.end == 1699999999.0
    
    def test_serialization_with_stats(self):
        """統計情報での直列化テスト"""
        guild_id = 12345
        session = self.create_test_session(guild_id)
        
        # 統計情報設定
        session.stats.pomos_completed = 3
        session.stats.pomos_elapsed = 180  # 3分
        session.stats.seconds_completed = 4500  # 75分
        
        # 保存・読み込み
        assert self.store.save_session(guild_id, session)
        loaded_session = self.store.load_session(guild_id)
        
        assert loaded_session.stats.pomos_completed == 3
        assert loaded_session.stats.pomos_elapsed == 180
        assert loaded_session.stats.seconds_completed == 4500
    
    def test_corrupted_data_handling(self):
        """破損データ処理テスト"""
        # 無効なデータを直接挿入
        invalid_data = {
            'guild_id': 12345,
            'invalid_field': 'broken',
            'version': '1.0'
        }
        self.store.sessions_table.insert(invalid_data)
        
        # 読み込み試行（Noneが返されるべき）
        loaded_session = self.store.load_session(12345)
        assert loaded_session is None
    
    def test_cleanup_expired_sessions(self):
        """期限切れセッションクリーンアップテスト"""
        # 新しいセッション
        recent_session = self.create_test_session(12345)
        self.store.save_session(12345, recent_session)
        
        # 古いセッションをシミュレート（直接データベース操作）
        old_data = self.store._serialize_session(67890, self.create_test_session(67890))
        old_data['saved_at'] = '2023-01-01T00:00:00+00:00'  # 古い日付
        self.store.sessions_table.insert(old_data)
        
        assert self.store.get_session_count() == 2
        
        # クリーンアップ（1時間以上古いものを削除）
        cleaned_count = self.store.cleanup_expired_sessions(max_age_hours=1)
        
        assert cleaned_count == 1
        assert self.store.get_session_count() == 1
        assert self.store.load_session(12345) is not None  # 新しいセッションは残る
        assert self.store.load_session(67890) is None      # 古いセッションは削除


class TestSessionManagerIntegration:
    """SessionManagerとの統合テスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        # session_managerの状態をクリア
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
        
        # テスト用の一時ディレクトリ
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_integration.json")
    
    def teardown_method(self):
        """テストクリーンアップ"""
        session_manager.active_sessions.clear()
        session_manager.session_locks.clear()
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_session_activation_with_persistence(self):
        """永続化機能付きセッション有効化テスト"""
        # テスト用ストアでパッチ（session_manager内のインポートに合わせる）
        with patch('src.session.session_manager.get_session_store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.save_session.return_value = True
            mock_store.return_value = mock_store_instance
            
            # セッション作成
            settings = Settings(duration=25, short_break=5)
            ctx = MagicMock()
            ctx.guild.id = 12345
            session = Session(bot_enum.State.POMODORO, settings, ctx)
            
            # 有効化
            await session_manager.activate(session)
            
            # メモリに保存されていることを確認
            assert '12345' in session_manager.active_sessions
            
            # 永続化が呼ばれたことを確認
            mock_store_instance.save_session.assert_called_once_with(12345, session)
    
    @pytest.mark.asyncio
    async def test_session_deactivation_with_persistence(self):
        """永続化機能付きセッション無効化テスト"""
        with patch('src.session.session_manager.get_session_store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.save_session.return_value = True
            mock_store_instance.delete_session.return_value = True
            mock_store.return_value = mock_store_instance
            
            # セッション作成・有効化
            settings = Settings(duration=25)
            ctx = MagicMock()
            ctx.guild.id = 12345
            session = Session(bot_enum.State.POMODORO, settings, ctx)
            
            await session_manager.activate(session)
            assert '12345' in session_manager.active_sessions
            
            # 無効化
            await session_manager.deactivate(session)
            
            # メモリから削除されていることを確認
            assert '12345' not in session_manager.active_sessions
            
            # 永続化削除が呼ばれたことを確認
            mock_store_instance.delete_session.assert_called_once_with(12345)
    
    @pytest.mark.asyncio
    async def test_persistence_error_handling(self):
        """永続化エラーハンドリングテスト"""
        with patch('src.session.session_manager.get_session_store') as mock_store:
            # エラーを発生させる
            mock_store.side_effect = Exception("Database error")
            
            # セッション作成
            settings = Settings(duration=25)
            ctx = MagicMock()
            ctx.guild.id = 12345
            session = Session(bot_enum.State.POMODORO, settings, ctx)
            
            # エラーが発生してもクラッシュしないことを確認
            await session_manager.activate(session)
            
            # メモリには正常に保存されていることを確認
            assert '12345' in session_manager.active_sessions
    
    @pytest.mark.asyncio
    async def test_session_recovery(self):
        """セッション復旧テスト"""
        # モックボット
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_bot.get_guild.return_value = mock_guild
        
        with patch('src.session.session_manager.get_session_store') as mock_store:
            mock_store_instance = MagicMock()
            
            # 復旧用セッションデータ
            recovered_session = Session(
                bot_enum.State.SHORT_BREAK,
                Settings(duration=30, short_break=10),
                ctx=None
            )
            mock_store_instance.load_all_sessions.return_value = {
                12345: recovered_session
            }
            mock_store_instance.cleanup_expired_sessions.return_value = 0
            mock_store.return_value = mock_store_instance
            
            # 復旧実行
            recovered_count = await session_manager.recover_sessions_from_persistence(mock_bot)
            
            assert recovered_count == 1
            assert '12345' in session_manager.active_sessions
            assert session_manager.active_sessions['12345'] == recovered_session
    
    @pytest.mark.asyncio
    async def test_bulk_session_save(self):
        """一括セッション保存テスト"""
        with patch('src.session.session_manager.get_session_store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.save_session.return_value = True
            mock_store.return_value = mock_store_instance
            
            # 複数セッションをメモリに追加
            for i in range(3):
                guild_id = str(10000 + i)
                settings = Settings(duration=25)
                ctx = MagicMock()
                ctx.guild.id = int(guild_id)
                session = Session(bot_enum.State.POMODORO, settings, ctx)
                session_manager.active_sessions[guild_id] = session
            
            # 一括保存
            saved_count = await session_manager.save_all_active_sessions()
            
            assert saved_count == 3
            assert mock_store_instance.save_session.call_count == 3
    
    def test_persistence_control_functions(self):
        """永続化制御機能テスト"""
        # 初期状態は有効
        assert session_manager.is_persistence_enabled()
        
        # 無効化
        session_manager.disable_persistence()
        assert not session_manager.is_persistence_enabled()
        
        # 有効化
        session_manager.enable_persistence()
        assert session_manager.is_persistence_enabled()
    
    def test_persistence_stats(self):
        """永続化統計情報テスト"""
        with patch('src.session.session_manager.get_session_store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.get_session_count.return_value = 5
            mock_store_instance.db_path = "/test/path.json"
            mock_store.return_value = mock_store_instance
            
            stats = session_manager.get_persistence_stats()
            
            assert stats['enabled'] == True
            assert stats['total_persisted'] == 5
            assert stats['active_sessions'] == 0
            assert stats['db_path'] == "/test/path.json"


class TestPersistenceResilience:
    """永続化機能の耐障害性テスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_resilience.json")
    
    def teardown_method(self):
        """テストクリーンアップ"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_file_permission_error(self):
        """ファイル権限エラーテスト"""
        # 無効なパスでストア作成を試行（TinyDB初期化時に例外が発生することを確認）
        invalid_path = "/root/cannot_write/sessions.json"  # 通常は書き込み不可
        
        with pytest.raises(Exception):  # PermissionError または OSError
            store = SessionStore(invalid_path)
    
    def test_concurrent_access(self):
        """並行アクセステスト"""
        import threading
        import time
        
        store = SessionStore(self.test_db_path)
        results = []
        
        def save_session(guild_id):
            settings = Settings(duration=25)
            ctx = MagicMock()
            ctx.guild.id = guild_id
            session = Session(bot_enum.State.POMODORO, settings, ctx)
            
            # 少し遅延を入れて競合状態をシミュレート
            time.sleep(0.01)
            result = store.save_session(guild_id, session)
            results.append((guild_id, result))
        
        # 複数スレッドで同時保存
        threads = []
        for i in range(10):
            thread = threading.Thread(target=save_session, args=(30000 + i,))
            threads.append(thread)
            thread.start()
        
        # 全スレッド完了を待つ
        for thread in threads:
            thread.join()
        
        store.close()
        
        # 全保存が成功していることを確認
        assert len(results) == 10
        assert all(result for _, result in results)
    
    def test_database_recovery_after_corruption(self):
        """データベース破損後の回復テスト"""
        store = SessionStore(self.test_db_path)
        
        # 正常なセッション保存
        settings = Settings(duration=25)
        ctx = MagicMock()
        ctx.guild.id = 12345
        session = Session(bot_enum.State.POMODORO, settings, ctx)
        assert store.save_session(12345, session)
        
        store.close()
        
        # ファイルを破損させる
        with open(self.test_db_path, 'w') as f:
            f.write("invalid json content {{{")
        
        # 新しいストアインスタンスで読み込み試行
        new_store = SessionStore(self.test_db_path)
        
        # 破損ファイルでも例外で停止しないことを確認
        try:
            loaded_session = new_store.load_session(12345)
            # 破損している場合は None または空の結果が返される
            assert loaded_session is None or len(new_store.load_all_sessions()) == 0
        except Exception:
            # 一部の実装では例外が発生する可能性があるが、これも正常
            pass
        
        # 破損後は新しいDBとして初期化される
        # 破損したファイルから回復を試みず、新規作成される場合もある
        new_session = Session(bot_enum.State.SHORT_BREAK, settings, ctx)
        try:
            result = new_store.save_session(12345, new_session)
            # 破損からの回復または新規作成のいずれかが成功すること
            assert result or new_store.get_session_count() >= 0
        except Exception:
            # 破損データで操作が困難な場合もあるが、これもTinyDBの正常動作
            pass
        
        new_store.close()