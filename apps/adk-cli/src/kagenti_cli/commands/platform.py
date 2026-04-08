# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import configparser
import datetime
import functools
import importlib.metadata
import importlib.resources
import json
import os
import pathlib
import platform as platform_module
import shlex
import shutil
import sys
import tempfile
import typing
import uuid
from enum import StrEnum
from subprocess import CompletedProcess
from typing import TypedDict

import anyio
import httpx
import pydantic
import typer
import yaml
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from kagenti_cli.async_typer import AsyncTyper
from kagenti_cli.configuration import Configuration
from kagenti_cli.console import console
from kagenti_cli.utils import get_local_github_token, merge, run_command, verbosity

app = AsyncTyper()
configuration = Configuration()


@functools.cache
def detect_driver() -> typing.Literal["lima", "wsl"]:
    has_lima = (importlib.resources.files("kagenti_cli") / "data" / "bin" / "limactl").is_file() or shutil.which(
        "limactl"
    )
    arch = "aarch64" if platform_module.machine().lower() == "arm64" else platform_module.machine().lower()

    if platform_module.system() == "Windows" or shutil.which("wsl.exe"):
        return "wsl"
    elif has_lima and (
        os.path.exists("/System/Library/Frameworks/Virtualization.framework") or shutil.which(f"qemu-system-{arch}")
    ):
        return "lima"
    else:
        console.error("Could not find a compatible VM runtime.")
        if platform_module.system() == "Darwin":
            console.hint("This version of macOS is unsupported, please update the system.")
        elif platform_module.system() == "Linux":
            if not has_lima:
                console.hint(
                    "This Linux distribution is not suppored by Lima VM binary releases (required: glibc>=2.34). Manually install Lima VM by either:\n"
                    + "  - Your distribution's package manager, if available (https://repology.org/project/lima/versions)\n"
                    + "  - Homebrew for Linux, which uses its own separate glibc (https://brew.sh)\n"
                    + "  - Building it yourself, and ensuring that [green]limactl[/green] is in PATH (https://lima-vm.io/docs/installation/source/)"
                )
            if not shutil.which(f"qemu-system-{arch}"):
                console.hint(
                    f"QEMU is needed on Linux, please install it and ensure that [green]qemu-system-{arch}[/green] is in PATH. Refer to https://www.qemu.org/download/ for instructions."
                )
                console.hint(
                    f"On some distributions (e.g. RHEL) you might need to manually create the symlink: [green]sudo ln -s /usr/libexec/qemu-kvm /usr/bin/qemu-system-{arch}[/green]"
                )
        sys.exit(1)


@functools.cache
def detect_export_import_paths() -> tuple[str, str]:
    if detect_driver() == "lima":
        pathlib.Path("/tmp/kagenti-adk").mkdir(parents=True, exist_ok=True)
        path = f"/tmp/kagenti-adk/{uuid.uuid4()}.tar"
        return (path, path)
    fd, tmp_path = tempfile.mkstemp(suffix=".tar")
    os.close(fd)
    wp = str(pathlib.Path(tmp_path).resolve().absolute())
    return (wp, f"/mnt/{wp[0].lower()}/{wp[2:].replace('\\', '/').removeprefix('/')}")


@functools.cache
def detect_limactl() -> str:
    bundled = importlib.resources.files("kagenti_cli") / "data" / "bin" / "limactl"
    return str(bundled) if bundled.is_file() else str(shutil.which("limactl"))


class LimaVMStatus(TypedDict):
    name: str
    status: str


async def detect_vm_status(vm_name: str) -> typing.Literal["running", "stopped", "missing"]:
    if Configuration().running_inside_vm:
        return "running"
    if detect_driver() == "lima":
        result = await run_command(
            [detect_limactl(), "--tty=false", "list", "--format=json"],
            "Looking for existing Kagenti ADK platform",
            env={"LIMA_HOME": str(Configuration().lima_home)},
            cwd="/",
        )
        for line in result.stdout.decode().split("\n"):
            if line and (status_data := pydantic.TypeAdapter(LimaVMStatus).validate_json(line)).get("name") == vm_name:
                return "running" if status_data["status"].lower() == "running" else "stopped"
    else:
        wsl_env = {"WSL_UTF8": "1", "WSLENV": os.getenv("WSLENV", "") + ":WSL_UTF8"}
        for status, cmd in [("running", ["--running"]), ("stopped", [])]:
            if (
                vm_name
                in (
                    await run_command(
                        ["wsl.exe", "--list", "--quiet", *cmd],
                        f"Looking for {status} Kagenti ADK platform",
                        env=wsl_env,
                    )
                )
                .stdout.decode()
                .splitlines()
            ):
                return typing.cast(typing.Literal["running", "stopped"], status)
    return "missing"


async def run_in_vm(
    vm_name: str,
    command: list[str],
    message: str,
    env: dict[str, str] | None = None,
    input: bytes | None = None,
    check: bool = True,
) -> CompletedProcess[bytes]:
    vm_env = {"KUBECONFIG": "/var/lib/microshift/resources/kubeadmin/kubeconfig", **(env or {})}
    if Configuration().running_inside_vm:
        return await run_command(
            ["sudo", "-E", *command],
            message,
            env=vm_env,
            input=input,
            check=check,
        )
    if detect_driver() == "lima":
        return await run_command(
            [detect_limactl(), "shell", f"--tty={sys.stdin.isatty()}", vm_name, "--", "sudo", "-E", *command],
            message,
            env={"LIMA_HOME": str(Configuration().lima_home)} | vm_env,
            cwd="/",
            input=input,
            check=check,
        )
    return await run_command(
        ["wsl.exe", "--user", "root", "--distribution", vm_name, "--", *command],
        message,
        env={**vm_env, "WSL_UTF8": "1", "WSLENV": "".join("{k}/u" for k in vm_env.keys() | {"WSL_UTF8"})},
        input=input,
        check=check,
    )


def canonify_image_tag(t: str) -> str:
    t = t.strip().strip("'").strip('"').replace(" @", "@")
    if "@" in t:
        base, digest = t.split("@")
        last_colon_idx = base.rfind(":")
        last_slash_idx = base.rfind("/")
        if last_colon_idx > last_slash_idx:
            base = base[:last_colon_idx]
        t = f"{base}@{digest}"
    return t if "." in t.split("/")[0] else f"docker.io/{t}"


async def detect_image_shas(
    vm_name: str,
    loaded_images: set[str],
    *,
    mode: typing.Literal["guest", "host"],
) -> dict[str, str]:
    return {
        canon_tag: sha
        for line in (
            (
                await run_command(["docker", "images", "--digests"], "Listing host images")
                if mode == "host"
                else await run_in_vm(
                    vm_name,
                    ["crictl", "--timeout=30s", "images"],
                    "Listing guest images",
                )
            )
            .stdout.decode()
            .splitlines()[1:]
        )
        if (x := line.split())
        and len(x) >= 3
        and (x[1] != "<none>")
        and (canon_tag := canonify_image_tag(f"{x[0]}:{x[1]}")) in loaded_images
        and (sha := x[2])
    }


class ImagePullMode(StrEnum):
    guest = "guest"
    host = "host"
    hybrid = "hybrid"
    skip = "skip"


CHART_PREFIXES = ("kagenti-deps:", "kagenti:", "kagenti-adk:")


def parse_scoped_set_values(set_values_list: list[str]) -> dict[str, list[str]]:
    """Split --set values by chart prefix. Unprefixed defaults to 'kagenti-adk'."""
    result: dict[str, list[str]] = {"kagenti-adk": [], "kagenti": [], "kagenti-deps": []}
    for value in set_values_list:
        for prefix in CHART_PREFIXES:
            if value.startswith(prefix):
                result[prefix.rstrip(":")].append(value[len(prefix) :])
                break
        else:
            result["kagenti-adk"].append(value)
    return result


@app.command("start", help="Start Kagenti ADK platform. [Local only]")
async def start_cmd(
    set_values_list: typing.Annotated[
        list[str],
        typer.Option(
            "--set",
            help="Set Helm chart values. Prefix with chart name: --set kagenti:key=val, --set kagenti-deps:key=val. Unprefixed applies to kagenti-adk.",
            default_factory=list,
            show_default=False,
        ),
    ],
    image_pull_mode: typing.Annotated[
        ImagePullMode,
        typer.Option(
            "--image-pull-mode",
            help=(
                "guest = pull all images inside VM [default]\n"
                "host = pull unavailable images on host, then import all\n"
                "hybrid = import available images from host, pull the rest in VM\n"
                "skip = skip explicit pull step (Kubernetes will attempt to pull missing images)"
            ),
        ),
    ] = ImagePullMode.guest,
    values_file: typing.Annotated[
        pathlib.Path | None,
        typer.Option(
            "-f",
            help="YAML values file with chart-scoped sections: kagenti-adk:, kagenti:, kagenti-deps:",
        ),
    ] = None,
    lima_image: typing.Annotated[
        str | None, typer.Option("--lima-image", help="Local path or URL to Lima image (.qcow2)")
    ] = None,
    wsl_image: typing.Annotated[
        str | None, typer.Option("--wsl-image", help="Local path or URL to WSL distro image (.wsl)")
    ] = None,
    vm_name: typing.Annotated[str, typer.Option(hidden=True)] = "kagenti-adk",
    verbose: typing.Annotated[bool, typer.Option("-v", "--verbose", help="Show verbose output")] = False,
    skip_login: typing.Annotated[bool, typer.Option(hidden=True)] = False,
    no_wait_for_platform: typing.Annotated[bool, typer.Option(hidden=True)] = False,
):
    import kagenti_cli.commands.server

    if values_file and not await anyio.Path(values_file).is_file():
        raise FileNotFoundError(f"Values file {values_file} not found.")

    # Parse chart-scoped values from -f file and --set flags
    user_values = yaml.safe_load(pathlib.Path(values_file).read_text()) if values_file else {}  # noqa: ASYNC240
    if not isinstance(user_values, dict):
        user_values = {}
    scoped_sets = parse_scoped_set_values(set_values_list)

    with verbosity(verbose):
        version = importlib.metadata.version("kagenti-cli").replace("rc", "-rc")
        arch = "x86_64" if platform_module.machine().lower() in ["x86_64", "amd64"] else "aarch64"
        Configuration().home.mkdir(parents=True, exist_ok=True)
        if Configuration().running_inside_vm:
            console.info("Running inside VM, skipping VM management.")
            await run_command(["sudo", "systemctl", "start", "microshift"], "Starting MicroShift service")
        else:
            match detect_driver():
                case "lima":
                    lima_env = {"LIMA_HOME": str(Configuration().lima_home)}
                    match await detect_vm_status(vm_name):
                        case "missing":
                            for name, label in [(vm_name, "previous"), ("kagenti-platform", "legacy")]:
                                await run_command(
                                    [detect_limactl(), "--tty=false", "delete", "--force", name],
                                    f"Cleaning up remains of {label} instance",
                                    env=lima_env,
                                    check=False,
                                    cwd="/",
                                )
                            import psutil

                            total_memory_gib = psutil.virtual_memory().total // (1024**3)
                            if total_memory_gib < 4:
                                console.error("Not enough memory. Kagenti ADK platform requires at least 4 GB of RAM.")
                                sys.exit(1)
                            if total_memory_gib < 8:
                                console.warning("Less than 8 GB of RAM detected. Performance may be degraded.")

                            current_lima_image = (
                                lima_image
                                or f"https://github.com/kagenti/adk/releases/download/v{version}/microshift-vm-{arch}.qcow2"
                            )
                            if current_lima_image.startswith(("/", "./")):
                                current_lima_image = str(await anyio.Path(current_lima_image).absolute())

                            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete_on_close=False) as f:
                                f.write(
                                    yaml.dump(
                                        {
                                            "images": [
                                                {
                                                    "location": current_lima_image,
                                                    "arch": arch,
                                                },
                                            ],
                                            "portForwards": [
                                                {
                                                    "guestIP": "127.0.0.1",
                                                    "guestPortRange": [1024, 65535],
                                                    "hostPortRange": [1024, 65535],
                                                    "hostIP": "127.0.0.1",
                                                },
                                                {"guestIP": "0.0.0.0", "proto": "any", "ignore": True},
                                            ],
                                            "mounts": [
                                                {
                                                    "location": "/tmp/kagenti-adk",
                                                    "mountPoint": "/tmp/kagenti-adk",
                                                    "writable": True,
                                                }
                                            ],
                                            "mountTypesUnsupported": ["9p"],
                                            "containerd": {"system": False, "user": False},
                                            "hostResolver": {"hosts": {"host.docker.internal": "host.lima.internal"}},
                                            "memory": f"{round(min(8.0, max(3.0, total_memory_gib / 2)))}GiB",
                                        }
                                    )
                                )
                                f.flush()
                                f.close()
                                await run_command(
                                    [detect_limactl(), "--tty=false", "start", f.name, f"--name={vm_name}"],
                                    "Creating a Lima VM",
                                    env=lima_env,
                                    cwd="/",
                                )
                        case "stopped":
                            await run_command(
                                [detect_limactl(), "--tty=false", "start", vm_name],
                                "Starting up",
                                env=lima_env,
                                cwd="/",
                            )
                        case "running":
                            console.info("Updating an existing instance.")
                case "wsl":
                    if (await run_command(["wsl.exe", "--status"], "Checking for WSL2", check=False)).returncode != 0:
                        console.error(
                            "WSL is not installed. Please follow the Kagenti ADK installation instructions: https://kagenti.github.io/adk/stable/introduction/quickstart#windows"
                        )
                        console.hint(
                            "Run [green]wsl.exe --install[/green] as administrator. If you just did this, restart your PC and run the same command again. Full installation may require up to two restarts. WSL is properly set up once you reach a working Linux terminal. You can verify this by running [green]wsl.exe[/green] without arguments."
                        )
                        sys.exit(1)
                    config_file_path = (
                        pathlib.Path.home()
                        if platform_module.system() == "Windows"
                        else pathlib.Path(
                            (
                                await run_command(
                                    ["/bin/sh", "-c", '''wslpath "$(cmd.exe /c 'echo %USERPROFILE%')"'''],
                                    "Detecting home path",
                                )
                            )
                            .stdout.decode()
                            .strip()
                        )
                    ) / ".wslconfig"
                    config_file_path.touch()
                    with config_file_path.open("r+") as f:
                        content = f.read()
                        config = configparser.ConfigParser()
                        config.read_string(content)
                        if not config.has_section("wsl2"):
                            config.add_section("wsl2")
                        wsl2_networking_mode = config.get("wsl2", "networkingMode", fallback=None)
                        if wsl2_networking_mode and wsl2_networking_mode != "nat":
                            config.set("wsl2", "networkingMode", "nat")
                            f.seek(0)
                            f.truncate(0)
                            config.write(f)
                            if platform_module.system() == "Linux":
                                console.warning(
                                    "WSL networking mode updated. Please close WSL, run [green]wsl --shutdown[/green] from PowerShell, re-open WSL and run [green]kagenti-adk platform start[/green] again."
                                )
                                sys.exit(1)
                            await run_command(["wsl.exe", "--shutdown"], "Updating WSL2 networking")
                    Configuration().home.mkdir(parents=True, exist_ok=True)
                    if await detect_vm_status(vm_name) == "missing":
                        await run_command(
                            ["wsl.exe", "--unregister", vm_name],
                            "Cleaning up remains of previous instance",
                            check=False,
                        )
                        await run_command(
                            ["wsl.exe", "--unregister", "kagenti-platform"],
                            "Cleaning up remains of legacy instance",
                            check=False,
                        )

                        current_wsl_image = (
                            wsl_image
                            or f"https://github.com/kagenti/adk/releases/download/v{version}/microshift-vm-{arch}.wsl"
                        )
                        install_dir = Configuration().home / "wsl" / vm_name
                        install_dir.mkdir(parents=True, exist_ok=True)
                        if current_wsl_image.startswith(("http://", "https://")):
                            with tempfile.NamedTemporaryFile(suffix=".wsl", delete=True, delete_on_close=False) as tmp:
                                with console.status("Downloading WSL distribution...", spinner="dots"):
                                    async with httpx.AsyncClient(follow_redirects=True) as client:
                                        async with client.stream("GET", current_wsl_image) as response:
                                            response.raise_for_status()
                                            async for chunk in response.aiter_bytes():
                                                tmp.write(chunk)
                                tmp.close()
                                await run_command(
                                    ["wsl.exe", "--import", vm_name, str(install_dir), tmp.name],
                                    "Importing WSL distribution",
                                )
                        else:
                            await run_command(
                                ["wsl.exe", "--import", vm_name, str(install_dir), current_wsl_image],
                                "Importing WSL distribution",
                            )
                        await run_command(["wsl.exe", "--terminate", vm_name], "Restarting Kagenti ADK VM")
                    await run_in_vm(
                        vm_name,
                        ["/usr/bin/setsid", "-f", "/usr/bin/sleep", "infinity"],
                        "Ensuring persistence of Kagenti ADK VM",
                    )
                    await run_in_vm(
                        vm_name,
                        [
                            "bash",
                            "-c",
                            "echo $(ip route show | grep -i default | cut -d' ' -f3) host.docker.internal >> /etc/hosts",
                        ],
                        "Setting up internal networking",
                    )

        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "until test -f /var/lib/microshift/resources/kubeadmin/kubeconfig; do sleep 5; done && chmod o+x /var/lib/microshift /var/lib/microshift/resources /var/lib/microshift/resources/kubeadmin && chmod o+r /var/lib/microshift/resources/kubeadmin/kubeconfig",
            ],
            "Waiting for kubeconfig",
        )
        kubeconfig_local = anyio.Path(Configuration().lima_home / vm_name / "copied-from-guest" / "kubeconfig.yaml")
        await kubeconfig_local.parent.mkdir(parents=True, exist_ok=True)
        await kubeconfig_local.write_text(
            (
                await run_in_vm(
                    vm_name,
                    ["cat", "/var/lib/microshift/resources/kubeadmin/kubeconfig"],
                    "Copying kubeconfig from Kagenti ADK platform",
                )
            ).stdout.decode()
        )
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                'command -v helm && exit 0; case $(uname -m) in x86_64) ARCH="amd64" ;; aarch64) ARCH="arm64" ;; esac; curl -fsSL "https://get.helm.sh/helm-v4.1.1-linux-${ARCH}.tar.gz" | tar -xzf - --strip-components=1 -C /usr/local/bin "linux-${ARCH}/helm"; chmod +x /usr/local/bin/helm',
            ],
            "Installing Helm",
        )
        # --- Prepare kagenti-adk chart and import images before any deployments ---
        await run_in_vm(
            vm_name,
            ["bash", "-c", "cat >/tmp/kagenti-adk-chart.tgz"],
            "Preparing Helm chart",
            input=(importlib.resources.files("kagenti_cli") / "data" / "helm-chart.tgz").read_bytes(),
        )
        await run_in_vm(
            vm_name,
            ["bash", "-c", "cat >/tmp/kagenti-adk-values.yaml"],
            "Preparing Helm values",
            input=yaml.dump(
                merge(
                    {
                        "encryptionKey": "Ovx8qImylfooq4-HNwOzKKDcXLZCB3c_m0JlB9eJBxc=",
                        "trustProxyHeaders": True,
                        "localStorage": True,
                        "gateway": {"enabled": True, "parentRef": {"name": "http", "namespace": "kagenti-system"}},
                        "auth": {
                            "enabled": True,
                            "keycloakProvisionJob": {
                                "enabled": True,
                                "adminUser": "admin",
                                "adminPassword": "admin",
                                "seedUsers": [
                                    {
                                        "username": "admin",
                                        "password": "admin",
                                        "firstName": "Admin",
                                        "lastName": "User",
                                        "email": "admin@beeai.dev",
                                        "roles": ["adk-admin", "kagenti-admin"],
                                        "enabled": True,
                                    }
                                ],
                            },
                            "validateAudience": False,
                            "nextauthUrl": "http://adk.localtest.me:8080",
                            "apiUrl": "http://adk-api.localtest.me:8080",
                            "oidcProvider": {
                                "issuerUrl": "http://keycloak-service.keycloak:8080/realms/adk",
                                "publicIssuerUrl": "http://keycloak.localtest.me:8080/realms/adk",
                                "name": "Keycloak",
                                "id": "keycloak",
                                "rolesPath": "realm_access.roles",
                                "uiClientId": "adk-ui",
                                "uiClientSecret": "adk-ui-secret",
                                "serverClientId": "adk-server",
                                "serverClientSecret": "adk-server-secret",
                            },
                        },
                        "exampleAgent": {"enabled": True},
                        "features": {"uiLocalSetup": True},
                        "providerBuilds": {"enabled": True},
                        "disableProviderDownscaling": True,
                        "server": {
                            "cors": {
                                "enabled": True,
                                "allowOriginRegex": r"https?://(localhost|127\.0\.0\.1|[a-z0-9.-]*\.?localtest\.me)(:\d+)?",
                                "allowCredentials": True,
                            },
                        },
                    },
                    user_values.get("kagenti-adk", {}),
                )
            ).encode("utf-8"),
        )
        # --- Prepare kagenti chart values and version before image listing ---
        kagenti_chart_version = "0.6.0-alpha.2"
        kagenti_deps_values = yaml.dump(
            merge(
                {
                    "openshift": False,
                    "components": {
                        "keycloak": {"enabled": True},
                        "istio": {"enabled": False},
                        "kiali": {"enabled": False},
                        "mcpInspector": {"enabled": False},
                        "otel": {"enabled": False},
                        "mlflow": {"enabled": False},
                        "containerRegistry": {"enabled": True},
                        "spire": {"enabled": False},
                        "tekton": {"enabled": False},
                        "shipwright": {"enabled": False},
                        "certManager": {"enabled": False},
                        "gatewayApi": {"enabled": False},
                        "metricsServer": {"enabled": False},
                        "ingressGateway": {"enabled": True},
                    },
                    "keycloak": {
                        "namespace": "keycloak",
                        "auth": {"adminUser": "admin", "adminPassword": "admin"},
                        "url": "http://keycloak-service.keycloak:8080",
                        "publicUrl": "http://keycloak.localtest.me:8080",
                        "extraEnvVars": [
                            {"name": "KC_HOSTNAME_BACKCHANNEL_DYNAMIC", "value": "true"},
                        ],
                    },
                    "phoenix": {
                        "database": {"type": "sqlite"},
                    },
                    "containerRegistry": {
                        "service": {"type": "NodePort", "nodePort": 30500},
                    },
                },
                user_values.get("kagenti-deps", {}),
            )
        )
        kagenti_values = yaml.dump(
            merge(
                {
                    "openshift": False,
                    "components": {
                        "agentOperator": {"enabled": False},
                        "platformWebhook": {"enabled": False},
                        "agentNamespaces": {"enabled": True},
                        "ui": {"enabled": True},
                        "mcpGateway": {"enabled": False},
                        "istio": {"enabled": False},
                    },
                    "agentNamespaces": ["team1"],
                    "keycloak": {
                        "enabled": True,
                        "namespace": "keycloak",
                        "url": "http://keycloak-service.keycloak:8080",
                        "publicUrl": "http://keycloak.localtest.me:8080",
                        "realm": "adk",
                        "autoBootstrapRealm": False,
                        "adminSecretName": "keycloak-initial-admin",
                        "adminUsernameKey": "username",
                        "adminPasswordKey": "password",
                    },
                    "ui": {
                        "auth": {"enabled": True},
                        "namespace": "kagenti-system",
                        "domainName": "localtest.me",
                        "hostname": "kagenti-ui.localtest.me",
                        "url": "http://kagenti-ui.localtest.me:8080",
                        "api": {"hostname": "kagenti-api.localtest.me"},
                    },
                    "apiOAuthSecret": {"enabled": True},
                    "spire": {"enabled": False},
                },
                user_values.get("kagenti", {}),
            )
        )
        for name, content in [("kagenti-deps", kagenti_deps_values), ("kagenti", kagenti_values)]:
            await run_in_vm(
                vm_name,
                ["bash", "-c", f"cat >/tmp/{name}-values.yaml"],
                f"Preparing {name} values",
                input=content.encode("utf-8"),
            )
        # List images from all charts (kagenti-adk + kagenti + kagenti-deps)
        helm_template_cmds = "; ".join(
            f"helm template {name} {src}"
            + (f" --version={kagenti_chart_version}" if ver else "")
            + f" --values=/tmp/{name}-values.yaml"
            + (" " + " ".join(shlex.quote(f"--set={v}") for v in scoped_sets[name]) if scoped_sets[name] else "")
            for name, src, ver in [
                ("kagenti-adk", "/tmp/kagenti-adk-chart.tgz", False),
                ("kagenti-deps", "oci://ghcr.io/kagenti/kagenti/kagenti-deps", True),
                ("kagenti", "oci://ghcr.io/kagenti/kagenti/kagenti", True),
            ]
        )
        loaded_images = {
            canonify_image_tag(typing.cast(str, yaml.safe_load(line)))
            for line in (
                await run_in_vm(
                    vm_name,
                    [
                        "/bin/bash",
                        "-c",
                        "{ " + helm_template_cmds + r"; } | sed -n '/^\s*image:/{ /{{/!{ s/.*image:\s*//p } }'",
                    ],
                    "Listing necessary images",
                )
            )
            .stdout.decode()
            .splitlines()
        }
        images_to_import_from_host: set[str] = set()
        shas_guest_before: dict[str, str] = {}
        if image_pull_mode in {ImagePullMode.host, ImagePullMode.hybrid}:
            await run_in_vm(
                vm_name,
                ["timeout", "2m", "bash", "-c", "until crictl info >/dev/null 2>&1; do sleep 2; done"],
                "Waiting for CRI-O to be ready",
            )
            shas_guest_before = await detect_image_shas(vm_name, loaded_images, mode="guest")
            shas_host = await detect_image_shas(vm_name, loaded_images, mode="host")
            if image_pull_mode == ImagePullMode.host:
                for image in loaded_images - shas_host.keys():
                    await run_command(["docker", "pull", image], f"Pulling image {image} on host")
                shas_host = await detect_image_shas(vm_name, loaded_images, mode="host")
            images_to_import_from_host = dict(shas_host.items() - shas_guest_before.items()).keys() & loaded_images
            if images_to_import_from_host:
                host_path, guest_path = detect_export_import_paths()
                try:
                    await run_command(
                        ["docker", "image", "save", "-o", host_path, *images_to_import_from_host],
                        f"Exporting image{'' if len(images_to_import_from_host) == 1 else 's'} {', '.join(images_to_import_from_host)} from Docker",
                    )
                    await run_in_vm(
                        vm_name,
                        [
                            "bash",
                            "-c",
                            "\n".join(
                                f"skopeo copy docker-archive:{guest_path}:{img} containers-storage:{img} &"
                                for img in images_to_import_from_host
                            )
                            + "\nwait",
                        ],
                        f"Importing image{'' if len(images_to_import_from_host) == 1 else 's'} {', '.join(images_to_import_from_host)} into Kagenti ADK platform",
                    )
                finally:
                    await anyio.Path(host_path).unlink(missing_ok=True)
        if image_pull_mode in {ImagePullMode.guest, ImagePullMode.hybrid}:
            github_token = get_local_github_token()
            for image in loaded_images - images_to_import_from_host:
                await run_in_vm(
                    vm_name,
                    [
                        "skopeo",
                        "copy",
                        *(
                            ["--src-username", "x-access-token", "--src-password", github_token]
                            if github_token and image.startswith("ghcr.io/")
                            else []
                        ),
                        f"docker://{image}",
                        f"containers-storage:{image}",
                    ],
                    f"Pulling image {image}",
                    env={"GITHUB_TOKEN": github_token} if github_token and image.startswith("ghcr.io/") else None,
                )

        # --- Kagenti platform installation ---
        await run_in_vm(
            vm_name,
            [
                "kubectl",
                "apply",
                "-f",
                "https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml",
            ],
            "Installing kagenti prerequisites (Gateway API CRDs)",
        )
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "V=1.28.0; "
                "helm repo add istio https://istio-release.storage.googleapis.com/charts/ 2>/dev/null || true; helm repo update istio; "
                "kubectl create namespace istio-system --dry-run=client -o yaml | kubectl apply -f -; "
                "helm upgrade --install istio-base istio/base --version=$V --namespace=istio-system --wait --force-conflicts; "
                "helm upgrade --install istiod istio/istiod --version=$V --namespace=istio-system --wait --force-conflicts "
                "--set pilot.resources.requests.cpu=50m --set pilot.resources.requests.memory=256Mi",
            ],
            "Installing Istio (Gateway API controller)",
        )
        phoenix_enabled = any("components.otel.enabled=true" in v.lower() for v in scoped_sets.get("kagenti-deps", []))
        await run_in_vm(
            vm_name,
            [
                "helm",
                "upgrade",
                "--install",
                "kagenti-deps",
                "oci://ghcr.io/kagenti/kagenti/kagenti-deps",
                f"--version={kagenti_chart_version}",
                "--namespace=kagenti-system",
                "--create-namespace",
                "--values=/tmp/kagenti-deps-values.yaml",
                "--timeout=10m",
                "--force-conflicts",
                *(f"--set={v}" for v in scoped_sets["kagenti-deps"]),
            ],
            "Installing kagenti dependencies (Keycloak)",
        )
        # Fix keycloak postgres data dir ownership to match MicroShift's SCC-assigned UID.
        # The postgres:17 image requires the process to own its data dir for initdb chmod.
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "UID_RANGE=$(kubectl get namespace keycloak -o jsonpath='{.metadata.annotations.openshift\\.io/sa\\.scc\\.uid-range}') && "
                "BASE_UID=${UID_RANGE%%/*} && "
                'chown -R "$BASE_UID:$BASE_UID" /kagenti-keycloak-postgres-data && '
                "chmod 700 /kagenti-keycloak-postgres-data && "
                "kubectl delete pod -n keycloak postgres-0 --ignore-not-found",
            ],
            "Fixing keycloak postgres data directory ownership",
        )
        # Label namespaces for shared gateway access and create otel-collector route
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "kubectl create namespace kagenti-adk --dry-run=client -o yaml | kubectl apply -f - && "
                "for ns in kagenti-adk keycloak kagenti-system istio-system; do kubectl label namespace $ns shared-gateway-access=true --overwrite; done && "
                "kubectl apply -f - <<'EOF'\n"
                "apiVersion: gateway.networking.k8s.io/v1\n"
                "kind: HTTPRoute\n"
                "metadata:\n"
                "  name: otel-collector\n"
                "  namespace: kagenti-system\n"
                "spec:\n"
                "  parentRefs:\n"
                "    - name: http\n"
                "      namespace: kagenti-system\n"
                "  hostnames:\n"
                '    - "otel-collector.localtest.me"\n'
                "  rules:\n"
                "    - backendRefs:\n"
                "        - name: otel-collector\n"
                "          port: 8335\n"
                "EOF",
            ],
            "Configuring gateway routes",
        )

        # --- Kagenti ADK helm install ---
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "timeout 5m bash -c 'until kubectl get nodes --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | grep -q .; do sleep 5; done' && "
                "kubectl get nodes --no-headers -o custom-columns=NAME:.metadata.name | xargs -I {} sh -c \"grep -q '{}' /etc/hosts || echo '127.0.0.1 {}' >> /etc/hosts\"",
            ],
            "Ensuring node name resolution",
        )
        await run_in_vm(
            vm_name,
            [
                "helm",
                "upgrade",
                "--install",
                "kagenti-adk",
                "/tmp/kagenti-adk-chart.tgz",
                "--namespace=kagenti-adk",
                "--create-namespace",
                "--values=/tmp/kagenti-adk-values.yaml",
                "--timeout=20m",
                "--wait",
                *(f"--set={v}" for v in scoped_sets["kagenti-adk"]),
            ],
            "Deploying Kagenti ADK platform with Helm",
        )
        await run_in_vm(
            vm_name,
            [
                "helm",
                "upgrade",
                "--install",
                "kagenti",
                "oci://ghcr.io/kagenti/kagenti/kagenti",
                f"--version={kagenti_chart_version}",
                "--namespace=kagenti-system",
                "--create-namespace",
                "--values=/tmp/kagenti-values.yaml",
                "--timeout=10m",
                *(f"--set={v}" for v in scoped_sets["kagenti"]),
            ],
            "Installing kagenti platform (operator + backend)",
        )
        if shas_guest_before:
            replaced_digests = set(shas_guest_before.values()) - set(
                (await detect_image_shas(vm_name, loaded_images, mode="guest")).values()
            )
            if replaced_digests:
                pods = json.loads(
                    (
                        await run_in_vm(
                            vm_name, ["kubectl", "get", "pods", "-o", "json", "--all-namespaces"], "Getting pods"
                        )
                    ).stdout
                )
                for pod in pods.get("items", []):
                    if any(
                        cs.get("imageID", "") in replaced_digests
                        for cs in pod.get("status", {}).get("containerStatuses", [])
                    ):
                        ns, name = pod["metadata"]["namespace"], pod["metadata"]["name"]
                        await run_in_vm(
                            vm_name,
                            ["kubectl", "delete", "pod", name, "-n", ns],
                            f"Removing pod with obsolete image {ns}/{name}",
                        )
        await run_in_vm(
            vm_name,
            [
                "timeout",
                "5m",
                "bash",
                "-c",
                "until kubectl wait --for=condition=Ready pod -n openshift-dns -l dns.operator.openshift.io/daemonset-dns=default --timeout=2m; do sleep 5; done",
            ],
            "Waiting for DNS to be ready",
        )
        await run_in_vm(
            vm_name,
            [
                "bash",
                "-euxc",
                'systemctl daemon-reload; systemctl start "kubectl-port-forward@kagenti-system:http-istio:8080:80" & systemctl start "kubectl-port-forward@kagenti-system:otel-collector:4318" &',
            ],
            "Forwarding VM services to host",
        )

        if not no_wait_for_platform:
            with console.status("Waiting for Kagenti ADK platform to be ready...", spinner="dots"):
                async with httpx.AsyncClient() as client:
                    try:
                        async for attempt in AsyncRetrying(
                            stop=stop_after_delay(datetime.timedelta(minutes=20)),
                            wait=wait_fixed(datetime.timedelta(seconds=1)),
                            retry=retry_if_exception_type((httpx.HTTPError, ConnectionError)),
                            reraise=True,
                        ):
                            with attempt:
                                (await client.get("http://adk-api.localtest.me:8080/healthcheck")).raise_for_status()
                    except Exception as ex:
                        raise ConnectionError(
                            "Server did not start in 20 minutes. Please check your internet connection."
                        ) from ex

        await run_in_vm(
            vm_name,
            [
                "bash",
                "-c",
                "kubectl wait --for=condition=Complete job/keycloak-provision -n kagenti-adk --timeout=300s",
            ],
            "Waiting for Keycloak provisioning to complete",
        )
        console.success("Kagenti ADK platform started successfully!")
        if phoenix_enabled:
            console.print(
                "\nLicense Notice:\nPhoenix (provided by kagenti) is licensed under the Elastic License v2 (ELv2),\n"
                "which has specific terms regarding commercial use and distribution. By using this platform,\n"
                "you acknowledge compliance with the ELv2 license terms.\n"
                "See: https://github.com/Arize-ai/phoenix/blob/main/LICENSE\n",
                style="dim",
            )

        if not skip_login:
            await kagenti_cli.commands.server.server_login("http://adk-api.localtest.me:8080")


@app.command("stop", help="Stop Kagenti ADK platform. [Local only]")
async def stop_cmd(
    vm_name: typing.Annotated[str, typer.Option(hidden=True)] = "kagenti-adk",
    verbose: typing.Annotated[bool, typer.Option("-v", "--verbose", help="Show verbose output")] = False,
):
    with verbosity(verbose):
        if Configuration().running_inside_vm:
            await run_command(
                ["sudo", "bash", "-c", "systemctl stop 'kubectl-port-forward@*'"],
                "Stopping port-forwarding services",
                check=False,
            )
            await run_command(
                ["sudo", "systemctl", "stop", "microshift"],
                "Stopping MicroShift service",
            )
            console.success("Kagenti ADK platform stopped successfully.")
            return
        if await detect_vm_status(vm_name) == "missing":
            console.info("Kagenti ADK platform not found. Nothing to stop.")
            return
        if detect_driver() == "lima":
            await run_command(
                [detect_limactl(), "--tty=false", "stop", "--force", vm_name],
                "Stopping Kagenti ADK VM",
                env={"LIMA_HOME": str(Configuration().lima_home)},
                cwd="/",
            )
        else:
            await run_command(["wsl.exe", "--terminate", vm_name], "Stopping Kagenti ADK VM")
        console.success("Kagenti ADK platform stopped successfully.")


@app.command("delete", help="Delete Kagenti ADK platform. [Local only]")
async def delete_cmd(
    vm_name: typing.Annotated[str, typer.Option(hidden=True)] = "kagenti-adk",
    verbose: typing.Annotated[bool, typer.Option("-v", "--verbose", help="Show verbose output")] = False,
):
    with verbosity(verbose):
        if Configuration().running_inside_vm:
            await run_command(
                ["sudo", "bash", "-c", "systemctl stop 'kubectl-port-forward@*'"],
                "Stopping port-forwarding services",
                check=False,
            )
            await run_command(
                ["sudo", "systemctl", "stop", "microshift"],
                "Stopping MicroShift service",
                check=False,
            )
            await run_command(
                ["sudo", "bash", "-c", "rm -rf /var/lib/microshift/*"],
                "Removing MicroShift data",
            )
            console.success("Kagenti ADK platform deleted successfully.")
            return
        if detect_driver() == "lima":
            await run_command(
                [detect_limactl(), "--tty=false", "delete", "--force", vm_name],
                "Deleting Kagenti ADK platform",
                env={"LIMA_HOME": str(Configuration().lima_home)},
                check=False,
                cwd="/",
            )
        else:
            await run_command(["wsl.exe", "--unregister", vm_name], "Deleting Kagenti ADK platform", check=False)
        console.success("Kagenti ADK platform deleted successfully.")


@app.command("import", help="Import a local docker image into the Kagenti ADK platform. [Local only]")
async def import_cmd(
    tag: typing.Annotated[str, typer.Argument(help="Docker image tag to import")],
    vm_name: typing.Annotated[str, typer.Option(hidden=True)] = "kagenti-adk",
    verbose: typing.Annotated[bool, typer.Option("-v", "--verbose", help="Show verbose output")] = False,
):
    with verbosity(verbose):
        if (await detect_vm_status(vm_name)) != "running":
            console.error("Kagenti ADK platform is not running.")
            sys.exit(1)
        if Configuration().running_inside_vm:
            console.info("Running inside VM — images are already available to CRI-O via shared storage.")
            return
        host_path, guest_path = detect_export_import_paths()
        try:
            await run_command(["docker", "image", "save", "-o", host_path, tag], f"Exporting image {tag} from Docker")
            await run_in_vm(
                vm_name,
                ["skopeo", "copy", f"docker-archive:{guest_path}:{tag}", f"containers-storage:{tag}"],
                f"Importing image {tag} into Kagenti ADK platform",
            )
        finally:
            await anyio.Path(host_path).unlink(missing_ok=True)


@app.command("exec", help="For debugging -- execute a command inside the Kagenti ADK platform VM. [Local only]")
async def exec_cmd(
    command: typing.Annotated[list[str] | None, typer.Argument()] = None,
    vm_name: typing.Annotated[str, typer.Option(hidden=True)] = "kagenti-adk",
    verbose: typing.Annotated[bool, typer.Option("-v", "--verbose", help="Show verbose output")] = False,
):
    with verbosity(verbose, show_success_status=False):
        if (await detect_vm_status(vm_name)) != "running":
            console.error("Kagenti ADK platform is not running.")
            sys.exit(1)
        if Configuration().running_inside_vm:
            await anyio.run_process(
                ["sudo", *(command or ["/bin/bash"])],
                check=False,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        elif detect_driver() == "lima":
            await anyio.run_process(
                [
                    detect_limactl(),
                    "shell",
                    f"--tty={sys.stdin.isatty()}",
                    vm_name,
                    "--",
                    "sudo",
                    *(command or ["/bin/bash"]),
                ],
                check=False,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                env={**os.environ, "LIMA_HOME": str(Configuration().lima_home)},
                cwd="/",
            )
        else:
            await anyio.run_process(
                ["wsl.exe", "--user", "root", "--distribution", vm_name, "--", *(command or ["/bin/bash"])],
                check=False,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                cwd="/",
            )
