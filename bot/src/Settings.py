import discord
from configs import user_messages as u_msg, config


class Settings:

    def __init__(self, duration, short_break=None, long_break=None, intervals=None):
        self.duration = duration
        self.short_break = short_break
        self.long_break = long_break
        self.intervals = intervals

    @classmethod
    async def is_valid(cls, ctx, duration: int, short_break: int = None,
                       long_break: int = None, intervals: int = None) -> bool:
        if config.MAX_INTERVAL_MINUTES > duration > 0 \
                and (not short_break or config.MAX_INTERVAL_MINUTES > short_break > 0) \
                and (not long_break or config.MAX_INTERVAL_MINUTES > long_break > 0) \
                and (not intervals or config.MAX_INTERVAL_MINUTES > intervals > 0):
            return True
        await ctx.send("is_valid:" + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR)
        return False

    @classmethod
    async def is_valid_interaction(cls, interaction: discord.Interaction, duration: int, short_break: int = None,
                       long_break: int = None, intervals: int = None) -> bool:
        print(f"DEBUG: is_valid_interaction called with: duration={duration}, short_break={short_break}, long_break={long_break}, intervals={intervals}")
        print(f"DEBUG: MAX_INTERVAL_MINUTES={config.MAX_INTERVAL_MINUTES}")
        
        duration_valid = config.MAX_INTERVAL_MINUTES >= duration > 0
        short_break_valid = not short_break or config.MAX_INTERVAL_MINUTES >= short_break > 0
        long_break_valid = not long_break or config.MAX_INTERVAL_MINUTES >= long_break > 0
        intervals_valid = not intervals or config.MAX_INTERVAL_MINUTES >= intervals > 0
        
        print(f"DEBUG: duration_valid={duration_valid}, short_break_valid={short_break_valid}, long_break_valid={long_break_valid}, intervals_valid={intervals_valid}")
        
        is_valid = duration_valid and short_break_valid and long_break_valid and intervals_valid
        print(f"DEBUG: validation result: {is_valid}")
        
        return is_valid
