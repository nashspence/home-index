#!/bin/bash
set -e
pip install --quiet \
    black==25.1.0 \
    ruff==0.12.0 \
    mypy==1.10.0 \
    pytest==8.4.1 \
    pytest-asyncio==0.23.6 \
    jsonschema==4.24.0 \
    fastapi==0.116.1 \
    asgiwebdav==1.5.0 \
    uvicorn==0.35.0 \
    aiofiles==23.2.1 \
    httpx==0.28.1

# Tools for linting/formatting Gherkin snippets in Markdown
npm install --quiet -g \
    gherkin-lint@4.2.4 \
    prettier-plugin-gherkin@3.1.2

# Formatter runner for fenced code blocks
cargo install --locked mdsf --version 0.10.3
