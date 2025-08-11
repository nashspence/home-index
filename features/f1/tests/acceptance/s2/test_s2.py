from __future__ import annotations

import asyncio
from pathlib import Path
import docker
import pytest

from shared.acceptance import search_meili
from shared.acceptance_helpers import (
    EventMatcher,
    assert_file_indexed,
    compose_paths_for_test,
    compose_up,
    make_watchers,
)

HOME_INDEX_CONTAINER_NAME = "f1s2_home-index"
MEILI_CONTAINER_NAME = "f1s2_meilisearch"


@pytest.fixture(autouse=True)
def _pytest_report_hook(request):
    yield


def pytest_runtest_makereport(item, call):
    setattr(item, f"rep_{call.when}", call)


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.mark.asyncio
# new file appears mid-run
async def test_f1s2(tmp_path: Path, docker_client, request):
    compose_file, workdir, output_dir = compose_paths_for_test(__file__)

    async with make_watchers(
        docker_client,
        [HOME_INDEX_CONTAINER_NAME, MEILI_CONTAINER_NAME],
        request=request,
    ) as watchers:
        async with compose_up(
            compose_file,
            watchers=watchers,
            containers=[MEILI_CONTAINER_NAME],
        ):
            async with compose_up(
                compose_file,
                watchers=watchers,
                containers=[HOME_INDEX_CONTAINER_NAME],
            ):
                await watchers[HOME_INDEX_CONTAINER_NAME].wait_for_sequence(
                    [
                        EventMatcher(r"\[INFO\] start file sync"),
                        EventMatcher(r"\[INFO\] completed file sync"),
                    ],
                    timeout=10,
                )

                (workdir / "input" / "new.txt").write_text("new")

                await watchers[HOME_INDEX_CONTAINER_NAME].wait_for_sequence(
                    [
                        EventMatcher(r"\[INFO\] start file sync"),
                        EventMatcher(r"\[INFO\] commit changes to meilisearch"),
                        EventMatcher(r"\[INFO\] completed file sync"),
                    ],
                    timeout=10,
                )
            doc_id = assert_file_indexed(workdir, output_dir, "new.txt")
            docs = await asyncio.to_thread(
                search_meili, compose_file, workdir, f'id = "{doc_id}"'
            )
            assert docs
        for w in watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)
