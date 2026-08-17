import contextlib

from libopensonic import AsyncConnection
from stoat import (
    Forbidden,
    InstanceLivekitVoiceFeature,
    MessageCreateEvent,
    SendableEmbed,
    TextChannel,
)
from stoat.ext import commands

from ranma.classes.sessions import SessionManager, SessionManagerFull
from ranma.utilities.ranma import RanmaBot
from ranma.utilities.resolve_node import node_from_timezone
from ranma.utilities.settings import settings


class PlayerGear(commands.Gear):
    def __init__(self, bot: RanmaBot) -> None:
        super().__init__()
        self.bot = bot
        self.server = AsyncConnection(
            settings.server.base_url,
            settings.server.username,
            settings.server.password,
            settings.server.port,
            api_key=settings.server.api_key,
        )
        self.session_manager = SessionManager(self.server)

    async def gear_unload(self) -> None:
        await self.server.cleanup()
        return await super().gear_unload()

    @commands.command()
    async def disconnect(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return
        if ctx.channel.voice is None:
            await ctx.message.reply("Channel lacks voice data.")
            return

        if not self.session_manager.exists(ctx.channel):
            await ctx.message.reply("Channel doesn't have a session.")
            return

        await self.session_manager.delete(ctx.channel)

    @commands.command()
    async def skip(self, ctx: commands.Context) -> None:

        # Check if the command was sent in a voice channel
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return

        # Check if the user is present in the channel
        if not any(
            user.user_id == ctx.author.id for user in ctx.channel.voice_states.participants.values()
        ):
            await ctx.message.reply(
                "You must be present in the voice channel to manage its session."
            )
            return

        # Check if a session exists for the channel
        if not self.session_manager.exists(ctx.channel):
            await ctx.message.reply("You'll need to start a session channel to manage the queue.")
            return

        await self.session_manager.skip(ctx.channel)
        await ctx.message.reply(embeds=[SendableEmbed(title="Skipped!")])

    @commands.command()
    async def play(self, ctx: commands.Context, *, query: str) -> None:

        # Check if the command was sent in a voice channel
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return

        # Check if the user is present in the channel
        if not any(
            user.user_id == ctx.author.id for user in ctx.channel.voice_states.participants.values()
        ):
            await ctx.message.reply(
                "You must be present in the voice channel to manage its session."
            )
            return

        # Check if a session exists for the channel
        if not self.session_manager.exists(ctx.channel):
            await ctx.message.reply("You'll need to start a session channel to manage the queue.")
            return

        # Loading embed
        msg = await ctx.message.reply(
            embeds=[SendableEmbed(title="Loading...", description="This may take a second.")]
        )

        # Fetch possible songs
        search = await self.server.search3(
            query,
            artist_count=0,
            album_count=0,
            song_count=10,
        )

        # Check if any results were found
        if search.song is None or len(search.song) < 1:
            await msg.edit(
                embeds=[
                    SendableEmbed(
                        title="No results...", description=f"No results were found for `{query}`."
                    )
                ]
            )
            return

        # TODO: Tidy
        result_text = ""
        for index, song in enumerate(search.song):
            result_text = (
                result_text + f"{index + 1}. {song.title} ({song.album}) by {song.display_artist}\n"
            )
        result_text = result_text.removesuffix("\n")

        await msg.edit(
            embeds=[
                SendableEmbed(
                    title="Results!",
                    description=f"Found {len(search.song)} tracks, reply with number of the track you'd like to queue.\n\n{result_text}",
                )
            ]
        )

        reply = await self.bot.wait_for(
            MessageCreateEvent,
            check=lambda event: (
                event.message.author.id == ctx.author.id
                and event.message.channel.id == ctx.channel.id
            ),
        )
        with contextlib.suppress(Forbidden):
            await reply.message.delete()

        try:
            int(reply.message.content)
        except TypeError:
            await msg.edit(
                embeds=[
                    SendableEmbed(
                        title="Not a number...",
                        description="Your reply was not a number, please rerun the command to retry.",
                    )
                ]
            )
            return

        try:
            song = search.song[int(reply.message.content) - 1]
        except IndexError:
            await msg.edit(
                embeds=[
                    SendableEmbed(
                        title="Not in range...",
                        description="Your reply was not in the range given, please rerun the command to retry.",
                    )
                ]
            )
            return

        pos = self.session_manager.enqueue(ctx.channel, song)
        await msg.edit(
            embeds=[
                SendableEmbed(
                    title=f"Queued - {song.title}",
                    description=f'Added "{song.title}" by {song.display_artist or song.artist or "N/A"} to the session queue at position {pos + 1}.',
                )
            ]
        )

    @commands.command()
    async def connect(self, ctx: commands.Context) -> None:
        # Check if the command was sent in a voice channel
        if not isinstance(ctx.channel, TextChannel):
            await ctx.message.reply("This command can only run in a voice compatible channel.")
            return

        # Check if the channel has voice data
        if ctx.channel.voice is None:
            await ctx.message.reply("Channel lacks voice data.")
            return

        # Check if the user is present in the channel
        if not any(
            user.user_id == ctx.author.id for user in ctx.channel.voice_states.participants.values()
        ):
            await ctx.message.reply(
                "You must be present in the voice channel to manage its session."
            )
            return

        # Check if an existing session exists for the channel
        if self.session_manager.exists(ctx.channel):
            await ctx.message.reply("Channel already has a session.")
            return

        # Send progressive message
        msg = await ctx.message.reply(
            embeds=[
                SendableEmbed(
                    title="Loading the cassette tape...",
                    description="Currently querying voice node information.",
                )
            ]
        )

        # Select a voice node to use
        node = ctx.channel.voice_states.node
        if node == "":
            instance = await self.bot.http.query_node()

            # Handle non-Livekit instances
            if not isinstance(instance.features.voice, InstanceLivekitVoiceFeature):
                await msg.edit(
                    embeds=[
                        SendableEmbed(
                            title="Failed to load...",
                            description="Instance is not Livekit compatible, are the nodes down?",
                        )
                    ]
                )
                return

            # Handle no advertised nodes
            if len(instance.features.voice.nodes) < 1:
                await msg.edit(
                    embeds=[
                        SendableEmbed(
                            title="Failed to load...",
                            description="Instance has Livekit enabled but advertises no nodes.",
                        )
                    ]
                )
                return

            node = node_from_timezone(instance.features.voice.nodes).name

        await msg.edit(
            embeds=[
                SendableEmbed(
                    title="Engaging the read heads...",
                    description="Connecting to voice node.",
                )
            ]
        )

        # Connect and setup session
        room = await ctx.channel.connect(node=node)
        try:
            await self.session_manager.new(room, ctx.channel)
        except SessionManagerFull:
            await room.disconnect()
            await msg.edit(
                embeds=[
                    SendableEmbed(
                        title="Failed...",
                        description="Instance has hit its configured channel limit, try again later.",
                    )
                ]
            )
            return

        await msg.edit(
            embeds=[
                SendableEmbed(
                    title="Ready to play!",
                    description=f"Created a new session in {ctx.channel.mention}, start queuing music with *{ctx.prefix.strip()}play __[song]__*!",
                )
            ]
        )
