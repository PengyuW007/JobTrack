# JobTrack
JobTrack is a Python based job application tracking system that automatically synchronizes job-related emails from Gmail, 
stores application records in SQLite, analyzes recruitment progress, and generates visual funnel reports.

## Features

### Gmail Synchronization

- Connects to Gmail using Gmail API
- Reads job-related emails automatically
- Supports incremental synchronization
- Avoids duplicate records

### Application Tracking

- Consolidates multiple emails into a single application record
- Tracks application status changes
- Stores company, position, sender, subject, and timestamps

### Recruitment Analytics

- Total applications
- Assessment count
- Interview count
- Rejection count
- Offer count
- Conversion rates

### Visualization

- Generates recruitment funnel charts
- Exports funnel reports as images

## Installation & API Setup

Clone the repository:
````
git clone https://github.com/yourusername/JobTrack.git
cd JobTrack
````
Create virtual environment:
````
python -m venv venv
````
Activate environment:

Windows:
````
venv\Scripts\activate
````
Install dependencies:
````
pip install -r requirements.txt
````

### Gmail API Setup
1. Create a Google Cloud Project
2. Enable Gmail API
3. Create OAuth Desktop Credentials
4. Download:
````
credentials.json
````
5. Place it in the project root directory
6. Run
````
python main.py
````

## Itinerary
````
Gmail API
  ↓
Email Parser
  ↓
SQLite
  ↓
Analytics Service/Email Classifier
  ↓
Visualization
````

## Tech Stack
- Python 
- Gmail API
  - google-api-python-client 
  - google-auth
- sqlite3

## Architecture
````
JobTrack
│
├── gmail/
│   └── Gmail API integration
│
├── parsers/
│   └── Email parsing logic
│
├── business/
│   ├── EmailClassifier
│   └── AnalyticsService
│
├── persistence/
│   ├── DataAccess
│   └── DataAccessJob
│
├── objects/
│   └── JobApplication
│
├── visualization/
│   └── FunnelChart
│
└── tracker.db
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