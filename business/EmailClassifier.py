class EmailClassifier:

    @staticmethod
    def detect_status(subject):
        text = subject.lower()

        if "offer" in text or "congratulations" in text:
            return "Offer"

        if "interview" in text:
            return "Interview"

        if "assessment" in text or "coding test" in text:
            return "Assessment"

        if (
            "unfortunately" in text
            or "not moving forward" in text
            or "not be further considered" in text
            or "application update" in text
            or "update on your application" in text
        ):
            return "Rejected"

        if (
            "thank you for applying" in text
            or "application received" in text
            or "thanks for your application" in text
            or "we received your application" in text
        ):
            return "Applied"

        return "Unknown"