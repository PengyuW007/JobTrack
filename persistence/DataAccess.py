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
        VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(gmail_id) DO UPDATE SET
            company = excluded.company,
            position = excluded.position,
            sender = excluded.sender,
            email_date = excluded.email_date,
            status = excluded.status,
            interview_count = excluded.interview_count,
            offer = excluded.offer,
            subject = excluded.subject,
            body_preview = excluded.body_preview
        """,
                            (
                                job.gmail_id,
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