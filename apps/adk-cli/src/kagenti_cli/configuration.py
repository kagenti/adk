# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import contextlib
import functools
import importlib.metadata
import pathlib
import re
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import pydantic
import pydantic_settings
from kagenti_adk.platform import PlatformClient, use_platform_client
from pydantic import SecretStr

from kagenti_cli.auth_manager import AuthManager
from kagenti_cli.console import console


def _is_connect_error(exc: BaseException) -> bool:
    """Check if an exception (or its chain) indicates a connection failure."""
    while exc is not None:
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError, OSError)):
            return True
        exc = exc.__cause__  # type: ignore[assignment]
    return False


@functools.cache
def version():
    # Python strips '-', we need to re-insert it: 1.2.3rc1 -> 1.2.3-rc1
    return re.sub(r"([0-9])([a-z])", r"\1-\2", importlib.metadata.version("kagenti-cli"))


@functools.cache
class Configuration(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_file=None, env_prefix="KAGENTI_ADK_", env_nested_delimiter="__", extra="allow"
    )
    debug: bool = False
    home: pathlib.Path = pydantic.Field(default_factory=lambda: pathlib.Path.home() / ".kagenti" / "adk")
    username: str = "admin"
    password: SecretStr | None = None
    server_metadata_ttl: int = 86400

    kagenti_url: str = "http://kagenti-api.localtest.me:8080"

    running_inside_vm: bool = pydantic.Field(default_factory=lambda: pathlib.Path("/etc/adk").exists())

    oidc_enabled: bool = False
    client_id: str | None = None
    client_secret: str | None = None

    @property
    def lima_home(self) -> pathlib.Path:
        return self.home / "lima"

    @property
    def auth_file(self) -> pathlib.Path:
        """Return auth config file path"""
        return self.home / "auth.json"

    @property
    def auth_manager(self) -> AuthManager:
        return AuthManager(self.auth_file)

    @asynccontextmanager
    async def use_platform_client(self) -> AsyncGenerator[PlatformClient]:
        if self.auth_manager.active_server is None:
            console.error("No server selected.")
            console.hint(
                "Run [green]kagenti-adk platform start[/green] to start a local server, or [green]kagenti-adk server login[/green] to connect to a remote one."
            )
            sys.exit(1)

        auth_token = None
        try:
            auth_token = await self.auth_manager.load_auth_token()
        except Exception as e:
            if _is_connect_error(e):
                console.error(f"Cannot connect to server: {self.auth_manager.active_server}")
                console.hint(
                    "Start the Kagenti ADK platform using: [green]kagenti-adk platform start[/green]. "
                    "If that does not help, run [green]kagenti-adk platform delete[/green] to clean up, "
                    "then [green]kagenti-adk platform start[/green] again."
                )
                sys.exit(1)
            # Auto-recover for local dev by re-authenticating with admin:admin
            if self.auth_manager.active_server and "adk-api.localtest.me" in self.auth_manager.active_server:
                with contextlib.suppress(Exception):
                    auth_token = await self.auth_manager.login_with_password(
                        self.auth_manager.active_server, username="admin", password="admin"
                    )
            if not auth_token:
                console.error(f"Failed to load authentication: {e}")
                console.hint(
                    f"Run [green]kagenti-adk server login {self.auth_manager.active_server}[/green] to re-authenticate."
                )
                sys.exit(1)

        async with use_platform_client(
            auth=(self.username, self.password.get_secret_value()) if self.password else None,
            auth_token=auth_token.access_token if auth_token else None,
            base_url=(self.auth_manager.active_server or "") + "/",
        ) as client:
            yield client
