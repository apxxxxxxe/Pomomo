import discord
# Support both Context and Interaction


def get_voice_client(ctx):
    voice_client = getattr(ctx, 'voice_client', None) or ctx.guild.voice_client
    if not (voice_client and voice_client.is_connected()):
        return
    return voice_client


def get_voice_channel(ctx):
    vc = get_voice_client(ctx)
    if not vc:
        return
    return vc.channel


def get_true_members_in_voice_channel(ctx) -> [discord.Member]:
    vc = get_voice_channel(ctx)
    if not vc:
        return []
    members = vc.members
    for member in members:
        if member.bot:
            members.remove(member)
    return members


def get_voice_channel_interaction(interaction):
    """Get voice channel from interaction object"""
    voice_client = interaction.guild.voice_client
    if not (voice_client and voice_client.is_connected()):
        return
    return voice_client.channel


