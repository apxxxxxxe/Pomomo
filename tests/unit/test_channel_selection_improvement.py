"""
チャンネル選択ロジック改善のテスト

サーバミュート通知のメッセージ送信先チャンネル選択について：
1. ボイスチャンネルと同名のテキストチャンネル優先
2. フォールバック: General
3. 最終フォールバック: 最初の利用可能なテキストチャンネル
"""
import pytest
from unittest.mock import MagicMock
from tests.mocks.discord_mocks import MockTextChannel, MockGuild, MockVoiceChannel
from cogs.subscribe import Subscribe


def create_mock_text_channel(name, send_permission=True):
    """テキストチャンネルのモックを作成"""
    channel = MockTextChannel(name=name)
    # permissions_forメソッドをオーバーライド
    perm = MagicMock()
    perm.send_messages = send_permission
    channel.permissions_for = MagicMock(return_value=perm)
    return channel


class TestChannelSelectionImprovement:
    """チャンネル選択ロジック改善のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MagicMock()
        self.subscribe = Subscribe(self.bot)
    
    def test_finds_matching_voice_channel_name_first_priority(self):
        """1. ボイスチャンネルと同名のテキストチャンネルが最優先で選択される"""
        text_channels = [
            create_mock_text_channel("general", send_permission=True),
            create_mock_text_channel("pomomo-test", send_permission=True),  # ボイスチャンネルと同名
            create_mock_text_channel("General", send_permission=True)
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "pomomo-test"
    
    def test_falls_back_to_general_when_no_matching_name(self):
        """2. 同名チャンネルがない場合はGeneralにフォールバック"""
        text_channels = [
            create_mock_text_channel("general", send_permission=True),
            create_mock_text_channel("random", send_permission=True),
            create_mock_text_channel("General", send_permission=True)
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "General"
    
    def test_uses_first_available_when_no_general(self):
        """3. GeneralもないときはA最初の利用可能なテキストチャンネル"""
        text_channels = [
            create_mock_text_channel("general", send_permission=True),
            create_mock_text_channel("random", send_permission=True),
            create_mock_text_channel("other-channel", send_permission=True)
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "general"  # 最初のチャンネル
    
    def test_skips_channels_without_send_permission(self):
        """権限のないチャンネルは正しくスキップされる"""
        text_channels = [
            create_mock_text_channel("pomomo-test", send_permission=False),  # 権限なし（同名だがスキップ）
            create_mock_text_channel("General", send_permission=True),       # 権限あり
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "General"
    
    def test_returns_none_when_no_channels_with_permission(self):
        """送信権限のあるチャンネルが存在しない場合はNoneを返す"""
        text_channels = [
            create_mock_text_channel("general", send_permission=False),
            create_mock_text_channel("random", send_permission=False),
            create_mock_text_channel("General", send_permission=False)
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is None
    
    def test_priority_order_with_multiple_matches(self):
        """複数の条件が同時に満たされる場合の優先順位確認"""
        text_channels = [
            create_mock_text_channel("General", send_permission=True),      # 2番目の優先度
            create_mock_text_channel("pomomo-test", send_permission=True),  # 1番目の優先度（ボイスチャンネルと同名）
            create_mock_text_channel("general", send_permission=True)       # 3番目の優先度
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "pomomo-test"  # 同名チャンネルが最優先
    
    def test_case_sensitive_channel_matching(self):
        """チャンネル名のマッチングが大文字小文字を区別することを確認"""
        text_channels = [
            create_mock_text_channel("POMOMO-TEST", send_permission=True),  # 大文字（マッチしない）
            create_mock_text_channel("General", send_permission=True),
            create_mock_text_channel("general", send_permission=True)
        ]
        guild = MockGuild()
        guild.text_channels = text_channels
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")  # 小文字
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is not None
        assert result.name == "General"  # 同名ではないのでGeneralにフォールバック
    
    def test_empty_text_channels_list(self):
        """テキストチャンネルが存在しない場合"""
        guild = MockGuild()
        guild.text_channels = []
        guild.me = MagicMock()
        
        voice_channel = MockVoiceChannel(name="pomomo-test")
        
        result = self.subscribe._find_target_text_channel(guild, voice_channel)
        
        assert result is None