class EmailClassifier:

    @staticmethod
    def detect_status(subject, full_text):
        subject_text = subject.lower()
        text = full_text.lower()

        # Offer should be strict and preferably based on subject / clear phrases
        if (
                "offer letter" in subject_text
                or "we would like to offer you" in text
                or "we are pleased to offer you" in text
                or "pleased to extend an offer" in text
        ):
            return "Offer"

        INTERVIEW_PHRASES = [
            "interview invitation",
            "invite you to interview",
            "invited to interview",
            "schedule an interview",
            "technical interview",
            "phone interview",
            "video interview",
            "virtual interview",
            "phone screen",
            "screening call"
        ]

        ASSESSMENT_PHRASES = [
            "complete the assessment",
            "assessment invitation",
            "coding challenge",
            "coding assessment",
            "online assessment",
            "take the assessment",
            "complete your assessment",
            "complete the coding test"
        ]

        if any(
                phrase in text
                for phrase in INTERVIEW_PHRASES
        ):
            return "Interview"

        if any(
                phrase in text
                for phrase in ASSESSMENT_PHRASES
        ):
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

        interview_keywords = [
            "you have been invited to an interview",
            "you are invited to interview",
            "we would like to invite you to interview",
            "we'd like to invite you to interview",
            "schedule your interview",
            "schedule an interview",
            "scheduled a video interview",
            "video interview with",
            "phone interview with",
            "technical interview with",
            "interview confirmation",
            "interview invitation"
        ]

        return 1 if any(keyword in text for keyword in interview_keywords) else 0

    @staticmethod
    def detect_offer_flag(status):
        return 1 if status == "Offer" else 0

    @staticmethod
    def is_job_related(text):
        text = text.lower()

        keywords = [
            "thank you for applying",
            "thanks for applying",
            "application received",
            "we received your application",
            "your job application",
            "indeed application",
            "interview",
            "assessment",
            "coding test",
            "unfortunately",
            "not moving forward",
            "regret to inform you",
            "offer letter",
            "talent acquisition"
        ]

        return any(keyword in text for keyword in keywords)

    @staticmethod
    def detect_assessment_count(text):

        text = text.lower()

        assessment_keywords = [
            "assessment invitation",
            "complete the assessment",
            "online assessment",
            "coding assessment",
            "coding challenge",
            "complete your assessment",
            "take the assessment",
            "complete the coding test"
        ]

        return 1 if any(
            keyword in text
            for keyword in assessment_keywords
        ) else 0
