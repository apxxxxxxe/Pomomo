"""
音声機能の統合テスト

音声再生、VoiceClient管理、音声ファイルの存在確認など
実運用で重要な音声関連機能を網羅的にテスト
"""
import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from tests.mocks.discord_mocks import MockGuild, MockVoiceChannel, MockMember
from tests.mocks.voice_mocks import MockVoiceClient
from src.voice_client import vc_manager
from src.utils import player


class TestVoiceClientManager:
    """VoiceClient管理のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        # グローバル状態をクリア
        vc_manager.connected_sessions.clear()
        vc_manager.connection_locks.clear()
    
    def create_mock_guild_and_channel(self, guild_id=12345):
        """モックのギルドとボイスチャンネルを作成"""
        guild = MockGuild(id=guild_id)
        voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=guild)
        guild.voice_channels = [voice_channel]
        return guild, voice_channel
    
    @pytest.mark.asyncio
    async def test_connect_to_voice_channel_success(self):
        """ボイスチャンネルへの接続成功テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # VoiceClientのモックを作成
        mock_voice_client = MockVoiceClient()
        voice_channel.connect = AsyncMock(return_value=mock_voice_client)
        
        # 接続実行
        result = await vc_manager.connect(guild.id, voice_channel)
        
        # 検証
        assert result == mock_voice_client
        assert guild.id in vc_manager.connected_sessions
        assert vc_manager.connected_sessions[guild.id] == mock_voice_client
        voice_channel.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """既に接続済みの場合のテスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 既存の接続を設定
        existing_voice_client = MockVoiceClient()
        vc_manager.connected_sessions[guild.id] = existing_voice_client
        
        # 再接続試行
        result = await vc_manager.connect(guild.id, voice_channel)
        
        # 既存の接続が返されることを確認
        assert result == existing_voice_client
    
    @pytest.mark.asyncio
    async def test_connect_voice_channel_failure(self):
        """ボイスチャンネル接続失敗テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 接続失敗をシミュレート
        voice_channel.connect = AsyncMock(side_effect=Exception("Connection failed"))
        
        # 接続試行
        result = await vc_manager.connect(guild.id, voice_channel)
        
        # 失敗時はNoneが返されることを確認
        assert result is None
        assert guild.id not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """ボイスチャンネルからの切断成功テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 接続済みの状態を設定
        mock_voice_client = MockVoiceClient()
        vc_manager.connected_sessions[guild.id] = mock_voice_client
        
        # 切断実行
        await vc_manager.disconnect(guild.id)
        
        # 検証
        mock_voice_client.disconnect.assert_called_once()
        assert guild.id not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """未接続状態での切断試行テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        # 未接続状態で切断試行（エラーが起きないことを確認）
        await vc_manager.disconnect(guild.id)
        
        # 特に例外が発生しないことを確認
        assert guild.id not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_with_exception(self):
        """切断時の例外処理テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 切断失敗をシミュレート
        mock_voice_client = MockVoiceClient()
        mock_voice_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        vc_manager.connected_sessions[guild.id] = mock_voice_client
        
        # 切断実行（例外が適切に処理されることを確認）
        await vc_manager.disconnect(guild.id)
        
        # セッションはクリーンアップされることを確認
        assert guild.id not in vc_manager.connected_sessions
    
    def test_get_connected_session_exists(self):
        """接続済みセッション取得テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        mock_voice_client = MockVoiceClient()
        vc_manager.connected_sessions[guild.id] = mock_voice_client
        
        result = vc_manager.get_connected_session(guild.id)
        assert result == mock_voice_client
    
    def test_get_connected_session_not_exists(self):
        """未接続セッション取得テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        result = vc_manager.get_connected_session(guild.id)
        assert result is None


class TestVoicePlayer:
    """音声再生機能のテスト"""
    
    @pytest.mark.asyncio
    async def test_alert_with_existing_voice_client(self):
        """VoiceClient存在時の音声再生テスト"""
        guild_id = 12345
        
        # モックのVoiceClientを設定
        mock_voice_client = MockVoiceClient()
        
        with patch('src.voice_client.vc_manager.get_connected_session', return_value=mock_voice_client):
            with patch('discord.FFmpegPCMAudio') as mock_audio:
                mock_source = Mock()
                mock_audio.return_value = mock_source
                
                await player.alert(guild_id, "test.mp3")
                
                # 音声再生が呼ばれることを確認
                mock_voice_client.play.assert_called_once_with(mock_source)
    
    @pytest.mark.asyncio 
    async def test_alert_without_voice_client(self):
        """VoiceClient非存在時の音声再生テスト"""
        guild_id = 12345
        
        with patch('src.voice_client.vc_manager.get_connected_session', return_value=None):
            # VoiceClientが存在しない場合、例外が発生しないことを確認
            await player.alert(guild_id, "test.mp3")
    
    @pytest.mark.asyncio
    async def test_alert_with_file_not_found(self):
        """音声ファイルが存在しない場合のテスト"""
        guild_id = 12345
        
        mock_voice_client = MockVoiceClient()
        
        with patch('src.voice_client.vc_manager.get_connected_session', return_value=mock_voice_client):
            with patch('discord.FFmpegPCMAudio', side_effect=FileNotFoundError("File not found")):
                # ファイルが存在しない場合、適切にハンドリングされることを確認
                await player.alert(guild_id, "nonexistent.mp3")
                
                # play は呼ばれないことを確認
                mock_voice_client.play.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_alert_with_play_exception(self):
        """音声再生時の例外処理テスト"""
        guild_id = 12345
        
        mock_voice_client = MockVoiceClient()
        mock_voice_client.play = AsyncMock(side_effect=Exception("Play failed"))
        
        with patch('src.voice_client.vc_manager.get_connected_session', return_value=mock_voice_client):
            with patch('discord.FFmpegPCMAudio') as mock_audio:
                mock_audio.return_value = Mock()
                
                # 例外が適切にハンドリングされることを確認
                await player.alert(guild_id, "test.mp3")


class TestVoiceFileExistence:
    """音声ファイルの存在確認テスト"""
    
    def test_sound_files_exist(self):
        """必要な音声ファイルが存在することを確認"""
        sound_files = [
            "sounds/pomo_start.mp3",
            "sounds/long_break.mp3"
        ]
        
        for sound_file in sound_files:
            file_path = os.path.join(os.getcwd(), sound_file)
            assert os.path.exists(file_path), f"音声ファイル {sound_file} が存在しません"
            assert os.path.isfile(file_path), f"{sound_file} はファイルではありません"
            
            # ファイルサイズが0でないことを確認
            file_size = os.path.getsize(file_path)
            assert file_size > 0, f"音声ファイル {sound_file} のサイズが0です"


class TestConcurrentVoiceOperations:
    """並行音声操作のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        vc_manager.connected_sessions.clear()
        vc_manager.connection_locks.clear()
    
    @pytest.mark.asyncio
    async def test_concurrent_connections_to_same_guild(self):
        """同じギルドへの並行接続テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        mock_voice_client = MockVoiceClient()
        voice_channel.connect = AsyncMock(return_value=mock_voice_client)
        
        # 並行接続を試行
        import asyncio
        results = await asyncio.gather(
            vc_manager.connect(guild.id, voice_channel),
            vc_manager.connect(guild.id, voice_channel),
            vc_manager.connect(guild.id, voice_channel)
        )
        
        # 全て同じVoiceClientインスタンスが返されることを確認
        assert all(result == mock_voice_client for result in results)
        # 実際の接続は1回だけ行われることを確認
        assert voice_channel.connect.call_count == 1
    
    @pytest.mark.asyncio 
    async def test_concurrent_connections_to_different_guilds(self):
        """異なるギルドへの並行接続テスト"""
        guild1, voice_channel1 = self.create_mock_guild_and_channel(12345)
        guild2, voice_channel2 = self.create_mock_guild_and_channel(67890)
        
        mock_voice_client1 = MockVoiceClient()
        mock_voice_client2 = MockVoiceClient()
        voice_channel1.connect = AsyncMock(return_value=mock_voice_client1)
        voice_channel2.connect = AsyncMock(return_value=mock_voice_client2)
        
        # 並行接続を試行
        import asyncio
        result1, result2 = await asyncio.gather(
            vc_manager.connect(guild1.id, voice_channel1),
            vc_manager.connect(guild2.id, voice_channel2)
        )
        
        # それぞれ異なるVoiceClientが返されることを確認
        assert result1 == mock_voice_client1
        assert result2 == mock_voice_client2
        assert len(vc_manager.connected_sessions) == 2
    
    def create_mock_guild_and_channel(self, guild_id=12345):
        """モックのギルドとボイスチャンネルを作成"""
        guild = MockGuild(id=guild_id)
        voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=guild)
        guild.voice_channels = [voice_channel]
        return guild, voice_channel


class TestVoiceConnectionLifecycle:
    """音声接続のライフサイクルテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        vc_manager.connected_sessions.clear()
        vc_manager.connection_locks.clear()
    
    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self):
        """接続から切断までの完全なライフサイクルテスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=guild)
        
        # 1. 接続
        mock_voice_client = MockVoiceClient()
        voice_channel.connect = AsyncMock(return_value=mock_voice_client)
        
        result = await vc_manager.connect(guild.id, voice_channel)
        assert result == mock_voice_client
        assert guild.id in vc_manager.connected_sessions
        
        # 2. 音声再生
        with patch('discord.FFmpegPCMAudio') as mock_audio:
            mock_source = Mock()
            mock_audio.return_value = mock_source
            
            await player.alert(guild.id, "test.mp3")
            mock_voice_client.play.assert_called_once_with(mock_source)
        
        # 3. 切断
        await vc_manager.disconnect(guild.id)
        mock_voice_client.disconnect.assert_called_once()
        assert guild.id not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_reconnection_after_disconnect(self):
        """切断後の再接続テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=guild)
        
        # 最初の接続
        mock_voice_client1 = MockVoiceClient()
        voice_channel.connect = AsyncMock(return_value=mock_voice_client1)
        
        result1 = await vc_manager.connect(guild.id, voice_channel)
        await vc_manager.disconnect(guild.id)
        
        # 再接続
        mock_voice_client2 = MockVoiceClient()
        voice_channel.connect.return_value = mock_voice_client2
        
        result2 = await vc_manager.connect(guild.id, voice_channel)
        
        # 新しいインスタンスが作成されることを確認
        assert result2 == mock_voice_client2
        assert voice_channel.connect.call_count == 2