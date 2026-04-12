#!/bin/bash
# Double-click this file in Finder to paste a link in Terminal (saves to Downloads).
cd "$(dirname "$0")"
export SYSTEM_VERSION_COMPAT=0
exec python3 main.py
