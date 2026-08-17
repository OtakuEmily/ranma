from stoat import InstanceLivekitVoiceFeature, SendableEmbed, TextChannel
from stoat.ext import commands

from ranma.classes.sessions import SessionManager
from ranma.utilities.ranma import RanmaBot
from ranma.utilities.resolve_node import node_from_timezone


class PlayerGear(commands.Gear):
    def __init__(self, bot: RanmaBot) -> None:
        super().__init__()
        self.bot = bot
        self.session_manager = SessionManager()

    @commands.command()
    async def disconnect(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return
        if ctx.channel.voice is None:
            await ctx.message.reply("Channel lacks voice data.")
            return

        if self.session_manager.exists(ctx.channel):
            await ctx.message.reply("Channel already has a session.")
            return

    @commands.command()
    async def connect(self, ctx: commands.Context) -> None:
        # TODO (Emily): Swap behaviour to user's voice channel though this is way fucking harder

        # Check if the command was sent in a voice channel
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return
        if ctx.channel.voice is None:
            await ctx.message.reply("Channel lacks voice data.")
            return

        if self.session_manager.exists(ctx.channel):
            await ctx.message.reply("Channel already has a session.")
            return

        # Select a voice node to use
        node = ctx.channel.voice_states.node
        if node == "":
            instance = await self.bot.http.query_node()

            if not isinstance(instance.features.voice, InstanceLivekitVoiceFeature):
                await ctx.message.reply("Instance did not provide Livekit voice features...")
                return

            if len(instance.features.voice.nodes) < 1:
                await ctx.message.reply("Instance did not provide voice nodes...")
                return

            node = node_from_timezone(instance.features.voice.nodes).name

        room = await ctx.channel.connect(node=node)
        self.session_manager.new(room, ctx.channel)

        await ctx.message.reply(
            embeds=[
                SendableEmbed(
                    title="New session!",
                    description=f"Created a new session in {ctx.channel.mention}, start queuing music with `@{self.bot.me.display_name or self.bot.me.name} play [song]`!",
                )
            ]
        )
