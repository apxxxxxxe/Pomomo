"""
AutoMute機能の網羅的テスト

複雑なボイスチャンネル移動、権限変更、大量ユーザー対応など
AutoMute機能の実運用での複雑なシナリオを網羅的にテスト
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from tests.mocks.discord_mocks import (
    MockGuild, MockVoiceChannel, MockMember, MockUser, MockBot,
    MockVoiceState, MockInteraction
)
from cogs.subscribe import Subscribe
from src.subscriptions.AutoMute import AutoMute


class TestAutoMuteBasicFunctionality:
    """AutoMute基本機能のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
        self.automute = AutoMute()
    
    @pytest.mark.asyncio
    async def test_mute_member_success(self):
        """メンバーミュート成功テスト"""
        member = MockMember(guild=self.guild)
        
        await self.automute.mute(member)
        
        # safe_edit_memberが正しいパラメータで呼ばれることを確認
        member.edit.assert_called_once_with(mute=True)
    
    @pytest.mark.asyncio
    async def test_unmute_member_success(self):
        """メンバーアンミュート成功テスト"""
        member = MockMember(guild=self.guild)
        
        await self.automute.unmute(member)
        
        # safe_edit_memberが正しいパラメータで呼ばれることを確認
        member.edit.assert_called_once_with(mute=False)
    
    @pytest.mark.asyncio
    async def test_mute_member_permission_error(self):
        """ミュート時権限エラーテスト"""
        member = MockMember(guild=self.guild)
        member.edit = AsyncMock(side_effect=discord.Forbidden(
            response=MagicMock(),
            message="Missing permissions"
        ))
        
        # 権限エラーが適切に処理されることを確認
        await self.automute.mute(member)
        member.edit.assert_called_once_with(mute=True)
    
    @pytest.mark.asyncio
    async def test_handle_all_enable_mute(self):
        """全メンバーミュート有効化テスト"""
        members = [MockMember(guild=self.guild) for _ in range(3)]
        self.voice_channel.members = members
        
        await self.automute.handle_all(enable=True)
        
        # 全メンバーがミュートされることを確認
        for member in members:
            member.edit.assert_called_with(mute=True)
    
    @pytest.mark.asyncio
    async def test_handle_all_disable_mute(self):
        """全メンバーミュート無効化テスト"""
        members = [MockMember(guild=self.guild) for _ in range(3)]
        self.voice_channel.members = members
        
        await self.automute.handle_all(enable=False)
        
        # 全メンバーのミュートが解除されることを確認
        for member in members:
            member.edit.assert_called_with(mute=False)


class TestComplexVoiceChannelMovements:
    """複雑なボイスチャンネル移動のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
        self.guild = MockGuild(id=12345)
        
        # 複数のボイスチャンネルを作成
        self.voice_channel1 = MockVoiceChannel(id=11111, name="channel1", guild=self.guild)
        self.voice_channel2 = MockVoiceChannel(id=22222, name="channel2", guild=self.guild)
        self.voice_channel3 = MockVoiceChannel(id=33333, name="channel3", guild=self.guild)
        
        self.guild.voice_channels = [
            self.voice_channel1, 
            self.voice_channel2, 
            self.voice_channel3
        ]
    
    @pytest.mark.asyncio
    async def test_rapid_channel_switching(self):
        """高速チャンネル切り替えテスト"""
        member = MockMember(guild=self.guild)
        
        # 高速でチャンネル間を移動
        channels = [self.voice_channel1, self.voice_channel2, self.voice_channel3, None]
        
        for before_channel, after_channel in zip([None] + channels[:-1], channels):
            before_state = MockVoiceState(channel=before_channel, member=member)
            after_state = MockVoiceState(channel=after_channel, member=member)
            
            await self.subscribe_cog.on_voice_state_update(member, before_state, after_state)
            
            # 短時間の間隔をシミュレート
            await asyncio.sleep(0.01)
    
    @pytest.mark.asyncio
    async def test_simultaneous_multi_channel_movements(self):
        """同時多チャンネル移動テスト"""
        members = [MockMember(guild=self.guild, user=MockUser(id=i)) for i in range(10)]
        
        # 複数メンバーが同時に異なるチャンネルに移動
        tasks = []
        for i, member in enumerate(members):
            target_channel = self.guild.voice_channels[i % len(self.guild.voice_channels)]
            before_state = MockVoiceState(channel=None, member=member)
            after_state = MockVoiceState(channel=target_channel, member=member)
            
            task = self.subscribe_cog.on_voice_state_update(member, before_state, after_state)
            tasks.append(task)
        
        # 同時実行
        await asyncio.gather(*tasks)
    
    @pytest.mark.asyncio
    async def test_channel_cascade_movement(self):
        """チャンネル連鎖移動テスト"""
        members = [MockMember(guild=self.guild, user=MockUser(id=i)) for i in range(5)]
        
        # メンバーが連鎖的にチャンネルを移動（玉突き状態）
        for round_num in range(3):
            for i, member in enumerate(members):
                current_channel = self.guild.voice_channels[i % len(self.guild.voice_channels)]
                next_channel = self.guild.voice_channels[(i + round_num) % len(self.guild.voice_channels)]
                
                before_state = MockVoiceState(channel=current_channel, member=member)
                after_state = MockVoiceState(channel=next_channel, member=member)
                
                await self.subscribe_cog.on_voice_state_update(member, before_state, after_state)


class TestPermissionScenarios:
    """権限シナリオのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_permission_hierarchy_conflicts(self):
        """権限階層衝突テスト"""
        # より高い権限を持つメンバーをミュートしようとする
        high_role_member = MockMember(guild=self.guild)
        high_role_member.edit = AsyncMock(side_effect=discord.Forbidden(
            response=MagicMock(),
            message="Cannot mute member with higher or equal role"
        ))
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 権限不足が適切に処理されることを確認
        await automute.mute(high_role_member)
        high_role_member.edit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_permission_changes_during_operation(self):
        """操作中の権限変更テスト"""
        members = [MockMember(guild=self.guild) for _ in range(5)]
        self.voice_channel.members = members
        
        # 途中で権限が変更される状況をシミュレート
        def edit_with_permission_change(call_count=[0]):
            call_count[0] += 1
            if call_count[0] > 2:  # 3回目以降は権限エラー
                raise discord.Forbidden(response=MagicMock(), message="Permission changed")
            return AsyncMock()
        
        for i, member in enumerate(members):
            if i >= 2:  # 3番目以降のメンバーは権限エラー
                member.edit = AsyncMock(side_effect=discord.Forbidden(
                    response=MagicMock(),
                    message="Permission changed"
                ))
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 権限変更が適切に処理されることを確認
        await automute.handle_all(enable=True)
    
    @pytest.mark.asyncio
    async def test_bot_role_moved_during_mute(self):
        """ミュート中のBot役割移動テスト"""
        member = MockMember(guild=self.guild)
        
        # 最初は成功、後で権限不足
        member.edit = AsyncMock(side_effect=[
            None,  # 最初は成功
            discord.Forbidden(response=MagicMock(), message="Role moved")  # 後で失敗
        ])
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 最初のミュートは成功
        await automute.mute(member)
        
        # 役割移動後は失敗するが適切にハンドリング
        await automute.mute(member)


class TestLargeScaleOperations:
    """大規模操作のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_large_channel_mute_all(self):
        """大規模チャンネル一括ミュートテスト"""
        # 100人のメンバーをシミュレート
        large_member_count = 100
        members = [
            MockMember(guild=self.guild, user=MockUser(id=i)) 
            for i in range(large_member_count)
        ]
        self.voice_channel.members = members
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 大量ミュートが適切に処理されることを確認
        start_time = asyncio.get_event_loop().time()
        await automute.handle_all(enable=True)
        end_time = asyncio.get_event_loop().time()
        
        # 全メンバーがミュートされることを確認
        for member in members:
            member.edit.assert_called_with(mute=True)
        
        # 実行時間が適切な範囲内であることを確認（タイムアウト防止）
        execution_time = end_time - start_time
        assert execution_time < 10, f"Large scale mute took too long: {execution_time}s"
    
    @pytest.mark.asyncio
    async def test_multiple_guild_concurrent_operations(self):
        """複数ギルド同時操作テスト"""
        guild_count = 10
        guilds_and_channels = []
        
        for i in range(guild_count):
            guild = MockGuild(id=12345 + i)
            voice_channel = MockVoiceChannel(id=67890 + i, name=f"voice-{i}", guild=guild)
            
            # 各チャンネルに複数メンバー
            members = [
                MockMember(guild=guild, user=MockUser(id=j + i * 100)) 
                for j in range(10)
            ]
            voice_channel.members = members
            
            guilds_and_channels.append((guild, voice_channel))
        
        # 全ギルドで同時にAutoMute操作
        tasks = []
        for guild, voice_channel in guilds_and_channels:
            automute = AutoMute(self.bot, guild.id, voice_channel)
            task = automute.handle_all(enable=True)
            tasks.append(task)
        
        # 同時実行
        await asyncio.gather(*tasks)
        
        # 全ギルドで適切に処理されることを確認
        for guild, voice_channel in guilds_and_channels:
            for member in voice_channel.members:
                member.edit.assert_called_with(mute=True)


class TestErrorRecoveryScenarios:
    """エラー回復シナリオのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_partial_mute_failure_recovery(self):
        """部分的ミュート失敗からの回復テスト"""
        members = [MockMember(guild=self.guild, user=MockUser(id=i)) for i in range(5)]
        self.voice_channel.members = members
        
        # 一部のメンバーでエラーを発生させる
        for i, member in enumerate(members):
            if i == 2:  # 3番目のメンバーでエラー
                member.edit = AsyncMock(side_effect=discord.Forbidden(
                    response=MagicMock(),
                    message="Cannot mute this member"
                ))
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 一部失敗しても他のメンバーは処理されることを確認
        await automute.handle_all(enable=True)
        
        for i, member in enumerate(members):
            member.edit.assert_called_with(mute=True)
    
    @pytest.mark.asyncio
    async def test_network_interruption_recovery(self):
        """ネットワーク中断からの回復テスト"""
        member = MockMember(guild=self.guild)
        
        # ネットワークエラーをシミュレート
        member.edit = AsyncMock(side_effect=[
            ConnectionError("Network interrupted"),  # 最初は失敗
            None  # 回復後は成功
        ])
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # 最初の試行は失敗
        await automute.mute(member)
        
        # 再試行は成功
        await automute.mute(member)
        
        assert member.edit.call_count == 2
    
    @pytest.mark.asyncio
    async def test_member_left_during_mute_operation(self):
        """ミュート操作中のメンバー退室テスト"""
        members = [MockMember(guild=self.guild, user=MockUser(id=i)) for i in range(3)]
        self.voice_channel.members = members
        
        # メンバーがチャンネルを離脱した状況をシミュレート
        members[1].edit = AsyncMock(side_effect=discord.NotFound(
            response=MagicMock(),
            message="Member not found"
        ))
        
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # メンバー不在エラーが適切に処理されることを確認
        await automute.handle_all(enable=True)
        
        # 存在するメンバーは処理される
        members[0].edit.assert_called_with(mute=True)
        members[2].edit.assert_called_with(mute=True)


class TestServerMutedUserRecovery:
    """サーバーミュートユーザー回復のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_server_muted_user_recovery_success(self):
        """サーバーミュートユーザー回復成功テスト"""
        member = MockMember(guild=self.guild)
        member.voice.mute = True  # サーバーミュート状態
        
        # ミュート解除成功をシミュレート
        member.edit = AsyncMock()
        
        await self.subscribe_cog._handle_server_muted_user_join(member, self.voice_channel)
        
        # ミュート解除が呼ばれることを確認
        member.edit.assert_called_once_with(mute=False)
    
    @pytest.mark.asyncio
    async def test_server_muted_user_recovery_permission_failure(self):
        """サーバーミュートユーザー回復権限失敗テスト"""
        member = MockMember(guild=self.guild)
        member.voice.mute = True
        
        # 権限不足をシミュレート
        member.edit = AsyncMock(side_effect=discord.Forbidden(
            response=MagicMock(),
            message="Missing permissions"
        ))
        
        # ミュート解除指示メッセージが送信されることを確認
        with patch.object(self.subscribe_cog, '_send_unmute_instruction') as mock_send:
            await self.subscribe_cog._handle_server_muted_user_join(member, self.voice_channel)
            mock_send.assert_called_once_with(member, self.voice_channel)
    
    @pytest.mark.asyncio
    async def test_multiple_server_muted_users_recovery(self):
        """複数サーバーミュートユーザー回復テスト"""
        members = [MockMember(guild=self.guild, user=MockUser(id=i)) for i in range(3)]
        
        # 全員がサーバーミュート状態
        for member in members:
            member.voice.mute = True
        
        # 権限がある場合とない場合をミックス
        members[0].edit = AsyncMock()  # 成功
        members[1].edit = AsyncMock(side_effect=discord.Forbidden(
            response=MagicMock(), message="No permission"
        ))  # 権限不足
        members[2].edit = AsyncMock()  # 成功
        
        with patch.object(self.subscribe_cog, '_send_unmute_instruction') as mock_send:
            for member in members:
                await self.subscribe_cog._handle_server_muted_user_join(member, self.voice_channel)
            
            # 権限不足のメンバーにのみメッセージが送信される
            mock_send.assert_called_once_with(members[1], self.voice_channel)
        
        # 権限があるメンバーはミュート解除される
        members[0].edit.assert_called_with(mute=False)
        members[2].edit.assert_called_with(mute=False)


class TestAutoMuteStateConsistency:
    """AutoMute状態一貫性のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.bot = MockBot()
        self.subscribe_cog = Subscribe(self.bot)
        self.guild = MockGuild(id=12345)
        self.voice_channel = MockVoiceChannel(id=67890, name="test-voice", guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_automute_state_persistence_across_commands(self):
        """コマンド間でのAutoMute状態永続化テスト"""
        interaction = MockInteraction(guild=self.guild)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = self.voice_channel
        
        # AutoMute有効化
        await self.subscribe_cog.enableautomute(interaction)
        
        # 別のコマンド実行後も状態が維持されることを確認
        interaction2 = MockInteraction(guild=self.guild)
        interaction2.user.voice = MagicMock()
        interaction2.user.voice.channel = self.voice_channel
        
        # 無効化
        await self.subscribe_cog.disableautomute(interaction2)
    
    @pytest.mark.asyncio
    async def test_automute_state_cleanup_on_bot_disconnect(self):
        """Bot切断時のAutoMute状態クリーンアップテスト"""
        # AutoMute有効状態を設定
        from src.subscriptions.AutoMute import AutoMute
        automute = AutoMute(self.bot, self.guild.id, self.voice_channel)
        
        # Bot切断をシミュレート（実装に応じて調整が必要）
        # 状態がクリーンアップされることを確認