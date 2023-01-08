# Cosplay Display

## About

This is a small Python app to display images from my Google Drive.
It can be run from the host, but the documentation will focus on Docker for cross-platform purposes.

## Setup

1. Change to the project directory.
2. Build the docker image: `docker build -t cosplay-display:latest -f Dockerfile`
3. Run the application:
   * Mac / Linux: `./run.sh`
   * Windows: `docker run -t -p 8000:8000 --mount type=bind,source=$(pwd),target=/app`

## To Do

* Move the image list to a database.
* Move source code to a separate directory.

## Changes

*2023-01-08:* Update script to use one port, for authentication and serving. Create README file.

*2022-12-25:* Create Docker file with plans to run on Windows.

*2022-12-17:* Stub in files.

*2022-12-03:* Switch from HTML Canvas to [Pillow](https://pillow.readthedocs.io/en/stable/) for image resizing.

*2022-11-26:* Initian commit with previous work included. Using HTML Canvas to display images.
