from __future__ import annotations

from pathlib import Path
from typing import List

import docker
import pytest

from shared.acceptance_helpers import (
    EventMatcher,
    compose_paths_for_test,
    compose_up,
    make_watchers,
)

CONTAINER_NAMES: List[str] = ["f1s5_home-index"]


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
# long-running sync never overlaps
async def test_f1s5(tmp_path: Path, docker_client, request):
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    async with make_watchers(
        docker_client,
        CONTAINER_NAMES,
        request=request,
    ) as watchers:
        async with compose_up(
            compose_file,
            watchers=watchers,
        ):
            events = await watchers["f1s5_home-index"].wait_for_sequence(
                [
                    EventMatcher("start file sync"),
                    EventMatcher("completed file sync"),
                    EventMatcher("start file sync"),
                ],
                timeout=120,
            )
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)

    assert events[1].ts < events[2].ts
