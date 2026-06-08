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

            email_date TEXT,

            status TEXT,

            interview_count INTEGER DEFAULT 0,

            offer INTEGER DEFAULT 0,

            subject TEXT
        )
        """)

        self.conn.commit()

    def insert_job(self, gmail_id, company, position, email_date, status, interview_count, offer, subject):
        self.cursor.execute("""
        INSERT OR IGNORE INTO jobs(
            gmail_id,
            company,
            position,
            email_date,
            status,
            interview_count,
            offer,
            subject
        )
        VALUES(?,?,?,?,?,?,?,?)
        """, (
            gmail_id,
            company,
            position,
            email_date,
            status,
            interview_count,
            offer,
            subject
        ))

        self.conn.commit()

    def close(self):
        self.conn.close()