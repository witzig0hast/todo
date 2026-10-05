"""Minimaler Wyoming-ASR-Client (wyoming-whisper, TCP, JSON-Lines + Binär-Payload)."""
import asyncio
import json
import wave
from io import BytesIO

from . import config

RATE, WIDTH, CHANNELS = 16000, 2, 1
CHUNK_BYTES = 16384


class WhisperError(Exception):
    pass


class AudioError(ValueError):
    pass


def wav_to_pcm(data: bytes) -> bytes:
    """Prüft ein WAV (16 kHz, 16 Bit, Mono) und gibt die PCM-Daten zurück."""
    try:
        with wave.open(BytesIO(data), "rb") as w:
            if (w.getframerate(), w.getsampwidth(), w.getnchannels()) != (RATE, WIDTH, CHANNELS):
                raise AudioError("Audio muss 16 kHz, 16 Bit, Mono sein.")
            if w.getnframes() / RATE > config.MAX_AUDIO_SECONDS:
                raise AudioError(f"Aufnahme zu lang (max. {config.MAX_AUDIO_SECONDS} s).")
            pcm = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise AudioError("Ungültige WAV-Datei.") from exc
    if not pcm:
        raise AudioError("Leere Aufnahme.")
    return pcm


def _encode(type_: str, data: dict | None = None, payload: bytes = b"") -> bytes:
    header: dict = {"type": type_}
    if data is not None:
        header["data"] = data
    if payload:
        header["payload_length"] = len(payload)
    return json.dumps(header).encode() + b"\n" + payload


async def _read_event(reader: asyncio.StreamReader) -> dict:
    line = await reader.readline()
    if not line:
        raise WhisperError("Verbindung zum Whisper-Server unerwartet beendet.")
    header = json.loads(line)
    data = dict(header.get("data") or {})
    if header.get("data_length"):
        data.update(json.loads(await reader.readexactly(header["data_length"])))
    if header.get("payload_length"):
        await reader.readexactly(header["payload_length"])
    return {"type": header.get("type"), "data": data}


async def _transcribe(pcm: bytes, language: str | None) -> str:
    reader, writer = await asyncio.open_connection(config.WHISPER_HOST, config.WHISPER_PORT)
    try:
        fmt = {"rate": RATE, "width": WIDTH, "channels": CHANNELS}
        writer.write(_encode("transcribe", {"language": language} if language else {}))
        writer.write(_encode("audio-start", fmt))
        for i in range(0, len(pcm), CHUNK_BYTES):
            writer.write(_encode("audio-chunk", fmt, pcm[i : i + CHUNK_BYTES]))
            await writer.drain()
        writer.write(_encode("audio-stop", {}))
        await writer.drain()
        while True:
            event = await _read_event(reader)
            if event["type"] == "transcript":
                return (event["data"].get("text") or "").strip()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def transcribe(pcm: bytes, language: str | None = None) -> str:
    try:
        return await asyncio.wait_for(_transcribe(pcm, language or config.WHISPER_LANGUAGE), config.WHISPER_TIMEOUT)
    except (OSError, asyncio.TimeoutError, json.JSONDecodeError, asyncio.IncompleteReadError) as exc:
        raise WhisperError("Whisper-Server nicht erreichbar oder antwortet nicht.") from exc
