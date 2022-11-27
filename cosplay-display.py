import argparse
import io
import json
import http.server as hs
import os
import logging
import sys

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from random import randint

logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', ]

# Mime types
FOLDER_TYPE = 'application/vnd.google-apps.folder'

# JSON files
DEFAULT_CREDENTIALS_JSON = "credentials.json"
DEFAULT_IMAGES_JSON = "images.json"
DEFAULT_TOKEN_JSON = "token.json"

DEFAULT_REFRESH_SECONDS = 30
DEFAULT_SERVING_PORT = 8000
DEFAULT_STARTING_DIRECTORY = "cosplayers"

# HTML
INDEX_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<script>
function scaleToFit(img) {
var canvas = document.getElementById("mainCanvas");
var context = canvas.getContext("2d");
var hRatio = canvas.width  / img.width;
var vRatio =  canvas.height / img.height;
var ratio  = Math.min(hRatio, vRatio);
var centerShift_x = (canvas.width - img.width*ratio) / 2;
var centerShift_y = (canvas.height - img.height*ratio) / 2;
context.imageSmoothingEnabled = true;
context.imageSmoothingQuality = "high";
context.clearRect(0, 0, canvas.width, canvas.height);
context.drawImage(img, 0, 0, img.width, img.height, centerShift_x, centerShift_y, img.width*ratio, img.height*ratio);
}
function loadImage() {
var img = new Image();
img.src = "/img";
img.onload = function() { scaleToFit(this); }
}
function startUp() {
setInterval(loadImage, 30000);
loadImage();
}
</script>
<title>COSPLAY DISPLAY</title>
</head>
<body style="margin: 0px; padding: 0px;" onload="startUp()">
<canvas style="margin: 0px; padding: 0px; width: 100%; height: 100%; position: absolute; top: 0px; left: 0px;" id="mainCanvas"></canvas>
</body>
</html>
""".replace("\n", "")


def setup_args():
    parser = argparse.ArgumentParser(description="Cosplay Display")
    # Flags to pick which action to take.
    parser.add_argument("--make-list", dest="make_list", action="store_true")
    parser.add_argument("--serve-site", dest="serve_site", action="store_true")
    # Parameters with default, environment variable values needed by all actions.
    parser.add_argument("--credentials", dest="credentials", type=str,
                        default=os.getenv("CREDENTIALS_JSON", DEFAULT_CREDENTIALS_JSON))
    parser.add_argument("--image-list", dest="image_list", type=str,
                        default=os.getenv("IMAGES_JSON", DEFAULT_IMAGES_JSON))
    parser.add_argument("--token", dest="token", type=str,
                        default=os.getenv("TOKEN_JSON", DEFAULT_TOKEN_JSON))
    # Returns the parsed parameters.
    return parser.parse_args()


# Google API Methods
def create_service(token_json, credentials):
    """
    Shamelessly lifted from GDrive API demo code.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_json, 'w') as token:
            token.write(creds.to_json())
    service = build('drive', 'v3', credentials=creds)
    return service


# Google Drive methods for building the image list.
def get_files_by_query(service, query):
    query = " and ".join(query) if isinstance(query, list) else query
    files = []
    page_token = None
    while True:
        response = service.files().list(q=query, spaces='drive', pageToken=page_token).execute()
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken')
        if page_token is None:
            break
    return files


def get_all_images_from_folder_and_subfolders(service, folder_id):
    image_list = []
    folder_and_image_list = get_files_by_query(service, f"'{folder_id}' in parents")

    # TODO: list comprehension minimizes loop size. Or async?
    for file in folder_and_image_list:
        if file.get("mimeType") == FOLDER_TYPE:
            image_list.extend(get_all_images_from_folder_and_subfolders(service, file.get("id")))
        elif file.get("mimeType").startswith("image/"):
            image_list.append(file)
    return image_list


# Google Drive methods for serving random images.
def get_random_image_from_json(filename):
    with open(filename) as readfile:
        cosplayers_from_file = json.load(readfile)
    return cosplayers_from_file[randint(0, len(cosplayers_from_file))]


def download_image(image_json, service):
    random_cosplay_file = get_random_image_from_json(image_json)
    request = service.files().get_media(fileId=random_cosplay_file.get("id"))
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)

    while True:
        status, done = downloader.next_chunk()
        if done:
            break

    return random_cosplay_file.get("mimeType"), file.getvalue()


# Web server components.
class WebHandler(hs.BaseHTTPRequestHandler):
    image_list = None
    service = None

    def _get_image(self):
        return download_image(self.image_list, self.service)

    def _get_index(self):
        return "text/html", INDEX_PAGE.encode()

    def do_GET(self):
        mime_type, data = self._get_image() if self.path.startswith("/img") else self._get_index()
        self.send_response(200)
        self.send_header("Content-type", mime_type)
        self.end_headers()
        self.wfile.write(data)


class WebServer(hs.HTTPServer):
    def __init__(self, handler, address="", port=DEFAULT_SERVING_PORT):
        super().__init__((address, port), handler)


# Script actions.
def make_list(args, service):
    # get the root folder
    cosplayers_folder = get_files_by_query(service, [f"name = '{DEFAULT_STARTING_DIRECTORY}'"])
    cosplayers_folder_id = cosplayers_folder[0].get("id")

    # build image list
    image_list = get_all_images_from_folder_and_subfolders(service, cosplayers_folder_id)

    # save to file
    image_list_json = json.dumps(image_list, indent=4)
    with open(args.image_list, "w") as fh:
        fh.write(image_list_json)


def serve_site(args, service):
    """
    Serve the web site that displays random images.
    """
    WebHandler.image_list = args.image_list
    WebHandler.service = service

    ws = WebServer(WebHandler)
    ws.serve_forever()


def main():
    args = setup_args()
    service = create_service(args.token, args.credentials)

    if args.make_list:
        make_list(args, service)
    elif args.serve_site:
        serve_site(args, service)
    else:
        raise ValueError("You must use --make-list or --serve-site when running the script.")


if __name__ == '__main__':
    main()
