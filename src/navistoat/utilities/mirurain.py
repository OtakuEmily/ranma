"""Navistoat-specific extensions to the Stoat bot framework."""

from typing import Any

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from stoat import Message, Shard
from stoat.ext import commands
from tortoise import Tortoise

from navistoat.events.startup import StartupEvent

from .database import build_tortoise_config
from .settings import settings

tracer = trace.get_tracer(__name__)


class NavistoatBot(commands.Bot):
    """Bot subclass that wires the Navistoat lifecycle and command checks."""

    def __init__(
        self,
        *,
        description: str | None = None,
        self_bot: bool = False,
        strip_after_prefix: bool = False,
        user_bot: bool = False,
        **options: Any,
    ) -> None:
        """Initialize the Navistoat bot with project-specific defaults.

        Args:
            description: Bot description.
            self_bot: Whether the bot runs in self-bot mode.
            strip_after_prefix: Whether to strip content after the prefix.
            user_bot: Whether the bot runs in user-bot mode.
            **options: Additional options passed to the Stoat bot base class.
        """
        super().__init__(
            self.prefix,
            description=description,
            self_bot=self_bot,
            strip_after_prefix=strip_after_prefix,
            user_bot=user_bot,
            **options,
        )
        self._has_fired_startup = False
        self._db_initialised = False

    async def setup_hook(self) -> None:
        """Dispatch startup events before running the base setup hook."""
        if not self._db_initialised:
            await Tortoise.init(config=build_tortoise_config(settings.database.uri))
            self._db_initialised = True

        if not self._has_fired_startup:
            self.dispatch(StartupEvent())
            self._has_fired_startup = True
        return await super().setup_hook()

    async def close(self, *, http: bool = True, cleanup_websocket: bool = True) -> None:
        """Close the bot and database connections in shutdown order."""
        try:
            await super().close(http=http, cleanup_websocket=cleanup_websocket)
        finally:
            if self._db_initialised:
                await Tortoise.close_connections()
                self._db_initialised = False

    async def process_commands(self, message: Message, shard: Shard, /) -> None:
        """Process an incoming message and execute matching commands with tracing.

        Args:
            message: Incoming message event.
            shard: Gateway shard that delivered the message.
        """
        # TODO (Emily): Refactor all of this shit
        if message.author.bot:
            return

        ctx = await self.get_context(message, shard)
        if ctx.command is None:
            return

        with tracer.start_as_current_span(
            "stoat.command.pending",
        ) as span:
            span.set_attribute("stoat.message.id", message.id)
            span.set_attribute("stoat.author.id", message.author_id)
            span.set_attribute("stoat.channel.id", message.channel_id)
            span.set_attribute("stoat.command.prefix", ctx.prefix)
            span.set_attribute("stoat.command.parents", ctx.invoked_parents or [])
            span.set_attribute("stoat.command.qualified_name", ctx.command.qualified_name)

            try:
                await super().process_commands(message, shard)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            else:
                span.set_status(Status(StatusCode.OK))
            finally:
                span.update_name("stoat.command")

    async def _block_dms(self, ctx: commands.Context) -> bool:
        """Reject command execution in direct messages.

        Args:
            ctx: Command execution context.

        Returns:
            True when command execution is permitted.

        Raises:
            commands.CheckFailure: If the command is invoked in a direct message.
        """
        if ctx.server is None:
            raise commands.CheckFailure("Commands are unavailable in direct messages.")

        return True

    async def prefix(self, _: commands.Context) -> list[str]:
        """Return valid command prefixes for the current context.

        Args:
            ctx: Command execution context.

        Returns:
            Command prefixes valid for the current context.
        """
        prefixes = ["navistoat!", "mr!", "miru!"]

        if self.me:
            prefixes.append(f"{self.me.mention} ")
            prefixes.append(self.me.mention)

        return prefixes
