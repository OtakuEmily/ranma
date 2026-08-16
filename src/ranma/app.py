from importlib.metadata import version
from time import time

from loguru import logger

from ranma.events.startup import StartupEvent
from ranma.gears.player import PlayerGear

from .utilities.ranma import RanmaBot
from .utilities.settings import settings

gears = [PlayerGear]


def main() -> None:
    start = time()
    bot = RanmaBot()

    @bot.listen()
    async def startup(event: StartupEvent) -> None:
        for g in gears:
            gear = g(bot)
            await bot.add_gear(gear)
            logger.info(f"registered {gear.qualified_name}")
        logger.info("completed registering gears")

        end = time()
        logger.info(f"intialised in {(end - start) * 1000:.2f}ms")

    logger.info(f"starting ranma v{version('ranma')}")
    bot.run(settings.stoat.api_key)
