# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for MemoryStore protocol and MemoryHub implementation.

The ``memoryhub`` SDK is now a real dev dependency, so we drive the
underlying ``MemoryHubClient`` calls via mocks rather than stubbing the
whole module tree. The MemoryHubExtensionServer's ``lifespan()`` is
exercised by patching ``MemoryHubClient`` to return an ``AsyncMock``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from kagenti_adk.a2a.extensions.services.memoryhub import (
    MemoryHubExtensionMetadata,
    MemoryHubExtensionSpec,
    MemoryHubFulfillment,
)
from kagenti_adk.server.store.exceptions import MemoryRejectionError
from kagenti_adk.server.store.memory_store import MemoryResult
from kagenti_adk.server.store.memoryhub_memory_store import (
    MemoryHubExtensionServer,
    MemoryHubMemoryStoreInstance,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client() -> AsyncMock:
    """Return an async mock that looks like a MemoryHubClient."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _search_result(*memories) -> SimpleNamespace:
    return SimpleNamespace(results=list(memories))


def _memory_obj(
    id: str = "mem-1",
    content: str = "some content",
    scope: str = "user",
    weight: float = 0.7,
    relevance_score: float | None = None,
    stub: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        content=content,
        scope=scope,
        weight=weight,
        relevance_score=relevance_score,
        stub=stub,
    )


def _write_result(memory=None, curation=None) -> SimpleNamespace:
    if curation is None:
        curation = SimpleNamespace(reason="")
    return SimpleNamespace(memory=memory, curation=curation)


class _NotFoundError(Exception):
    """Stand-in matching ``memoryhub.exceptions.NotFoundError``."""


# ---------------------------------------------------------------------------
# MemoryResult model
# ---------------------------------------------------------------------------


class TestMemoryResult:
    def test_required_fields(self):
        r = MemoryResult(memory_id="id-1", content="hello", scope="user")
        assert r.memory_id == "id-1"
        assert r.content == "hello"
        assert r.scope == "user"

    def test_weight_default(self):
        r = MemoryResult(memory_id="x", content="y", scope="project")
        assert r.weight == 0.7

    def test_relevance_score_default_is_none(self):
        r = MemoryResult(memory_id="x", content="y", scope="project")
        assert r.relevance_score is None

    def test_explicit_weight_and_relevance(self):
        r = MemoryResult(memory_id="x", content="y", scope="org", weight=0.9, relevance_score=0.85)
        assert r.weight == 0.9
        assert r.relevance_score == 0.85


# ---------------------------------------------------------------------------
# MemoryHubMemoryStoreInstance operations
# ---------------------------------------------------------------------------


class TestMemoryHubMemoryStoreInstance:
    def _make(self, client=None) -> MemoryHubMemoryStoreInstance:
        return MemoryHubMemoryStoreInstance(
            context_id="ctx-99",
            client=client or _mock_client(),
        )

    # --- search ---

    async def test_search_maps_results(self):
        client = _mock_client()
        client.search.return_value = _search_result(
            _memory_obj(id="m1", content="alpha", scope="user", weight=0.8, relevance_score=0.9),
            _memory_obj(id="m2", content="beta", scope="project", weight=0.6, relevance_score=0.7),
        )
        inst = self._make(client)

        results = await inst.search("test query")

        client.search.assert_awaited_once_with("test query", scope=None, project_id=None, max_results=10)
        assert len(results) == 2
        assert results[0] == MemoryResult(
            memory_id="m1", content="alpha", scope="user", weight=0.8, relevance_score=0.9
        )
        assert results[1] == MemoryResult(
            memory_id="m2", content="beta", scope="project", weight=0.6, relevance_score=0.7
        )

    async def test_search_passes_optional_kwargs(self):
        client = _mock_client()
        client.search.return_value = _search_result()
        inst = self._make(client)

        await inst.search("q", scope="project", project_id="proj-1", max_results=5)

        client.search.assert_awaited_once_with("q", scope="project", project_id="proj-1", max_results=5)

    async def test_search_falls_back_to_stub_when_content_none(self):
        client = _mock_client()
        client.search.return_value = _search_result(_memory_obj(id="m1", content=None, stub="stub text", scope="user"))
        inst = self._make(client)

        results = await inst.search("q")
        assert results[0].content == "stub text"

    async def test_search_empty_string_when_both_none(self):
        client = _mock_client()
        client.search.return_value = _search_result(_memory_obj(id="m1", content=None, stub=None, scope="user"))
        inst = self._make(client)

        results = await inst.search("q")
        assert results[0].content == ""

    async def test_search_empty_results(self):
        client = _mock_client()
        client.search.return_value = _search_result()
        inst = self._make(client)

        results = await inst.search("nothing")
        assert results == []

    # --- create ---

    async def test_create_returns_memory_id(self):
        client = _mock_client()
        client.write.return_value = _write_result(memory=SimpleNamespace(id="new-id-42"))
        inst = self._make(client)

        memory_id = await inst.create("important fact")

        client.write.assert_awaited_once_with(
            "important fact",
            scope="user",
            weight=0.7,
            domains=None,
            project_id=None,
        )
        assert memory_id == "new-id-42"

    async def test_create_passes_all_params(self):
        client = _mock_client()
        client.write.return_value = _write_result(memory=SimpleNamespace(id="x"))
        inst = self._make(client)

        await inst.create(
            "content",
            scope="project",
            weight=0.9,
            tags=["infra", "k8s"],
            project_id="proj-1",
        )

        client.write.assert_awaited_once_with(
            "content",
            scope="project",
            weight=0.9,
            domains=["infra", "k8s"],
            project_id="proj-1",
        )

    async def test_create_raises_on_curation_rejection(self):
        client = _mock_client()
        client.write.return_value = _write_result(
            memory=None,
            curation=SimpleNamespace(reason="duplicate detected"),
        )
        inst = self._make(client)

        with pytest.raises(MemoryRejectionError) as exc_info:
            await inst.create("duplicate content")
        assert exc_info.value.reason == "duplicate detected"

    # --- read ---

    async def test_read_returns_memory_result(self):
        client = _mock_client()
        client.read.return_value = _memory_obj(id="m-read", content="stored fact", scope="user", weight=0.8)
        inst = self._make(client)

        result = await inst.read("m-read")

        client.read.assert_awaited_once_with("m-read")
        assert result == MemoryResult(memory_id="m-read", content="stored fact", scope="user", weight=0.8)

    async def test_read_returns_none_for_not_found(self):
        # Patch the NotFoundError in the implementation module to our local class
        # so the except clause matches our raised exception.
        from kagenti_adk.server.store import memoryhub_memory_store as impl

        with patch.object(impl, "NotFoundError", _NotFoundError):
            client = _mock_client()
            client.read.side_effect = _NotFoundError("not found")
            inst = self._make(client)

            result = await inst.read("missing-id")
            assert result is None

    async def test_read_empty_content_defaults_to_empty_string(self):
        client = _mock_client()
        client.read.return_value = _memory_obj(id="x", content=None, scope="user")
        inst = self._make(client)

        result = await inst.read("x")
        assert result.content == ""

    # --- update ---

    async def test_update_delegates_to_client(self):
        client = _mock_client()
        inst = self._make(client)

        await inst.update("m-1", "new content")

        client.update.assert_awaited_once_with("m-1", content="new content")

    async def test_update_returns_none(self):
        client = _mock_client()
        client.update.return_value = None
        inst = self._make(client)

        result = await inst.update("m-1", "content")
        assert result is None

    # --- delete ---

    async def test_delete_delegates_to_client(self):
        client = _mock_client()
        inst = self._make(client)

        await inst.delete("m-1")

        client.delete.assert_awaited_once_with("m-1")

    async def test_delete_returns_none(self):
        client = _mock_client()
        client.delete.return_value = None
        inst = self._make(client)

        result = await inst.delete("m-1")
        assert result is None


# ---------------------------------------------------------------------------
# MemoryHubExtensionServer lifecycle
# ---------------------------------------------------------------------------


class TestMemoryHubExtensionServerLifespan:
    def _server_with_default(self, fulfillment: MemoryHubFulfillment) -> MemoryHubExtensionServer:
        spec = MemoryHubExtensionSpec.single_demand(default=fulfillment)
        server = MemoryHubExtensionServer(spec)
        # Activate by simulating a parsed metadata payload.
        server._metadata_from_client = MemoryHubExtensionMetadata(memoryhub_fulfillments={"default": fulfillment})
        return server

    async def test_lifespan_opens_and_closes_api_key_client(self):
        fulfillment = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("the-key"))
        server = self._server_with_default(fulfillment)
        fake_client = _mock_client()

        with patch(
            "kagenti_adk.server.store.memoryhub_memory_store.MemoryHubClient",
            return_value=fake_client,
        ) as client_cls:
            async with server.lifespan():
                # Inside the lifespan, store() should hand back a usable instance.
                inst = server.store("ctx-1")
                assert isinstance(inst, MemoryHubMemoryStoreInstance)
                assert inst._context_id == "ctx-1"
                assert inst._client is fake_client

            client_cls.assert_called_once_with(url="http://hub", api_key="the-key")
            fake_client.__aenter__.assert_awaited_once()
            fake_client.__aexit__.assert_awaited_once_with(None, None, None)

        # After lifespan exit, store() raises.
        with pytest.raises(RuntimeError):
            server.store("ctx-1")

    async def test_lifespan_uses_oauth_path(self):
        fulfillment = MemoryHubFulfillment(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret=SecretStr("csec"),
        )
        server = self._server_with_default(fulfillment)
        fake_client = _mock_client()

        with patch(
            "kagenti_adk.server.store.memoryhub_memory_store.MemoryHubClient",
            return_value=fake_client,
        ) as client_cls:
            async with server.lifespan():
                pass

        client_cls.assert_called_once_with(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret="csec",
        )

    async def test_lifespan_noop_without_fulfillment(self):
        spec = MemoryHubExtensionSpec.single_demand()
        server = MemoryHubExtensionServer(spec)
        server._is_active = True  # active but no metadata, no default

        with patch("kagenti_adk.server.store.memoryhub_memory_store.MemoryHubClient") as client_cls:
            async with server.lifespan():
                pass
            client_cls.assert_not_called()

        # store() outside an active client must raise.
        with pytest.raises(RuntimeError):
            server.store("ctx")

    async def test_store_outside_lifespan_raises(self):
        fulfillment = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("k"))
        server = self._server_with_default(fulfillment)
        with pytest.raises(RuntimeError):
            server.store("ctx-x")


# ---------------------------------------------------------------------------
# httpx integration sanity check (verifies the install path stays wired)
# ---------------------------------------------------------------------------


class TestMemoryHubClientImportable:
    def test_real_memoryhub_client_importable(self):
        # Imports happen at module load; this just asserts they didn't blow up.
        from memoryhub.client import MemoryHubClient
        from memoryhub.exceptions import NotFoundError

        assert MemoryHubClient is not None
        assert issubclass(NotFoundError, Exception)
