#!/bin/bash
set -e
pip install --quiet \
    black==25.1.0 \
    ruff==0.12.0 \
    mypy==1.10.0 \
    pytest==8.4.1 \
    pytest-asyncio==0.23.6 \
    pytest-bdd==7.3.0 \
    jsonschema==4.24.0 \
    fastapi==0.116.1 \
    asgiwebdav==1.5.0 \
    uvicorn==0.35.0 \
    aiofiles==23.2.1 \
    httpx==0.28.1 \
    docker==7.1.0 \
    PyYAML==6.0.1 \
    types-PyYAML==6.0.12.20240311 \
    xxhash==3.5.0 \
    types-aiofiles==23.2.0.20240623 \
    reformat_gherkin==3.0.1

# Tools for linting/formatting Gherkin snippets in Markdown
npm install --quiet -g \
    gherkin-lint@4.2.4
