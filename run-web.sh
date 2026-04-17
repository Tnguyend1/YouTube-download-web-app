#!/bin/sh
# Start private web downloader (LAN-friendly). Password optional via APP_PASSWORD.
cd "$(dirname "$0")"
export SYSTEM_VERSION_COMPAT=0
exec python3 web_app.py
