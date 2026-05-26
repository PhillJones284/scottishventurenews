#!/usr/bin/env bash
set -e

python3 -m venv .venv
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r pipeline/requirements.txt

echo "Setup complete. Run: source .venv/bin/activate"
