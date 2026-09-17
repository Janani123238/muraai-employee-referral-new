#!/usr/bin/env bash
# Copies the entire frontend into backend/static so FastAPI can serve it as one
# deployable service. Run this any time you edit files under frontend/.
set -e
cp -R frontend/. backend/static/
echo "Synced frontend/ -> backend/static/"
