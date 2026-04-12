#!/bin/sh
# Paste-link download (default). For window UI: ./run-gui.sh --gui
cd "$(dirname "$0")"
export SYSTEM_VERSION_COMPAT=0
exec python3 main.py "$@"
