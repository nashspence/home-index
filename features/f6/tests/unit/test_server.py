import asyncio
from features.f6 import server


def test_serve_api_runs_uvicorn(monkeypatch):
    called = {}

    class DummyConfig:
        def __init__(self, app, host, port, loop):
            called["app"] = app
            called["host"] = host
            called["port"] = port
            called["loop"] = loop

    class DummyServer:
        def __init__(self, config):
            called["config"] = config

        async def serve(self):
            called["served"] = True

    monkeypatch.setattr(
        server,
        "uvicorn",
        type(
            "UV",
            (),
            {
                "Config": DummyConfig,
                "Server": DummyServer,
            },
        ),
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve_api())
    loop.close()
    asyncio.set_event_loop(None)

    assert called["app"] is server.app
    assert called["host"] == "0.0.0.0"
    assert called["port"] == server.API_PORT
    assert called["loop"] == "asyncio"
    assert called["served"] is True
