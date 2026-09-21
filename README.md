# JobTrack

JobTrack is a private desktop workspace for reviewing job opportunities and tracking applications. It imports job-related Gmail messages into a local SQLite database, displays an application funnel, checks whether a job may have been submitted before, and recommends one of the resumes selected by the user.

Project scope, architecture decisions, roadmap, ownership, AI decision/change history, verification outcomes, and current risks are maintained in the root [JobTrack Single Source of Truth](SSOT.md). This README remains the source for installation and end-user instructions.

The English desktop interface keeps Job check, Application history, and Resume choice on the left, with Resumes and Application overview on the right. The window does not scroll as a page; long descriptions, evidence, and tables can scroll within their own panels.

## License and access

JobTrack is proprietary, source-visible software, not an open-source project.
Its source is publicly visible for inspection, but no additional permission
to run, modify, redistribute, or use it commercially or non-commercially is
granted without prior written authorization from Pengyu Wang. See [LICENSE](LICENSE)
for the full notice and its exceptions. The installation and usage instructions
below are for the copyright holder and separately authorized users; they do not
grant usage rights.

Permissions already granted for previously MIT-licensed material remain in
effect. Third-party dependencies retain their own licenses. Rights granted by
GitHub's terms for public repositories, including viewing and forking through
the service, are not restricted by this notice.

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
- Supports custom From and To dates plus Today, Yesterday, 7D, 30D, 90D, and All shortcuts.
- Uses February 10, 2026 as the initial From date.
- Applies the selected date range to the chart only.

### Gmail application history

- Connects to Gmail with read-only OAuth permission.
- Classifies application, assessment, interview, rejection, and offer messages.
- Stores application records and supporting email evidence locally.
- Uses incremental synchronization after the first complete history import.
- Consolidates related messages and avoids duplicate Gmail message records.
- Shows the last successful synchronization time.

Gmail synchronization runs once after startup when an existing local authorization token is present, and whenever the user selects **Sync Gmail**. There is no midnight or daily timer. Automatic synchronization never opens the authorization browser; select **Sync Gmail** to connect or reconnect. The first synchronization may take longer because JobTrack must build the local history.

When synchronization ends, the chart and the currently checked job's application history refresh from the saved database. Resume assessment remains in place. If synchronization fails after saving some messages, the UI shows the incomplete-sync status while displaying the saved history.

### Job check and duplicate detection

- Accepts a complete job URL from LinkedIn, Indeed, or another public platform.
- Also accepts a pasted JD through a dedicated form with optional title and company fields and a large description editor. Select **Add JD** or **Edit JD**, then **Analyze JD** to build the job profile, check identifiable history, and compare enabled resumes. Cancel leaves the current draft and results unchanged. History checking requires a URL or both company and title; missing identifiers are shown as unavailable rather than as a negative result.
- Starts automatically after a URL is pasted or Enter is pressed, and shows an analyzing state while the job page is being read.
- Reads public `JobPosting` structured data when available.
- Rejects unfilled hiring-manager placeholders and prefers a complete visible job description when a page's structured data is stale.
- Uses browser fallback for sites that require JavaScript and tries the next supported browser if one browser session fails.
- Searches the complete local history independently of the chart date range.
- Detects exact URLs while ignoring common tracking parameters.
- Preserves platform job identifiers during URL normalization.
- Finds likely reposts when the company, title, and saved description are highly similar, even if the URL changed.
- Keeps Application history visible with distinct waiting, unavailable, no-match, possible-match, and exact-URL states.

Some platforms block automated access or require login. In those cases, JobTrack may be unable to retrieve the job description. `No previous application found` means no sufficiently strong match was found in the available local evidence; it does not guarantee that the job was never submitted.

### Resume manager

- Adds PDF, DOCX, TXT, and Markdown resumes from the clearly labelled **＋ Add resume** action above the table.
- Keeps Edit and Delete in separate table columns; Edit offers Rename and Replace file, while Delete asks for confirmation before removing the saved reference.
- Enables or disables individual resumes by double-clicking a row.
- Keeps resume files in their original folders; JobTrack stores only their paths and metadata in `tracker.db`.
- Compares all enabled and available resumes when a job description is parsed.
- Recomputes the current assessment when resume entries or enabled states change. Missing files and unreadable documents are reported instead of silently omitted.

### Basic resume recommendation

The Summary tab shows a resume choice, supporting source sentences, and requirements that need verification. The All resumes tab compares each readable candidate. For example:

```text
Recommended: Full Stack Resume
Local assessment · Resume choice, not a hiring prediction

Job direction: full stack
Project evidence: java, react, sql
```

The local assessment uses deterministic English-language rules. It separates work direction from technologies, recognizes skill aliases, checks simple alternative requirements such as Java or Python, and evaluates all candidates before choosing. Resume filenames do not determine the ranking. A confirmed label or a skill list alone does not establish delivery evidence.

Software jobs use the existing technical matcher. Other jobs use a separate local matcher that compares responsibility and requirement text without requiring a known occupation or skill name. It distinguishes required and preferred evidence, tools, transferable skills, credentials, education, and experience. Unknown terms and missing evidence lead to review, never an automatic Skip in the general matcher. Credentials and education still require manual verification; language support is English, and unsupported or incomplete inputs are reported in the existing result summary. The technical matcher's existing decisions and the workbench layout are unchanged.

For general jobs, common job-board headings separate responsibilities and qualifications from company descriptions, compensation, benefits, culture, and equity statements. The Summary tab presents the retained responsibilities and core qualifications as separate bullet items so long descriptions do not collapse into one Core skills paragraph.

The result can be Recommended resume, Review two options, No suitable resume found, or More job information needed. Mixed requirements, unassessed qualifications, unknown experience, incomplete inputs, and unreadable candidates prevent an unqualified recommendation. Numeric star ratings are not displayed as confidence. Complex phrasing and unsupported terminology still need manual review; no measured real-world accuracy is claimed.

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
| macOS | Chrome, Firefox, Edge |
| Linux | Firefox, Chrome, Edge |

Automatic job-page parsing uses a supported browser in headless mode, without opening a visible window. Safari is not used for automatic fallback because it does not support this mode. If a site blocks automated access, use Paste JD. Google authorization may still open a browser when you explicitly connect or reconnect Gmail.

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

Google then creates a local `token.json`. Later synchronizations reuse that token. If authorization is revoked or the token becomes invalid, automatic synchronization asks you to reconnect with **Sync Gmail**. A successful manual authorization replaces the local token.

JobTrack requests only this Gmail scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

## Using JobTrack

### 1. Import application history

Select **Sync Gmail** and complete Google authorization if prompted. Wait until the footer displays `Last synced at ...`.

### 2. Manage resumes

Select **＋ Add resume** above the Resume table to add local files. Double-click a row to enable or disable it. JobTrack infers each resume's work direction from responsibility and project evidence in its text. Select the row's Edit icon to rename it or replace its file, or select its Delete icon to remove the saved reference. Removing an entry does not delete the original file.

### 3. Check a job

Paste a complete public job URL into Job check and analysis begins automatically. If the retrieved description is missing or incomplete, use **Add JD** in the **Paste JD** tab, complete the independent form, and select **Analyze JD**. Reopen the form with **Edit JD** to revise the saved draft. **Review JD** shows the description used by assessment. JobTrack checks all imported application history and compares enabled resumes. Use **Clear** to remove the current inputs and result.

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
