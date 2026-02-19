#!/bin/bash
set -e
cd /home/bigbud712/ardomis
source .venv/bin/activate
exec python -u ardomis.py
