#!/bin/bash

function run_app() {
  docker run -t \
  -p 8000:8000 \
  --mount type=bind,source=$(pwd),target=/app \
  --rm cosplay-display $1
}

BASEDIR=$(dirname "$0")

cd "$BASEDIR"

run_app --make-list

# Give the port time to be freed.
sleep 2

run_app --serve-site
