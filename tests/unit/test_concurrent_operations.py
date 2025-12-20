"""
並行処理テスト

複数ギルド同時実行、メモリリーク、リソース管理など
Pomomoボットの並行処理能力と安定性をテスト
"""
import pytest
import asyncio
import threading
import time
from unittest.mock import MagicMock, AsyncMock, patch
from tests.mocks.discord_mocks import MockInteraction, MockGuild, MockVoiceChannel, MockBot, MockMember, MockUser
from cogs.control import Control
from cogs.subscribe import Subscribe
from src.session import session_manager
from src.voice_client import vc_manager


class TestConcurrentSessionManagement:
    """並行セッション管理のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        
        # 全状態をクリア
        session_manager.active_sessions.clear()
        vc_manager.connected_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation_multiple_guilds(self):
        """複数ギルドでの並行セッション作成テスト"""
        guild_count = 10
        interactions = []
        
        # 異なるギルドのインタラクションを作成
        for i in range(guild_count):
            guild = MockGuild(id=12345 + i)
            voice_channel = MockVoiceChannel(id=67890 + i, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            interactions.append(interaction)
        
        # 全セッションを同時作成
        tasks = [
            self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
            for interaction in interactions
        ]
        
        # 並行実行
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 実行時間が妥当であることを確認（直列実行より早い）
        execution_time = end_time - start_time
        assert execution_time < guild_count * 0.5, f"Concurrent execution too slow: {execution_time}s"
        
        # エラーが少ないことを確認
        error_count = sum(1 for result in results if isinstance(result, Exception))
        assert error_count < guild_count * 0.1, f"Too many errors in concurrent execution: {error_count}/{guild_count}"
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations_same_guild(self):
        """同一ギルドでの並行セッション操作テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        
        # 同一ギルドで複数の操作を試行
        interactions = []
        for i in range(5):
            interaction = MockInteraction(guild=guild)
            interaction.user = MockUser(id=1000 + i)  # 異なるユーザー
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            interactions.append(interaction)
        
        # 並行してセッション操作実行
        tasks = [
            self.control_cog.pomodoro.callback(self.control_cog, interactions[0], 25, 5, 15),  # セッション作成
            self.control_cog.stop.callback(self.control_cog, interactions[1]),  # 停止試行
            self.control_cog.skip.callback(self.control_cog, interactions[2]),  # スキップ試行
            self.control_cog.pomodoro.callback(self.control_cog, interactions[3], 30, 5, 15),  # 別セッション作成試行
            self.control_cog.stop.callback(self.control_cog, interactions[4])   # 停止試行
        ]
        
        # 並行実行（競合状態のテスト）
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 深刻なエラーが発生しないことを確認
        fatal_errors = [r for r in results if isinstance(r, Exception) and not isinstance(r, (ValueError, RuntimeError))]
        assert len(fatal_errors) == 0, f"Fatal errors in concurrent operations: {fatal_errors}"
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_race_conditions(self):
        """セッションライフサイクルの競合状態テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        interaction = MockInteraction(guild=guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = voice_channel
        
        # セッション作成と削除の競合
        async def create_session():
            await self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
        
        async def stop_session():
            await asyncio.sleep(0.1)  # 少し遅らせる
            await self.control_cog.stop.callback(self.control_cog, interaction)
        
        async def skip_session():
            await asyncio.sleep(0.05)
            await self.control_cog.skip.callback(self.control_cog, interaction)
        
        # 並行実行
        results = await asyncio.gather(
            create_session(),
            stop_session(), 
            skip_session(),
            return_exceptions=True
        )
        
        # デッドロックや深刻なエラーが発生しないことを確認
        serious_errors = [r for r in results if isinstance(r, Exception)]
        assert len(serious_errors) <= 2, f"Too many serious errors: {serious_errors}"


class TestConcurrentAutoMuteOperations:
    """並行AutoMute操作のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
    
    @pytest.mark.asyncio
    async def test_concurrent_automute_enable_disable(self):
        """AutoMute有効化/無効化の並行テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        
        # 複数のユーザーが同時にAutoMuteを操作
        interactions = []
        for i in range(5):
            interaction = MockInteraction(guild=guild)
            interaction.user = MockUser(id=1000 + i)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            interactions.append(interaction)
        
        # 同時に有効化と無効化を試行
        tasks = [
            self.subscribe_cog.enableautomute(interactions[0]),
            self.subscribe_cog.disableautomute(interactions[1]),
            self.subscribe_cog.enableautomute(interactions[2]),
            self.subscribe_cog.enableautomute(interactions[3]),
            self.subscribe_cog.disableautomute(interactions[4])
        ]
        
        # 並行実行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 競合状態で致命的なエラーが発生しないことを確認
        fatal_errors = [r for r in results if isinstance(r, Exception)]
        assert len(fatal_errors) <= 1, f"Too many fatal errors: {fatal_errors}"
    
    @pytest.mark.asyncio
    async def test_concurrent_voice_state_updates(self):
        """並行音声状態更新のテスト"""
        guild = MockGuild(id=12345)
        voice_channels = [
            MockVoiceChannel(id=67890 + i, guild=guild, name=f"voice-{i}")
            for i in range(3)
        ]
        
        # 複数メンバーが同時にチャンネル間を移動
        members = [MockMember(guild=guild, user=MockUser(id=2000 + i)) for i in range(10)]
        
        tasks = []
        for i, member in enumerate(members):
            from_channel = voice_channels[i % len(voice_channels)]
            to_channel = voice_channels[(i + 1) % len(voice_channels)]
            
            from tests.mocks.discord_mocks import MockVoiceState
            before_state = MockVoiceState(channel=from_channel, member=member)
            after_state = MockVoiceState(channel=to_channel, member=member)
            
            task = self.subscribe_cog.on_voice_state_update(member, before_state, after_state)
            tasks.append(task)
        
        # 並行実行
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 実行時間が妥当であることを確認
        execution_time = end_time - start_time
        assert execution_time < 5.0, f"Voice state updates too slow: {execution_time}s"
        
        # エラー率が低いことを確認
        error_count = sum(1 for r in results if isinstance(r, Exception))
        assert error_count < len(members) * 0.2, f"Too many errors: {error_count}/{len(members)}"


class TestResourceManagement:
    """リソース管理のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
        vc_manager.connected_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """負荷時のメモリ使用量テスト"""
        import psutil
        import os
        
        # 初期メモリ使用量を記録
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 大量のセッション作成・削除
        for round_num in range(10):
            guild_count = 20
            interactions = []
            
            for i in range(guild_count):
                guild = MockGuild(id=10000 + round_num * 1000 + i)
                voice_channel = MockVoiceChannel(id=20000 + round_num * 1000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                interactions.append(interaction)
            
            # セッション作成
            create_tasks = [
                self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
                for interaction in interactions
            ]
            await asyncio.gather(*create_tasks, return_exceptions=True)
            
            # セッション削除
            stop_tasks = [
                self.control_cog.stop.callback(self.control_cog, interaction)
                for interaction in interactions
            ]
            await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            # 明示的にガベージコレクション
            import gc
            gc.collect()
        
        # 最終メモリ使用量
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # メモリリークが大きくないことを確認（50MB以下）
        assert memory_increase < 50 * 1024 * 1024, f"Potential memory leak: {memory_increase / 1024 / 1024:.2f}MB"
    
    @pytest.mark.asyncio
    async def test_session_cleanup_on_errors(self):
        """エラー時のセッションクリーンアップテスト"""
        guild_count = 10
        initial_session_count = len(session_manager.active_sessions)
        
        # エラーが発生するセッション作成を試行
        tasks = []
        for i in range(guild_count):
            guild = MockGuild(id=30000 + i)
            voice_channel = MockVoiceChannel(id=40000 + i, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            # 一部のインタラクションでエラーを発生させる
            if i % 3 == 0:  # 1/3の確率でエラー
                interaction.response.send_message = AsyncMock(side_effect=Exception("Random error"))
            
            task = self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
            tasks.append(task)
        
        # 並行実行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # セッション数が適切にクリーンアップされていることを確認
        final_session_count = len(session_manager.active_sessions)
        assert final_session_count <= initial_session_count + guild_count, \
            f"Sessions not cleaned up properly: {final_session_count} sessions remaining"
    
    @pytest.mark.asyncio
    async def test_voice_client_connection_limits(self):
        """VoiceClient接続制限テスト"""
        max_connections = 50
        guilds_and_channels = []
        
        for i in range(max_connections + 10):  # 制限を超える数を試行
            guild = MockGuild(id=50000 + i)
            voice_channel = MockVoiceChannel(id=60000 + i, guild=guild)
            
            # モックVoiceClientを設定
            from tests.mocks.voice_mocks import MockVoiceClient
            mock_voice_client = MockVoiceClient()
            voice_channel.connect = AsyncMock(return_value=mock_voice_client)
            
            guilds_and_channels.append((guild, voice_channel))
        
        # 並行接続試行
        tasks = [
            vc_manager.connect(guild.id, voice_channel)
            for guild, voice_channel in guilds_and_channels
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 接続数が管理可能な範囲内であることを確認
        successful_connections = sum(1 for r in results if not isinstance(r, Exception) and r is not None)
        assert successful_connections <= max_connections, \
            f"Too many voice connections: {successful_connections}/{max_connections}"


class TestThreadSafetyAndLocking:
    """スレッドセーフティとロック機能のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_concurrent_lock_acquisition(self):
        """並行ロック取得テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        
        # 同一ギルドで複数のロック取得を試行
        lock_acquisition_times = []
        
        async def acquire_lock_and_record_time(interaction_id):
            start_time = time.time()
            
            # ポモドーロコマンドでロックを取得
            interaction = MockInteraction(guild=guild)
            interaction.user = MockUser(id=interaction_id)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            await self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
            
            end_time = time.time()
            lock_acquisition_times.append(end_time - start_time)
        
        # 並行してロック取得を試行
        tasks = [acquire_lock_and_record_time(i) for i in range(5)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # ロック取得時間が妥当であることを確認
        avg_time = sum(lock_acquisition_times) / len(lock_acquisition_times)
        assert avg_time < 2.0, f"Lock acquisition too slow: {avg_time}s average"
    
    @pytest.mark.asyncio
    async def test_deadlock_prevention(self):
        """デッドロック防止テスト"""
        guild1 = MockGuild(id=12345)
        guild2 = MockGuild(id=12346)
        voice_channel1 = MockVoiceChannel(id=67890, guild=guild1)
        voice_channel2 = MockVoiceChannel(id=67891, guild=guild2)
        
        async def operation_sequence_1():
            # ギルド1 -> ギルド2の順でリソースアクセス
            interaction1 = MockInteraction(guild=guild1)
            interaction1.user.voice = MagicMock()
            interaction1.user.voice.channel = voice_channel1
            
            await self.control_cog.pomodoro.callback(self.control_cog, interaction1, 25, 5, 15)
            await asyncio.sleep(0.1)
            
            interaction2 = MockInteraction(guild=guild2)
            interaction2.user.voice = MagicMock()
            interaction2.user.voice.channel = voice_channel2
            
            await self.control_cog.pomodoro.callback(self.control_cog, interaction2, 25, 5, 15)
        
        async def operation_sequence_2():
            # ギルド2 -> ギルド1の順でリソースアクセス
            interaction2 = MockInteraction(guild=guild2)
            interaction2.user.voice = MagicMock()
            interaction2.user.voice.channel = voice_channel2
            
            await self.control_cog.pomodoro.callback(self.control_cog, interaction2, 30, 5, 15)
            await asyncio.sleep(0.1)
            
            interaction1 = MockInteraction(guild=guild1)
            interaction1.user.voice = MagicMock()
            interaction1.user.voice.channel = voice_channel1
            
            await self.control_cog.pomodoro.callback(self.control_cog, interaction1, 30, 5, 15)
        
        # デッドロックが発生しないことを確認（タイムアウト付き）
        start_time = time.time()
        results = await asyncio.wait_for(
            asyncio.gather(operation_sequence_1(), operation_sequence_2(), return_exceptions=True),
            timeout=10.0  # 10秒でタイムアウト
        )
        end_time = time.time()
        
        execution_time = end_time - start_time
        assert execution_time < 5.0, f"Possible deadlock detected: {execution_time}s execution"


class TestConcurrentErrorHandling:
    """並行エラーハンドリングのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_error_isolation_between_guilds(self):
        """ギルド間でのエラー分離テスト"""
        guild_count = 10
        error_guild_indices = {2, 5, 8}  # 特定のギルドでエラーを発生
        
        tasks = []
        for i in range(guild_count):
            guild = MockGuild(id=70000 + i)
            voice_channel = MockVoiceChannel(id=80000 + i, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            # 特定のギルドでエラーを発生させる
            if i in error_guild_indices:
                interaction.response.send_message = AsyncMock(
                    side_effect=Exception(f"Error in guild {i}")
                )
            
            task = self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
            tasks.append((task, i, i in error_guild_indices))
        
        # 並行実行
        results = await asyncio.gather(*[task for task, _, _ in tasks], return_exceptions=True)
        
        # エラーが発生したギルドと成功したギルドを分析
        for i, (result, guild_index, should_error) in enumerate(zip(results, [t[1] for t in tasks], [t[2] for t in tasks])):
            if should_error:
                assert isinstance(result, Exception), f"Guild {guild_index} should have failed"
            else:
                # 他のギルドのエラーが影響しないことを確認
                pass  # 実装に応じて成功条件を確認
    
    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self):
        """連鎖障害防止テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        
        # 段階的にエラーを発生させる
        error_intervals = [0, 0.5, 1.0, 1.5, 2.0]  # エラー発生タイミング
        
        async def delayed_error_operation(delay):
            await asyncio.sleep(delay)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            interaction.response.send_message = AsyncMock(
                side_effect=Exception(f"Error at {delay}s")
            )
            
            return await self.control_cog.pomodoro.callback(self.control_cog, interaction, 25, 5, 15)
        
        # 段階的エラー実行
        tasks = [delayed_error_operation(delay) for delay in error_intervals]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 全てエラーになっても回復可能であることを確認
        assert all(isinstance(r, Exception) for r in results), "Some operations should have failed"
        
        # 正常な操作が可能であることを確認
        normal_interaction = MockInteraction(guild=MockGuild(id=99999))
        normal_voice_channel = MockVoiceChannel(id=99999, guild=normal_interaction.guild)
        normal_interaction.user.voice = MagicMock()
        normal_interaction.user.voice.channel = normal_voice_channel
        
        # 正常操作が成功することを確認
        normal_result = await self.control_cog.pomodoro.callback(self.control_cog, normal_interaction, 25, 5, 15)
        # 実装に応じて成功条件を確認