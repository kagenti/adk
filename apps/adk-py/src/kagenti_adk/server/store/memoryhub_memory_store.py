# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

"""MemoryStore backed by MemoryHub (https://github.com/redhat-ai-americas/memory-hub).

Wraps the ``memoryhub`` Python SDK to provide governed, cross-session memory
to ADK agents via the MemoryStore protocol. Requires the ``memoryhub`` extra:

    pip install kagenti-adk[memoryhub]

Authentication is configured via environment variables:

    OAuth 2.1 (recommended):
        MEMORYHUB_URL, MEMORYHUB_AUTH_URL, MEMORYHUB_CLIENT_ID, MEMORYHUB_CLIENT_SECRET

    API key (dev/testing):
        MEMORYHUB_URL, MEMORYHUB_API_KEY
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from kagenti_adk.server.store.memory_store import MemoryResult, MemoryStore, MemoryStoreInstance

if TYPE_CHECKING:
    from a2a.types import Message
    from memoryhub.client import MemoryHubClient

    from kagenti_adk.server.context import RunContext

logger = logging.getLogger(__name__)

__all__ = [
    "MemoryHubMemoryStore",
    "MemoryHubMemoryStoreInstance",
    "create_memory_dependency",
]


class MemoryHubMemoryStoreInstance(MemoryStoreInstance):
    """Per-context memory operations backed by MemoryHub."""

    def __init__(self, context_id: str, client: MemoryHubClient) -> None:
        self._context_id = context_id
        self._client = client

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        project_id: str | None = None,
        max_results: int = 10,
    ) -> list[MemoryResult]:
        result = await self._client.search(
            query,
            scope=scope,
            project_id=project_id,
            max_results=max_results,
        )
        return [
            MemoryResult(
                memory_id=m.id,
                content=m.content or m.stub or "",
                scope=m.scope,
                weight=m.weight,
                relevance_score=m.relevance_score,
            )
            for m in result.results
        ]

    async def create(
        self,
        content: str,
        *,
        scope: str = "user",
        weight: float = 0.7,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> str:
        result = await self._client.write(
            content,
            scope=scope,
            weight=weight,
            domains=tags,
            project_id=project_id,
        )
        if result.memory is None:
            # Curation gated the create — return empty string to signal no-op
            logger.warning("MemoryHub curation gated create: %s", result.curation.reason)
            return ""
        return result.memory.id

    async def read(self, memory_id: str) -> MemoryResult | None:
        from memoryhub.exceptions import NotFoundError

        try:
            m = await self._client.read(memory_id)
        except NotFoundError:
            return None
        return MemoryResult(
            memory_id=m.id,
            content=m.content or "",
            scope=m.scope,
            weight=m.weight,
        )

    async def update(self, memory_id: str, content: str) -> None:
        await self._client.update(memory_id, content=content)

    async def delete(self, memory_id: str) -> None:
        await self._client.delete(memory_id)


class MemoryHubMemoryStore(MemoryStore):
    """Factory for MemoryHub-backed memory store instances.

    Holds connection configuration and lazily creates the MemoryHubClient
    on first use. The client is shared across all instances (contexts)
    because it manages its own auth token lifecycle.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        auth_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._url = url
        self._auth_url = auth_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_key = api_key
        self._client: MemoryHubClient | None = None

    @classmethod
    def from_env(cls) -> MemoryHubMemoryStore:
        """Create from MEMORYHUB_* environment variables."""
        return cls(
            url=os.environ.get("MEMORYHUB_URL"),
            auth_url=os.environ.get("MEMORYHUB_AUTH_URL"),
            client_id=os.environ.get("MEMORYHUB_CLIENT_ID"),
            client_secret=os.environ.get("MEMORYHUB_CLIENT_SECRET"),
            api_key=os.environ.get("MEMORYHUB_API_KEY"),
        )

    async def _get_client(self) -> MemoryHubClient:
        if self._client is None:
            from memoryhub.client import MemoryHubClient

            if self._api_key:
                self._client = MemoryHubClient(
                    url=self._url,
                    api_key=self._api_key,
                )
            else:
                self._client = MemoryHubClient(
                    url=self._url,
                    auth_url=self._auth_url,
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                )
            await self._client.__aenter__()
            logger.info("MemoryHub client connected to %s", self._url)
        return self._client

    async def close(self) -> None:
        """Close the underlying MemoryHub client session."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def create(self, context_id: str) -> MemoryStoreInstance:
        client = await self._get_client()
        return MemoryHubMemoryStoreInstance(context_id=context_id, client=client)


class _MemoryProxy:
    """Lazy-initializing proxy that resolves the MemoryStoreInstance on first use.

    The ADK's Depends framework calls the dependency callable synchronously and
    yields the return value. Since MemoryStore.create() is async, we can't call
    it during dependency resolution. Instead, we return this proxy which lazily
    awaits create() on the first method call.
    """

    def __init__(self, store: MemoryHubMemoryStore, context_id: str) -> None:
        self._store = store
        self._context_id = context_id
        self._instance: MemoryHubMemoryStoreInstance | None = None

    async def _resolve(self) -> MemoryHubMemoryStoreInstance:
        if self._instance is None:
            self._instance = await self._store.create(self._context_id)
        return self._instance

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        project_id: str | None = None,
        max_results: int = 10,
    ) -> list[MemoryResult]:
        inst = await self._resolve()
        return await inst.search(query, scope=scope, project_id=project_id, max_results=max_results)

    async def create(
        self,
        content: str,
        *,
        scope: str = "user",
        weight: float = 0.7,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> str:
        inst = await self._resolve()
        return await inst.create(content, scope=scope, weight=weight, tags=tags, project_id=project_id)

    async def read(self, memory_id: str) -> MemoryResult | None:
        inst = await self._resolve()
        return await inst.read(memory_id)

    async def update(self, memory_id: str, content: str) -> None:
        inst = await self._resolve()
        return await inst.update(memory_id, content)

    async def delete(self, memory_id: str) -> None:
        inst = await self._resolve()
        return await inst.delete(memory_id)


def create_memory_dependency(store: MemoryHubMemoryStore):
    """Create a DI-compatible dependency provider for the ADK Depends pattern.

    Returns a synchronous callable (required by ADK's Depends) that produces
    a lazy-initializing proxy. The proxy resolves the MemoryStoreInstance
    on first async method call.

    Usage::

        memory_store = MemoryHubMemoryStore.from_env()
        memory_dep = create_memory_dependency(memory_store)

        @server.agent()
        async def my_agent(
            input: Message,
            context: RunContext,
            memory: Annotated[MemoryHubMemoryStoreInstance, Depends(memory_dep)],
        ):
            results = await memory.search("user preferences")
    """

    def provider(message: Message, context: RunContext, request_context: Any) -> _MemoryProxy:
        return _MemoryProxy(store, context.context_id)

    return provider
