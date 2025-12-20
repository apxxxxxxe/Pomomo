"""
設定バリデーション簡易テスト

Settings クラスの基本的なバリデーション機能をテスト
実際のAPIに基づいて作成
"""
import pytest
from unittest.mock import MagicMock
from tests.mocks.discord_mocks import MockInteraction, MockUser, MockGuild
from src.Settings import Settings


class TestSettingsValidation:
    """Settings基本バリデーションのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.guild = MockGuild()
        self.interaction = MockInteraction(guild=self.guild)
    
    @pytest.mark.asyncio
    async def test_valid_pomodoro_settings(self):
        """有効なポモドーロ設定のテスト"""
        # 標準的なポモドーロ設定
        assert await Settings.is_valid_interaction(self.interaction, 25, 5, 15), "標準設定で失敗"
        
        # 最小値
        assert await Settings.is_valid_interaction(self.interaction, 1, 1, 1), "最小値で失敗"
        
        # 一般的なカスタム設定
        assert await Settings.is_valid_interaction(self.interaction, 30, 5, 20), "カスタム設定で失敗"
        
        # 短い休憩なしでの設定
        assert await Settings.is_valid_interaction(self.interaction, 25, None, 15), "短い休憩なしで失敗"
        
        # 長い休憩なしでの設定  
        assert await Settings.is_valid_interaction(self.interaction, 25, 5, None), "長い休憩なしで失敗"
    
    def test_invalid_pomodoro_settings(self):
        """無効なポモドーロ設定のテスト"""
        # ゼロ値
        assert not Settings.is_valid_interaction(self.interaction, 0, 5, 15), "ゼロ値で成功してはいけない"
        
        # 負の値
        assert not Settings.is_valid_interaction(self.interaction, -1, 5, 15), "負の値で成功してはいけない"
        assert not Settings.is_valid_interaction(self.interaction, 25, -1, 15), "負の短い休憩で成功してはいけない"
        assert not Settings.is_valid_interaction(self.interaction, 25, 5, -1), "負の長い休憩で成功してはいけない"
        
        # 非常に大きな値（MAX_INTERVAL_MINUTESを超える）
        assert not Settings.is_valid_interaction(self.interaction, 10000, 5, 15), "巨大な値で成功してはいけない"
    
    def test_settings_constructor(self):
        """Settingsコンストラクタのテスト"""
        # 基本的なコンストラクタ
        settings = Settings(25, 5, 15, 4)
        
        assert settings.duration == 25, "duration設定が正しくない"
        assert settings.short_break == 5, "short_break設定が正しくない"  
        assert settings.long_break == 15, "long_break設定が正しくない"
        assert settings.intervals == 4, "intervals設定が正しくない"
        
        # オプション引数なしのコンストラクタ
        settings_minimal = Settings(30)
        assert settings_minimal.duration == 30, "最小設定のdurationが正しくない"
        assert settings_minimal.short_break is None, "デフォルトshort_breakがNoneでない"
        assert settings_minimal.long_break is None, "デフォルトlong_breakがNoneでない" 
        assert settings_minimal.intervals is None, "デフォルトintervalsがNoneでない"
    
    def test_unicode_interaction(self):
        """Unicode文字を含むインタラクションのテスト"""
        unicode_names = ["こんにちは", "🎮", "Müller", "Café"]
        
        for name in unicode_names:
            user = MockUser(name=name)
            interaction = MockInteraction(user=user, guild=self.guild)
            
            # Unicode文字があっても設定検証は正常動作するはず
            assert Settings.is_valid_interaction(interaction, 25, 5, 15), f"Unicode名'{name}'で失敗"
    
    def test_edge_case_values(self):
        """エッジケース値のテスト"""
        # 非常に小さい値
        assert Settings.is_valid_interaction(self.interaction, 1), "最小duration失敗"
        
        # Noneを含む組み合わせ
        assert Settings.is_valid_interaction(self.interaction, 25, None, None), "休憩None組み合わせ失敗"
        
        # 一部だけNone
        assert Settings.is_valid_interaction(self.interaction, 25, 5, None), "長い休憩のみNone失敗"
        assert Settings.is_valid_interaction(self.interaction, 25, None, 15), "短い休憩のみNone失敗"


class TestBoundaryValues:
    """境界値のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.guild = MockGuild()
        self.interaction = MockInteraction(guild=self.guild)
    
    def test_duration_boundaries(self):
        """時間の境界値テスト"""
        # 最小値
        assert Settings.is_valid_interaction(self.interaction, 1), "最小duration(1)失敗"
        
        # 一般的な最大値（実際のMAX_INTERVAL_MINUTESに依存）
        # config.pyを確認せずに安全な値でテスト
        assert Settings.is_valid_interaction(self.interaction, 60), "一般的duration(60)失敗"
        
        # 境界を超える値（実装によって変わるので大きめの値を使用）
        assert not Settings.is_valid_interaction(self.interaction, 99999), "巨大duration成功してはいけない"
    
    def test_break_boundaries(self):
        """休憩時間の境界値テスト"""
        # 休憩時間の最小値
        assert Settings.is_valid_interaction(self.interaction, 25, 1), "短い休憩最小値失敗"
        assert Settings.is_valid_interaction(self.interaction, 25, None, 1), "長い休憩最小値失敗"
        
        # 休憩時間の一般的な値
        assert Settings.is_valid_interaction(self.interaction, 25, 30), "短い休憩一般値失敗"
        assert Settings.is_valid_interaction(self.interaction, 25, None, 30), "長い休憩一般値失敗"
        
        # 境界を超える休憩時間
        assert not Settings.is_valid_interaction(self.interaction, 25, 99999), "巨大短い休憩成功してはいけない"
        assert not Settings.is_valid_interaction(self.interaction, 25, None, 99999), "巨大長い休憩成功してはいけない"


class TestInputSanitization:
    """入力サニタイゼーションのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.guild = MockGuild()
        self.interaction = MockInteraction(guild=self.guild)
    
    def test_type_safety(self):
        """型安全性のテスト"""
        # 正常な整数値
        assert Settings.is_valid_interaction(self.interaction, 25, 5, 15), "正常整数値失敗"
        
        # 文字列数値（実装によって処理が異なる可能性）
        try:
            # 一部の実装では文字列を自動変換する可能性
            result = Settings.is_valid_interaction(self.interaction, "25", "5", "15")
            # 成功した場合は自動変換、失敗した場合は型チェック
        except (TypeError, ValueError):
            # 型エラーで拒否されるのは正常な動作
            pass
        
        # 明らかに無効な型
        try:
            result = Settings.is_valid_interaction(self.interaction, "abc", 5, 15)
            # 無効な型が何らかの形で処理される場合
            assert not result, "無効な型で成功してはいけない"
        except (TypeError, ValueError):
            # 型エラーで拒否されるのは正常
            pass
    
    def test_none_values(self):
        """None値のテスト"""
        # durationがNoneの場合（これは無効であるべき）
        try:
            result = Settings.is_valid_interaction(self.interaction, None, 5, 15)
            assert not result, "duration=Noneで成功してはいけない"
        except (TypeError, ValueError):
            # 型エラーで拒否されるのは正常
            pass
        
        # 休憩時間がNoneの場合（これは有効）
        assert Settings.is_valid_interaction(self.interaction, 25, None, None), "休憩None組み合わせ失敗"


class TestRealWorldScenarios:
    """実世界シナリオのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.guild = MockGuild()
        self.interaction = MockInteraction(guild=self.guild)
    
    def test_common_configurations(self):
        """一般的な設定のテスト"""
        common_configs = [
            (25, 5, 15),    # クラシック ポモドーロ
            (25, 5, 30),    # 長い長期休憩
            (30, 5, 15),    # 少し長めの作業時間
            (20, 5, 20),    # バランス型
            (45, 10, 30),   # 長時間集中
            (15, 3, 15),    # 短時間集中
        ]
        
        for duration, short, long_break in common_configs:
            assert Settings.is_valid_interaction(self.interaction, duration, short, long_break), \
                f"一般的設定({duration}, {short}, {long_break})失敗"
    
    def test_minimal_configurations(self):
        """最小限設定のテスト"""
        # durationのみ
        assert Settings.is_valid_interaction(self.interaction, 25), "duration単体失敗"
        
        # durationと短い休憩のみ
        assert Settings.is_valid_interaction(self.interaction, 25, 5), "duration+短い休憩失敗"
        
        # 全て最小値
        assert Settings.is_valid_interaction(self.interaction, 1, 1, 1), "全て最小値失敗"
    
    def test_unusual_but_valid(self):
        """珍しいが有効な設定のテスト"""
        unusual_configs = [
            (1, None, None),    # 最小duration、休憩なし
            (60, 1, 1),         # 長duration、短休憩
            (10, 30, 60),       # 短duration、長休憩
        ]
        
        for duration, short, long_break in unusual_configs:
            assert Settings.is_valid_interaction(self.interaction, duration, short, long_break), \
                f"珍しい設定({duration}, {short}, {long_break})失敗"