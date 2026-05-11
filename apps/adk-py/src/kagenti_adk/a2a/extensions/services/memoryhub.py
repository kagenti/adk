# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import os
from types import NoneType
from typing import TYPE_CHECKING, Any, Self

import pydantic
from a2a.server.agent_execution.context import RequestContext
from a2a.types import Message as A2AMessage
from pydantic import SecretStr
from typing_extensions import override

from kagenti_adk.a2a.extensions.base import (
    DEFAULT_DEMAND_NAME,
    BaseExtensionClient,
    BaseExtensionServer,
    BaseExtensionSpec,
)
from kagenti_adk.util.pydantic import REVEAL_SECRETS, SecureBaseModel, redact_str

__all__ = [
    "MemoryHubDemand",
    "MemoryHubExtensionClient",
    "MemoryHubExtensionMetadata",
    "MemoryHubExtensionParams",
    "MemoryHubExtensionServer",
    "MemoryHubExtensionSpec",
    "MemoryHubFulfillment",
]

if TYPE_CHECKING:
    from kagenti_adk.server.context import RunContext


class MemoryHubFulfillment(SecureBaseModel):
    """Connection details the client provides for a MemoryHub instance."""

    url: str
    """
    Base URL of the MemoryHub MCP endpoint, e.g.
    ``https://memory-hub-mcp.example.com/mcp/``.
    """

    api_key: SecretStr | None = None
    """
    Static API key for the dev/testing path. Mutually exclusive with the
    OAuth fields below.
    """

    auth_url: str | None = None
    """
    OAuth 2.1 token endpoint. Required together with ``client_id`` and
    ``client_secret`` for the OAuth path.
    """

    client_id: str | None = None
    """
    OAuth 2.1 client identifier.
    """

    client_secret: SecretStr | None = None
    """
    OAuth 2.1 client secret.
    """

    @pydantic.field_serializer("url")
    def _redact_url(self, v: str, info) -> str:
        return redact_str(v, info)


class MemoryHubDemand(pydantic.BaseModel):
    """A request from the agent for a MemoryHub fulfillment."""

    description: str | None = None
    """
    Short description of how the memory store will be used. Intended to be
    shown in the UI alongside a connection picker.
    """


class MemoryHubExtensionParams(pydantic.BaseModel):
    memoryhub_demands: dict[str, MemoryHubDemand]
    """MemoryHub connections that the agent requires the client to provide."""


class MemoryHubExtensionMetadata(pydantic.BaseModel):
    memoryhub_fulfillments: dict[str, MemoryHubFulfillment] = {}
    """Connection details corresponding to the agent's demands."""


class MemoryHubExtensionSpec(BaseExtensionSpec[MemoryHubExtensionParams, MemoryHubExtensionMetadata]):
    URI: str = "https://a2a-extensions.adk.kagenti.dev/services/memoryhub/v1"

    @classmethod
    def single_demand(
        cls,
        name: str = DEFAULT_DEMAND_NAME,
        description: str | None = None,
        default: MemoryHubFulfillment | None = None,
    ) -> Self:
        return cls(
            params=MemoryHubExtensionParams(memoryhub_demands={name: MemoryHubDemand(description=description)}),
            default=(MemoryHubExtensionMetadata(memoryhub_fulfillments={name: default}) if default else None),
        )


class MemoryHubExtensionServer(BaseExtensionServer[MemoryHubExtensionSpec, MemoryHubExtensionMetadata]):
    @override
    def handle_incoming_message(self, message: A2AMessage, run_context: RunContext, request_context: RequestContext):
        super().handle_incoming_message(message, run_context, request_context)

        if not self._metadata_from_client or not self._metadata_from_client.memoryhub_fulfillments:
            fulfillment = _memoryhub_fulfillment_from_env()
            if fulfillment:
                self._metadata_from_client = MemoryHubExtensionMetadata(memoryhub_fulfillments={"default": fulfillment})


class MemoryHubExtensionClient(BaseExtensionClient[MemoryHubExtensionSpec, NoneType]):
    def fulfillment_metadata(self, *, memoryhub_fulfillments: dict[str, MemoryHubFulfillment]) -> dict[str, Any]:
        return {
            self.spec.URI: MemoryHubExtensionMetadata(memoryhub_fulfillments=memoryhub_fulfillments).model_dump(
                mode="json", context={REVEAL_SECRETS: True}
            )
        }


def _memoryhub_fulfillment_from_env() -> MemoryHubFulfillment | None:
    """Build a default MemoryHub fulfillment from environment variables.

    Reads ``MEMORYHUB_URL`` (required), and either ``MEMORYHUB_API_KEY``
    (dev path) or ``MEMORYHUB_AUTH_URL`` + ``MEMORYHUB_CLIENT_ID`` +
    ``MEMORYHUB_CLIENT_SECRET`` (OAuth 2.1 path). Returns None if no URL
    is set or no usable credential is available.
    """
    url = os.environ.get("MEMORYHUB_URL")
    if not url:
        return None

    api_key = os.environ.get("MEMORYHUB_API_KEY")
    auth_url = os.environ.get("MEMORYHUB_AUTH_URL")
    client_id = os.environ.get("MEMORYHUB_CLIENT_ID")
    client_secret = os.environ.get("MEMORYHUB_CLIENT_SECRET")

    if api_key:
        return MemoryHubFulfillment(url=url, api_key=SecretStr(api_key))
    if auth_url and client_id and client_secret:
        return MemoryHubFulfillment(
            url=url,
            auth_url=auth_url,
            client_id=client_id,
            client_secret=SecretStr(client_secret),
        )
    return None
