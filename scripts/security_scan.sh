#!/bin/sh
# Run on source checkout. Reports contain package metadata, never application records.
set -eu
cd "$(dirname "$0")/.."
mkdir -p .local/security
uvx --from pip-audit pip-audit --path .venv/lib/python3.14/site-packages --format json --output .local/security/python.json --progress-spinner off
(cd apps/web && npm audit --audit-level=high --json > ../../.local/security/node.json)
for kind in api web; do
  docker image save -o ".local/security/$kind.tar" "safer-$kind:local-readiness"
  docker run --rm -v "$(pwd)/.local/security/$kind.tar:/input/image.tar:ro" -v safer-trivy-cache:/root/.cache aquasec/trivy:0.76.0 image --input /input/image.tar --severity HIGH,CRITICAL --exit-code 1 --scanners vuln --format json > ".local/security/$kind.json"
  docker run --rm -v "$(pwd)/.local/security/$kind.tar:/input/image.tar:ro" -v safer-trivy-cache:/root/.cache aquasec/trivy:0.76.0 image --input /input/image.tar --format cyclonedx > ".local/security/$kind-sbom.json"
done
