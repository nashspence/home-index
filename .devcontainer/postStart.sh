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
    redis==5.0.4 \
    PyYAML==6.0.1 \
    xxhash==3.5.0 \
    types-PyYAML==6.0.12 \
    docker==7.1.0 \
    sentence-transformers==4.1.0 \
    transformers==4.53.0

# Install the development tools used by `check.sh`.
./.devcontainer/install_dev_tools.sh
source /workspace/venv/bin/activate
