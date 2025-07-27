from __future__ import annotations

from pathlib import Path

import docker
import pytest

from shared.acceptance_helpers import (
    compose_paths_for_test,
    compose_up,
    make_watchers,
)

HOME_INDEX_CONTAINER_NAME = "f1s8_home-index"
MEILI_CONTAINER_NAME = "f1s8_meilisearch"


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
# invalid cron blocks startup
async def test_f1s8(tmp_path: Path, docker_client, request):
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
            await watchers[HOME_INDEX_CONTAINER_NAME].wait_for_line(
                "invalid cron expression", timeout=10
            )
        watchers[HOME_INDEX_CONTAINER_NAME].assert_no_line("start file sync")
        watchers[MEILI_CONTAINER_NAME].assert_no_line(lambda line: "ERROR" in line)
