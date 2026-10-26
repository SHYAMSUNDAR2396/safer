"""Compose wrapper that supplies only private directory paths and non-secret UID metadata."""

import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = json.loads((root / ".local/readiness-paths.json").read_text())
env = os.environ | {
    "SAFER_PRIVATE_DIR": paths["private_dir"],
    "SAFER_LOCAL_UID": paths["uid"],
    "SAFER_LOCAL_GID": paths["gid"],
}
args = sys.argv[1:] or [
    "up",
    "-d",
    "--no-build",
    "app",
    "web-readiness",
    "readiness-worker",
    "readiness-relay",
]
raise SystemExit(
    subprocess.call(
        [
            str(root / "scripts/compose.sh"),
            "-f",
            "compose.yaml",
            "-f",
            "compose.readiness.yaml",
            "-f",
            "compose.containers.yaml",
            *args,
        ],
        cwd=root,
        env=env,
    )
)
