from __future__ import annotations

from pathlib import Path

import docker
import pytest

from shared.acceptance_helpers import (
    EventMatcher,
    compose_paths_for_test,
    compose_up,
    make_watchers,
)

from ..helpers import _expected_interval

HOME_INDEX_CONTAINER_NAME = "f1s4_home-index"
MEILI_CONTAINER_NAME = "f1s4_meilisearch"


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
# regular cadence honoured
async def test_f1s4(tmp_path: Path, docker_client, request):
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    async with make_watchers(
        docker_client,
        [HOME_INDEX_CONTAINER_NAME, MEILI_CONTAINER_NAME],
        request=request,
    ) as watchers:
        async with compose_up(
            compose_file,
            watchers=watchers,
        ):
            events = await watchers[HOME_INDEX_CONTAINER_NAME].wait_for_sequence(
                [
                    EventMatcher(r"\[INFO\] start file sync"),
                    EventMatcher(r"\[INFO\] start file sync"),
                    EventMatcher(r"\[INFO\] start file sync"),
                ],
                timeout=10,
            )
        interval = events[-1].ts - events[-2].ts
        expected = _expected_interval("*/2 * * * * *")
        assert interval >= expected - 3
        assert interval <= expected + 3
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)
