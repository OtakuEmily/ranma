import asyncio
from typing import TypedDict

from libopensonic import AsyncConnection
from libopensonic.media.media_types import Child
from livekit.rtc import Room
from stoat import TextChannel

from ranma.utilities.audio import ProducerSignal, audio_consumer, audio_producer
from ranma.utilities.settings import settings


class SessionManagerFull(Exception):
    """Raised when the session manager runs out of slots."""


class Session(TypedDict):
    channel_id: str
    voice_room: Room
    playback_queue: list[Child]

    # Audio production
    producer_process: asyncio.Task[None]
    producer_command_queue: asyncio.Queue[ProducerSignal]

    # Audio consumution
    consumer_process: asyncio.Task[None]
    consumer_queue: asyncio.Queue[bytes | None]


class SessionManager:
    def __init__(self, server: AsyncConnection) -> None:
        self.sessions: dict[str, Session] = {}
        self.server = server

    def exists(self, channel: TextChannel) -> bool:
        return self.sessions.get(channel.id) is not None

    async def delete(self, channel: TextChannel) -> None:

        session = self.sessions.get(channel.id)
        if session is None:
            return

        session["consumer_queue"].put_nowait(None)
        session["producer_command_queue"].put_nowait(ProducerSignal.KILL)

        session["consumer_process"].cancel()
        session["producer_process"].cancel()

        await session["voice_room"].disconnect()

        del self.sessions[channel.id]

    def enqueue(self, channel: TextChannel, song: Child) -> int:
        session = self.sessions.get(channel.id)
        if session is None:
            raise TypeError("channel has no session")

        queue = session["playback_queue"]
        queue.append(song)
        return len(queue) - 1

    async def skip(self, channel: TextChannel) -> None:
        session = self.sessions.get(channel.id)
        if session is None:
            raise TypeError("channel has no session")

        session["producer_command_queue"].put_nowait(ProducerSignal.SKIP)

    async def new(self, room: Room, channel: TextChannel) -> str:
        possible_session = self.sessions.get(channel.id)
        if possible_session is not None:
            return possible_session["channel_id"]

        if len(self.sessions) >= settings.limits.max_channels:
            raise SessionManagerFull(
                f"session manager has hit its {settings.limits.max_channels} channel limit"
            )

        consumer_queue = asyncio.Queue()
        playback_queue: list[Child] = []
        producer_command_queue: asyncio.Queue[ProducerSignal] = asyncio.Queue()

        # Spawn the consumer and producer tasks
        # TODO: Attach better error handling and respawning
        consumer_process = asyncio.create_task(
            audio_consumer(
                room,
                consumer_queue,
            )
        )
        producer_process = asyncio.create_task(
            audio_producer(
                consumer_queue,
                playback_queue,
                self.server,
                producer_command_queue,
            )
        )

        self.sessions[channel.id] = {
            "channel_id": channel.id,
            "voice_room": room,
            "playback_queue": playback_queue,
            "consumer_process": consumer_process,
            "consumer_queue": consumer_queue,
            "producer_process": producer_process,
            "producer_command_queue": producer_command_queue,
        }

        return channel.id
