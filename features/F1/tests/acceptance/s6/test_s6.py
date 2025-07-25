from __future__ import annotations

import os
from pathlib import Path
from typing import List

import docker
import pytest

from shared.acceptance_helpers import (
    AsyncDockerLogWatcher,
    EventMatcher,
    compose_paths_for_test,
    compose_up_with_watchers,
    dump_on_failure,
)

from ..helpers import _expected_interval

CONTAINER_NAMES: List[str] = ["f1s6_home-index"]


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
async def test_f1s6(tmp_path: Path, docker_client, request):
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    recorded: List[AsyncDockerLogWatcher] = []

    # first run with cron1
    os.environ["CRON_EXPRESSION"] = "* * * * * *"
    async with compose_up_with_watchers(
        compose_file, docker_client, CONTAINER_NAMES
    ) as watchers:
        recorded.extend(watchers.values())
        await watchers["f1s6_home-index"].wait_for_sequence(
            [
                EventMatcher("start file sync"),
                EventMatcher("start file sync"),
            ],
            timeout=120,
        )

    # second run with cron2
    os.environ["CRON_EXPRESSION"] = "*/2 * * * * *"
    async with compose_up_with_watchers(
        compose_file, docker_client, CONTAINER_NAMES
    ) as watchers:
        recorded.extend(watchers.values())
        events = await watchers["f1s6_home-index"].wait_for_sequence(
            [
                EventMatcher("start file sync"),
                EventMatcher("start file sync"),
            ],
            timeout=120,
        )
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)

    interval = events[-1].ts - events[-2].ts
    expected = _expected_interval("*/2 * * * * *")
    assert abs(interval - expected) <= 1

    dump_on_failure(request, CONTAINER_NAMES, recorded)
