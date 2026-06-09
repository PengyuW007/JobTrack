import base64
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo


def get_header(headers, name):
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")


def convert_to_toronto(date_string):

    dt = parsedate_to_datetime(date_string)

    toronto_time = dt.astimezone(
        ZoneInfo("America/Toronto")
    )

    return toronto_time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def extract_body(payload):
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            body += extract_body(part)
    else:
        data = payload.get("body", {}).get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            body += decoded

    return body
