#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION="3.13"
if [[ -f ".python-version" ]]; then
  PYTHON_VERSION="$(tr -d '[:space:]' < .python-version)"
fi

UV_BIN=""

probe_uv_candidate() {
  local candidate="${1:-}"
  [[ -n "$candidate" ]] || return 1

  if "$candidate" --version >/dev/null 2>&1; then
    UV_BIN="$candidate"
    return 0
  fi

  return 1
}

find_uv() {
  local userprofile_posix=""
  local candidates=()

  if command -v uv >/dev/null 2>&1; then
    candidates+=("$(command -v uv)")
  fi

  if command -v uv.exe >/dev/null 2>&1; then
    candidates+=("$(command -v uv.exe)")
  fi

  candidates+=(
    "$HOME/.local/bin/uv"
    "$HOME/.local/bin/uv.exe"
    "$HOME/.cargo/bin/uv"
    "$HOME/.cargo/bin/uv.exe"
  )

  if [[ -n "${USERPROFILE:-}" ]] && command -v cygpath >/dev/null 2>&1; then
    userprofile_posix="$(cygpath "$USERPROFILE")"
    candidates+=(
      "$userprofile_posix/.local/bin/uv.exe"
      "$userprofile_posix/.cargo/bin/uv.exe"
    )
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if probe_uv_candidate "$candidate"; then
      return 0
    fi
  done

  return 1
}

ensure_uv() {
  if find_uv; then
    return 0
  fi

  echo "uv not found. Installing via the official installer..."

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "[ERROR] curl or wget is required to install uv." >&2
    return 1
  fi

  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if [[ -n "${USERPROFILE:-}" ]] && command -v cygpath >/dev/null 2>&1; then
    userprofile_posix="$(cygpath "$USERPROFILE")"
    export PATH="$userprofile_posix/.local/bin:$userprofile_posix/.cargo/bin:$PATH"
  fi

  if find_uv; then
    return 0
  fi

  echo "[ERROR] uv was installed but could not be located in this shell." >&2
  echo "Add \$HOME/.local/bin to PATH or open a new terminal, then rerun install-adapter.sh." >&2
  return 1
}

ensure_uv

echo "Installing codex-openai-adapter"
echo "Working directory: $PWD"
echo "Using uv: $UV_BIN"
echo "Python version: $PYTHON_VERSION"
echo

"$UV_BIN" python install "$PYTHON_VERSION"
if [[ -x ".venv/bin/python" ]]; then
  echo "Reusing existing .venv"
elif [[ -d ".venv" ]]; then
  echo "Existing .venv is incompatible with this platform. Recreating..."
  rm -rf .venv
  "$UV_BIN" venv --python "$PYTHON_VERSION" .venv
else
  "$UV_BIN" venv --python "$PYTHON_VERSION" .venv
fi

if [[ -f "uv.lock" ]]; then
  echo "Syncing dependencies from uv.lock with dev extras..."
  if ! "$UV_BIN" sync --frozen --extra dev; then
    echo "Frozen sync failed. Retrying with a normal sync..."
    "$UV_BIN" sync --extra dev
  fi
else
  echo "Syncing dependencies from pyproject.toml with dev extras..."
  "$UV_BIN" sync --extra dev
fi

echo
echo "Installation complete."
echo "Start the adapter with:"
echo "  ./run-adapter.sh"
