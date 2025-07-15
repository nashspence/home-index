#!/bin/bash
set -e
pip install --quiet \
    black==25.1.0 \
    ruff==0.12.0 \
    mypy==1.10.0 \
    pytest==8.4.1 \
    jsonschema==4.24.0 \
    fastapi==0.116.1 \
    asgiwebdav==1.5.0 \
    uvicorn==0.35.0 \
    aiofiles==23.2.1 \
    httpx==0.28.1
./check.sh
