import os.path

from objects.JobApplication import JobApplication
from persistence.DataAccess import DataAccess
from persistence.DataAccessJob import DataAccessJob
from business.EmailClassifier import EmailClassifier
from business.AnalyticsService import AnalyticsService
from gmail.GmailService import get_header, extract_body, convert_to_toronto
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

    all_messages = []
    page_token = None

    while True:

        results = service.users().messages().list(
            userId="me",
            q='after:2026/02/10',
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

    count = 0
    for index, msg in enumerate(all_messages, start=1):
        if index % 10 == 0:
            print(f"Processed {index}/{total}")

        count += 1
        if count > 50:
            break
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
            status,
            EmailClassifier.detect_interview_count(combined_text),
            EmailClassifier.detect_offer_flag(status),
            subject,
            body[:500]
        )

        db.insert_job(job)
        inserted_count += 1
    print(f"Inserted {inserted_count} job-related emails")
    job_dao = DataAccessJob(db.conn)

    all_jobs = job_dao.get_all_jobs()
    interview_jobs = job_dao.get_interview_jobs()
    rejected_jobs = job_dao.get_rejected_jobs()
    offer_jobs = job_dao.get_offer_jobs()

    print("All:", len(all_jobs))
    print("Interview:", len(interview_jobs))
    print("Rejected:", len(rejected_jobs))
    print("Offer:", len(offer_jobs))

    analytics = AnalyticsService(job_dao)

    summary = analytics.get_summary()

    print(summary)

    db.close()


if __name__ == "__main__":
    main()
