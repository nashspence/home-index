import ast
import pathlib
import types
import os
import time
import pytest

# Extract retry_until_ready function without importing entire module
SRC = pathlib.Path("packages/home_index/main.py").read_text()
module = ast.parse(SRC)
nodes = []
for node in module.body:
    if (
        isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "RETRY_UNTIL_READY_SECONDS"
    ):
        nodes.append(node)
    if isinstance(node, ast.FunctionDef) and node.name == "retry_until_ready":
        nodes.append(node)
        break
assert len(nodes) == 2, "Definitions not found"
retry_src = ast.Module(body=nodes, type_ignores=[])
code = compile(retry_src, filename="<retry>", mode="exec")
ns = {"time": time, "os": os}
exec(code, ns)
retry_until_ready = ns["retry_until_ready"]

def test_retry_helper_stops_when_a_call_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, 'sleep', lambda s: sleeps.append(s))
    attempts = {'c':0}
    def fn():
        attempts['c'] += 1
        if attempts['c'] < 3:
            raise ValueError('no')
        return 'ok'
    result = retry_until_ready(fn, 'fail', seconds=3)
    assert result == 'ok'
    assert attempts['c'] == 3
    assert sleeps == [1,1]

def test_retry_helper_fails_after_repeated_errors(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, 'sleep', lambda s: sleeps.append(s))
    def fn():
        raise ValueError('no')
    with pytest.raises(RuntimeError):
        retry_until_ready(fn, 'fail', seconds=2)
    assert sleeps == [1]
