"""
セッション目標管理システム
"""
import logging
from typing import Dict, Optional, Tuple
import random

logger = logging.getLogger(__name__)

# セッション目標の格納
# 構造: {(guild_id, user_id): {"goal": str, "check_count": int, "reacted_messages": set}}
session_goals: Dict[Tuple[int, int], Dict[str, any]] = {}

# 進捗確認対象外ユーザーのリアクション記録
# 構造: {(guild_id, user_id): set(message_id)}
non_goal_user_reactions: Dict[Tuple[int, int], set] = {}

# ギルドレベルの作業回数カウント（進捗確認用）
# 構造: {guild_id: work_count}
guild_work_counts: Dict[int, int] = {}


def set_goal(guild_id: int, user_id: int, goal: str) -> None:
    """
    セッション目標を設定する
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        goal: 目標内容
    """
    key = (guild_id, user_id)
    session_goals[key] = {
        "goal": goal,
        "check_count": 0,
        "reacted_messages": set()
    }
    logger.info(f"Goal set for user {user_id} in guild {guild_id}: {goal}")

def get_goal(guild_id: int, user_id: int) -> Optional[str]:
    """
    セッション目標を取得する
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        
    Returns:
        目標内容（存在しない場合はNone）
    """
    key = (guild_id, user_id)
    goal_data = session_goals.get(key)
    return goal_data["goal"] if goal_data else None

def increment_check_count(guild_id: int, user_id: int) -> int:
    """
    進捗確認回数をインクリメントし、現在の回数を返す
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        
    Returns:
        現在の確認回数
    """
    key = (guild_id, user_id)
    if key in session_goals:
        session_goals[key]["check_count"] += 1
        return session_goals[key]["check_count"]
    return 0

def calculate_progress_check_frequency(work_duration_minutes: int) -> int:
    """
    作業時間に基づいて進捗確認の頻度を動的に計算する
    およそ1時間ごとに進捗確認を行うための作業回数を求める
    
    Args:
        work_duration_minutes: 作業時間（分）
        
    Returns:
        n回の作業ごとに進捗確認を行う値
    """
    ONE_HOUR_SECONDS = 3600
    work_duration_seconds = work_duration_minutes * 60
    
    # 1時間あたりの理想的な作業セッション数を計算
    ideal_sessions_per_hour = ONE_HOUR_SECONDS / work_duration_seconds
    
    # 四捨五入して整数にし、最小値を1にする
    frequency = max(1, round(ideal_sessions_per_hour))
    
    logger.debug(f"Work duration: {work_duration_minutes}min, calculated frequency: {frequency}")
    return frequency

def should_check_progress(guild_id: int, user_id: int, work_duration_minutes: int) -> bool:
    """
    進捗確認を行うべきかどうかを判定する（ギルドベース）
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        work_duration_minutes: 作業時間（分）
        
    Returns:
        進捗確認を行うべき場合True
    """
    key = (guild_id, user_id)
    if key not in session_goals:
        return False
    
    # ギルド全体の作業回数をチェック
    guild_count = get_guild_work_count(guild_id)
    # 動的に計算した頻度を使用
    progress_check_frequency = calculate_progress_check_frequency(work_duration_minutes)
    return guild_count % progress_check_frequency == 0

def remove_goal(guild_id: int, user_id: int) -> bool:
    """
    セッション目標を削除する
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        
    Returns:
        削除に成功した場合True
    """
    key = (guild_id, user_id)
    if key in session_goals:
        goal = session_goals[key]["goal"]
        del session_goals[key]
        logger.info(f"Goal removed for user {user_id} in guild {guild_id}: {goal}")
        return True
    return False

def remove_all_goals_for_guild(guild_id: int) -> int:
    """
    指定したギルドの全ての目標を削除する
    
    Args:
        guild_id: ギルドID
        
    Returns:
        削除した目標の数
    """
    keys_to_remove = [key for key in session_goals.keys() if key[0] == guild_id]
    count = len(keys_to_remove)
    for key in keys_to_remove:
        del session_goals[key]
    
    if count > 0:
        logger.info(f"Removed {count} goals for guild {guild_id}")
    
    return count

def get_all_goals_for_guild(guild_id: int) -> Dict[int, str]:
    """
    指定したギルドの全ての目標を取得する
    
    Args:
        guild_id: ギルドID
        
    Returns:
        {user_id: goal}の辞書
    """
    result = {}
    for (g_id, user_id), goal_data in session_goals.items():
        if g_id == guild_id:
            result[user_id] = goal_data["goal"]
    return result

# リアクション別応援メッセージ
ENCOURAGEMENT_MESSAGES = {
    "🏆": [
        "おめでとうございます！🎉",
        "目標達成、お疲れさまでした！👏",
        "完璧です！次も頑張りましょう！🌟"
    ],
    "😎": [
        "いいですね！👍",
        "順調に進んでいますね！😊",
        "その調子です！💪",
        "良いペースですね！⚡"
    ],
    "👌": [
        "続けていきましょう！📈",
        "少しずつ前進していますね！🚶‍♂️",
        "継続が大切です！🔄",
        "焦らずあなたのペースで！🐎"
    ],
    "😇": [
        "一息入れてもいいかもしれませんね。コーヒーはいかがですか？☕",
        "休憩も大切です。リフレッシュしましょう！🌿",
        "少し気分転換してみませんか？🍃",
    ]
}

def get_encouragement_message(reaction: str) -> str:
    """
    リアクションに応じた応援メッセージを取得する
    
    Args:
        reaction: リアクション文字列
        
    Returns:
        応援メッセージ
    """
    messages = ENCOURAGEMENT_MESSAGES.get(reaction, ["頑張りましょう！"])
    return random.choice(messages)

def has_user_reacted_to_message(guild_id: int, user_id: int, message_id: int) -> bool:
    """
    ユーザーが特定のメッセージに既にリアクションしているかチェック
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        message_id: メッセージID
        
    Returns:
        既にリアクションしている場合True
    """
    key = (guild_id, user_id)
    goal_data = session_goals.get(key)
    if goal_data:
        return message_id in goal_data["reacted_messages"]
    return False

def mark_user_reacted_to_message(guild_id: int, user_id: int, message_id: int) -> None:
    """
    ユーザーが特定のメッセージにリアクションしたことを記録
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        message_id: メッセージID
    """
    key = (guild_id, user_id)
    if key in session_goals:
        session_goals[key]["reacted_messages"].add(message_id)
        logger.debug(f"Marked reaction for user {user_id} on message {message_id}")

def clear_user_reaction_history(guild_id: int, user_id: int) -> None:
    """
    ユーザーのリアクション履歴をクリア（目標削除時に使用）
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
    """
    key = (guild_id, user_id)
    if key in session_goals:
        session_goals[key]["reacted_messages"].clear()
        logger.debug(f"Cleared reaction history for user {user_id}")

def has_non_goal_user_reacted_to_message(guild_id: int, user_id: int, message_id: int) -> bool:
    """
    進捗確認対象外ユーザーが特定のメッセージに既にリアクションしているかチェック
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        message_id: メッセージID
        
    Returns:
        既にリアクションしている場合True
    """
    key = (guild_id, user_id)
    reaction_set = non_goal_user_reactions.get(key)
    if reaction_set:
        return message_id in reaction_set
    return False

def mark_non_goal_user_reacted_to_message(guild_id: int, user_id: int, message_id: int) -> None:
    """
    進捗確認対象外ユーザーが特定のメッセージにリアクションしたことを記録
    
    Args:
        guild_id: ギルドID
        user_id: ユーザーID
        message_id: メッセージID
    """
    key = (guild_id, user_id)
    if key not in non_goal_user_reactions:
        non_goal_user_reactions[key] = set()
    non_goal_user_reactions[key].add(message_id)
    logger.debug(f"Marked non-goal user reaction for user {user_id} on message {message_id}")

def remove_non_goal_user_reactions_for_guild(guild_id: int) -> int:
    """
    指定したギルドの進捗確認対象外ユーザーのリアクション記録を全削除
    
    Args:
        guild_id: ギルドID
        
    Returns:
        削除したユーザー数
    """
    keys_to_remove = [key for key in non_goal_user_reactions.keys() if key[0] == guild_id]
    count = len(keys_to_remove)
    for key in keys_to_remove:
        del non_goal_user_reactions[key]
    
    if count > 0:
        logger.debug(f"Removed non-goal user reactions for {count} users in guild {guild_id}")
    
    return count


def increment_guild_work_count(guild_id: int) -> int:
    """
    ギルドの作業回数をインクリメントし、現在の回数を返す
    
    Args:
        guild_id: ギルドID
        
    Returns:
        現在の作業回数
    """
    if guild_id in guild_work_counts:
        guild_work_counts[guild_id] += 1
    else:
        guild_work_counts[guild_id] = 1
    
    logger.debug(f"Guild {guild_id} work count incremented to {guild_work_counts[guild_id]}")
    return guild_work_counts[guild_id]


def get_guild_work_count(guild_id: int) -> int:
    """
    ギルドの現在の作業回数を取得する
    
    Args:
        guild_id: ギルドID
        
    Returns:
        現在の作業回数
    """
    return guild_work_counts.get(guild_id, 0)
