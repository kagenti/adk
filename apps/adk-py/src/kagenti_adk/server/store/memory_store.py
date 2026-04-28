# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

"""Long-term governed memory store abstraction for AI agents.

This module defines the MemoryStore protocol — a complement to ContextStore
that handles durable, cross-session knowledge rather than per-context
conversation replay. ContextStore answers "what was said in this conversation";
MemoryStore answers "what does this agent know across all conversations."

The protocol is backend-agnostic. The MemoryHub implementation in
memoryhub_memory_store.py is one concrete backend; others (Redis, SQLite,
in-memory for testing) can implement the same interface.
"""

from __future__ import annotations

import abc
from typing import Protocol

from pydantic import BaseModel

__all__ = [
    "MemoryResult",
    "MemoryStore",
    "MemoryStoreInstance",
]


class MemoryResult(BaseModel):
    """A single memory returned from search or read."""

    memory_id: str
    content: str
    scope: str
    weight: float = 0.7
    relevance_score: float | None = None


class MemoryStoreInstance(Protocol):
    """Operations on governed memory, scoped to a context.

    Each method maps to a standard memory lifecycle operation.
    Implementations should raise backend-specific errors for
    authorization failures or validation issues.
    """

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        project_id: str | None = None,
        max_results: int = 10,
    ) -> list[MemoryResult]: ...

    async def create(
        self,
        content: str,
        *,
        scope: str = "user",
        weight: float = 0.7,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> str:
        """Create a new memory. Returns the new memory_id."""
        ...

    async def read(self, memory_id: str) -> MemoryResult | None: ...

    async def update(self, memory_id: str, content: str) -> None: ...

    async def delete(self, memory_id: str) -> None: ...


class MemoryStore(abc.ABC):
    """Factory that creates MemoryStoreInstance objects per context.

    Mirrors the ContextStore pattern: the factory holds connection config,
    create() returns a per-context instance.
    """

    @property
    def required_extensions(self) -> set[str]:
        return set()

    @abc.abstractmethod
    async def create(self, context_id: str) -> MemoryStoreInstance: ...
