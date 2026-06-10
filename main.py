import os.path

from objects.JobApplication import JobApplication
from persistence.DataAccess import DataAccess
from persistence.DataAccessJob import DataAccessJob
from business.EmailClassifier import EmailClassifier
from business.AnalyticsService import AnalyticsService
from gmail.GmailService import get_header, extract_body, convert_to_toronto
from parsers.EmailParser import EmailParser
from visualization.FunnelChart import FunnelChart

from datetime import datetime
from zoneinfo import ZoneInfo

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

    FULL_REBUILD = False

    if FULL_REBUILD:
        query = "after:2026/02/10"
    else:
        last_sync_date = db.get_last_sync_date()

        if last_sync_date:
            query = f"after:{last_sync_date}"
        else:
            query = "after:2026/02/10"

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

    count = 0
    for index, msg in enumerate(all_messages, start=1):
        if index % 10 == 0:
            print(f"Processed {index}/{total}")
        #
        # count += 1
        # if count > 50:
        #     break
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
    first_job_date = analytics.get_first_application_date()
    print(first_job_date)

    summary = analytics.get_summary()
    print(summary)

    analytics.print_funnel_report()

    funnel = analytics.get_funnel_data()

    today_display = datetime.now(
        ZoneInfo("America/Toronto")
    ).strftime("%Y-%m-%d")

    FunnelChart.show_funnel(
        applications=funnel["applications"],
        assessments=funnel["assessments"],
        interviews=funnel["interviews"],
        rejected=funnel["rejected"],
        offers=funnel["offers"],
        start_date=first_job_date[:10],
        end_date=today_display
    )

    today = datetime.now(
        ZoneInfo("America/Toronto")
    ).strftime("%Y/%m/%d")

    db.update_last_sync_date(today)
    print("Last sync date updated:", today)

    db.close()


if __name__ == "__main__":
    main()
