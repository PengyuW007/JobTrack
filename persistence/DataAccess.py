import sqlite3


class DataAccess:

    def __init__(self):
        self.conn = sqlite3.connect("tracker.db")
        self.cursor = self.conn.cursor()

    def create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            gmail_id TEXT UNIQUE,
            application_key TEXT UNIQUE,
            company TEXT,
            position TEXT,
            sender TEXT,

            email_date TEXT,
            status TEXT,

            interview_count INTEGER DEFAULT 0,
            offer INTEGER DEFAULT 0,

            subject TEXT,
            body_preview TEXT
        )
        """)

        self.conn.commit()

    def insert_job(self, job):
        self.cursor.execute("""
        INSERT INTO jobs(
            gmail_id,
            application_key,
            company,
            position,
            sender,
            email_date,
            status,
            interview_count,
            offer,
            subject,
            body_preview
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(application_key) DO UPDATE SET
            company = excluded.company,
            position = excluded.position,
            sender = excluded.sender,
            email_date = MIN(jobs.email_date, excluded.email_date),
            status = CASE
    WHEN
        CASE excluded.status
            WHEN 'Unknown' THEN 0
            WHEN 'Applied' THEN 1
            WHEN 'Assessment' THEN 2
            WHEN 'Interview' THEN 3
            WHEN 'Rejected' THEN 4
            WHEN 'Offer' THEN 5
            ELSE 0
        END
        >
        CASE jobs.status
            WHEN 'Unknown' THEN 0
            WHEN 'Applied' THEN 1
            WHEN 'Assessment' THEN 2
            WHEN 'Interview' THEN 3
            WHEN 'Rejected' THEN 4
            WHEN 'Offer' THEN 5
            ELSE 0
        END
    THEN excluded.status
    ELSE jobs.status
END,
            interview_count = MAX(jobs.interview_count, excluded.interview_count),
            offer = MAX(jobs.offer, excluded.offer),
            subject = excluded.subject,
            body_preview = excluded.body_preview
        """,
                            (
                                job.gmail_id,
                                job.application_key,
                                job.company,
                                job.position,
                                job.sender,
                                job.email_date,
                                job.status,
                                job.interview_count,
                                job.offer,
                                job.subject,
                                job.body_preview
                            ))

        self.conn.commit()

    def close(self):
        self.conn.close()
