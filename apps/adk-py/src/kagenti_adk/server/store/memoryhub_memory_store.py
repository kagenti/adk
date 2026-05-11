# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

"""MemoryStore backed by MemoryHub (https://github.com/redhat-ai-americas/memory-hub).

Wraps the ``memoryhub`` Python SDK to provide governed, cross-session memory
to ADK agents via the MemoryStore protocol. Requires the ``memoryhub`` extra:

    uv add kagenti-adk[memoryhub]

The connection is supplied to agents via the MemoryHub A2A service extension
(``services.memoryhub.MemoryHubExtensionSpec``); the
:class:`MemoryHubExtensionServer` opens and closes the underlying client as
part of its ``lifespan`` and exposes per-context store instances via
:meth:`MemoryHubExtensionServer.store`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from memoryhub.client import MemoryHubClient
from memoryhub.exceptions import NotFoundError
from typing_extensions import override

from kagenti_adk.a2a.extensions.services.memoryhub import (
    MemoryHubExtensionServer as _BaseMemoryHubExtensionServer,
)
from kagenti_adk.server.store.exceptions import MemoryRejectionError
from kagenti_adk.server.store.memory_store import MemoryResult, MemoryStoreInstance

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = [
    "MemoryHubExtensionServer",
    "MemoryHubMemoryStoreInstance",
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
        # memoryhub.WriteResult.memory is None when the SDK's curation pipeline rejected the write
        if result.memory is None:
            raise MemoryRejectionError(result.curation.reason)
        return result.memory.id

    async def read(self, memory_id: str) -> MemoryResult | None:
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


class MemoryHubExtensionServer(_BaseMemoryHubExtensionServer):
    """Server-side MemoryHub extension that owns the MemoryHub client lifecycle.

    Subclasses the protocol-only base with a ``lifespan()`` that opens the
    underlying ``memoryhub.client.MemoryHubClient`` from the active
    :class:`MemoryHubFulfillment` and closes it on exit. Use
    :meth:`store` to obtain a :class:`MemoryHubMemoryStoreInstance` bound
    to the request's context.
    """

    _client: MemoryHubClient | None = None

    @asynccontextmanager
    @override
    async def lifespan(self) -> AsyncGenerator[None]:
        fulfillment = self._resolve_fulfillment()
        if fulfillment is None:
            # Extension was not fulfilled by the client and no env fallback;
            # leave _client unset so accidental store() use raises clearly.
            yield
            return

        if fulfillment.api_key is not None:
            client = MemoryHubClient(
                url=fulfillment.url,
                api_key=fulfillment.api_key.get_secret_value(),
            )
        else:
            client = MemoryHubClient(
                url=fulfillment.url,
                auth_url=fulfillment.auth_url,
                client_id=fulfillment.client_id,
                client_secret=(
                    fulfillment.client_secret.get_secret_value() if fulfillment.client_secret is not None else None
                ),
            )

        await client.__aenter__()
        self._client = client
        logger.info("MemoryHub client connected to %s", fulfillment.url)
        try:
            yield
        finally:
            await client.__aexit__(None, None, None)
            self._client = None

    def store(self, context_id: str) -> MemoryHubMemoryStoreInstance:
        """Return a per-context store instance.

        Must be called inside the extension's ``lifespan`` window — i.e.
        from agent code that depends on the extension via ``Annotated[...,
        MemoryHubExtensionSpec.single_demand()]``.
        """
        if self._client is None:
            raise RuntimeError(
                "MemoryHubExtensionServer.store() called without an active client. "
                "Either fulfill the extension via A2A metadata or set MEMORYHUB_URL "
                "and credentials in the environment."
            )
        return MemoryHubMemoryStoreInstance(context_id=context_id, client=self._client)

    def _resolve_fulfillment(self):
        # data() falls back to spec.default if the client did not provide metadata.
        try:
            data = self.data
        except AttributeError:
            return None
        if data is None or not data.memoryhub_fulfillments:
            return None
        return next(iter(data.memoryhub_fulfillments.values()))
