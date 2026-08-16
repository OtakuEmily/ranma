"""Ranma-specific extensions to the Stoat bot framework."""

from typing import Any

from stoat.ext import commands

from ranma.events.startup import StartupEvent
from ranma.utilities.settings import settings


class RanmaBot(commands.Bot):
    """Bot subclass that wires the Ranma lifecycle and command checks."""

    def __init__(
        self,
        *,
        description: str | None = None,
        self_bot: bool = False,
        strip_after_prefix: bool = False,
        user_bot: bool = False,
        **options: Any,
    ) -> None:
        """Initialise Ranma with project-specific defaults.

        Args:
            self_bot: Whether the bot runs in self-bot mode.
            strip_after_prefix: Whether to strip content after the prefix.
            user_bot: Whether the bot runs in user-bot mode.
            **options: Additional options passed to the Stoat bot base class.
        """
        super().__init__(
            self.prefix,
            description="Ranma, an OpenSubsonic music bot for Stoat.chat.",
            self_bot=self_bot,
            strip_after_prefix=strip_after_prefix,
            user_bot=user_bot,
            **options,
        )
        self._has_fired_startup = False

    async def setup_hook(self) -> None:
        """Dispatch startup events before running the base setup hook."""
        if not self._has_fired_startup:
            self.dispatch(StartupEvent())
            self._has_fired_startup = True
        return await super().setup_hook()

    async def close(self, *, http: bool = True, cleanup_websocket: bool = True) -> None:
        """Close the bot and database connections in shutdown order."""
        await super().close(http=http, cleanup_websocket=cleanup_websocket)

    async def prefix(self, _: commands.Context) -> list[str]:
        """Return valid command prefixes for the current context.

        Args:
            ctx: Command execution context.

        Returns:
            Command prefixes valid for the current context.
        """
        prefixes = ["ranma!", "rm!"]

        if self.me:
            prefixes.append(f"{self.me.mention} ")
            prefixes.append(self.me.mention)

        return prefixes
