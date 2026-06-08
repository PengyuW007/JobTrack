import os.path

from persistence.DataAccess import DataAccess
from business.EmailClassifier import EmailClassifier
from gmail.GmailService import get_header, extract_body

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
            format="full",
        ).execute()

        headers = message["payload"]["headers"]

        subject = get_header(headers, "Subject")
        sender = get_header(headers, "From")
        date = get_header(headers, "Date")
        body = extract_body(message["payload"])

        combined_text = subject + " " + body
        status = EmailClassifier.detect_status(combined_text)

        print("Status:", status)
        print("Body Preview:", body[:300])

        db.insert_job(
            msg["id"],
            "",
            "",
            sender,
            date,
            status,
            1 if status == "Interview" else 0,
            1 if status == "Offer" else 0,
            subject,
            body[:500]
        )

        print("Inserted:", subject)

    db.close()


if __name__ == "__main__":
    main()