#!/usr/bin/env sh
# Launch the Tetris game (macOS / Linux).
cd "$(dirname "$0")" || exit 1
export PYTHONIOENCODING=utf-8

PY=""

# 1) prefer an interpreter that already has pygame
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import pygame" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done

# 2) otherwise take any Python, install pygame for it below
if [ -z "$PY" ]; then
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then
            PY="$cand"
            break
        fi
    done
fi

if [ -z "$PY" ]; then
    echo "[ERROR] Python was not found. Install Python 3.9 or newer." >&2
    exit 1
fi

if ! "$PY" -c "import pygame" >/dev/null 2>&1; then
    echo "pygame is not installed for $PY, installing it now..."
    "$PY" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt         || "$PY" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pygame-ce
fi

exec "$PY" tetris.py "$@"
