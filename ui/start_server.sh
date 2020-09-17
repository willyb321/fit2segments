#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

python -m http.server --bind 127.0.0.1
