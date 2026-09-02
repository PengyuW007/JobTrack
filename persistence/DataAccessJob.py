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
            created_date,
            last_updated_date,
            status,
            assessment_count,
            interview_count,
            offer,
            subject,
            body_preview
        FROM jobs
        ORDER BY created_date DESC
        """)

        rows = self.cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_jobs_by_date_range(self, start_date, end_date):
        """Return applications whose first application date is in the range.

        Dates are YYYY-MM-DD strings.  The comparison is inclusive at both
        ends; created_date also contains a time and timezone suffix, so only
        its ISO date prefix is compared.
        """
        self.cursor.execute("""
        SELECT
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
        FROM jobs
        WHERE substr(created_date, 1, 10) BETWEEN ? AND ?
        ORDER BY created_date DESC
        """, (start_date, end_date))

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
            created_date,
            last_updated_date,
            status,
            assessment_count,
            interview_count,
            offer,
            subject,
            body_preview
        FROM jobs
        WHERE status = ?
        ORDER BY created_date DESC
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
            created_date,
            last_updated_date,
            status,
            assessment_count,
            interview_count,
            offer,
            subject,
            body_preview
        FROM jobs
        WHERE interview_count > 0
        ORDER BY created_date DESC
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
            created_date,
            last_updated_date,
            status,
            assessment_count,
            interview_count,
            offer,
            subject,
            body_preview
        FROM jobs
        WHERE offer = 1 OR status = 'Offer'
        ORDER BY created_date DESC
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
            created_date=row[5],
            last_updated_date=row[6],
            status=row[7],
            assessment_count=row[8],
            interview_count=row[9],
            offer=row[10],
            subject=row[11],
            body_preview=row[12]
        )

    def get_first_application_date(self):
        self.cursor.execute("""
        SELECT MIN(created_date)
        FROM jobs
        """)

        row = self.cursor.fetchone()

        if row and row[0]:
            return row[0]

        return None
