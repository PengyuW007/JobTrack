# JobTrack

## Itinerary
````
Python Script
 ↓
Gmail API
 ↓
Read job application emails
 ↓
Parse company/job/status/interview information
 ↓
Update Excel or SQLite database
````

## Tech Stack
- Python 
- google-api-python-client 
- google-auth 
- pandas 
- openpyxl 
- sqlite3 
- schedule / Windows Task Scheduler

## Architecture
````
job_email_tracker/
│
├── main.py
├── gmail_service.py
├── email_parser.py
├── tracker.xlsx
├── token.json
├── credentials.json
└── requirements.txt
````

## Workflow
1. Create an OAuth Client using Google Cloud

2. Download credentials.json

3. Log in to Gmail for authorization on the first run of Python

4. Token.json will be automatically generated thereafter

5. Read new emails on each subsequent run

6. Remove duplicates based on message_id

7. Update the Excel or SQLite database

## Pseudo Code for Automatic Classification
````
if "interview" in text:
    status = "Interview"
elif "assessment" in text or "coding test" in text:
    status = "Assessment"
elif "unfortunately" in text or "not move forward" in text:
    status = "Rejected"
elif "thank you for applying" in text:
    status = "Applied"
elif "offer" in text or "congratulations" in text:
    status = "Offer"
else:
    status = "Unknown"
````