import asyncio
import uuid
from typing import TypedDict

from libopensonic.media.media_types import Child
from livekit.rtc import Room
from stoat import TextChannel


class Session(TypedDict):
    id: str
    channel_id: str
    voice_room: Room
    playback_queue: list[Child]
    ffmpeg_process: None
    packet_queue: asyncio.Queue[bytes | None]
    packet_queue_process: asyncio.Task[None]


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    def exists(self, channel: TextChannel) -> bool:
        return any(session["channel_id"] == channel.id for _, session in self.sessions.items())

    def get_by_channel(self, channel: TextChannel) -> Session | None:
        return next(
            (session for session in self.sessions.values() if session["channel_id"] == channel.id),
            None,
        )

    def delete(self, id: str) -> None:

        # TODO: Deconstruct

        del self.sessions[id]

    def new(self, room: Room, channel: TextChannel) -> str:
        possible_session = self.get_by_channel(channel)
        if possible_session is not None:
            return possible_session["id"]

        session_id = str(uuid.uuid4())

        self.sessions[session_id] = {
            "id": session_id,
            "channel_id": channel.id,
            "voice_room": room,
            "playback_queue": [],
            "packet_queue": asyncio.Queue(maxsize=100),
            "packet_queue_process": None,
            "ffmpeg_process": None,
        }

        return session_id
