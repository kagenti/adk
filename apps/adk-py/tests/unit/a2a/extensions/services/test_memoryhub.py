# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from kagenti_adk.a2a.extensions import (
    MemoryHubExtensionClient,
    MemoryHubExtensionMetadata,
    MemoryHubExtensionParams,
    MemoryHubExtensionSpec,
    MemoryHubFulfillment,
)
from kagenti_adk.a2a.extensions.services.memoryhub import _memoryhub_fulfillment_from_env
from kagenti_adk.util.pydantic import REVEAL_SECRETS

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env():
    """Ensure no MEMORYHUB env vars leak between tests."""
    env_vars = [
        "MEMORYHUB_URL",
        "MEMORYHUB_API_KEY",
        "MEMORYHUB_AUTH_URL",
        "MEMORYHUB_CLIENT_ID",
        "MEMORYHUB_CLIENT_SECRET",
    ]
    with patch.dict(os.environ, {}, clear=False):
        for var in env_vars:
            os.environ.pop(var, None)
        yield


# ---------------------------------------------------------------------------
# Spec construction / round-trip
# ---------------------------------------------------------------------------


class TestMemoryHubExtensionSpec:
    def test_uri_is_versioned(self):
        spec = MemoryHubExtensionSpec(
            params=MemoryHubExtensionParams(memoryhub_demands={})
        )
        assert spec.URI == "https://a2a-extensions.adk.kagenti.dev/services/memoryhub/v1"

    def test_single_demand_default_name(self):
        spec = MemoryHubExtensionSpec.single_demand()
        assert "default" in spec.params.memoryhub_demands
        assert spec.params.memoryhub_demands["default"].description is None

    def test_single_demand_custom_name_and_description(self):
        spec = MemoryHubExtensionSpec.single_demand(
            name="primary", description="cross-session knowledge"
        )
        assert "primary" in spec.params.memoryhub_demands
        assert spec.params.memoryhub_demands["primary"].description == "cross-session knowledge"

    def test_single_demand_with_default_fulfillment(self):
        default = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("k"))
        spec = MemoryHubExtensionSpec.single_demand(default=default)
        assert spec.default is not None
        assert spec.default.memoryhub_fulfillments["default"].url == "http://hub"

    def test_to_agent_card_extensions_round_trips(self):
        spec = MemoryHubExtensionSpec.single_demand(description="test")
        extensions = spec.to_agent_card_extensions()
        assert len(extensions) == 1
        assert extensions[0].uri == MemoryHubExtensionSpec.URI


# ---------------------------------------------------------------------------
# Fulfillment serialization (redaction)
# ---------------------------------------------------------------------------


class TestMemoryHubFulfillmentSerialization:
    def test_api_key_redacted_in_default_dump(self):
        f = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("super-secret"))
        dumped = f.model_dump()
        # SecretStr's repr keeps the value behind a wrapper; ensure it isn't leaked as a plain str.
        assert dumped["api_key"] != "super-secret"

    def test_api_key_revealed_with_context(self):
        f = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("super-secret"))
        dumped = f.model_dump(context={REVEAL_SECRETS: True})
        assert dumped["api_key"] == "super-secret"

    def test_client_secret_redacted_in_default_dump(self):
        f = MemoryHubFulfillment(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret=SecretStr("csec"),
        )
        dumped = f.model_dump()
        assert dumped["client_secret"] != "csec"

    def test_client_secret_revealed_with_context(self):
        f = MemoryHubFulfillment(
            url="http://hub",
            auth_url="http://auth",
            client_id="cid",
            client_secret=SecretStr("csec"),
        )
        dumped = f.model_dump(context={REVEAL_SECRETS: True})
        assert dumped["client_secret"] == "csec"


# ---------------------------------------------------------------------------
# Client metadata production
# ---------------------------------------------------------------------------


class TestMemoryHubExtensionClient:
    def test_fulfillment_metadata_reveals_secrets(self):
        spec = MemoryHubExtensionSpec.single_demand()
        client = MemoryHubExtensionClient(spec)
        fulfillment = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("the-key"))

        metadata = client.fulfillment_metadata(memoryhub_fulfillments={"default": fulfillment})

        assert spec.URI in metadata
        payload = metadata[spec.URI]
        assert payload["memoryhub_fulfillments"]["default"]["api_key"] == "the-key"

    def test_fulfillment_metadata_round_trip(self):
        spec = MemoryHubExtensionSpec.single_demand()
        client = MemoryHubExtensionClient(spec)
        fulfillment = MemoryHubFulfillment(url="http://hub", api_key=SecretStr("the-key"))

        metadata = client.fulfillment_metadata(memoryhub_fulfillments={"default": fulfillment})
        # Server side parses MemoryHubExtensionMetadata back from this payload.
        parsed = MemoryHubExtensionMetadata.model_validate(metadata[spec.URI])
        assert "default" in parsed.memoryhub_fulfillments
        assert parsed.memoryhub_fulfillments["default"].url == "http://hub"


# ---------------------------------------------------------------------------
# Env-var fallback
# ---------------------------------------------------------------------------


class TestMemoryHubFulfillmentFromEnv:
    def test_returns_none_when_no_env_vars(self):
        assert _memoryhub_fulfillment_from_env() is None

    def test_returns_none_when_url_only(self):
        os.environ["MEMORYHUB_URL"] = "http://hub"
        assert _memoryhub_fulfillment_from_env() is None

    def test_api_key_path(self):
        os.environ["MEMORYHUB_URL"] = "http://hub"
        os.environ["MEMORYHUB_API_KEY"] = "the-key"

        result = _memoryhub_fulfillment_from_env()
        assert result is not None
        assert result.url == "http://hub"
        assert result.api_key.get_secret_value() == "the-key"
        assert result.client_secret is None

    def test_oauth_path(self):
        os.environ["MEMORYHUB_URL"] = "http://hub"
        os.environ["MEMORYHUB_AUTH_URL"] = "http://auth"
        os.environ["MEMORYHUB_CLIENT_ID"] = "cid"
        os.environ["MEMORYHUB_CLIENT_SECRET"] = "csec"

        result = _memoryhub_fulfillment_from_env()
        assert result is not None
        assert result.url == "http://hub"
        assert result.auth_url == "http://auth"
        assert result.client_id == "cid"
        assert result.client_secret.get_secret_value() == "csec"

    def test_api_key_takes_precedence_over_oauth(self):
        os.environ["MEMORYHUB_URL"] = "http://hub"
        os.environ["MEMORYHUB_API_KEY"] = "the-key"
        os.environ["MEMORYHUB_AUTH_URL"] = "http://auth"
        os.environ["MEMORYHUB_CLIENT_ID"] = "cid"
        os.environ["MEMORYHUB_CLIENT_SECRET"] = "csec"

        result = _memoryhub_fulfillment_from_env()
        assert result is not None
        assert result.api_key.get_secret_value() == "the-key"
        assert result.auth_url is None
        assert result.client_id is None

    def test_returns_none_when_oauth_partial(self):
        os.environ["MEMORYHUB_URL"] = "http://hub"
        os.environ["MEMORYHUB_AUTH_URL"] = "http://auth"
        # missing client_id and client_secret
        assert _memoryhub_fulfillment_from_env() is None


# ---------------------------------------------------------------------------
# Params validation
# ---------------------------------------------------------------------------


class TestMemoryHubExtensionParams:
    def test_empty_demands_allowed(self):
        params = MemoryHubExtensionParams(memoryhub_demands={})
        assert params.memoryhub_demands == {}

    def test_multiple_demands(self):
        params = MemoryHubExtensionParams(
            memoryhub_demands={
                "primary": _demand("primary store"),
                "audit": _demand("audit log"),
            }
        )
        assert set(params.memoryhub_demands) == {"primary", "audit"}


def _demand(description: str):
    from kagenti_adk.a2a.extensions.services.memoryhub import MemoryHubDemand

    return MemoryHubDemand(description=description)
