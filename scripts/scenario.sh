#!/usr/bin/env bash
# Stop/restart recovery demo: duplicates, a late v2 event, malformed input,
# processor restarts and two replays. Exits nonzero on any mismatch.
set -euo pipefail
cd "$(dirname "$0")/.."

cli() { docker compose run --rm -T cli "$@"; }
FP=/data/fingerprint.txt

echo "== 1. baseline events"
cli publish --phase baseline
cli wait --bronze 4 --silver 4 --timeout 240
cli verify --stage baseline

echo "== 2. stop processors, publish duplicate + late v2 + malformed"
docker compose stop raw materializer
cli publish --phase outage
docker compose start raw materializer
cli wait --bronze 7 --silver 5 --timeout 240

echo "== 3. verify recovered state"
cli verify --stage final --fingerprint-out "$FP"

echo "== 4. restart again without new data"
docker compose restart raw materializer
sleep 45
cli verify --stage final --fingerprint-in "$FP"

echo "== 5. replay from Bronze twice"
cli replay && cli verify --stage final --fingerprint-in "$FP"
cli replay && cli verify --stage final --fingerprint-in "$FP"

echo "SCENARIO PASSED"
