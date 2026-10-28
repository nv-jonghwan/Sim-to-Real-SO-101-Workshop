#!/bin/bash
set -e

source /root/env 2>/dev/null || true

# Interactive Bash activates from .bashrc so its prompt includes the venv name.
# Activate here for direct, non-Bash container commands.
if [ "$(basename "$1")" != "bash" ]; then
    source "${ISAACLAB_VENV}/bin/activate"
fi

mkdir -p /root/.cache/warp

# Native redirection covers driver shaders; OVRtx also writes derived data and
# application shaders beneath its package cache.
OVRTX_PERSIST_ROOT=/root/.cache/ovrtx
if mountpoint -q "${OVRTX_PERSIST_ROOT}"; then
    readarray -t OVRTX_PATHS < <("${ISAACLAB_VENV}/bin/python" -c \
        "import importlib.metadata, importlib.util, pathlib
version = importlib.metadata.version('ovrtx')
package = pathlib.Path(next(iter(importlib.util.find_spec('ovrtx').submodule_search_locations)))
print(version)
print(package / 'bin/cache')")
    OVRTX_PERSIST="${OVRTX_PERSIST_ROOT}/${OVRTX_PATHS[0]}"
    OVRTX_CACHE="${OVRTX_PATHS[1]}"
    export OVRTX_SHADER_CACHE_PATH="${OVRTX_PERSIST}/driver"
    OVRTX_PACKAGE_CACHE="${OVRTX_PERSIST}/package"
    mkdir -p "${OVRTX_SHADER_CACHE_PATH}" "${OVRTX_PACKAGE_CACHE}"
    if [ -d "${OVRTX_CACHE}" ] && [ ! -L "${OVRTX_CACHE}" ]; then
        cp -an "${OVRTX_CACHE}/." "${OVRTX_PACKAGE_CACHE}/"
        mv "${OVRTX_CACHE}" "${OVRTX_CACHE}.shipped"
        ln -s "${OVRTX_PACKAGE_CACHE}" "${OVRTX_CACHE}"
    fi
else
    mkdir -p "${OVRTX_SHADER_CACHE_PATH}"
fi

# Prefer a live-mounted workshop source tree when one is available.
uv pip install --python "${ISAACLAB_VENV}/bin/python" --no-build-isolation -e \
    /workspace/Sim-to-Real-SO-101-Workshop/source/sim_to_real_so101 >/dev/null 2>&1 || true

exec "$@"
