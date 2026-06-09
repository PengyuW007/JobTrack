import re

class EmailParser:

    @staticmethod
    def extract_company(sender):

        match = re.match(r"(.+?)\s*<", sender)

        if match:
            return match.group(1).strip()

        return sender

    @staticmethod
    def extract_position(subject,body):
        subject = subject or ""
        body = body or ""

        # 1. Position directly appears in subject
        subject_patterns = [
            r"^(.+?)\s*-\s*STACK IT Recruitment",
            r"^(.+?)\s*-\s*[A-Za-z0-9 &,.]+$",
            r"Indeed Application:\s*(.+)",
            r"Application for\s*(.+?)\s*with",
            r"Application for\s*(.+)",
        ]

        for pattern in subject_patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return EmailParser.clean_position(match.group(1))

        # 2. Position appears in body
        text = (subject + " " + body).replace("\n", " ")

        body_patterns = [
            r"application for the\s+(.+?)\s+position",
            r"application for\s+(.+?)\s+position",
            r"applying for the\s+(.+?)\s+position",
            r"applying to the\s+(.+?)\s+position",
            r"applied for the\s+(.+?)\s+position",
            r"applied to the\s+(.+?)\s+position",
            r"received your application for the\s+(.+?)\s+job",
            r"received your application for\s+(.+?)\s+job",
            r"your application for the\s+(.+?)\s+role",
            r"your application for\s+(.+?)\s+role",
            r"interest in the\s+(.+?)\s+role",
            r"interest in our\s+(.+?)\s+role",
            r"for the\s+(.+?)\s+opportunity",
            r"for our\s+(.+?)\s+opportunity",
        ]

        for pattern in body_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return EmailParser.clean_position(match.group(1))

        return ""

    @staticmethod
    def clean_position(position):
        if not position:
            return ""

        position = position.strip()

        position = re.split(
            r"\s+(at|with|role|job|position|opportunity|opening)\s+",
            position,
            flags=re.IGNORECASE
        )[0].strip()

        position = position.replace("&#40;", "(").replace("&#41;", ")")
        position = position.replace("&amp;", "&")
        position = position.replace("  ", " ")

        return position.title()