# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

# Maintainer note: this E2E test requires a reachable MemoryHub instance.
#
# URL resolution order:
#   1. MEMORYHUB_E2E_URL env var / repo secret (explicit override)
#   2. MemoryHub discovery endpoint (auto-detects current sandbox URL)
#
# Credentials (at least one set required):
#   MEMORYHUB_E2E_API_KEY              — static API key
#   MEMORYHUB_E2E_AUTH_URL             — OAuth 2.1 credentials (all three)
#   MEMORYHUB_E2E_CLIENT_ID
#   MEMORYHUB_E2E_CLIENT_SECRET
#
# When neither credential set is configured the test skips cleanly so
# contributor forks don't fail on a missing secret.
#
# URL drift handling: the configured backend can move (URL changes,
# certificate expires, credentials rotate) without anyone updating the
# repo secrets. A pre-flight probe distinguishes that drift from real
# test logic regressions and converts it into an xfail with a clear
# reason, instead of a mysterious assertion failure deep inside the
# example agent's task stream.

from __future__ import annotations

import os

import httpx
import pytest
from a2a.client.helpers import create_text_message_object
from a2a.types import SendMessageRequest, TaskState
from kagenti_adk.a2a.extensions import (
    MemoryHubExtensionClient,
    MemoryHubExtensionSpec,
    MemoryHubFulfillment,
)
from pydantic import SecretStr

# The pre-flight URL drift probe needs the memoryhub SDK in the test
# environment. The SDK is an optional extra of kagenti-adk and is not
# installed by adk-server's dev deps, so collect-skip if it isn't there
# rather than break the whole adk-server e2e suite.
pytest.importorskip("memoryhub")

from memoryhub.client import MemoryHubClient
from memoryhub.exceptions import (
    AuthenticationError,
    ConnectionFailedError,
    MemoryHubError,
)

from tests.e2e.examples.conftest import run_example

pytestmark = pytest.mark.e2e

DISCOVERY_URL = "https://redhat-ai-americas.github.io/memory-hub/discovery.json"


def _discover_url(timeout: float = 5.0) -> str | None:
    """Fetch the current MCP URL from the MemoryHub discovery endpoint."""
    try:
        resp = httpx.get(DISCOVERY_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        default = data.get("default", "sandbox")
        return data["instances"][default]["mcp_url"]
    except Exception:
        return None


def _fulfillment_from_secrets() -> MemoryHubFulfillment | None:
    url = os.environ.get("MEMORYHUB_E2E_URL") or _discover_url()
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


def _client_for(fulfillment: MemoryHubFulfillment) -> MemoryHubClient:
    if fulfillment.api_key is not None:
        return MemoryHubClient(
            url=fulfillment.url,
            api_key=fulfillment.api_key.get_secret_value(),
        )
    return MemoryHubClient(
        url=fulfillment.url,
        auth_url=fulfillment.auth_url,
        client_id=fulfillment.client_id,
        client_secret=(fulfillment.client_secret.get_secret_value() if fulfillment.client_secret is not None else None),
    )


def _classify_drift(exc: BaseException, url: str) -> str | None:
    """Walk the exception's cause chain looking for a drift signal.

    FastMCP wraps transport errors in a generic ``RuntimeError`` at
    ``_connect``; the original ``httpx.ConnectError`` / DNS failure
    only shows up in ``__cause__``. Walk the chain so DNS failures and
    refused-connection cases are still classified as URL drift instead
    of leaking as generic errors.
    """
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, AuthenticationError):
            return f"MemoryHub auth drift at {url}: credentials rejected ({cur})"
        if isinstance(cur, ConnectionFailedError):
            return f"MemoryHub URL drift at {url}: cannot reach backend ({cur})"
        if isinstance(cur, (httpx.HTTPError, OSError)):
            return f"MemoryHub URL drift at {url}: transport error ({type(cur).__name__}: {cur})"
        if isinstance(cur, MemoryHubError):
            return f"MemoryHub backend unhealthy at {url}: {type(cur).__name__}: {cur}"
        cur = cur.__cause__ or cur.__context__
    return None


async def _xfail_on_backend_drift(fulfillment: MemoryHubFulfillment) -> None:
    """Probe MemoryHub before we spin up the example.

    The example agent will use these exact credentials to call MemoryHub
    once it's running. If the URL has moved, the cert is invalid, or the
    credentials no longer authenticate, that surfaces here as a single
    xfail with a clear reason — not as a generic
    ``task.status.state == FAILED`` assertion error after spending CI
    time on the platform deploy.
    """
    try:
        async with _client_for(fulfillment) as client:
            await client.get_session()
    except Exception as exc:
        reason = _classify_drift(exc, str(fulfillment.url))
        if reason is not None:
            pytest.xfail(reason)
        raise


@pytest.mark.usefixtures("clean_up", "setup_platform_client")
async def test_memoryhub_recall_example(subtests, get_final_task_from_stream, a2a_client_factory):
    fulfillment = _fulfillment_from_secrets()
    if fulfillment is None:
        pytest.skip(
            "MemoryHub E2E not configured: no MEMORYHUB_E2E_URL set, discovery endpoint unreachable, "
            "and/or no credentials (MEMORYHUB_E2E_API_KEY or OAuth trio)."
        )

    await _xfail_on_backend_drift(fulfillment)

    example_path = "agent-integration/memoryhub/memoryhub-recall"

    async with run_example(example_path, a2a_client_factory) as running_example:
        spec = MemoryHubExtensionSpec.from_agent_card(running_example.provider.agent_card)
        metadata = MemoryHubExtensionClient(spec).fulfillment_metadata(memoryhub_fulfillments={"default": fulfillment})

        with subtests.test("agent recalls and stores via MemoryHub"):
            message = create_text_message_object(content="favorite color is teal")
            message.metadata = metadata
            message.context_id = running_example.context.id
            task = await get_final_task_from_stream(
                running_example.client.send_message(SendMessageRequest(message=message))
            )

            assert task.status.state == TaskState.TASK_STATE_COMPLETED, f"Fail: {task.status.message.parts[0].text}"
            text = task.history[-1].parts[0].text
            assert "stored 1" in text
            assert "recalled" in text
