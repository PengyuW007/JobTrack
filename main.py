import os.path
import os
from email.utils import parseaddr

from objects.JobApplication import JobApplication
from persistence.DataAccess import DataAccess
from business.EmailClassifier import EmailClassifier
from gmail.GmailService import get_header, extract_body, convert_to_toronto
from parsers.EmailParser import EmailParser
from visualization.Workbench import Workbench

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLASSIFIER_VERSION = 2


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

def synchronize_gmail(progress=None):
    db = DataAccess()
    db.create_tables()

    try:
        sync_started_at = datetime.now(timezone.utc)
        sync_started = sync_started_at.astimezone(
            ZoneInfo("America/Toronto")
        ).strftime("%Y/%m/%d")
        sync_started_epoch = int(sync_started_at.timestamp())
        service = get_gmail_service()
        account_email = service.users().getProfile(
            userId="me"
        ).execute(num_retries=3).get("emailAddress", "").casefold()

        # One full history pass supplies evidence missing from legacy 500-character previews.
        db.conn.execute("CREATE TABLE IF NOT EXISTS evidence_metadata (id INTEGER PRIMARY KEY, completed INTEGER, classifier_version INTEGER DEFAULT 1)")
        metadata_columns = {row[1] for row in db.conn.execute("PRAGMA table_info(evidence_metadata)")}
        if "classifier_version" not in metadata_columns:
            db.conn.execute("ALTER TABLE evidence_metadata ADD COLUMN classifier_version INTEGER DEFAULT 1")
        metadata = db.conn.execute("SELECT completed, classifier_version FROM evidence_metadata WHERE id = 1").fetchone()
        FULL_REBUILD = metadata is None or not metadata[0] or (metadata[1] or 1) < CLASSIFIER_VERSION

        if FULL_REBUILD:
            query = ""
            scanned_ids = db.get_scanned_gmail_ids(CLASSIFIER_VERSION)
        else:
            scanned_ids = set()
            last_sync_epoch = db.get_last_sync_epoch()
            last_sync_date = db.get_last_sync_date()

            if last_sync_epoch:
                query = f"after:{last_sync_epoch}"
            elif last_sync_date:
                query = f"after:{last_sync_date}"
            else:
                query = ""

        all_messages = []
        page_token = None

        while True:

            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=500,
                pageToken=page_token
            ).execute(num_retries=3)

            all_messages.extend(
                results.get("messages", [])
            )
            if progress:
                progress(f"Finding email… {len(all_messages)} found")

            page_token = results.get("nextPageToken")

            if not page_token:
                break

        inserted_count = 0
        unreadable_count = 0
        total = len(all_messages)

        def checkpoint(message_id, current_index):
            db.mark_gmail_scanned(message_id, CLASSIFIER_VERSION)
            if current_index % 25 == 0 or current_index == total:
                db.conn.commit()
                if progress:
                    progress(f"Syncing email… {current_index}/{total}")

        for index, msg in enumerate(all_messages, start=1):
            if msg["id"] in scanned_ids:
                if progress and (index % 25 == 0 or index == total):
                    progress(f"Syncing email… {index}/{total}")
                continue
            message = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full",
            ).execute(num_retries=3)

            try:
                payload = message.get("payload") or {}
                headers = payload.get("headers") or []
                subject = get_header(headers, "Subject")
                sender = get_header(headers, "From")
                raw_date = get_header(headers, "Date")
                if not raw_date:
                    raise ValueError("Message has no Date header")
                date = convert_to_toronto(raw_date)
                body = extract_body(payload)
            except (AttributeError, KeyError, TypeError, ValueError):
                unreadable_count += 1
                checkpoint(msg["id"], index)
                continue

            if account_email and parseaddr(sender)[1].casefold() == account_email:
                checkpoint(msg["id"], index)
                continue

            combined_text = subject + " " + body
            if not EmailClassifier.is_job_related(combined_text):
                checkpoint(msg["id"], index)
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
            checkpoint(msg["id"], index)
            inserted_count += 1
        db.update_last_sync_date(sync_started, sync_started_epoch)
        db.conn.execute(
            "INSERT OR REPLACE INTO evidence_metadata(id, completed, classifier_version) VALUES (1, 1, ?)",
            (CLASSIFIER_VERSION,),
        )
        db.clear_gmail_scan_progress()
        db.conn.commit()
        return unreadable_count
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
