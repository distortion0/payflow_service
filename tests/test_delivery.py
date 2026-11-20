"""At-least-once, unordered, parallel delivery must not change the final state."""

import asyncio
import random
from collections import Counter
from collections.abc import Iterable
from typing import Any

import pytest
from httpx import AsyncClient

from tests.helpers import assert_happy_path_responses, post_event


async def post_all(client: AsyncClient, payloads: Iterable[dict[str, Any]]) -> list[str]:
    outcomes = []
    for payload in payloads:
        response = await post_event(client, payload)
        assert response.status_code == 200
        outcomes.append(response.json()["outcome"])
    return outcomes


async def test_reverse_order(client: AsyncClient, happy_path: list[dict[str, Any]]) -> None:
    outcomes = await post_all(client, reversed(happy_path))

    assert outcomes == ["processed"] * len(happy_path)
    await assert_happy_path_responses(client)


@pytest.mark.parametrize("seed", [1, 7, 42, 1337, 2026])
async def test_random_order(
    client: AsyncClient, happy_path: list[dict[str, Any]], seed: int
) -> None:
    random.Random(seed).shuffle(happy_path)

    await post_all(client, happy_path)

    await assert_happy_path_responses(client)


async def test_every_event_delivered_twice(
    client: AsyncClient, happy_path: list[dict[str, Any]]
) -> None:
    outcomes = await post_all(client, [payload for payload in happy_path for _ in range(2)])

    assert outcomes == ["processed", "duplicate"] * len(happy_path)
    await assert_happy_path_responses(client)


@pytest.mark.parametrize("seed", [0, 1, 2])
async def test_everything_in_parallel_with_duplicates(
    client: AsyncClient, happy_path: list[dict[str, Any]], seed: int
) -> None:
    batch = happy_path * 2
    random.Random(seed).shuffle(batch)

    responses = await asyncio.gather(*(post_event(client, payload) for payload in batch))

    assert {response.status_code for response in responses} == {200}
    outcomes = Counter(response.json()["outcome"] for response in responses)
    assert outcomes == {"processed": len(happy_path), "duplicate": len(happy_path)}
    await assert_happy_path_responses(client)
