#!/bin/sh
set -eu

# Configurable through env vars:
# KAGENTI_ADK_VERSION = latest (default, latest stable version) | pre (latest version including prereleases) | <version> (specific version)

# These get updated by `mise release`:
LATEST_STABLE_KAGENTI_ADK_VERSION=0.8.1
LATEST_KAGENTI_ADK_VERSION=0.8.1

case "${KAGENTI_ADK_VERSION:-latest}" in "latest") KAGENTI_ADK_VERSION=$LATEST_STABLE_KAGENTI_ADK_VERSION ;; "pre") KAGENTI_ADK_VERSION=$LATEST_KAGENTI_ADK_VERSION ;; esac

# This gets updated by Renovate:
# renovate: datasource=python-version depName=python
PYTHON_VERSION=3.14

error() {
    printf "\n💥 \033[31mERROR:\033[0m: Kagenti ADK CLI installation has failed. Please report the above error: https://github.com/kagenti/adk/issues\n" >&2
    exit 1
}

echo "Starting the Kagenti ADK installer..."

# Check if running as root (not supported)
if [ "$(id -u)" = "0" ]; then
    printf "\n💥 \033[31mERROR:\033[0m: Kagenti ADK CLI should not be installed as root. Please run as a regular user.\n" >&2
    exit 1
fi

# Check if this is WSL (not supported)
if [ -n "${WSL_DISTRO_NAME-}" ] || (uname -r | grep -q -i "microsoft"); then
    printf "\n💥 \033[31mERROR:\033[0m: Kagenti ADK CLI is not supported on WSL. Please follow the Windows installation instructions to install in PowerShell instead.\n" >&2
    exit 1
fi

# Ensure that we have uv on PATH
export PATH="${XDG_BIN_HOME:+${XDG_BIN_HOME}:}${XDG_DATA_HOME:+$(realpath -m ${XDG_DATA_HOME}/../bin):}${HOME:+${HOME}/.local/bin:}$PATH"

# Always install uv to ensure we have the latest version for consistency
echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | UV_PRINT_QUIET=1 sh || error

# Install a uv-managed Python version (uv should do that automatically but better be explicit)
# --no-bin to avoid putting it in PATH (not necessary)
echo "Installing Python..."
uv python install --quiet --python-preference=only-managed --no-bin $PYTHON_VERSION || error

# Separately uninstall potential old versions to remove envs created with wrong Python versions
# Also remove obsolete version from Homebrew and any local executables potentially left behind by Homebrew or old uv versions
echo "Removing old versions..."
uv tool uninstall --quiet kagenti-cli >/dev/null 2>&1 || true

# Install kagenti-adk using a uv-managed Python version
# We set the version to error out on platforms incompatible with the latest version
# It also avoids accidentally installing prereleases of dependencies by only allowing explicitly set ones
echo "Installing Kagenti ADK CLI..."
uv tool install --quiet --python-preference=only-managed --python=$PYTHON_VERSION --refresh --prerelease allow --with "kagenti-adk==$KAGENTI_ADK_VERSION" "kagenti-cli==$KAGENTI_ADK_VERSION" --force || error

# Finish set up using CLI (install QEMU on Linux, start platform, set up API keys, run UI, ...)
kagenti-adk self install
