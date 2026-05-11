# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


class MemoryRejectionError(RuntimeError):
    """Raised when the memory store refused to record a memory.

    Backends that run a pre-storage pipeline (deduplication, contradiction
    detection, policy/curator rules) may reject a write. The ``reason``
    attribute carries the backend's explanation when one is provided.
    """

    def __init__(self, reason: str | None = None):
        msg = f"Memory store rejected the memory: {reason}" if reason else "Memory store rejected the memory"
        super().__init__(msg)
        self.reason = reason
