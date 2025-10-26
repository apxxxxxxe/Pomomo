"""
ボイスチャンネル確認のユーティリティ関数
"""

import discord


async def require_same_voice_channel(interaction: discord.Interaction) -> bool:
    """
    実行ユーザがbotと同じボイスチャンネルに参加しているかを確認
    
    Args:
        interaction: Discord Interaction オブジェクト
        
    Returns:
        bool: 同じボイスチャンネルにいる場合True、そうでない場合False
    """
    # ユーザーがボイスチャンネルに参加していない場合
    if not interaction.user.voice:
        return False
    
    # botのボイスクライアント取得
    guild = interaction.guild
    if guild and guild.voice_client:
        # botがボイスチャンネルに接続している場合、同じチャンネルかチェック
        if interaction.user.voice.channel != guild.voice_client.channel:
            return False
    
    return True
