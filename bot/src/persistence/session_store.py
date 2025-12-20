"""
セッション永続化ストア

TinyDBを使用してセッション情報をローカルファイルに保存・復元
"""
import os
import json
import time as t
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from src.session.Session import Session
from src.Settings import Settings
from src.Timer import Timer
from src.Stats import Stats
from configs import bot_enum


class SessionStore:
    """セッション永続化ストア"""
    
    def __init__(self, db_path: str = "pomomo_sessions.json"):
        """
        ストア初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        self.db_path = db_path
        # キャッシュミドルウェアを使用してパフォーマンス向上
        self.db = TinyDB(
            db_path, 
            storage=CachingMiddleware(JSONStorage),
            indent=2,
            ensure_ascii=False
        )
        self.sessions_table = self.db.table('sessions')
        self.Query = Query()
    
    def save_session(self, guild_id: int, session: Session) -> bool:
        """
        セッションを保存
        
        Args:
            guild_id: ギルドID
            session: 保存するセッション
            
        Returns:
            保存成功時True
        """
        try:
            session_data = self._serialize_session(guild_id, session)
            
            # 既存セッションがあれば更新、なければ挿入
            existing = self.sessions_table.search(self.Query.guild_id == guild_id)
            if existing:
                self.sessions_table.update(session_data, self.Query.guild_id == guild_id)
            else:
                self.sessions_table.insert(session_data)
            
            return True
        except Exception as e:
            print(f"セッション保存エラー (Guild: {guild_id}): {e}")
            return False
    
    def load_session(self, guild_id: int) -> Optional[Session]:
        """
        セッションを読み込み
        
        Args:
            guild_id: ギルドID
            
        Returns:
            復元されたセッション、存在しない場合はNone
        """
        try:
            result = self.sessions_table.search(self.Query.guild_id == guild_id)
            if not result:
                return None
            
            session_data = result[0]
            return self._deserialize_session(session_data)
        
        except Exception as e:
            print(f"セッション読み込みエラー (Guild: {guild_id}): {e}")
            return None
    
    def delete_session(self, guild_id: int) -> bool:
        """
        セッションを削除
        
        Args:
            guild_id: ギルドID
            
        Returns:
            削除成功時True
        """
        try:
            self.sessions_table.remove(self.Query.guild_id == guild_id)
            return True
        except Exception as e:
            print(f"セッション削除エラー (Guild: {guild_id}): {e}")
            return False
    
    def load_all_sessions(self) -> Dict[int, Session]:
        """
        全セッションを読み込み
        
        Returns:
            guild_idをキーとするセッション辞書
        """
        sessions = {}
        try:
            for session_data in self.sessions_table.all():
                guild_id = session_data.get('guild_id')
                session = self._deserialize_session(session_data)
                if guild_id and session:
                    sessions[guild_id] = session
        except Exception as e:
            print(f"全セッション読み込みエラー: {e}")
        
        return sessions
    
    def clear_all_sessions(self) -> bool:
        """
        全セッションを削除
        
        Returns:
            削除成功時True
        """
        try:
            self.sessions_table.truncate()
            return True
        except Exception as e:
            print(f"全セッション削除エラー: {e}")
            return False
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """
        期限切れセッションをクリーンアップ
        
        Args:
            max_age_hours: 最大保持時間（時間）
            
        Returns:
            削除されたセッション数
        """
        try:
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            
            expired_sessions = self.sessions_table.search(
                self.Query.saved_at < cutoff_time.isoformat()
            )
            
            if expired_sessions:
                self.sessions_table.remove(
                    self.Query.saved_at < cutoff_time.isoformat()
                )
            
            return len(expired_sessions)
        except Exception as e:
            print(f"期限切れセッションクリーンアップエラー: {e}")
            return 0
    
    def get_session_count(self) -> int:
        """
        保存されているセッション数を取得
        
        Returns:
            セッション数
        """
        return len(self.sessions_table.all())
    
    def close(self):
        """データベースを閉じる"""
        try:
            self.db.close()
        except Exception as e:
            print(f"データベース終了エラー: {e}")
    
    def _serialize_session(self, guild_id: int, session: Session) -> Dict[str, Any]:
        """セッションをシリアライズ"""
        return {
            'guild_id': guild_id,
            'settings': {
                'duration': session.settings.duration,
                'short_break': session.settings.short_break,
                'long_break': session.settings.long_break,
                'intervals': session.settings.intervals
            },
            'timer': {
                'remaining': session.timer.remaining,
                'running': session.timer.running,
                'end': session.timer.end
            },
            'stats': {
                'pomos_completed': session.stats.pomos_completed,
                'pomos_elapsed': session.stats.pomos_elapsed,
                'seconds_completed': session.stats.seconds_completed
            },
            'state': session.state,
            'timeout': session.timeout,
            'current_session_start_time': session.current_session_start_time.isoformat() if session.current_session_start_time else None,
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'version': '1.0'
        }
    
    def _deserialize_session(self, data: Dict[str, Any]) -> Optional[Session]:
        """セッションをデシリアライズ"""
        try:
            # Settings復元
            settings_data = data['settings']
            settings = Settings(
                duration=settings_data['duration'],
                short_break=settings_data.get('short_break'),
                long_break=settings_data.get('long_break'),
                intervals=settings_data.get('intervals')
            )
            
            # Sessionオブジェクト作成（ctxはNoneで初期化、後で設定が必要）
            state = data['state']
            session = Session(state, settings, ctx=None)
            
            # Timer復元
            timer_data = data['timer']
            session.timer.remaining = timer_data['remaining']
            session.timer.running = timer_data['running']
            session.timer.end = timer_data.get('end')
            
            # Stats復元
            stats_data = data['stats']
            session.stats.pomos_completed = stats_data['pomos_completed']
            session.stats.pomos_elapsed = stats_data['pomos_elapsed']
            session.stats.seconds_completed = stats_data['seconds_completed']
            
            # その他の属性復元
            session.timeout = data.get('timeout', 0)
            
            if data.get('current_session_start_time'):
                session.current_session_start_time = datetime.fromisoformat(data['current_session_start_time'])
            
            return session
            
        except Exception as e:
            print(f"セッションデシリアライズエラー: {e}")
            return None


# グローバルストアインスタンス
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """グローバルセッションストアを取得"""
    global _session_store
    if _session_store is None:
        # データベースファイルをbotディレクトリ配下に配置
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'pomomo_sessions.json')
        _session_store = SessionStore(db_path)
    return _session_store


def close_session_store():
    """グローバルセッションストアを閉じる"""
    global _session_store
    if _session_store:
        _session_store.close()
        _session_store = None