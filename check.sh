#!/bin/bash
set -e
black --check .
ruff check .
