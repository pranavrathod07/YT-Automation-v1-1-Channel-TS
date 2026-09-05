"""
Pehli baar setup ke liye:
    python youtube_uploader.py --authorize main_channel

Ye ek browser window kholega, apne YT channel ke Google account se login karo,
permission do -> tokens/token_<account>.json save ho jayega. Uske baad automation
isi token se automatically login karega, dubara login nahi karna padega (jab tak
revoke na karo).

NOTE: Ab tokens JSON format me store hote hai (pickle nahi), taaki GitHub Actions
secrets (YOUTUBE_TOKEN_JSON) se seedha compatible rahe aur headless run me bhi kaam kare.
"""

import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import TOKENS_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"  # sab accounts isi ek OAuth client se authorize honge


def _token_path(account):
    os.makedirs(TOKENS_DIR, exist_ok=True)
    return os.path.join(TOKENS_DIR, f"token_{account}.json")


def get_authenticated_service(account):
    token_file = _token_path(account)
    creds = None

    # 1) account-specific token: tokens/token_<account>.json
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    # 2) fallback: generic token.json (root se, GitHub Actions secret ke through banta hai)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(
                    f"{CLIENT_SECRETS_FILE} nahi mila. Google Cloud Console se "
                    "OAuth client (Desktop app) banake yaha rakho."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            print(f"\n>>> Browser me is baar us Google account se login karo jiska token banana hai: {account}\n")
            creds = flow.run_local_server(port=0)

        # refresh/naya token dono cases me disk pe (JSON) save kar do
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_short(account, video_path, title, description, tags, privacy_status="public"):
    youtube = get_authenticated_service(account)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "17",  # Sports
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"Upload complete! Video ID: {response['id']}")
    return response["id"]


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--authorize":
        account = sys.argv[2]
        get_authenticated_service(account)
        print(f"Authorization done. tokens/token_{account}.json ban gaya.")
    else:
        print("Chalao: python youtube_uploader.py --authorize <account_name>")
        print("Example: python youtube_uploader.py --authorize channel1")
