import base64


def get_header(headers, name):
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")


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