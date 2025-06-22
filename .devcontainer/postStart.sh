#!/bin/bash
/usr/local/bin/start-docker.sh
if [ -d /tmp/.ssh ]; then
  cp -r /tmp/.ssh /root/
  chmod 700 /root/.ssh
  chmod 600 /root/.ssh/*
fi
cd /workspace
python -m venv venv
./venv/bin/pip install --upgrade pip
PATH="/workspace/venv/bin:$PATH"
./venv/bin/pip install \
    apscheduler==3.11.0 \
    debugpy==1.8.14 \
    meilisearch-python-sdk==4.7.1 \
    python-magic==0.4.27 \
    jsonschema==4.24.0 \
    xxhash==3.5.0 \
    sentence-transformers==4.1.0 \
    transformers==4.52.4 \
    black==25.1.0 ruff==0.12.0 mypy==1.10.0 pytest==8.4.1
source /workspace/venv/bin/activate
