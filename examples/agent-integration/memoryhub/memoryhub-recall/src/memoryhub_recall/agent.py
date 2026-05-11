# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Annotated

from a2a.types import Message
from a2a.utils.message import get_message_text
from kagenti_adk.a2a.extensions import (
    MemoryHubExtensionSpec,
)
from kagenti_adk.a2a.types import AgentMessage
from kagenti_adk.server import Server
from kagenti_adk.server.context import RunContext
from kagenti_adk.server.store.memoryhub_memory_store import MemoryHubExtensionServer

server = Server()


@server.agent()
async def memoryhub_recall_example(
    input: Message,
    context: RunContext,
    memoryhub: Annotated[MemoryHubExtensionServer, MemoryHubExtensionSpec.single_demand()],
):
    """Search MemoryHub for the user's query, then store one fact from the input."""
    query = get_message_text(input)
    store = memoryhub.store(context.context_id)

    results = await store.search(query, max_results=5)
    await store.create(
        f"User mentioned: {query}",
        scope="project",
        project_id="kagenti-tests",
        weight=0.7,
    )

    yield AgentMessage(text=f"recalled {len(results)} items, stored 1")


def run():
    server.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    run()
