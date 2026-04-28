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

from pydantic import BaseModel, Field

__all__ = [
    "MemoryResult",
    "MemoryStore",
    "MemoryStoreInstance",
]


class MemoryResult(BaseModel):
    """A single memory returned from search or read.

    Field semantics are intentionally backend-agnostic. Concrete backends
    map their own concepts onto these fields; the MemoryHub backend's
    mapping is documented inline as a worked example.
    """

    memory_id: str = Field(
        description="Backend-assigned identifier for the memory."
    )
    content: str = Field(
        description="The memory's payload. May be a stub for search results."
    )
    scope: str = Field(
        description=(
            "Visibility/governance domain. Backend-defined; in MemoryHub: "
            "one of user/project/campaign/organizational/enterprise."
        )
    )
    weight: float = Field(
        default=0.7,
        description=(
            "Priority/curation signal in the range 0.0-1.0. Backends may use "
            "it for ranking or ignore it."
        ),
    )
    relevance_score: float | None = Field(
        default=None,
        description=(
            "Search relevance score returned by the backend; None for "
            "non-search results."
        ),
    )


class MemoryStoreInstance(Protocol):
    """Operations on governed memory, scoped to a context.

    Each method maps to a standard memory lifecycle operation.
    Implementations should raise backend-specific errors for
    authorization failures or validation issues.

    Common keyword arguments share semantics across all methods:

    - ``scope``: Visibility/governance domain. Backend-defined; in
      MemoryHub: one of user/project/campaign/organizational/enterprise.
    - ``weight``: Priority/curation signal in the range 0.0-1.0. Backends
      may use it for ranking or ignore it.
    - ``tags``: Free-form tags for grouping/filtering. Backend-defined
      semantics; in MemoryHub: "domains" attached to a memory.
    - ``project_id``: Optional grouping within a memory store;
      backend-defined semantics. In MemoryHub: a project with member-based
      access control. NOT a tenancy boundary — tenancy is established by
      the backend's auth credentials.
    """

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        project_id: str | None = None,
        max_results: int = 10,
    ) -> list[MemoryResult]:
        """Search for memories matching ``query``.

        ``scope`` and ``project_id`` filter results; their semantics are
        backend-defined. See the class docstring for the cross-method
        conventions.
        """
        ...

    async def create(
        self,
        content: str,
        *,
        scope: str = "user",
        weight: float = 0.7,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> str:
        """Create a new memory. Returns the new memory_id.

        ``scope``, ``weight``, ``tags`` and ``project_id`` follow the
        cross-method conventions documented on the class.
        """
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
