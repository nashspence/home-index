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

HOME_INDEX_CONTAINER_NAME = "f1s5_home-index"
MEILI_CONTAINER_NAME = "f1s5_meilisearch"


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
                    EventMatcher(r"\[INFO\] completed file sync"),
                    EventMatcher(r"\[INFO\] start file sync"),
                ],
                timeout=10,
            )
        start_ts, completed_ts, _ = (e.ts for e in events)
        for evt in watchers[HOME_INDEX_CONTAINER_NAME]._remembered:
            if start_ts < evt.ts < completed_ts and "start file sync" in evt.raw:
                raise AssertionError("sync overlapped previous run")
        assert completed_ts < events[2].ts
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)
