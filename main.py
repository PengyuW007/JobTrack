import os.path

from persistence.DataAccess import DataAccess
from business.EmailClassifier import EmailClassifier
from gmail.GmailService import get_header, extract_body
from parsers.EmailParser import EmailParser

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
        if "pengyuwang777@gmail.com" in sender.lower():
            continue
        date = get_header(headers, "Date")
        body = extract_body(message["payload"])

        combined_text = subject + " " + body
        status = EmailClassifier.detect_status(subject, combined_text)

        company = EmailParser.extract_company(sender)
        position = EmailParser.extract_position(subject, body)

        db.insert_job(
            msg["id"],
            company,
            position,
            sender,
            date,
            status,
            EmailClassifier.detect_interview_count(combined_text),
            EmailClassifier.detect_offer_flag(status),
            subject,
            body[:500]
        )

        print("Inserted:", subject)

        # if "jana" in subject.lower():
        #     print("=" * 100)
        #     print(subject)
        #     print(body[:3000])

    db.close()


if __name__ == "__main__":
    main()