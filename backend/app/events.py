"""In-Prozess-Pub/Sub für Server-Sent-Events (UI-Stream und Agent-Inbox-Stream)."""
import asyncio
import json
from collections import defaultdict
from typing import Any

_subs: dict[tuple[str, int], set[asyncio.Queue]] = defaultdict(set)
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe(channel: str, key: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subs[(channel, key)].add(q)
    return q


def unsubscribe(channel: str, key: int, q: asyncio.Queue) -> None:
    _subs[(channel, key)].discard(q)
    if not _subs[(channel, key)]:
        _subs.pop((channel, key), None)


def _deliver(channel: str, key: int, payload: str) -> None:
    for q in list(_subs.get((channel, key), ())):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def has_subscribers(channel: str, key: int) -> bool:
    return bool(_subs.get((channel, key)))


def publish(channel: str, key: int, event: str, data: Any, event_id: int | None = None) -> None:
    """Thread-sicher: darf aus synchronen Endpunkten (Threadpool) aufgerufen werden."""
    id_line = f"id: {event_id}\n" if event_id is not None else ""
    payload = f"{id_line}event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    if _loop is not None and _loop.is_running():
        _loop.call_soon_threadsafe(_deliver, channel, key, payload)


def sse_response(gen):
    from fastapi.responses import StreamingResponse

    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
