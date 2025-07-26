from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

import docker
import pytest

from shared.acceptance import search_meili
from shared.acceptance_helpers import (
    AsyncDockerLogWatcher,
    EventMatcher,
    assert_file_indexed,
    compose_paths_for_test,
    compose_up_with_watchers,
    dump_on_failure,
    meilisearch_running,
)

CONTAINER_NAMES: List[str] = ["f1s3_home-index"]


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
# file contents change
async def test_f1s3(tmp_path: Path, docker_client, request):
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    recorded: List[AsyncDockerLogWatcher] = []

    async with compose_up_with_watchers(
        compose_file, docker_client, CONTAINER_NAMES
    ) as watchers:
        recorded.extend(watchers.values())

        await watchers["f1s3_home-index"].wait_for_sequence(
            [
                EventMatcher("start file sync"),
                EventMatcher("completed file sync"),
            ],
            timeout=120,
        )

        existing = set((output_dir / "metadata" / "by-id").iterdir())
        hello = workdir / "input" / "hello.txt"
        hello.write_text("changed")

        await watchers["f1s3_home-index"].wait_for_sequence(
            [
                EventMatcher("start file sync"),
                EventMatcher("completed file sync"),
            ],
            timeout=120,
        )
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)

    new_id = assert_file_indexed(workdir, output_dir, "hello.txt")
    assert any(p.name != new_id for p in existing)

    async with meilisearch_running(compose_file):
        docs = await asyncio.to_thread(
            search_meili, compose_file, workdir, f'id = "{new_id}"'
        )
        assert docs

    dump_on_failure(request, CONTAINER_NAMES, recorded)
