import os.path
import os

from objects.JobApplication import JobApplication
from persistence.DataAccess import DataAccess
from business.EmailClassifier import EmailClassifier
from gmail.GmailService import get_header, extract_body, convert_to_toronto
from parsers.EmailParser import EmailParser
from visualization.Workbench import Workbench

from datetime import datetime
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

        except RefreshError:
            print("Token expired or revoked. Removing token.json...")
            os.remove("token.json")
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def synchronize_gmail():
    db = DataAccess()
    db.create_tables()

    try:
        sync_started = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y/%m/%d")
        service = get_gmail_service()

        # One full history pass supplies evidence missing from legacy 500-character previews.
        db.conn.execute("CREATE TABLE IF NOT EXISTS evidence_metadata (id INTEGER PRIMARY KEY, completed INTEGER)")
        FULL_REBUILD = db.conn.execute("SELECT completed FROM evidence_metadata WHERE id = 1").fetchone() is None

        if FULL_REBUILD:
            query = ""
        else:
            last_sync_date = db.get_last_sync_date()

            if last_sync_date:
                query = f"after:{last_sync_date}"
            else:
                query = ""

        print("Gmail query:", query)

        all_messages = []
        page_token = None

        while True:

            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=100,
                pageToken=page_token
            ).execute()

            all_messages.extend(
                results.get("messages", [])
            )

            page_token = results.get("nextPageToken")

            if not page_token:
                break

        print(f"Found {len(all_messages)} emails")

        inserted_count = 0
        total = len(all_messages)

        for index, msg in enumerate(all_messages, start=1):
            if index % 10 == 0:
                print(f"Processed {index}/{total}")
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

            raw_date = get_header(headers, "Date")
            date = convert_to_toronto(raw_date)

            body = extract_body(message["payload"])

            combined_text = subject + " " + body
            if not EmailClassifier.is_job_related(combined_text):
                continue
            status = EmailClassifier.detect_status(subject, combined_text)

            company = EmailParser.extract_company(sender, subject, body)
            position = EmailParser.extract_position(subject, body)
            application_key = EmailParser.generate_application_key(
                company,
                position
            )
            job = JobApplication(
                msg["id"],
                application_key,
                company,
                position,
                sender,
                date,
                date,
                status,
                EmailClassifier.detect_assessment_count(combined_text),
                EmailClassifier.detect_interview_count(combined_text),
                EmailClassifier.detect_offer_flag(status),
                subject,
                body[:500]
            )

            db.insert_job(job)
            db.save_evidence(job, body)
            inserted_count += 1
        print(f"Inserted {inserted_count} job-related emails")
        db.update_last_sync_date(sync_started)
        db.conn.execute("INSERT OR REPLACE INTO evidence_metadata VALUES (1, 1)")
        db.conn.commit()
    finally:
        db.close()


def main():
    db = DataAccess()
    db.create_tables()
    try:
        Workbench(db, synchronize_gmail).run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
