# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, TypedDict, Unpack
from unittest.mock import MagicMock

import pytest

from kagenti_adk.a2a.extensions import (
    CitationExtensionServer,
    CitationExtensionSpec,
    TrajectoryExtensionServer,
    TrajectoryExtensionSpec,
)
from kagenti_adk.a2a.extensions.streaming import StreamingExtensionServer, StreamingExtensionSpec
from kagenti_adk.server.dependencies import Depends, extract_dependencies

pytestmark = pytest.mark.unit


class MyExtensions(TypedDict):
    a: Annotated[CitationExtensionServer, CitationExtensionSpec()]
    b: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()]
    c: Annotated[StreamingExtensionServer, StreamingExtensionSpec()]


class MyExtensionsComplex(TypedDict):
    b: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()]


@pytest.mark.unit
def test_extract_dependencies_simple() -> None:
    def agent(a: Annotated[CitationExtensionServer, CitationExtensionSpec()]) -> None:
        pass

    assert extract_dependencies(agent).keys() == {"a"}


def test_extract_dependencies_extra_parameters() -> None:
    def agent(a: Annotated[CitationExtensionServer, CitationExtensionSpec()], b: bool) -> None:
        pass

    with pytest.raises(TypeError) as exc_info:
        extract_dependencies(agent)

    assert str(exc_info.value) == "The agent function contains extra parameters with unknown type annotation: {'b'}"


@pytest.mark.unit
def test_extract_dependencies_kwargs() -> None:
    def agent(**kwargs: Unpack[MyExtensions]) -> None:
        pass

    assert extract_dependencies(agent).keys() == {"a", "b", "c"}


def test_extract_dependencies_complex() -> None:

    def agent(
        a: Annotated[CitationExtensionServer, CitationExtensionSpec()],
        **kwargs: Unpack[MyExtensionsComplex],
    ) -> None:
        pass

    assert extract_dependencies(agent).keys() == {"a", "b"}


# ---------------------------------------------------------------------------
# Depends supports awaitable callables (issue #229)
# ---------------------------------------------------------------------------


class TestDependsAwaitable:
    """Depends should resolve both sync and async dependency callables."""

    async def test_sync_callable_still_works(self) -> None:
        sentinel = object()
        dep = Depends(lambda _msg, _ctx, _rctx: sentinel)
        async with dep(MagicMock(), MagicMock(), MagicMock()) as resolved:
            assert resolved is sentinel

    async def test_async_callable_resolves_awaited_value(self) -> None:
        sentinel = object()

        async def async_provider(_msg, _ctx, _rctx):
            return sentinel

        dep = Depends(async_provider)
        async with dep(MagicMock(), MagicMock(), MagicMock()) as resolved:
            assert resolved is sentinel

    async def test_async_callable_returning_lifespan_object_enters_and_exits(self) -> None:
        events: list[str] = []

        class Lifespanned:
            @asynccontextmanager
            async def lifespan(self):
                events.append("enter")
                try:
                    yield
                finally:
                    events.append("exit")

        instance = Lifespanned()

        async def async_provider(_msg, _ctx, _rctx):
            return instance

        dep = Depends(async_provider)
        async with dep(MagicMock(), MagicMock(), MagicMock()) as resolved:
            assert resolved is instance
            events.append("body")

        assert events == ["enter", "body", "exit"]

    async def test_sync_callable_returning_lifespan_object_regression(self) -> None:
        """BaseExtensionServer-style: sync callable that returns an instance with .lifespan()."""
        events: list[str] = []

        class Lifespanned:
            @asynccontextmanager
            async def lifespan(self):
                events.append("enter")
                try:
                    yield
                finally:
                    events.append("exit")

        instance = Lifespanned()
        dep = Depends(lambda _msg, _ctx, _rctx: instance)
        async with dep(MagicMock(), MagicMock(), MagicMock()) as resolved:
            assert resolved is instance

        assert events == ["enter", "exit"]
