from __future__ import annotations

import uvicorn

from .api import API_PORT, app


async def serve_api() -> None:
    config = uvicorn.Config(app, host="0.0.0.0", port=API_PORT, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()
