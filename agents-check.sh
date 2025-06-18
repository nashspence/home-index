#!/bin/bash
set -e
pip install --quiet black==25.1.0 ruff==0.12.0
black --check .
ruff check .
