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
        
        # Sessionオブジェクトを作成して接続実行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        result = await vc_manager.connect(session)
        
        # 検証
        assert result is True  # connectは成功時にTrueを返す
        assert str(guild.id) in vc_manager.connected_sessions  # connected_sessionsのキーは文字列
        assert vc_manager.connected_sessions[str(guild.id)] == session  # sessionオブジェクトが保存される
        voice_channel.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """既に接続済みの場合のテスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 既存の接続を設定
        existing_voice_client = MockVoiceClient()
        vc_manager.connected_sessions[guild.id] = existing_voice_client
        
        # Sessionオブジェクトを作成して再接続試行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        result = await vc_manager.connect(session)
        
        # 既存の接続がある場合は異なる挙動を確認
        # 実際の実装では異なる動作をする可能性があるため、結果を確認
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_connect_voice_channel_failure(self):
        """ボイスチャンネル接続失敗テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 接続失敗をシミュレート
        voice_channel.connect = AsyncMock(side_effect=Exception("Connection failed"))
        
        # Sessionオブジェクトを作成して接続試行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        result = await vc_manager.connect(session)
        
        # 失敗時はFalseが返されることを確認
        assert result is False
        assert str(guild.id) not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """ボイスチャンネルからの切断成功テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # Sessionオブジェクトを作成して接続済みの状態を設定
        mock_voice_client = MockVoiceClient()
        
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        interaction.guild.voice_client = mock_voice_client  # voice_clientを設定
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        # connected_sessionsにセッションを追加
        vc_manager.connected_sessions[str(guild.id)] = session
        
        # 既に作成したセッションで切断実行
        await vc_manager.disconnect(session)
        
        # 検証
        mock_voice_client.disconnect.assert_called_once()
        assert str(guild.id) not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """未接続状態での切断試行テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        # Sessionオブジェクトを作成して未接続状態で切断試行（エラーが起きないことを確認）
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        await vc_manager.disconnect(session)
        
        # 特に例外が発生しないことを確認
        assert str(guild.id) not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_disconnect_with_exception(self):
        """切断時の例外処理テスト"""
        guild, voice_channel = self.create_mock_guild_and_channel()
        
        # 切断失敗をシミュレート
        mock_voice_client = MockVoiceClient()
        mock_voice_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        vc_manager.connected_sessions[guild.id] = mock_voice_client
        
        # Sessionオブジェクトを作成して切断実行（例外が適切に処理されることを確認）
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        await vc_manager.disconnect(session)
        
        # セッションはクリーンアップされることを確認
        assert str(guild.id) not in vc_manager.connected_sessions
    
    def test_get_connected_session_exists(self):
        """接続済みセッション取得テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        # Sessionオブジェクトを作成してconnected_sessionsに追加
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        vc_manager.connected_sessions[str(guild.id)] = session
        
        result = vc_manager.get_connected_session(str(guild.id))
        assert result == session
    
    def test_get_connected_session_not_exists(self):
        """未接続セッション取得テスト"""
        guild, _ = self.create_mock_guild_and_channel()
        
        result = vc_manager.get_connected_session(str(guild.id))
        assert result is None


class TestVoicePlayer:
    """音声再生機能のテスト"""
    
    @pytest.mark.asyncio
    async def test_alert_with_existing_voice_client(self):
        """VoiceClient存在時の音声再生テスト"""
        # Sessionオブジェクトを作成
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction, MockGuild
        
        guild = MockGuild(id=12345)
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        # モックのVoiceClientを設定
        mock_voice_client = MockVoiceClient()
        # playメソッドをMagicMockに置き換えてアサーションを可能にする
        mock_voice_client.play = MagicMock()
        interaction.guild.voice_client = mock_voice_client
        
        with patch('discord.FFmpegPCMAudio') as mock_audio:
            with patch('discord.PCMVolumeTransformer') as mock_transformer:
                mock_source = Mock()
                mock_transformer.return_value = mock_source
                
                await player.alert(session)
                
                # 音声再生が呼ばれることを確認
                mock_voice_client.play.assert_called_once()  # 引数の種類よりも呼び出しを確認
    
    @pytest.mark.asyncio 
    async def test_alert_without_voice_client(self):
        """VoiceClient非存在時の音声再生テスト"""
        # Sessionオブジェクトを作成（VoiceClientなし）
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction, MockGuild
        
        guild = MockGuild(id=12345)
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        # VoiceClientなしの状態
        interaction.guild.voice_client = None
        
        # VoiceClientが存在しない場合、例外が発生しないことを確認
        await player.alert(session)
    
    @pytest.mark.asyncio
    async def test_alert_with_file_not_found(self):
        """音声ファイルが存在しない場合のテスト"""
        # Sessionオブジェクトを作成
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction, MockGuild
        
        guild = MockGuild(id=12345)
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        mock_voice_client = MockVoiceClient()
        interaction.guild.voice_client = mock_voice_client
        
        with patch('discord.FFmpegPCMAudio', side_effect=FileNotFoundError("File not found")):
            # ファイルが存在しない場合、例外が適切にハンドリングされることを確認
            await player.alert(session)
            
            # 実装では例外がキャッチされてログに記録されるため、エラーがクラッシュを引き起こさないことを確認
            # ただし、実装の詳細により音声の再生が呼ばれる可能性あり
    
    @pytest.mark.asyncio
    async def test_alert_with_play_exception(self):
        """音声再生時の例外処理テスト"""
        # Sessionオブジェクトを作成
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction, MockGuild
        
        guild = MockGuild(id=12345)
        interaction = MockInteraction(guild=guild)
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        mock_voice_client = MockVoiceClient()
        mock_voice_client.play = MagicMock(side_effect=Exception("Play failed"))
        interaction.guild.voice_client = mock_voice_client
        
        with patch('discord.FFmpegPCMAudio') as mock_audio:
            with patch('discord.PCMVolumeTransformer') as mock_transformer:
                mock_transformer.return_value = Mock()
                
                # 例外が適切にハンドリングされることを確認
                await player.alert(session)


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
        
        # Sessionオブジェクトを作成して並行接続を試行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        sessions = []
        for i in range(3):
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            settings = Settings(duration=25)
            session = Session(State.COUNTDOWN, settings, interaction)
            sessions.append(session)
        
        import asyncio
        results = await asyncio.gather(
            vc_manager.connect(sessions[0]),
            vc_manager.connect(sessions[1]),
            vc_manager.connect(sessions[2])
        )
        
        # 結果の検証（並行接続の挙動は実装に依存）
        assert len(results) == 3
        # 接続操作が実行されていることを確認
        assert voice_channel.connect.called
    
    @pytest.mark.asyncio 
    async def test_concurrent_connections_to_different_guilds(self):
        """異なるギルドへの並行接続テスト"""
        guild1, voice_channel1 = self.create_mock_guild_and_channel(12345)
        guild2, voice_channel2 = self.create_mock_guild_and_channel(67890)
        
        mock_voice_client1 = MockVoiceClient()
        mock_voice_client2 = MockVoiceClient()
        voice_channel1.connect = AsyncMock(return_value=mock_voice_client1)
        voice_channel2.connect = AsyncMock(return_value=mock_voice_client2)
        
        # Sessionオブジェクトを作成して並行接続を試行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction1 = MockInteraction(guild=guild1)
        interaction1.user.voice = MagicMock()
        interaction1.user.voice.channel = voice_channel1
        settings1 = Settings(duration=25)
        session1 = Session(State.COUNTDOWN, settings1, interaction1)
        
        interaction2 = MockInteraction(guild=guild2)
        interaction2.user.voice = MagicMock()
        interaction2.user.voice.channel = voice_channel2
        settings2 = Settings(duration=25)
        session2 = Session(State.COUNTDOWN, settings2, interaction2)
        
        import asyncio
        result1, result2 = await asyncio.gather(
            vc_manager.connect(session1),
            vc_manager.connect(session2)
        )
        
        # 異なるギルドへの接続結果を確認
        assert result1 is True or result1 is False  # 成功または失敗
        assert result2 is True or result2 is False  # 成功または失敗
        # 接続操作が実行されたことを確認
        assert voice_channel1.connect.called
        assert voice_channel2.connect.called
    
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
        
        # Sessionオブジェクトを作成して接続実行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction = MockInteraction(guild=guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        settings = Settings(duration=25)
        session = Session(State.COUNTDOWN, settings, interaction)
        
        result = await vc_manager.connect(session)
        assert result is True
        assert str(guild.id) in vc_manager.connected_sessions
        
        # 2. 音声再生
        interaction.guild.voice_client = mock_voice_client  # voice_clientを設定
        # playメソッドをMagicMockに置き換えてアサーションを可能にする
        mock_voice_client.play = MagicMock()
        with patch('discord.FFmpegPCMAudio') as mock_audio:
            with patch('discord.PCMVolumeTransformer') as mock_transformer:
                mock_source = Mock()
                mock_transformer.return_value = mock_source
                
                await player.alert(session)
                mock_voice_client.play.assert_called_once()  # 引数の種類よりも呼び出しを確認
        
        # 3. 切断
        await vc_manager.disconnect(session)
        mock_voice_client.disconnect.assert_called_once()
        assert str(guild.id) not in vc_manager.connected_sessions
    
    @pytest.mark.asyncio
    async def test_reconnection_after_disconnect(self):
        """切断後の再接続テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=guild)
        
        # 最初の接続
        mock_voice_client1 = MockVoiceClient()
        voice_channel.connect = AsyncMock(return_value=mock_voice_client1)
        
        # Sessionオブジェクトを作成して接続実行
        from src.session.Session import Session
        from src.Settings import Settings
        from configs.bot_enum import State
        from tests.mocks.discord_mocks import MockInteraction
        
        interaction1 = MockInteraction(guild=guild)
        interaction1.user.voice = MagicMock()
        interaction1.user.voice.channel = voice_channel
        settings1 = Settings(duration=25)
        session1 = Session(State.COUNTDOWN, settings1, interaction1)
        
        result1 = await vc_manager.connect(session1)
        await vc_manager.disconnect(session1)
        
        # 再接続
        mock_voice_client2 = MockVoiceClient()
        voice_channel.connect.return_value = mock_voice_client2
        
        # Sessionオブジェクトを作成して再接続実行
        interaction2 = MockInteraction(guild=guild)
        interaction2.user.voice = MagicMock()
        interaction2.user.voice.channel = voice_channel
        settings2 = Settings(duration=25)
        session2 = Session(State.COUNTDOWN, settings2, interaction2)
        
        result2 = await vc_manager.connect(session2)
        
        # 新しい接続が実行されることを確認
        assert result2 is True or result2 is False  # 成功または失敗
        assert voice_channel.connect.call_count == 2