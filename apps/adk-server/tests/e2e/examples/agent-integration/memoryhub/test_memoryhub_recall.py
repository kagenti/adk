# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

# Maintainer note: this E2E test requires a reachable MemoryHub instance.
# Add the following repository secrets so CI runs the test:
#   MEMORYHUB_E2E_URL              (required) — public MemoryHub MCP URL
#   MEMORYHUB_E2E_API_KEY          (one of)  — static API key
#   MEMORYHUB_E2E_AUTH_URL         (or…)
#   MEMORYHUB_E2E_CLIENT_ID
#   MEMORYHUB_E2E_CLIENT_SECRET    — OAuth 2.1 credentials
# When neither credential set is configured the test skips cleanly so
# contributor forks don't fail on a missing secret.

from __future__ import annotations

import os

import pytest
from a2a.client.helpers import create_text_message_object
from a2a.types import SendMessageRequest, TaskState
from kagenti_adk.a2a.extensions import (
    MemoryHubExtensionClient,
    MemoryHubExtensionSpec,
    MemoryHubFulfillment,
)
from pydantic import SecretStr

from tests.e2e.examples.conftest import run_example

pytestmark = pytest.mark.e2e


def _fulfillment_from_secrets() -> MemoryHubFulfillment | None:
    url = os.environ.get("MEMORYHUB_E2E_URL")
    if not url:
        return None
    api_key = os.environ.get("MEMORYHUB_E2E_API_KEY")
    if api_key:
        return MemoryHubFulfillment(url=url, api_key=SecretStr(api_key))
    auth_url = os.environ.get("MEMORYHUB_E2E_AUTH_URL")
    client_id = os.environ.get("MEMORYHUB_E2E_CLIENT_ID")
    client_secret = os.environ.get("MEMORYHUB_E2E_CLIENT_SECRET")
    if auth_url and client_id and client_secret:
        return MemoryHubFulfillment(
            url=url,
            auth_url=auth_url,
            client_id=client_id,
            client_secret=SecretStr(client_secret),
        )
    return None


@pytest.mark.usefixtures("clean_up", "setup_platform_client")
async def test_memoryhub_recall_example(subtests, get_final_task_from_stream, a2a_client_factory):
    fulfillment = _fulfillment_from_secrets()
    if fulfillment is None:
        pytest.skip(
            "MemoryHub E2E secrets not configured (set MEMORYHUB_E2E_URL plus "
            "MEMORYHUB_E2E_API_KEY or the OAuth trio)."
        )

    example_path = "agent-integration/memoryhub/memoryhub-recall"

    async with run_example(example_path, a2a_client_factory) as running_example:
        spec = MemoryHubExtensionSpec.from_agent_card(running_example.provider.agent_card)
        metadata = MemoryHubExtensionClient(spec).fulfillment_metadata(
            memoryhub_fulfillments={"default": fulfillment}
        )

        with subtests.test("agent recalls and stores via MemoryHub"):
            message = create_text_message_object(content="favorite color is teal")
            message.metadata = metadata
            message.context_id = running_example.context.id
            task = await get_final_task_from_stream(
                running_example.client.send_message(SendMessageRequest(message=message))
            )

            assert task.status.state == TaskState.TASK_STATE_COMPLETED, (
                f"Fail: {task.status.message.parts[0].text}"
            )
            text = task.history[-1].parts[0].text
            assert "stored 1" in text
            assert "recalled" in text
