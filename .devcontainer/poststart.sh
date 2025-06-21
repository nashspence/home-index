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
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install black==25.1.0 ruff==0.12.0 pytest==8.4.1
source /workspace/venv/bin/activate
