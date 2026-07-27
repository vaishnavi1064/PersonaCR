#!/usr/bin/env bash
# Smoke test to verify clean install of PersonaCR backend dependencies.

set -euo pipefail

# Ensure we are in the workspace root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_DIR"

TEMP_VENV_NAME="temp_smoke_venv"

echo "=== PersonaCR Smoke Test ==="
echo "Workspace: $WORKSPACE_DIR"
echo "Temp virtualenv: $TEMP_VENV_NAME"

# Cleanup function to tear down the temp venv at the end
cleanup() {
    echo "=== Cleaning up ==="
    if [ -d "$TEMP_VENV_NAME" ]; then
        echo "Removing temp virtualenv..."
        rm -rf "$TEMP_VENV_NAME"
    fi
}
trap cleanup EXIT

# Prefer `python` (setup-python on GHA) with `python3` fallback.
if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    echo "Error: neither python nor python3 found on PATH." >&2
    exit 1
fi
echo "Using interpreter: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"

# 1. Create a throwaway virtual environment
echo "Creating virtual environment..."
"$PYTHON_BIN" -m venv "$TEMP_VENV_NAME"

# 2. Activate virtual environment
if [ -f "$TEMP_VENV_NAME/Scripts/activate" ]; then
    echo "Activating virtualenv (Windows structure)..."
    # shellcheck source=/dev/null
    source "$TEMP_VENV_NAME/Scripts/activate"
elif [ -f "$TEMP_VENV_NAME/bin/activate" ]; then
    echo "Activating virtualenv (Unix structure)..."
    # shellcheck source=/dev/null
    source "$TEMP_VENV_NAME/bin/activate"
else
    echo "Error: Could not find virtualenv activation script." >&2
    exit 1
fi

# 3. Install requirements
echo "Installing requirements from backend/requirements.txt..."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

# Repo uses `backend.src.*` imports with workspace root on PYTHONPATH (see pytest.ini).
export PYTHONPATH="$WORKSPACE_DIR${PYTHONPATH:+:$PYTHONPATH}"

# 4. Run python import check for the specified modules
echo "Running import checks (PYTHONPATH=$PYTHONPATH)..."
python -c "
import sys
try:
    import backend.src.evaluation.sts_scorer
    print('SUCCESS: Imported backend.src.evaluation.sts_scorer')
    import backend.src.core.embedder
    print('SUCCESS: Imported backend.src.core.embedder')
    import backend.src.main
    print('SUCCESS: Imported backend.src.main')
except ImportError as e:
    print(f'FAILURE: Import failed: {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'FAILURE: Unexpected error during import check: {e}', file=sys.stderr)
    sys.exit(1)
"

echo "=== Smoke Test Passed Successfully! ==="
