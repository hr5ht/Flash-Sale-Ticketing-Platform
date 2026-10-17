import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.main import app


@asynccontextmanager
async def open_socket(url: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
    path, _, query = url.partition("?")
    scope = {
        "type": "websocket",
        "path": path,
        "query_string": query.encode(),
        "headers": [],
        "subprotocols": [],
    }
    to_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    from_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    await to_app.put({"type": "websocket.connect"})
    task = asyncio.create_task(app(scope, to_app.get, from_app.put))
    try:
        accepted = await next_message(from_app)
        assert accepted["type"] == "websocket.accept"
        yield from_app
    finally:
        await to_app.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(task, timeout=5)


async def next_message(messages: asyncio.Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.wait_for(messages.get(), timeout=5)
