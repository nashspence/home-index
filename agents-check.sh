#!/bin/bash
set -e
pip install --quiet black==25.1.0 ruff==0.12.0 mypy==1.10.1 pytest==8.4.1 jsonschema==4.24.0
./check.sh
