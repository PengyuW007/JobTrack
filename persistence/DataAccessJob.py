from objects.JobApplication import JobApplication


class DataAccessJob:

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def get_all_jobs(self):
        self.cursor.execute("""
        SELECT
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
        FROM jobs
        ORDER BY email_date DESC
        """)

        rows = self.cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_jobs_by_status(self, status):
        self.cursor.execute("""
        SELECT
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
        FROM jobs
        WHERE status = ?
        ORDER BY email_date DESC
        """, (status,))

        rows = self.cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_interview_jobs(self):
        self.cursor.execute("""
        SELECT
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
        FROM jobs
        WHERE interview_count > 0
        ORDER BY email_date DESC
        """)

        rows = self.cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_rejected_jobs(self):
        return self.get_jobs_by_status("Rejected")

    def get_offer_jobs(self):
        self.cursor.execute("""
        SELECT
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
        FROM jobs
        WHERE offer = 1 OR status = 'Offer'
        ORDER BY email_date DESC
        """)

        rows = self.cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _row_to_job(row):
        return JobApplication(
            gmail_id=row[0],
            application_key=row[1],
            company=row[2],
            position=row[3],
            sender=row[4],
            email_date=row[5],
            status=row[6],
            interview_count=row[7],
            offer=row[8],
            subject=row[9],
            body_preview=row[10]
        )
