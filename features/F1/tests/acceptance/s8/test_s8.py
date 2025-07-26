from __future__ import annotations

from pathlib import Path
from typing import List

import docker
import pytest

from shared.acceptance_helpers import (
    compose_paths_for_test,
    compose_up,
    make_watchers,
)

CONTAINER_NAMES: List[str] = [
    "f1s8_home-index",
    "f1s8_meilisearch",
]


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
        CONTAINER_NAMES,
        request=request,
    ) as watchers:
        async with compose_up(
            compose_file,
            watchers=watchers,
        ):
            await watchers["f1s8_home-index"].wait_for_line(
                "invalid cron expression", timeout=5
            )
        watchers["f1s8_home-index"].assert_no_line("start file sync")
