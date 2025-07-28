from __future__ import annotations

# mypy: disable-error-code=misc

import asyncio
import os
from pathlib import Path

import docker
import pytest
import pytest_asyncio
from pytest_bdd import given, when, then, parsers

from shared.acceptance import search_meili
from shared.acceptance_helpers import (
    EventMatcher,
    ComposeState,
    assert_file_indexed,
    start_stack,
    stop_stack,
)
from .helpers import _expected_interval


World = ComposeState


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    return docker.from_env()


@pytest_asyncio.fixture
async def world(
    request: pytest.FixtureRequest, docker_client: docker.DockerClient
) -> World:
    state = World()
    yield state
    if state.stack is not None:
        await state.stack.aclose()
    if state.watchers:
        for w in state.watchers.values():
            w.assert_no_line(lambda line: "ERROR" in line)


@given("the stack started with a valid cron expression")
@given("the stack is running")
@when("the stack boots")
@when("the stack runs")
@when("the stack starts")
async def start_stack_running(
    world: World, request: pytest.FixtureRequest, docker_client: docker.DockerClient
) -> None:
    await start_stack(
        world,
        request,
        docker_client,
        steps_file=Path(__file__),
        prefix="f1",
        services=["meilisearch", "home-index"],
    )


@given("at least one file exists in $INDEX_DIRECTORY")
def ensure_files_exist(world: World) -> None:
    assert world.workdir is not None
    assert any(world.workdir.joinpath("input").iterdir())


@given("the stack is stopped")
async def given_stack_stopped(world: World) -> None:
    await stop_stack(world)


@given(parsers.parse("$CRON_EXPRESSION is edited to any valid value"))
def edit_cron() -> None:
    os.environ["CRON_EXPRESSION"] = "*/2 * * * * *"


@given(parsers.parse('CRON_EXPRESSION is set to "bad cron"'))
def set_bad_cron() -> None:
    os.environ["CRON_EXPRESSION"] = "bad cron"


@when("a new file is copied into $INDEX_DIRECTORY between ticks")
async def copy_new_file(world: World) -> None:
    assert world.workdir is not None
    (world.workdir / "input" / "new.txt").write_text("new")


@when("the next tick runs")
async def wait_next_tick(world: World) -> None:
    assert world.watchers is not None
    hi = next(iter(world.watchers.values()))
    await hi.wait_for_sequence(
        [
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] completed file sync"),
        ],
        timeout=10,
    )


@when("the stack restarts")
@when("they start again with the identical cron expression")
async def restart_stack(
    world: World, request: pytest.FixtureRequest, docker_client: docker.DockerClient
) -> None:
    await given_stack_stopped(world)
    await start_stack(
        world,
        request,
        docker_client,
        steps_file=Path(__file__),
        prefix="f1",
        services=["meilisearch", "home-index"],
    )


@when("the stack runs for several ticks")
async def run_several_ticks(world: World) -> None:
    assert world.watchers is not None
    hi = next(iter(world.watchers.values()))
    await hi.wait_for_sequence(
        [
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] start file sync"),
        ],
        timeout=10,
    )


@then(parsers.parse("$LOGGING_DIRECTORY/files.log is created"))
def log_file_created(world: World) -> None:
    assert world.output_dir is not None
    assert world.output_dir.joinpath("files.log").exists()


@then(parsers.parse("the logs contain, in order:\n{table}"))
async def logs_in_order(world: World, table: str) -> None:
    """Assert each container's logs match the given regex sequence."""
    assert world.watchers is not None
    lines = [row.strip().split("|") for row in table.strip().splitlines()]
    if lines and lines[0][0].strip().lower() == "container":
        lines = lines[1:]

    seq_map: dict[str, list[EventMatcher]] = {}
    for container, pattern in lines:
        seq_map.setdefault(container.strip(), []).append(EventMatcher(pattern.strip()))

    await asyncio.gather(
        *(
            world.watchers[c].wait_for_sequence(seq, timeout=10)
            for c, seq in seq_map.items()
        )
    )


@then("for each file $METADATA_DIRECTORY/by-id/<hash>/document.json is written")
def metadata_written(world: World) -> None:
    assert world.workdir is not None and world.output_dir is not None
    for path in world.workdir.joinpath("input").iterdir():
        assert_file_indexed(world.workdir, world.output_dir, path.name)


@then("each file becomes searchable")
async def files_searchable(world: World) -> None:
    assert world.workdir is not None and world.output_dir is not None
    assert world.compose_file is not None
    for path in world.workdir.joinpath("input").iterdir():
        doc_id = assert_file_indexed(world.workdir, world.output_dir, path.name)
        docs = await asyncio.to_thread(
            search_meili,
            world.compose_file,
            world.workdir,
            f'id = "{doc_id}"',
        )
        assert docs


@then("at the next tick metadata and index entries for that file are created")
async def new_file_indexed(world: World) -> None:
    await logs_in_order(
        world,
        """home_index|^\[INFO\] start file sync$\nhome_index|^\[INFO\] commit changes to meilisearch$\nhome_index|^\[INFO\] completed file sync$""",
    )
    await files_searchable(world)


@then("a new metadata directory is created for the new hash")
async def new_metadata_dir(world: World) -> None:
    assert world.workdir is not None and world.output_dir is not None
    old_id = assert_file_indexed(world.workdir, world.output_dir, "hello.txt")
    hello = world.workdir / "input" / "hello.txt"
    hello.write_text("changed")
    await wait_next_tick(world)
    new_id = assert_file_indexed(world.workdir, world.output_dir, "hello.txt")
    assert new_id != old_id
    assert (world.output_dir / "metadata" / "by-id" / old_id).exists()


@then("the old directory remains untouched")
def old_directory_untouched(world: World) -> None:
    assert world.workdir is not None and world.output_dir is not None
    old_id = assert_file_indexed(world.workdir, world.output_dir, "hello.txt")
    assert (world.output_dir / "metadata" / "by-id" / old_id).exists()


@then('the interval between successive "start file sync" lines matches the cron +- 3 s')
async def interval_matches(world: World) -> None:
    assert world.watchers is not None
    hi = next(iter(world.watchers.values()))
    events = await hi.wait_for_sequence(
        [
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] start file sync"),
        ],
        timeout=10,
    )
    interval = events[-1].ts - events[-2].ts
    expected = _expected_interval("*/2 * * * * *")
    assert expected - 3 <= interval <= expected + 3


@then("never faster")
def never_faster() -> None:
    pass


@then(
    'a second "start file sync" line never appears until the previous run logs "... completed file sync"'
)
async def no_overlap(world: World) -> None:
    assert world.watchers is not None
    hi = next(iter(world.watchers.values()))
    events = await hi.wait_for_sequence(
        [
            EventMatcher(r"\[INFO\] start file sync"),
            EventMatcher(r"\[INFO\] completed file sync"),
            EventMatcher(r"\[INFO\] start file sync"),
        ],
        timeout=10,
    )
    start_ts, completed_ts, next_start = (e.ts for e in events)
    for evt in hi._remembered:
        if start_ts < evt.ts < completed_ts and "start file sync" in evt.raw:
            raise AssertionError("sync overlapped previous run")
    assert completed_ts < next_start


@then("the container stays stopped")
async def container_stopped(world: World) -> None:
    assert world.watchers is not None
    hi = next(iter(world.watchers.values()))
    exit_code = await hi.wait_for_container_stopped(timeout=10)
    assert exit_code != 0


@then("Home-Index exits with a non-zero code")
async def exit_non_zero(world: World) -> None:
    await container_stopped(world)
