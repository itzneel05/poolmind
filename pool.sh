#!/usr/bin/env bash
# poolmind CLI wrapper - run `pool <command>` from project root
cd "$(dirname "$0")"
exec .venv/Scripts/python.exe -m app.cli "$@"
