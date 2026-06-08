def detect_status(text):
    text = text.lower()

    if "offer" in text or "congratulations" in text:
        return "Offer"

    if "interview" in text:
        return "Interview"

    if "assessment" in text or "coding test" in text:
        return "Assessment"

    if (
        "unfortunately" in text
        or "not moving forward" in text
        or "not be proceeding"
        in text
    ):
        return "Rejected"

    if (
        "thank you for applying" in text
        or "application received" in text
    ):
        return "Applied"

    return "Unknown"