import asyncio
import signal as signals
from enum import Enum
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit

from libopensonic import AsyncConnection
from libopensonic.media.media_types import Child
from livekit import rtc
from loguru import logger

SAMPLE_RATE = 48000
NUM_CHANNELS = 1
BYTES_PER_SAMPLE = 2  # s16le
FRAME_DURATION_MS = 20
SAMPLES_PER_CHANNEL = SAMPLE_RATE * FRAME_DURATION_MS // 1000
FRAME_BYTES = SAMPLES_PER_CHANNEL * NUM_CHANNELS * BYTES_PER_SAMPLE


class ProducerSignal(Enum):
    PAUSE = "pause"
    RESUME = "resume"
    SKIP = "skip"
    KILL = "kill"


async def audio_consumer(room: rtc.Room, queue: asyncio.Queue[bytes | None]):

    buffer = bytearray()

    # Build Livekit source information
    source = rtc.AudioSource(
        sample_rate=SAMPLE_RATE,
        num_channels=NUM_CHANNELS,
    )
    track = rtc.LocalAudioTrack.create_audio_track(
        "music",
        source,
    )
    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_MICROPHONE,
    )

    await room.local_participant.publish_track(
        track,
        options,
    )

    # Handle chunks
    while True:
        chunk = await queue.get()

        if chunk is None:
            break  # break signal

        buffer.extend(chunk)

        # Once buffer fills up produce frame
        while len(buffer) >= FRAME_BYTES:
            frame_data = buffer[:FRAME_BYTES]
            del buffer[:FRAME_BYTES]

            frame = rtc.AudioFrame(
                data=frame_data,
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=SAMPLES_PER_CHANNEL,
            )

            await source.capture_frame(frame)

    await room.local_participant.unpublish_track(track.sid)


def build_stream_url(url: str, params: Mapping[str, object] | None = None) -> str:
    if params is None:
        return url

    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({str(k): str(v) for k, v in params.items()})

    return parsed._replace(query=urlencode(query)).geturl()


async def audio_producer(
    queue: asyncio.Queue[bytes | None],
    playback_queue: list[Child],
    server: AsyncConnection,
    command_queue: asyncio.Queue[ProducerSignal],
) -> None:
    paused = False
    stopped = False

    while not stopped:
        # Pull next track
        try:
            song = playback_queue.pop()
        except IndexError:
            await asyncio.sleep(1)
            continue

        # Get streaming info
        url, params = server.get_stream_url(song.id, tformat="raw")
        print(url, params)

        # Create FFmpeg process
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            build_stream_url(url, params),
            "-f",
            "s16le",
            "-ac",
            str(NUM_CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "pipe:1",
            "-nostdin",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"spawned ffmpeg process playing {song.id}")

        # Ensure pipes attach to the process
        stdout, stderr = process.stdout, process.stderr
        if stdout is None or stderr is None:
            raise RuntimeError("failed to attach ffmpeg pipes")

        # Signal processing
        skip = False
        try:
            while True:
                # Attempt to get a signal from the queue
                try:
                    signal = command_queue.get_nowait()
                except asyncio.QueueEmpty:
                    signal = None

                # Match the signal to an action
                match signal:
                    case ProducerSignal.PAUSE:
                        paused = True
                    case ProducerSignal.RESUME:
                        paused = False
                    case ProducerSignal.SKIP:
                        skip = True
                        break
                    case ProducerSignal.KILL:
                        stopped = True
                        break

                # Handle pausing
                if paused:
                    process.send_signal(signals.SIGSTOP)  # Halt ffmpeg
                while paused:
                    signal = await command_queue.get()
                    match signal:
                        case ProducerSignal.RESUME:
                            paused = False
                            process.send_signal(signals.SIGCONT)  # Resume ffmpeg
                        case ProducerSignal.SKIP:
                            skip = True
                            paused = False
                        case ProducerSignal.KILL:
                            stopped = True
                            break

                        case _:
                            pass

                if skip:
                    break

                # Read and push the chunk
                chunk = await stdout.read(FRAME_BYTES)
                if not chunk:
                    break
                await queue.put(chunk)

        # Handle end of execution tidy up
        finally:
            if process.returncode is None:
                process.terminate()

        # Notify about any errors post-execution
        if not skip and process.returncode not in (0, None):
            logger.error(
                f"ffmpeg exited with {process.returncode} when playing {song.id}",
                (await stderr.read()).decode(errors="replace").strip(),
            )
            raise RuntimeWarning(f"ffmpeg exited with {process.returncode} when playing {song.id}")
        paused = False
