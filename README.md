# JobTrack

JobTrack is a private desktop workspace for reviewing job opportunities and tracking applications. It imports job-related Gmail messages into a local SQLite database, displays an application funnel, checks whether a job may have been submitted before, and recommends one of the resumes selected by the user.

The English interface uses a two-column layout: controls and job details appear on the left, while the date-filtered application funnel remains visible on the right.

## Start here

JobTrack is currently a source-code download, not a one-click installer. If you are unfamiliar with Python, use an AI assistant as an installation guide:

1. Open ChatGPT in your web browser.
2. Send it the link to this GitHub repository.
3. Copy and send this request:

```text
Help me install and start this JobTrack project. I am not a programmer.
Ask whether I use Windows or macOS, then give me one step at a time.
Wait for me after every step and help me understand any error message.
Never ask me to share credentials.json, token.json, my database, or my resumes.
Use the installation instructions in README.md from this repository.
```

The assistant can explain each click and command, but it cannot safely receive your passwords, OAuth files, application database, or resumes.

### What a new user needs to do

1. Download and install Python 3.11 or newer.
2. Download JobTrack from GitHub and extract the ZIP file.
3. Install the required packages once.
4. Start JobTrack.
5. Add local resumes.
6. Optionally connect Gmail to import application history.

Detailed Windows and macOS instructions appear below. Complete the steps for your own operating system only.

## Features

### Application funnel

- Shows Applications, Rejected, Assessments, Interviews, and Offers.
- Supports custom From and To dates plus 7D, 30D, 90D, and All shortcuts.
- Uses February 10, 2026 as the initial From date.
- Applies the selected date range to the chart only.

### Gmail application history

- Connects to Gmail with read-only OAuth permission.
- Classifies application, assessment, interview, rejection, and offer messages.
- Stores application records and supporting email evidence locally.
- Uses incremental synchronization after the first complete history import.
- Consolidates related messages and avoids duplicate Gmail message records.
- Shows the last successful synchronization time.

Gmail synchronization runs when the user selects **Sync Gmail**. The first synchronization may take longer because JobTrack must build the local history.

### Job check and duplicate detection

- Accepts a complete job URL from LinkedIn, Indeed, or another public platform.
- Starts automatically after a URL is pasted or Enter is pressed.
- Reads public `JobPosting` structured data when available.
- Uses browser fallback for sites that require JavaScript.
- Searches the complete local history independently of the chart date range.
- Detects exact URLs while ignoring common tracking parameters.
- Preserves platform job identifiers during URL normalization.
- Finds likely reposts when the company, title, and saved description are highly similar, even if the URL changed.
- Keeps Application history hidden until a possible previous application is found.

Some platforms block automated access or require login. In those cases, JobTrack may be unable to retrieve the job description. `No previous application found` means no sufficiently strong match was found in the available local evidence; it does not guarantee that the job was never submitted.

### Resume manager

- Adds PDF, DOCX, TXT, and Markdown resumes by local file reference.
- Replaces, renames, or removes a saved resume entry.
- Enables or disables individual resumes by double-clicking a row.
- Keeps resume files in their original folders; JobTrack stores only their paths and metadata in `tracker.db`.
- Compares all enabled and available resumes when a job description is parsed.

### Basic resume recommendation

The current basic result panel intentionally displays only:

```text
Recommended: QA Resume.pdf
Match: ★★★  6.1/10
Local assessment
```

The local assessment uses deterministic skill and qualification rules. Its score is an estimate and may be less accurate for unusual roles or terminology.

### Basic version

The current public version is the **Basic version**. The workbench displays `Basic version · Local assessment` above Job check.

Resume analysis stays on the user's computer.

## Requirements

- Python 3.11 or newer
- Tk support for Python
- Internet access for Gmail synchronization and job-page retrieval
- A supported browser for job pages that cannot be read directly
- Google OAuth Desktop credentials for Gmail synchronization

JobTrack first requests a job page directly. If browser fallback is required, it tries installed browsers automatically:

| Operating system | Browser order |
| --- | --- |
| Windows | Edge, Chrome, Firefox |
| macOS | Safari, Chrome, Firefox, Edge |
| Linux | Firefox, Chrome, Edge |

Safari users may need to enable **Safari → Develop → Allow Remote Automation**. JobTrack must use a Selenium-supported browser because opening an ordinary default-browser window does not provide page content to the application.

## Download

Choose **Code → Download ZIP** on GitHub and extract the archive, or clone it:

```bash
git clone https://github.com/PengyuW007/JobTrack.git
cd JobTrack
```

## Windows installation and startup

Open PowerShell in the extracted `JobTrack` folder:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, install without activating the environment:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Double-click `Start JobTrack.vbs` to start the application without a command prompt. It runs `JobTrack.pyw` through the virtual environment's `pythonw.exe`.

To create a desktop shortcut:

1. Right-click the desktop and select **New → Shortcut**.
2. Enter the following target and replace the project path when necessary:

```text
C:\Windows\System32\wscript.exe "C:\Users\YourName\JobTrack\Start JobTrack.vbs"
```

3. Name the shortcut `JobTrack`.

Do not use `python main.py` for normal desktop startup because `python.exe` creates a console window.

## macOS installation and startup

JobTrack is currently distributed as source code rather than as a signed `.app`. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/macos/), then open Terminal in the extracted `JobTrack` folder:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

The official python.org macOS installer includes Tkinter. If `import tkinter` fails, replace the installed Python distribution with one that includes Tk support.

Start JobTrack from the project folder:

```bash
source venv/bin/activate
python3 JobTrack.pyw
```

A future packaged release can provide a signed `JobTrack.app` for startup without Terminal or a separate Python environment.

## Gmail API setup

Each user must create personal Google OAuth credentials. Credentials are not included in this repository.

1. Create or select a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Download the JSON credentials file.
6. Rename it to `credentials.json` and place it in the JobTrack project root.
7. Start JobTrack and select **Sync Gmail**.
8. Complete Google authorization in the browser.

Google then creates a local `token.json`. Later synchronizations reuse that token. If authorization is revoked or the token becomes invalid, JobTrack removes it and requests authorization again.

JobTrack requests only this Gmail scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

## Using JobTrack

### 1. Import application history

Select **Sync Gmail** and complete Google authorization if prompted. Wait until the footer displays `Last synced at ...`.

### 2. Manage resumes

Use **Add** to select local files. Double-click a row to enable or disable it. Use **Replace** for a newer file, **Rename** to change its display name, and **Remove** to delete its saved reference. Removing an entry does not delete the original file.

### 3. Check a job

Paste a complete public job URL into Job check. Analysis begins automatically. JobTrack displays the parsed company and title, checks all imported application history, and compares the description with enabled resumes. Use **Clear** to remove the current URL and result.

### 4. Review previous applications

When a possible match is found, Application history appears with the company, role, and application date. Select a row to view its stored status and match reason.

### 5. Filter the funnel

Choose From and To dates or use a shortcut. The filter changes only the chart. Duplicate detection always searches the complete available history.

## Local data and privacy

The following content must remain local and is excluded by `.gitignore`:

- `credentials.json` and other Google OAuth client files
- `token.json` and other authorization tokens
- `.env` files
- `tracker.db` and other SQLite databases
- PDF and DOCX resumes
- files inside `resumes/` or `private/`

Never commit OAuth secrets, Gmail content, application records, or personal resumes. The Basic version keeps resume analysis local.

## Data limitations

- Email classification may misclassify unusual recruiter messages.
- Multiple emails can belong to one application and do not necessarily represent separate submissions.
- Legacy records may contain only a shortened email preview.
- Gmail messages do not always include the original job description or URL.
- A repost cannot always be identified when the company, title, URL, or description changed substantially.
- Browser automation depends on browser support, the job platform, login state, and anti-automation controls.
- Resume scores are decision aids and do not predict recruiter or ATS outcomes.

## Architecture

```text
Gmail API
    ↓
Email classifier and parser
    ↓
Local SQLite database
    ↓
Duplicate and resume analysis services
    ↓
Tkinter workbench and Matplotlib funnel
```

```text
JobTrack/
├── business/       Analytics, duplicate matching, and resume recommendation
├── gmail/          Gmail message helpers
├── objects/        Application data objects
├── parsers/        Email parsing
├── persistence/    SQLite access
├── visualization/  Tkinter workbench and charts
├── tests/           Unit tests
├── JobTrack.pyw    GUI entry point
├── main.py          Application and Gmail synchronization
└── Start JobTrack.vbs
```

## Technology

- Python, Tkinter, SQLite, and Matplotlib
- Gmail API and Google OAuth
- Requests and Selenium
- pypdf

## Run tests

Windows:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS and Linux:

```bash
venv/bin/python3 -m unittest discover -s tests -v
```
