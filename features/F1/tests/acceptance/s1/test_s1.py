import asyncio
from pathlib import Path
from typing import List

import docker
import pytest
from shared.acceptance import search_meili
from shared.acceptance_helpers import (
    AsyncDockerLogWatcher,
    EventMatcher,
    compose_up_with_watchers,
    compose_down_and_stop,
    assert_file_indexed,
    dump_on_failure,
    compose_paths_for_test,
)

CONTAINER_NAMES: List[str] = ["f1s1_home-index"]


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
async def test_f1s1(tmp_path: Path, docker_client, request):
    # prepare isolated compose directory
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    recorded: List[AsyncDockerLogWatcher] = []

    watchers = await compose_up_with_watchers(
        compose_file, docker_client, CONTAINER_NAMES
    )
    recorded.extend(watchers.values())

    try:
        await watchers["f1s1_home-index"].wait_for_sequence(
            [
                EventMatcher("start file sync"),
                EventMatcher("commit changes to meilisearch"),
                EventMatcher(" * counted 1 documents in meilisearch"),
                EventMatcher("completed file sync"),
                EventMatcher("start file sync"),
                EventMatcher("commit changes to meilisearch"),
                EventMatcher(" * counted 1 documents in meilisearch"),
                EventMatcher("completed file sync"),
            ],
            timeout=120,
        )
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)
    finally:
        await compose_down_and_stop(compose_file, watchers.values())

    # filesystem assertions
    assert_file_indexed(workdir, output_dir, "hello.txt")

    docs = await asyncio.to_thread(search_meili, compose_file, workdir, "")
    assert docs

    dump_on_failure(request, CONTAINER_NAMES, recorded)
