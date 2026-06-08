import os.path
import base64
from email.mime.text import MIMEText
from persistence.DataAccess import DataAccess

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def main():
    db = DataAccess()
    db.create_tables()

    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        q='after:2026/02/10 (application OR applied OR interview OR recruiter OR assessment OR unfortunately OR offer)',
        maxResults=10
    ).execute()

    messages = results.get("messages", [])

    print(f"Found {len(messages)} emails")

    for msg in messages:
        message = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()

        headers = message["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")

        db.insert_job(
            msg["id"],
            sender,
            "",
            date,
            "Unknown",
            0,
            0,
            subject
        )

        print("Inserted:", subject)

    db.close()


if __name__ == "__main__":
    main()