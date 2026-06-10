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
            "interview_rate": f"{self.get_interview_rate()}%",
            "offer_rate": f"{self.get_offer_rate()}%"
        }

    def get_funnel_data(self):
        return {
            "applications": self.get_total_applications(),
            "assessments": self.get_assessment_count(),
            "interviews": self.get_interview_count(),
            "rejected": self.get_rejected_count(),
            "offers": self.get_offer_count()
        }

    def get_assessment_count(self):
        return len([
            job
            for job in self.job_dao.get_all_jobs()
            if job.assessment_count > 0
        ])

    def print_funnel_report(self):
        funnel = self.get_funnel_data()

        print("=" * 50)
        print("JOB SEARCH FUNNEL")
        print("=" * 50)

        print(f"Applications : {funnel['applications']}")
        print("      ↓")
        print(f"Assessments  : {funnel['assessments']}")
        print("      ↓")
        print(f"Interviews   : {funnel['interviews']}")
        print("      ↓")
        print(f"Rejected     : {funnel['rejected']}")
        print("      ↓")
        print(f"Offers       : {funnel['offers']}")

        print("=" * 50)