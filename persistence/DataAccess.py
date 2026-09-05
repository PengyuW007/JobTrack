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

            created_date TEXT,
            last_updated_date TEXT,
            status TEXT,
            assessment_count INTEGER DEFAULT 0,
            interview_count INTEGER DEFAULT 0,
            offer INTEGER DEFAULT 0,

            subject TEXT,
            body_preview TEXT
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_sync_date TEXT
        )
        """)

        self.conn.commit()

        self.cursor.executescript("""
        CREATE TABLE IF NOT EXISTS application_evidence (
            gmail_id TEXT PRIMARY KEY,
            application_key TEXT,
            company TEXT, position TEXT, date TEXT, status TEXT,
            subject TEXT, body TEXT
        );
        CREATE TABLE IF NOT EXISTS posting_snapshots (
            application_key TEXT, url TEXT, company TEXT,
            position TEXT, description TEXT,
            PRIMARY KEY (application_key, url)
        );
        """)
        self.conn.commit()

    def save_evidence(self, job, body):
        self.conn.execute("""
            INSERT OR REPLACE INTO application_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job.gmail_id, job.application_key, job.company, job.position,
              job.created_date, job.status, job.subject, body))
        self.conn.commit()

    def insert_job(self, job):
        self.cursor.execute("""
        INSERT INTO jobs(
            gmail_id,
            application_key,
            company,
            position,
            sender,
            created_date,
            last_updated_date,
            status,
            assessment_count,
            interview_count,
            offer,
            subject,
            body_preview
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(application_key) DO UPDATE SET
            company = excluded.company,
            position = excluded.position,
            sender = excluded.sender,
            created_date = MIN(jobs.created_date, excluded.created_date),
            last_updated_date = MAX(jobs.last_updated_date, excluded.last_updated_date),
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
            assessment_count = MAX(jobs.assessment_count, excluded.assessment_count),
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
                                job.created_date,
                                job.last_updated_date,
                                job.status,
                                job.assessment_count,
                                job.interview_count,
                                job.offer,
                                job.subject,
                                job.body_preview
                            ))

        self.conn.commit()

    def get_last_sync_date(self):
        self.cursor.execute("""
        SELECT last_sync_date
        FROM sync_metadata
        WHERE id = 1
        """)

        row = self.cursor.fetchone()

        if row:
            return row[0]

        return None

    def update_last_sync_date(self, sync_date):
        self.cursor.execute("""
        INSERT INTO sync_metadata(id, last_sync_date)
        VALUES(1, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_sync_date = excluded.last_sync_date
        """, (sync_date,))

        self.conn.commit()

    def close(self):
        self.conn.close()
