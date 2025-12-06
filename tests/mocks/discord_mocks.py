"""
Mock Discord objects for testing without actual Discord API calls.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from typing import Optional, List, Any, Dict


class MockUser:
    """Mock Discord User object"""
    
    def __init__(self, id: int = 12345, name: str = "TestUser", discriminator: str = "1234"):
        self.id = id
        self.name = name
        self.discriminator = discriminator
        self.display_name = name
        self.mention = f"<@{id}>"
        self.avatar = None
        self.bot = False
        self.system = False
        self.created_at = datetime.now()
        
    def __str__(self):
        return f"{self.name}#{self.discriminator}"
        
    def __eq__(self, other):
        if isinstance(other, MockUser):
            return self.id == other.id
        return False


class MockVoiceState:
    """Mock Discord VoiceState object"""
    
    def __init__(self, channel=None, member=None):
        self.channel = channel
        self.member = member
        self.self_mute = False
        self.self_deaf = False
        self.mute = False
        self.deaf = False
        self.afk = False


class MockMember(MockUser):
    """Mock Discord Member object"""
    
    def __init__(self, user: MockUser = None, guild=None, voice_channel=None):
        if user:
            super().__init__(user.id, user.name, user.discriminator)
        else:
            super().__init__()
        
        self.guild = guild
        self.nick = None
        self.roles = []
        self.joined_at = datetime.now()
        self.premium_since = None
        self.pending = False
        self.voice = MockVoiceState(channel=voice_channel, member=self)
        
        # Mock methods
        self.add_roles = AsyncMock()
        self.remove_roles = AsyncMock()
        self.edit = AsyncMock()
        self.kick = AsyncMock()
        self.ban = AsyncMock()


class MockRole:
    """Mock Discord Role object"""
    
    def __init__(self, id: int = 67890, name: str = "TestRole"):
        self.id = id
        self.name = name
        self.position = 1
        self.color = 0x000000
        self.hoist = False
        self.mentionable = False
        self.permissions = MagicMock()
        self.created_at = datetime.now()


class MockVoiceChannel:
    """Mock Discord VoiceChannel object"""
    
    def __init__(self, id: int = 11111, name: str = "Test Voice Channel", guild=None):
        self.id = id
        self.name = name
        self.guild = guild
        self.position = 0
        self.bitrate = 64000
        self.user_limit = 0
        self.members = []
        self.created_at = datetime.now()
        self.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))
        
        # Mock methods
        self.connect = AsyncMock()
        self.delete = AsyncMock()
        self.edit = AsyncMock()


class MockTextChannel:
    """Mock Discord TextChannel object"""
    
    def __init__(self, id: int = 22222, name: str = "test-channel", guild=None):
        self.id = id
        self.name = name
        self.guild = guild
        self.position = 0
        self.topic = None
        self.slowmode_delay = 0
        self.nsfw = False
        self.created_at = datetime.now()
        self.mention = f"<#{id}>"
        self.permissions_for = MagicMock(return_value=MagicMock(
            send_messages=True, 
            read_messages=True,
            view_channel=True
        ))
        
        # Mock methods
        self.send = AsyncMock()
        self.delete = AsyncMock()
        self.edit = AsyncMock()
        self.purge = AsyncMock()


class MockGuild:
    """Mock Discord Guild object"""
    
    def __init__(self, id: int = 54321, name: str = "Test Guild"):
        self.id = id
        self.name = name
        self.description = None
        self.icon = None
        self.banner = None
        self.splash = None
        self.owner_id = 12345
        self.region = "us-west"
        self.afk_channel = None
        self.afk_timeout = 300
        self.verification_level = 0
        self.default_notifications = 0
        self.explicit_content_filter = 0
        self.features = []
        self.premium_tier = 0
        self.premium_subscription_count = 0
        self.preferred_locale = "en-US"
        self.created_at = datetime.now()
        
        # Collections
        self.channels = []
        self.voice_channels = []
        self.text_channels = []
        self.members = []
        self.roles = []
        
        # Bot member
        self.me = MockMember(MockUser(id=99999, name="TestBot"), self)
        
        # Voice client
        self.voice_client = None
        
        # Mock methods
        self.get_channel = MagicMock()
        self.get_member = MagicMock()
        self.get_role = MagicMock()
        self.fetch_member = AsyncMock()
        self.ban = AsyncMock()
        self.unban = AsyncMock()
        self.kick = AsyncMock()
        self.edit = AsyncMock()


class MockInteractionResponse:
    """Mock Discord InteractionResponse object"""
    
    def __init__(self):
        self.send_message = AsyncMock()
        self.defer = AsyncMock()
        self.edit_message = AsyncMock()
        self.delete_message = AsyncMock()
        self.is_done = MagicMock(return_value=False)


class MockWebhook:
    """Mock Discord Webhook object"""
    
    def __init__(self):
        self.send = AsyncMock()
        self.edit = AsyncMock()
        self.delete = AsyncMock()


class MockFollowup:
    """Mock Discord Followup object"""
    
    def __init__(self):
        self.send = AsyncMock()
        self.edit = AsyncMock()
        self.delete = AsyncMock()


class MockInteraction:
    """Mock Discord Interaction object"""
    
    def __init__(self, user: MockUser = None, guild: MockGuild = None, 
                 channel: MockTextChannel = None, command_name: str = "test"):
        self.id = 98765
        self.type = 2  # ApplicationCommandType.chat_input
        self.token = "test_token"
        self.application_id = 11111
        self.user = user or MockUser()
        self.guild = guild or MockGuild()
        self.guild_id = self.guild.id
        self.channel = channel or MockTextChannel(guild=self.guild)
        self.channel_id = self.channel.id
        self.created_at = datetime.now()
        self.command = MagicMock(name=command_name)
        self.locale = "en-US"
        self.guild_locale = "en-US"
        
        # Client (bot instance)
        self.client = MockBot()
        
        # Response and followup
        self.response = MockInteractionResponse()
        self.followup = MockFollowup()
        
        # Mock methods
        self.edit_original_response = AsyncMock()
        self.delete_original_response = AsyncMock()
        self.original_response = AsyncMock()
        self.send = AsyncMock()


class MockMessage:
    """Mock Discord Message object"""
    
    def __init__(self, author: MockUser = None, channel: MockTextChannel = None,
                 content: str = "Test message"):
        self.id = 13579
        self.author = author or MockUser()
        self.channel = channel or MockTextChannel()
        self.guild = self.channel.guild
        self.content = content
        self.embeds = []
        self.attachments = []
        self.pinned = False
        self.mention_everyone = False
        self.mentions = []
        self.role_mentions = []
        self.created_at = datetime.now()
        self.edited_at = None
        
        # Mock methods
        self.edit = AsyncMock()
        self.delete = AsyncMock()
        self.pin = AsyncMock()
        self.unpin = AsyncMock()
        self.add_reaction = AsyncMock()
        self.remove_reaction = AsyncMock()
        self.clear_reactions = AsyncMock()


class MockBot:
    """Mock Discord Bot object"""
    
    def __init__(self):
        self.user = MockUser(id=99999, name="TestBot")
        self.guilds = []
        self.application_id = 11111
        self.owner_id = 12345
        self.command_prefix = "test!"
        self.description = "Test Bot"
        self.intents = MagicMock()
        self.latency = 0.1
        
        # Mock methods
        self.get_guild = MagicMock()
        self.get_channel = MagicMock()
        self.get_user = MagicMock()
        self.fetch_guild = AsyncMock()
        self.fetch_channel = AsyncMock()
        self.fetch_user = AsyncMock()
        self.add_cog = AsyncMock()
        self.remove_cog = AsyncMock()
        self.load_extension = AsyncMock()
        self.unload_extension = AsyncMock()
        self.reload_extension = AsyncMock()
        self.start = AsyncMock()
        self.close = AsyncMock()
        self.change_presence = AsyncMock()
        
        # Events
        self.wait_for = AsyncMock()
        self.wait_until_ready = AsyncMock()
        
        # Voice clients
        self.voice_clients = []