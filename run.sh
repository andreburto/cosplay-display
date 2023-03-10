#!/bin/bash

BASEDIR=$(dirname "$0")

cd "$BASEDIR"

docker run -t \
-p 8000:8000 \
--mount type=bind,source=$(pwd),target=/app \
--rm cosplay-display
