"""
パフォーマンス・負荷テスト

大規模ギルド、高頻度コマンド実行、メモリ使用量など
Pomomoボットのパフォーマンスと負荷耐性をテスト
"""
import pytest
import asyncio
import time
import statistics
from unittest.mock import MagicMock, AsyncMock, patch
from tests.mocks.discord_mocks import (
    MockInteraction, MockGuild, MockVoiceChannel, MockBot, 
    MockMember, MockUser, MockTextChannel
)
from cogs.control import Control
from cogs.subscribe import Subscribe
from src.session import session_manager
from src.voice_client import vc_manager


class TestHighVolumeOperations:
    """大量操作のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        self.subscribe_cog = Subscribe(self.bot)
        
        # 全状態をクリア
        session_manager.active_sessions.clear()
        vc_manager.connected_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_high_frequency_command_execution(self):
        """高頻度コマンド実行テスト"""
        guild = MockGuild(id=12345)
        voice_channel = MockVoiceChannel(id=67890, guild=guild)
        
        command_count = 100
        execution_times = []
        
        for i in range(command_count):
            interaction = MockInteraction(guild=guild)
            interaction.user = MockUser(id=1000 + i)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            start_time = time.time()
            
            try:
                # 異なるコマンドをローテーション
                if i % 4 == 0:
                    await self.control_cog.pomodoro(interaction, 25, 5, 15)
                elif i % 4 == 1:
                    await self.control_cog.stop(interaction)
                elif i % 4 == 2:
                    await self.control_cog.skip(interaction)
                else:
                    await self.control_cog.countdown(interaction, 10)
            except Exception:
                pass  # エラーは無視してパフォーマンスに集中
            
            end_time = time.time()
            execution_times.append(end_time - start_time)
        
        # パフォーマンス分析
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)
        p95_time = statistics.quantiles(execution_times, n=20)[18]  # 95パーセンタイル
        
        # パフォーマンス要件を確認
        assert avg_time < 0.1, f"Average execution time too slow: {avg_time:.3f}s"
        assert max_time < 1.0, f"Maximum execution time too slow: {max_time:.3f}s"
        assert p95_time < 0.2, f"95th percentile too slow: {p95_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_large_guild_simulation(self):
        """大規模ギルドシミュレーション"""
        large_guild = MockGuild(id=99999)
        
        # 大量のボイスチャンネルとメンバーを作成
        voice_channel_count = 20
        members_per_channel = 50
        
        voice_channels = []
        all_members = []
        
        for channel_id in range(voice_channel_count):
            voice_channel = MockVoiceChannel(
                id=100000 + channel_id, 
                name=f"voice-{channel_id}", 
                guild=large_guild
            )
            
            # チャンネルにメンバーを追加
            channel_members = []
            for member_id in range(members_per_channel):
                member = MockMember(
                    guild=large_guild,
                    user=MockUser(id=200000 + channel_id * 1000 + member_id)
                )
                channel_members.append(member)
                all_members.append(member)
            
            voice_channel.members = channel_members
            voice_channels.append(voice_channel)
        
        large_guild.voice_channels = voice_channels
        large_guild.members = all_members
        
        # 大規模ギルドでのAutoMute操作
        start_time = time.time()
        
        # 全チャンネルでAutoMute操作を並行実行
        tasks = []
        for voice_channel in voice_channels:
            from src.subscriptions.AutoMute import AutoMute
            automute = AutoMute(self.bot, large_guild.id, voice_channel)
            task = automute.handle_all(enable=True)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_members = voice_channel_count * members_per_channel
        
        # パフォーマンス要件
        execution_time = end_time - start_time
        members_per_second = total_members / execution_time
        
        assert execution_time < 30.0, f"Large guild processing too slow: {execution_time:.2f}s for {total_members} members"
        assert members_per_second > 50, f"Member processing rate too slow: {members_per_second:.2f} members/s"
    
    @pytest.mark.asyncio
    async def test_burst_traffic_handling(self):
        """バースト トラフィック処理テスト"""
        burst_size = 50
        burst_count = 5
        
        overall_start_time = time.time()
        burst_times = []
        
        for burst_num in range(burst_count):
            # バーストの準備
            interactions = []
            for i in range(burst_size):
                guild = MockGuild(id=300000 + burst_num * 1000 + i)
                voice_channel = MockVoiceChannel(id=400000 + burst_num * 1000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                interactions.append(interaction)
            
            # バースト実行
            burst_start_time = time.time()
            
            tasks = [
                self.control_cog.pomodoro(interaction, 25, 5, 15)
                for interaction in interactions
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            burst_end_time = time.time()
            burst_time = burst_end_time - burst_start_time
            burst_times.append(burst_time)
            
            # バースト間の間隔
            await asyncio.sleep(0.5)
        
        overall_end_time = time.time()
        
        # バーストパフォーマンス分析
        avg_burst_time = statistics.mean(burst_times)
        total_operations = burst_size * burst_count
        overall_time = overall_end_time - overall_start_time
        
        assert avg_burst_time < 5.0, f"Burst processing too slow: {avg_burst_time:.2f}s per burst"
        assert overall_time < burst_count * 10, f"Overall burst handling too slow: {overall_time:.2f}s"


class TestMemoryAndResourceUsage:
    """メモリとリソース使用量のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self):
        """メモリ使用量スケーリングテスト"""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")
        
        process = psutil.Process(os.getpid())
        
        # 段階的に負荷を増加させてメモリ使用量を測定
        session_counts = [10, 50, 100, 200]
        memory_measurements = []
        
        for session_count in session_counts:
            # ベースラインメモリ
            baseline_memory = process.memory_info().rss
            
            # セッション作成
            interactions = []
            for i in range(session_count):
                guild = MockGuild(id=500000 + i)
                voice_channel = MockVoiceChannel(id=600000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                interactions.append(interaction)
            
            # 全セッション作成
            tasks = [
                self.control_cog.pomodoro(interaction, 25, 5, 15)
                for interaction in interactions
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # メモリ使用量測定
            peak_memory = process.memory_info().rss
            memory_increase = peak_memory - baseline_memory
            memory_per_session = memory_increase / session_count
            memory_measurements.append((session_count, memory_per_session))
            
            # セッションクリーンアップ
            cleanup_tasks = [
                self.control_cog.stop(interaction)
                for interaction in interactions
            ]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # ガベージコレクション
            import gc
            gc.collect()
        
        # メモリ使用効率の分析
        for session_count, memory_per_session in memory_measurements:
            # セッション当たりのメモリ使用量が妥当であることを確認（1MB以下）
            assert memory_per_session < 1024 * 1024, \
                f"Memory per session too high: {memory_per_session / 1024:.2f}KB for {session_count} sessions"
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_effectiveness(self):
        """リソースクリーンアップ効果テスト"""
        cycles = 10
        baseline_session_count = len(session_manager.active_sessions)
        baseline_voice_count = len(vc_manager.connected_sessions)
        
        for cycle in range(cycles):
            session_count = 20
            
            # リソース作成
            interactions = []
            for i in range(session_count):
                guild = MockGuild(id=700000 + cycle * 1000 + i)
                voice_channel = MockVoiceChannel(id=800000 + cycle * 1000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                interactions.append(interaction)
            
            # セッション作成
            create_tasks = [
                self.control_cog.pomodoro(interaction, 25, 5, 15)
                for interaction in interactions
            ]
            await asyncio.gather(*create_tasks, return_exceptions=True)
            
            # 中間チェック
            mid_session_count = len(session_manager.active_sessions)
            mid_voice_count = len(vc_manager.connected_sessions)
            
            # クリーンアップ
            cleanup_tasks = [
                self.control_cog.stop(interaction)
                for interaction in interactions
            ]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # クリーンアップ効果確認
            final_session_count = len(session_manager.active_sessions)
            final_voice_count = len(vc_manager.connected_sessions)
            
            # リソースリークがないことを確認
            session_leak = final_session_count - baseline_session_count
            voice_leak = final_voice_count - baseline_voice_count
            
            assert session_leak <= cycle + 1, f"Session leak detected: {session_leak} sessions"
            assert voice_leak <= cycle + 1, f"Voice connection leak detected: {voice_leak} connections"
    
    @pytest.mark.asyncio
    async def test_garbage_collection_effectiveness(self):
        """ガベージコレクション効果テスト"""
        try:
            import gc
            import sys
        except ImportError:
            pytest.skip("GC utilities not available")
        
        # GCを無効化して対象を蓄積
        gc.disable()
        
        try:
            initial_objects = len(gc.get_objects())
            
            # 大量のオブジェクトを作成・削除
            for round_num in range(5):
                interactions = []
                for i in range(50):
                    guild = MockGuild(id=900000 + round_num * 1000 + i)
                    voice_channel = MockVoiceChannel(id=910000 + round_num * 1000 + i, guild=guild)
                    interaction = MockInteraction(guild=guild)
                    interaction.user.voice = MagicMock()
                    interaction.user.voice.channel = voice_channel
                    interactions.append(interaction)
                
                # オブジェクト作成
                tasks = [
                    self.control_cog.pomodoro(interaction, 25, 5, 15)
                    for interaction in interactions
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # オブジェクト削除
                cleanup_tasks = [
                    self.control_cog.stop(interaction)
                    for interaction in interactions
                ]
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                
                # 参照をクリア
                interactions.clear()
                tasks.clear()
                cleanup_tasks.clear()
            
            before_gc_objects = len(gc.get_objects())
            
            # GCを有効化して実行
            gc.enable()
            collected = gc.collect()
            
            after_gc_objects = len(gc.get_objects())
            
            # GCが効果的であることを確認
            gc_effectiveness = (before_gc_objects - after_gc_objects) / before_gc_objects
            
            assert collected > 0, "No objects collected by GC"
            assert gc_effectiveness > 0.1, f"GC not effective enough: {gc_effectiveness:.2%} reduction"
        
        finally:
            gc.enable()


class TestResponseTimeConsistency:
    """応答時間一貫性のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_response_time_under_load(self):
        """負荷時の応答時間テスト"""
        measurement_count = 100
        background_load_count = 50
        
        # バックグラウンド負荷を開始
        background_tasks = []
        for i in range(background_load_count):
            guild = MockGuild(id=1000000 + i)
            voice_channel = MockVoiceChannel(id=1100000 + i, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            task = self.control_cog.pomodoro(interaction, 25, 5, 15)
            background_tasks.append(task)
        
        # バックグラウンド負荷を開始（完了を待たない）
        background_future = asyncio.gather(*background_tasks, return_exceptions=True)
        
        # メイン測定
        response_times = []
        
        for i in range(measurement_count):
            guild = MockGuild(id=2000000 + i)
            voice_channel = MockVoiceChannel(id=2100000 + i, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            start_time = time.time()
            
            try:
                await self.control_cog.pomodoro(interaction, 25, 5, 15)
            except Exception:
                pass
            
            end_time = time.time()
            response_times.append(end_time - start_time)
            
            # 測定間隔
            await asyncio.sleep(0.01)
        
        # バックグラウンド負荷の完了を待つ
        await background_future
        
        # 応答時間の分析
        avg_response = statistics.mean(response_times)
        std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
        max_response = max(response_times)
        
        # 一貫性要件
        assert avg_response < 0.2, f"Average response time under load too slow: {avg_response:.3f}s"
        assert std_dev < 0.1, f"Response time too inconsistent: {std_dev:.3f}s standard deviation"
        assert max_response < 1.0, f"Maximum response time too slow: {max_response:.3f}s"
    
    @pytest.mark.asyncio
    async def test_response_time_degradation(self):
        """応答時間劣化テスト"""
        session_increments = [0, 10, 50, 100, 200]
        response_time_measurements = []
        
        for active_sessions in session_increments:
            # アクティブセッションを作成
            sessions = []
            for i in range(active_sessions):
                guild = MockGuild(id=3000000 + i)
                voice_channel = MockVoiceChannel(id=3100000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                sessions.append(interaction)
                
                await self.control_cog.pomodoro(interaction, 25, 5, 15)
            
            # 新しいセッションの応答時間を測定
            test_guild = MockGuild(id=4000000)
            test_voice_channel = MockVoiceChannel(id=4100000, guild=test_guild)
            test_interaction = MockInteraction(guild=test_guild)
            test_interaction.user.voice = MagicMock()
            test_interaction.user.voice.channel = test_voice_channel
            
            measurement_runs = 10
            run_times = []
            
            for run in range(measurement_runs):
                start_time = time.time()
                
                try:
                    await self.control_cog.pomodoro(test_interaction, 25, 5, 15)
                    await self.control_cog.stop(test_interaction)  # クリーンアップ
                except Exception:
                    pass
                
                end_time = time.time()
                run_times.append(end_time - start_time)
            
            avg_time = statistics.mean(run_times)
            response_time_measurements.append((active_sessions, avg_time))
            
            # セッションクリーンアップ
            cleanup_tasks = [
                self.control_cog.stop(session)
                for session in sessions
            ]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # 劣化分析
        baseline_time = response_time_measurements[0][1]  # セッション0個時
        
        for session_count, avg_time in response_time_measurements[1:]:
            degradation_ratio = avg_time / baseline_time
            
            # 劣化が許容範囲内であることを確認
            max_acceptable_degradation = 1 + (session_count * 0.01)  # 1%/セッション
            
            assert degradation_ratio <= max_acceptable_degradation, \
                f"Response time degradation too high with {session_count} sessions: {degradation_ratio:.2f}x baseline"


class TestThroughputMeasurement:
    """スループット測定のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.control_cog = Control(self.bot)
        session_manager.active_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_command_throughput(self):
        """コマンドスループットテスト"""
        duration_seconds = 10
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        command_count = 0
        successful_commands = 0
        
        while time.time() < end_time:
            guild = MockGuild(id=5000000 + command_count)
            voice_channel = MockVoiceChannel(id=5100000 + command_count, guild=guild)
            interaction = MockInteraction(guild=guild)
            interaction.user.voice = MagicMock()
            interaction.user.voice.channel = voice_channel
            
            try:
                await self.control_cog.pomodoro(interaction, 25, 5, 15)
                successful_commands += 1
            except Exception:
                pass
            
            command_count += 1
            
            # CPU時間を他のタスクに譲る
            await asyncio.sleep(0.001)
        
        actual_duration = time.time() - start_time
        commands_per_second = successful_commands / actual_duration
        success_rate = successful_commands / command_count if command_count > 0 else 0
        
        # スループット要件
        assert commands_per_second > 10, f"Command throughput too low: {commands_per_second:.2f} commands/s"
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2%}"
    
    @pytest.mark.asyncio
    async def test_concurrent_throughput(self):
        """並行スループットテスト"""
        concurrent_workers = 10
        commands_per_worker = 20
        
        async def worker(worker_id):
            successful = 0
            
            for i in range(commands_per_worker):
                guild = MockGuild(id=6000000 + worker_id * 1000 + i)
                voice_channel = MockVoiceChannel(id=6100000 + worker_id * 1000 + i, guild=guild)
                interaction = MockInteraction(guild=guild)
                interaction.user.voice = MagicMock()
                interaction.user.voice.channel = voice_channel
                
                try:
                    await self.control_cog.pomodoro(interaction, 25, 5, 15)
                    successful += 1
                except Exception:
                    pass
            
            return successful
        
        # 並行ワーカーを実行
        start_time = time.time()
        worker_results = await asyncio.gather(*[
            worker(worker_id) for worker_id in range(concurrent_workers)
        ])
        end_time = time.time()
        
        # 結果分析
        total_successful = sum(worker_results)
        total_attempted = concurrent_workers * commands_per_worker
        execution_time = end_time - start_time
        
        concurrent_throughput = total_successful / execution_time
        overall_success_rate = total_successful / total_attempted
        
        # 並行スループット要件
        assert concurrent_throughput > 50, f"Concurrent throughput too low: {concurrent_throughput:.2f} commands/s"
        assert overall_success_rate > 0.7, f"Overall success rate too low: {overall_success_rate:.2%}"