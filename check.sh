#!/bin/bash
set -e
black --check .
flake8
