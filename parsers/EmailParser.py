import re

class EmailParser:

    @staticmethod
    def extract_company(sender):

        match = re.match(r"(.+?)\s*<", sender)

        if match:
            return match.group(1).strip()

        return sender