#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
os.chdir(root)

repo = root.name
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
image = f"{repo}:ci"
module_image = f"{repo}-module:ci"

subprocess.run(["./check.sh"], check=True)
subprocess.run(
    [
        "docker",
        "build",
        "-f",
        "Dockerfile",
        "-t",
        image,
        "--build-arg",
        f"COMMIT_SHA={sha}",
        ".",
    ],
    check=True,
)
subprocess.run(
    [
        "docker",
        "build",
        "-f",
        "Dockerfile.module",
        "-t",
        module_image,
        "--build-arg",
        f"COMMIT_SHA={sha}",
        ".",
    ],
    check=True,
)

env = os.environ.copy()
env["IMAGE"] = image
env["MODULE_BASE_IMAGE"] = module_image
env["COMMIT_SHA"] = sha
env.setdefault("DEBUG", "False")
env.setdefault("WAIT_FOR_DEBUGPY_CLIENT", "False")
env.setdefault("DEBUGPY_HOST", "0.0.0.0")
env.setdefault("DEBUGPY_PORT", "5678")

for feature in sorted(Path("features").glob("F*/test/acceptance.py")):
    subprocess.run(["pytest", "-q", str(feature)], env=env, check=True)
