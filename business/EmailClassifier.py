class EmailClassifier:

    @staticmethod
    def detect_status(subject, full_text):
        subject_text = subject.lower()
        text = full_text.lower()

        # Offer should be strict and preferably based on subject / clear phrases
        if (
                "offer letter" in subject_text
                or "congratulations" in subject_text
                or "we would like to offer you" in text
                or "we are pleased to offer you" in text
                or "pleased to extend an offer" in text
        ):
            return "Offer"

        if "interview" in text:
            return "Interview"

        if "assessment" in text or "coding test" in text:
            return "Assessment"

        if (
                "unfortunately" in text
                or "not moving forward" in text
                or "not be further considered" in text
                or "not proceeding" in text
                or "not be proceeding" in text
                or "unable to select you" in text
                or "regret to inform you" in text
                or "pursue other candidates" in text
                or "decided to pursue other candidates" in text
                or "no longer being considered" in text
                or "will not be moving forward" in text
                or "we won't be moving forward" in text
        ):
            return "Rejected"

        if (
                "thank you for applying" in text
                or "thanks for applying" in text
                or "application received" in text
                or "thanks for your application" in text
                or "we received your application" in text
                or "indeed application" in subject_text
                or "your job application" in subject_text
        ):
            return "Applied"

        return "Unknown"

    @staticmethod
    def detect_interview_count(text):
        text = text.lower()

        if (
                "interview" in text
                or "speak with you" in text
                or "spoke with you" in text
                or "phone screen" in text
                or "hiring day" in text
                or "meet with you" in text
                or "meeting with you" in text
        ):
            return 1

        return 0

    @staticmethod
    def detect_offer_flag(status):
        return 1 if status == "Offer" else 0