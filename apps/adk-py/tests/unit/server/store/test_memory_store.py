# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for MemoryStore protocol and MemoryHub implementation.

The memoryhub SDK is an optional dependency, so we patch it at the module
level before importing the implementation. All tests are async-compatible
via pytest-asyncio's asyncio_mode = "auto" (set in pyproject.toml).
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagenti_adk.server.store.memory_store import MemoryResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — build a fake memoryhub module tree so the implementation can be
# imported and used without the real SDK installed.
# ---------------------------------------------------------------------------


def _make_memoryhub_stubs() -> tuple[ModuleType, MagicMock]:
    """Return (memoryhub package stub, MemoryHubClient class mock)."""
    client_mock = MagicMock()

    memoryhub = ModuleType("memoryhub")
    memoryhub_client = ModuleType("memoryhub.client")
    memoryhub_exceptions = ModuleType("memoryhub.exceptions")

    # NotFoundError used in the read() implementation
    class NotFoundError(Exception):
        pass

    memoryhub_exceptions.NotFoundError = NotFoundError
    memoryhub_client.MemoryHubClient = client_mock

    memoryhub.client = memoryhub_client
    memoryhub.exceptions = memoryhub_exceptions

    return memoryhub, client_mock, NotFoundError


def _install_stubs(memoryhub, client_mod, exc_mod):
    sys.modules.setdefault("memoryhub", memoryhub)
    sys.modules.setdefault("memoryhub.client", client_mod)
    sys.modules.setdefault("memoryhub.exceptions", exc_mod)


# Build stubs once for the module lifetime.
_memoryhub_stub, _ClientClass, _NotFoundError = _make_memoryhub_stubs()
_install_stubs(_memoryhub_stub, _memoryhub_stub.client, _memoryhub_stub.exceptions)

# Now it is safe to import the implementation.
from kagenti_adk.server.store.memoryhub_memory_store import (  # noqa: E402
    MemoryHubMemoryStore,
    MemoryHubMemoryStoreInstance,
    _MemoryProxy,
    create_memory_dependency,
)


# ---------------------------------------------------------------------------
# Factories
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
# MemoryHubMemoryStore construction and from_env
# ---------------------------------------------------------------------------


class TestMemoryHubMemoryStore:
    def test_direct_construction_stores_params(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="key-123")
        assert store._url == "http://hub"
        assert store._api_key == "key-123"
        assert store._client is None

    def test_from_env_reads_api_key(self, monkeypatch):
        monkeypatch.setenv("MEMORYHUB_URL", "http://hub.example.com")
        monkeypatch.setenv("MEMORYHUB_API_KEY", "secret-key")
        monkeypatch.delenv("MEMORYHUB_AUTH_URL", raising=False)
        monkeypatch.delenv("MEMORYHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("MEMORYHUB_CLIENT_SECRET", raising=False)

        store = MemoryHubMemoryStore.from_env()
        assert store._url == "http://hub.example.com"
        assert store._api_key == "secret-key"
        assert store._auth_url is None

    def test_from_env_reads_oauth_vars(self, monkeypatch):
        monkeypatch.setenv("MEMORYHUB_URL", "http://hub.example.com")
        monkeypatch.setenv("MEMORYHUB_AUTH_URL", "http://auth.example.com")
        monkeypatch.setenv("MEMORYHUB_CLIENT_ID", "client-id")
        monkeypatch.setenv("MEMORYHUB_CLIENT_SECRET", "client-secret")
        monkeypatch.delenv("MEMORYHUB_API_KEY", raising=False)

        store = MemoryHubMemoryStore.from_env()
        assert store._auth_url == "http://auth.example.com"
        assert store._client_id == "client-id"
        assert store._client_secret == "client-secret"
        assert store._api_key is None

    def test_from_env_missing_vars_yields_none(self, monkeypatch):
        for var in ("MEMORYHUB_URL", "MEMORYHUB_API_KEY", "MEMORYHUB_AUTH_URL",
                    "MEMORYHUB_CLIENT_ID", "MEMORYHUB_CLIENT_SECRET"):
            monkeypatch.delenv(var, raising=False)

        store = MemoryHubMemoryStore.from_env()
        assert store._url is None
        assert store._api_key is None

    async def test_create_returns_instance(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        client = _mock_client()
        store._client = client

        inst = await store.create("ctx-1")
        assert isinstance(inst, MemoryHubMemoryStoreInstance)
        assert inst._context_id == "ctx-1"
        assert inst._client is client

    async def test_get_client_uses_api_key_path(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="my-key")
        fake_client = _mock_client()
        _ClientClass.return_value = fake_client

        with patch("memoryhub.client.MemoryHubClient", _ClientClass):
            client = await store._get_client()

        _ClientClass.assert_called_once_with(url="http://hub", api_key="my-key")
        assert store._client is fake_client

    async def test_get_client_uses_oauth_path(self):
        store = MemoryHubMemoryStore(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret="csec",
        )
        fake_client = _mock_client()
        _ClientClass.reset_mock()
        _ClientClass.return_value = fake_client

        with patch("memoryhub.client.MemoryHubClient", _ClientClass):
            client = await store._get_client()

        _ClientClass.assert_called_once_with(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret="csec",
        )
        assert store._client is fake_client

    async def test_get_client_is_cached(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        fake_client = _mock_client()
        store._client = fake_client

        _ClientClass.reset_mock()
        client = await store._get_client()
        assert client is fake_client
        # Pre-populated _client — constructor must not be called again.
        _ClientClass.assert_not_called()


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

        client.search.assert_awaited_once_with(
            "test query", scope=None, project_id=None, max_results=10
        )
        assert len(results) == 2
        assert results[0] == MemoryResult(memory_id="m1", content="alpha", scope="user",
                                          weight=0.8, relevance_score=0.9)
        assert results[1] == MemoryResult(memory_id="m2", content="beta", scope="project",
                                          weight=0.6, relevance_score=0.7)

    async def test_search_passes_optional_kwargs(self):
        client = _mock_client()
        client.search.return_value = _search_result()
        inst = self._make(client)

        await inst.search("q", scope="project", project_id="proj-1", max_results=5)

        client.search.assert_awaited_once_with(
            "q", scope="project", project_id="proj-1", max_results=5
        )

    async def test_search_falls_back_to_stub_when_content_none(self):
        client = _mock_client()
        client.search.return_value = _search_result(
            _memory_obj(id="m1", content=None, stub="stub text", scope="user")
        )
        inst = self._make(client)

        results = await inst.search("q")
        assert results[0].content == "stub text"

    async def test_search_empty_string_when_both_none(self):
        client = _mock_client()
        client.search.return_value = _search_result(
            _memory_obj(id="m1", content=None, stub=None, scope="user")
        )
        inst = self._make(client)

        results = await inst.search("q")
        assert results[0].content == ""

    async def test_search_empty_results(self):
        client = _mock_client()
        client.search.return_value = _search_result()
        inst = self._make(client)

        results = await inst.search("nothing")
        assert results == []

    # --- write ---

    async def test_write_returns_memory_id(self):
        client = _mock_client()
        client.write.return_value = _write_result(
            memory=SimpleNamespace(id="new-id-42")
        )
        inst = self._make(client)

        memory_id = await inst.write("important fact")

        client.write.assert_awaited_once_with(
            "important fact",
            scope="user",
            weight=0.7,
            domains=None,
            project_id=None,
        )
        assert memory_id == "new-id-42"

    async def test_write_passes_all_params(self):
        client = _mock_client()
        client.write.return_value = _write_result(memory=SimpleNamespace(id="x"))
        inst = self._make(client)

        await inst.write(
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

    async def test_write_returns_empty_string_when_curation_blocks(self):
        client = _mock_client()
        client.write.return_value = _write_result(
            memory=None,
            curation=SimpleNamespace(reason="duplicate detected"),
        )
        inst = self._make(client)

        memory_id = await inst.write("duplicate content")
        assert memory_id == ""

    # --- read ---

    async def test_read_returns_memory_result(self):
        client = _mock_client()
        client.read.return_value = _memory_obj(
            id="m-read", content="stored fact", scope="user", weight=0.8
        )
        inst = self._make(client)

        result = await inst.read("m-read")

        client.read.assert_awaited_once_with("m-read")
        assert result == MemoryResult(
            memory_id="m-read", content="stored fact", scope="user", weight=0.8
        )

    async def test_read_returns_none_for_not_found(self):
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
# _MemoryProxy — lazy initialization and method delegation
# ---------------------------------------------------------------------------


class TestMemoryProxy:
    def _make_store_and_proxy(self, client=None) -> tuple[MemoryHubMemoryStore, _MemoryProxy]:
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        store._client = client or _mock_client()
        proxy = _MemoryProxy(store=store, context_id="ctx-proxy")
        return store, proxy

    async def test_instance_is_none_before_first_call(self):
        _, proxy = self._make_store_and_proxy()
        assert proxy._instance is None

    async def test_resolve_creates_instance_once(self):
        _, proxy = self._make_store_and_proxy()

        inst1 = await proxy._resolve()
        inst2 = await proxy._resolve()

        assert inst1 is inst2
        assert isinstance(inst1, MemoryHubMemoryStoreInstance)

    async def test_search_delegates_to_instance(self):
        client = _mock_client()
        client.search.return_value = _search_result(
            _memory_obj(id="p1", content="proxy content", scope="user")
        )
        _, proxy = self._make_store_and_proxy(client)

        results = await proxy.search("via proxy")
        assert len(results) == 1
        assert results[0].memory_id == "p1"

    async def test_write_delegates_to_instance(self):
        client = _mock_client()
        client.write.return_value = _write_result(memory=SimpleNamespace(id="proxy-id"))
        _, proxy = self._make_store_and_proxy(client)

        memory_id = await proxy.write("proxy write")
        assert memory_id == "proxy-id"

    async def test_read_delegates_to_instance(self):
        client = _mock_client()
        client.read.return_value = _memory_obj(id="r1", content="c", scope="user")
        _, proxy = self._make_store_and_proxy(client)

        result = await proxy.read("r1")
        assert result.memory_id == "r1"

    async def test_update_delegates_to_instance(self):
        client = _mock_client()
        _, proxy = self._make_store_and_proxy(client)

        await proxy.update("m-1", "updated")
        client.update.assert_awaited_once_with("m-1", content="updated")

    async def test_delete_delegates_to_instance(self):
        client = _mock_client()
        _, proxy = self._make_store_and_proxy(client)

        await proxy.delete("m-del")
        client.delete.assert_awaited_once_with("m-del")

    async def test_curation_blocked_write_via_proxy(self):
        client = _mock_client()
        client.write.return_value = _write_result(
            memory=None,
            curation=SimpleNamespace(reason="blocked"),
        )
        _, proxy = self._make_store_and_proxy(client)

        memory_id = await proxy.write("blocked content")
        assert memory_id == ""


# ---------------------------------------------------------------------------
# create_memory_dependency
# ---------------------------------------------------------------------------


class TestCreateMemoryDependency:
    def test_returns_callable(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        dep = create_memory_dependency(store)
        assert callable(dep)

    def test_provider_returns_proxy(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        dep = create_memory_dependency(store)

        fake_context = SimpleNamespace(context_id="ctx-dep-1")
        proxy = dep(message=None, context=fake_context, request_context=None)

        assert isinstance(proxy, _MemoryProxy)
        assert proxy._store is store
        assert proxy._context_id == "ctx-dep-1"

    def test_provider_uses_context_id_from_context(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        dep = create_memory_dependency(store)

        proxy_a = dep(None, SimpleNamespace(context_id="ctx-A"), None)
        proxy_b = dep(None, SimpleNamespace(context_id="ctx-B"), None)

        assert proxy_a._context_id == "ctx-A"
        assert proxy_b._context_id == "ctx-B"

    def test_each_call_returns_new_proxy(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        dep = create_memory_dependency(store)

        ctx = SimpleNamespace(context_id="ctx-same")
        p1 = dep(None, ctx, None)
        p2 = dep(None, ctx, None)

        assert p1 is not p2

    async def test_proxy_from_dependency_resolves_correctly(self):
        store = MemoryHubMemoryStore(url="http://hub", api_key="k")
        client = _mock_client()
        store._client = client
        client.search.return_value = _search_result(
            _memory_obj(id="dep-m1", content="dep content", scope="user")
        )

        dep = create_memory_dependency(store)
        proxy = dep(None, SimpleNamespace(context_id="ctx-resolve"), None)

        results = await proxy.search("dep query")
        assert len(results) == 1
        assert results[0].memory_id == "dep-m1"
