"""
Mock Voice Client objects for testing voice functionality without actual voice connections.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Optional


class MockAudioSource:
    """Mock Discord AudioSource object"""
    
    def __init__(self, title: str = "Test Audio", duration: float = 10.0):
        self.title = title
        self.duration = duration
        self.is_opus = False
        self.read = MagicMock(return_value=b'audio_data')
        self.cleanup = MagicMock()


class MockFFmpegPCMAudio(MockAudioSource):
    """Mock Discord FFmpegPCMAudio object"""
    
    def __init__(self, source: str = "test.mp3", **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.options = kwargs


class MockFFmpegOpusAudio(MockAudioSource):
    """Mock Discord FFmpegOpusAudio object"""
    
    def __init__(self, source: str = "test.mp3", **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.options = kwargs
        self.is_opus = True


class MockVoiceClient:
    """Mock Discord VoiceClient object"""
    
    def __init__(self, channel=None, guild=None):
        self.channel = channel
        self.guild = guild
        self.user = MagicMock(id=99999, name="TestBot")
        self.session_id = "test_session_id"
        self.token = "test_voice_token"
        self.endpoint = "test.discord.media"
        self.latency = 0.05
        self.average_latency = 0.05
        
        # Voice state
        self.is_connected = MagicMock(return_value=True)
        self.is_playing = MagicMock(return_value=False)
        self.is_paused = MagicMock(return_value=False)
        
        # Current source
        self.source = None
        
        # Mock methods
        self.play = MagicMock()
        self.pause = MagicMock()
        self.resume = MagicMock()
        self.stop = MagicMock()
        self.disconnect = AsyncMock()
        self.move_to = AsyncMock()
        self.cleanup = MagicMock()
        
        # Event handling
        self.wait_for = AsyncMock()
        
    def play(self, source, *, after=None):
        """Mock play method"""
        self.source = source
        self.is_playing.return_value = True
        self.is_paused.return_value = False
        
        # Simulate async completion
        if after:
            after(None)  # Call after callback with no error
            
    def pause(self):
        """Mock pause method"""
        if self.is_playing():
            self.is_paused.return_value = True
            
    def resume(self):
        """Mock resume method"""
        if self.is_paused():
            self.is_paused.return_value = False
            
    def stop(self):
        """Mock stop method"""
        self.is_playing.return_value = False
        self.is_paused.return_value = False
        self.source = None


class MockVoiceProtocol:
    """Mock Voice Protocol for lower-level voice operations"""
    
    def __init__(self):
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.send_audio = AsyncMock()
        self.start_voice = AsyncMock()
        self.stop_voice = AsyncMock()


class MockVoiceManager:
    """Mock Voice Manager for managing voice connections"""
    
    def __init__(self):
        self.voice_clients = {}
        self.connect = AsyncMock(return_value=MockVoiceClient())
        self.disconnect = AsyncMock()
        self.get_voice_client = MagicMock(return_value=None)
        
    async def connect_to_channel(self, channel):
        """Mock method to connect to a voice channel"""
        voice_client = MockVoiceClient(channel=channel, guild=channel.guild)
        self.voice_clients[channel.guild.id] = voice_client
        return voice_client
        
    async def disconnect_from_guild(self, guild_id):
        """Mock method to disconnect from a guild's voice channel"""
        if guild_id in self.voice_clients:
            voice_client = self.voice_clients[guild_id]
            await voice_client.disconnect()
            del self.voice_clients[guild_id]
            
    def get_voice_client_for_guild(self, guild_id):
        """Mock method to get voice client for a guild"""
        return self.voice_clients.get(guild_id)


class MockPlayerState:
    """Mock Player State for audio playback state"""
    
    def __init__(self):
        self.is_playing = False
        self.is_paused = False
        self.current_source = None
        self.volume = 1.0
        self.position = 0.0
        
    def set_playing(self, source=None):
        """Set player to playing state"""
        self.is_playing = True
        self.is_paused = False
        self.current_source = source
        
    def set_paused(self):
        """Set player to paused state"""
        self.is_paused = True
        
    def set_stopped(self):
        """Set player to stopped state"""
        self.is_playing = False
        self.is_paused = False
        self.current_source = None
        self.position = 0.0


# Utility functions for creating mock objects

def create_mock_voice_client(channel=None, guild=None):
    """Create a mock voice client with optional channel and guild"""
    return MockVoiceClient(channel=channel, guild=guild)


def create_mock_audio_source(source_type="pcm", **kwargs):
    """Create a mock audio source of the specified type"""
    if source_type.lower() == "opus":
        return MockFFmpegOpusAudio(**kwargs)
    else:
        return MockFFmpegPCMAudio(**kwargs)


def setup_voice_client_mocks():
    """Setup common voice client mocks for testing"""
    return {
        'voice_client': MockVoiceClient(),
        'voice_manager': MockVoiceManager(),
        'player_state': MockPlayerState(),
        'audio_source': MockAudioSource()
    }