class AnalyticsService:

    def __init__(self, job_dao):
        self.job_dao = job_dao

    def get_total_applications(self):
        return len(self.job_dao.get_all_jobs())

    def get_rejected_count(self):
        return len(self.job_dao.get_rejected_jobs())

    def get_interview_count(self):
        return len(self.job_dao.get_interview_jobs())

    def get_offer_count(self):
        return len(self.job_dao.get_offer_jobs())

    def get_interview_rate(self):
        total = self.get_total_applications()

        if total == 0:
            return 0

        return round(self.get_interview_count() / total * 100, 2)

    def get_offer_rate(self):
        total = self.get_total_applications()

        if total == 0:
            return 0

        return round(self.get_offer_count() / total * 100, 2)

    def get_summary(self):
        return {
            "total_applications": self.get_total_applications(),
            "rejected_count": self.get_rejected_count(),
            "interview_count": self.get_interview_count(),
            "offer_count": self.get_offer_count(),
            "interview_rate": self.get_interview_rate(),
            "offer_rate": self.get_offer_rate()
        }