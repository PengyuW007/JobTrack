import sqlite3
from datetime import datetime


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
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gmail_scan_progress (
            gmail_id TEXT PRIMARY KEY,
            classifier_version INTEGER NOT NULL
        );
        """)
        columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(sync_metadata)")}
        if "last_sync_at" not in columns:
            self.cursor.execute("ALTER TABLE sync_metadata ADD COLUMN last_sync_at TEXT")
        if "last_sync_epoch" not in columns:
            self.cursor.execute("ALTER TABLE sync_metadata ADD COLUMN last_sync_epoch INTEGER")
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

    def get_last_sync_epoch(self):
        row = self.conn.execute(
            "SELECT last_sync_epoch FROM sync_metadata WHERE id = 1"
        ).fetchone()
        return row[0] if row and row[0] else None

    def update_last_sync_date(self, sync_date, sync_epoch=None):
        self.cursor.execute("""
        INSERT INTO sync_metadata(id, last_sync_date, last_sync_at, last_sync_epoch)
        VALUES(1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_sync_date = excluded.last_sync_date,
            last_sync_at = excluded.last_sync_at,
            last_sync_epoch = COALESCE(excluded.last_sync_epoch, sync_metadata.last_sync_epoch)
        """, (
            sync_date,
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            sync_epoch,
        ))

        self.conn.commit()

    def get_last_sync_at(self):
        row = self.conn.execute("SELECT last_sync_at FROM sync_metadata WHERE id = 1").fetchone()
        return row[0] if row and row[0] else None

    def get_scanned_gmail_ids(self, classifier_version):
        return {
            row[0]
            for row in self.conn.execute(
                "SELECT gmail_id FROM gmail_scan_progress WHERE classifier_version = ?",
                (classifier_version,),
            )
        }

    def mark_gmail_scanned(self, gmail_id, classifier_version):
        self.conn.execute(
            "INSERT OR REPLACE INTO gmail_scan_progress(gmail_id, classifier_version) VALUES (?, ?)",
            (gmail_id, classifier_version),
        )

    def clear_gmail_scan_progress(self):
        self.conn.execute("DELETE FROM gmail_scan_progress")

    def get_resumes(self):
        return self.conn.execute(
            "SELECT id, name, file_path, enabled, updated_at FROM resumes ORDER BY name"
        ).fetchall()

    def add_resume(self, name, file_path):
        self.conn.execute(
            "INSERT INTO resumes(name, file_path, enabled, updated_at) VALUES (?, ?, 1, ?)",
            (name, file_path, datetime.now().astimezone().strftime("%Y-%m-%d"))
        )
        self.conn.commit()

    def update_resume(self, resume_id, name=None, file_path=None, enabled=None):
        current = self.conn.execute(
            "SELECT name, file_path, enabled FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not current:
            return
        self.conn.execute(
            "UPDATE resumes SET name = ?, file_path = ?, enabled = ?, updated_at = ? WHERE id = ?",
            (name if name is not None else current[0],
             file_path if file_path is not None else current[1],
             enabled if enabled is not None else current[2],
             datetime.now().astimezone().strftime("%Y-%m-%d"), resume_id)
        )
        self.conn.commit()

    def delete_resume(self, resume_id):
        self.conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        self.conn.commit()

    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
