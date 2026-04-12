#!/bin/bash
# Scans candidate-facing files for keywords that would reveal the crisis.
# Run before committing to the main branch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SCAN_DIRS=(
  "$PROJECT_DIR/configs"
  "$PROJECT_DIR/gateway"
  "$PROJECT_DIR/pod-service"
  "$PROJECT_DIR/candidate"
)

PATTERNS=(
  "single point of failure"
  "SPOF"
  "cascade failure"
  "cascading failure"
  "collapse scenario"
  "answer key"
  "rubric"
  "critical chokepoint"
  "bottleneck"
  "transitive dependency"
  "colony-wide crisis"
)

echo "=== Leakage Check ==="
echo "Scanning candidate-facing files for spoiler keywords..."
echo

found=0
for dir in "${SCAN_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    continue
  fi
  for pattern in "${PATTERNS[@]}"; do
    matches=$(grep -ril "$pattern" "$dir" 2>/dev/null || true)
    if [ -n "$matches" ]; then
      echo "FOUND: \"$pattern\" in:"
      echo "$matches" | sed 's/^/  /'
      found=1
    fi
  done
done

echo
if [ $found -eq 0 ]; then
  echo "PASS — No spoiler keywords found in candidate-facing files."
else
  echo "FAIL — Spoiler keywords detected. Review and remove before pushing to main."
  exit 1
fi
