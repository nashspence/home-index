import json


def test_run_server_registers_handlers(monkeypatch):
    import importlib

    rs = importlib.import_module("home_index_module.run_server")

    recorded = {}

    class DummyServer:
        def __init__(self, *args, **kwargs):
            recorded["init"] = True

        def register_instance(self, inst):
            recorded["instance"] = inst

        def serve_forever(self):
            recorded["served"] = True

        @property
        def server_address(self):
            return ("127.0.0.1", 0)

    monkeypatch.setattr(rs, "SimpleXMLRPCServer", DummyServer)

    def hello():
        return {"name": "mod", "version": 1}

    def check(fp, doc, md):
        return True

    def run_fn(fp, doc, md):
        return {"document": doc, "chunk_docs": []}

    rs.run_server("mod", hello, check, run_fn)

    handler = recorded["instance"]
    assert recorded["served"]
    assert json.loads(handler.hello()) == {"name": "mod", "version": 1}
    result = json.loads(handler.run(json.dumps({"id": "1", "paths": {"a": 1}})))
    assert result["document"]["id"] == "1"
