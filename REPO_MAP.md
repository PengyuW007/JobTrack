# JobTrack repository map

This is the read-first map for scoping changes. Confirm details in the relevant source file before editing; the map is orientation, not a substitute for code inspection.

## What the application is

JobTrack is a local Python desktop application. It imports job-related Gmail messages through read-only OAuth, stores normalized application data and evidence in a local SQLite database, displays an application funnel, checks new job URLs against prior applications, and recommends among user-selected resumes with local deterministic rules.

The public edition keeps job descriptions, resume contents, Gmail contents, and application history local. `tracker.db`, OAuth files, environment files, and resumes are private runtime data and must not enter Git or logs.

## Runtime architecture

```text
JobTrack.pyw
    -> main.main()
        -> DataAccess creates/migrates tracker.db
        -> Workbench builds the Tkinter UI

User selects Sync Gmail
    -> main.synchronize_gmail()
        -> Google OAuth + Gmail API (read-only)
        -> gmail/gmail_service.py decodes messages and dates
        -> EmailClassifier + EmailParser
        -> DataAccess writes jobs, evidence, and sync metadata
        -> Workbench refreshes the funnel

While JobTrack remains open
    -> Workbench schedules the same Gmail sync at Toronto midnight

User pastes a public job URL
    -> DuplicateService.fetch_posting()
        -> direct HTTP request
        -> Selenium browser fallback when needed
        -> JobPosting structured-data parsing
    -> DuplicateService.search()
        -> all local application history and saved evidence
    -> ResumeAdvisor.recommend()
        -> reads enabled local resume files
        -> performs local deterministic matching
    -> Workbench presents history and recommendation
```

## Directory and module responsibilities

| Path | Responsibility |
| --- | --- |
| `JobTrack.pyw` | GUI launcher. Changes the working directory to the repository root and calls `main.main()`. |
| `main.py` | Composition root, Google OAuth, Gmail synchronization, classification, parsing, and persistence orchestration. |
| `business/` | Domain services: funnel analytics, email classification, job-page retrieval/duplicate matching, and local resume recommendation. |
| `gmail/gmail_service.py` | Gmail header lookup, message-body extraction, and Toronto timezone conversion. |
| `objects/JobApplication.py` | Application record object shared by parsing and persistence. |
| `parsers/EmailParser.py` | Extracts company and position and generates an application key from email content. |
| `persistence/DataAccess.py` | SQLite connection, schema creation/migration, synchronization metadata, evidence, snapshots, settings, and resume records. |
| `persistence/DataAccessJob.py` | Read queries that turn job rows into `JobApplication` objects. |
| `visualization/Workbench.py` | Main Tkinter interface, background workers, event polling, job checking, resume management, Gmail sync controls, and embedded chart. |
| `visualization/DateRangeDialog.py` | Date validation and calendar/date-range UI. |
| `visualization/FunnelChart.py` | Standalone Matplotlib funnel renderer; the main workbench currently renders its embedded chart directly. |
| `tests/` | `unittest` coverage for duplicate detection, schema behavior, parsing/classification, resume management, and local resume advice. |
| `requirements.txt` | Runtime dependency ranges. |
| `README.md` | User installation, macOS/Windows startup, OAuth setup, feature behavior, privacy, and test commands. |
| `Start JobTrack.vbs` | Windows-only launcher; never use or advertise it for macOS/Linux. |

No packaging configuration, Makefile, or CI workflow is currently tracked.

## Data ownership and persistence

`DataAccess.create_tables()` owns the SQLite schema. The main tables are:

- `jobs`: one consolidated row per application key.
- `application_evidence`: complete supporting Gmail evidence per message.
- `posting_snapshots`: job URL/company/title/description snapshots used for repost matching.
- `resumes`: display names, local file paths, enabled state, and update dates; resume contents are not copied into the database.
- `sync_metadata`, `gmail_scan_progress`, and `evidence_metadata`: incremental/rebuild synchronization state.
- `app_settings`: local key/value application settings.

Database changes must remain backward compatible because schema upgrades run against a user's existing local `tracker.db`. Add or reuse migration logic in `DataAccess.create_tables()` and test idempotency.

## External integrations

- Google OAuth and Gmail API: configured locally with `credentials.json`; produces `token.json`; scope is `gmail.readonly`.
- Public job pages: fetched with `requests` after URL and public-IP validation.
- Browser fallback: Selenium tries Safari, Chrome, Firefox, then Edge on macOS. Safari may require **Develop > Allow Remote Automation**.
- Resume formats: TXT/Markdown via standard file reads, DOCX via ZIP/XML extraction, and PDF via `pypdf`.

Never add an external analysis provider or transmit private job, resume, email, or application data without the explicit consent flow required by `AGENTS.md`.

## Common commands

macOS setup with Python 3.11 or newer:

```bash
python3 -m venv venv
venv/bin/python3 -m pip install --upgrade pip
venv/bin/python3 -m pip install -r requirements.txt
```

Run the desktop application from the repository root:

```bash
venv/bin/python3 JobTrack.pyw
```

Run all tests:

```bash
venv/bin/python3 -m unittest discover -s tests -v
```

Compile-check tracked Python sources without starting the GUI:

```bash
venv/bin/python3 -m compileall -q business gmail objects parsers persistence visualization main.py JobTrack.pyw
```

## Change routing

- Gmail import behavior: begin with `main.py`, then the Gmail helper, classifier/parser, and persistence tests.
- Duplicate/repost behavior or job-board parsing: begin with `business/DuplicateService.py` and `tests/test_duplicates.py`.
- Resume file reading/scoring: begin with `business/ResumeAdvisor.py` and `tests/test_resume_advisor.py`.
- Funnel counts/date filtering: begin with `business/AnalyticsService.py`, `persistence/DataAccessJob.py`, and the chart-related workbench methods.
- Main-window behavior/layout: begin with `visualization/Workbench.py`; check whether an existing builder, worker, or event handler can be extended before adding one.
- Schema or saved settings: begin with `persistence/DataAccess.py`; preserve existing databases and add migration coverage.

## Known risk areas

- OAuth credentials, tokens, databases, email bodies, and resumes are private. Do not print or inspect their contents during ordinary diagnostics.
- Gmail synchronization performs schema writes and can trigger a full-history rebuild when classifier metadata changes.
- Duplicate detection intentionally searches all history even when the chart is date-filtered; do not couple these scopes.
- URL fetching includes SSRF defenses, redirect limits, response-size limits, and browser fallback. Preserve those controls when changing parsing.
- Tkinter must be updated on the UI thread. Background work reports results through `Workbench.events` and `poll()`.
- Browser automation varies by OS and installed browsers; do not require Chrome specifically.
- `JobTrack.pyw` sets the repository root as the working directory, so direct `main.py` execution from another directory is not equivalent.
- The repository declares Python 3.11+ and requires a Python build with Tk support.

## First 10 files to inspect

1. `AGENTS.md` — task boundaries, privacy, external-analysis, and commit rules.
2. `REPO_MAP.md` — architecture and change-routing overview.
3. `README.md` — supported user behavior and platform instructions.
4. `JobTrack.pyw` — normal desktop entry point.
5. `main.py` — composition and Gmail synchronization.
6. `visualization/Workbench.py` — main UI and asynchronous orchestration.
7. `persistence/DataAccess.py` — schema and local state writes.
8. `business/DuplicateService.py` — job-page parsing and history matching.
9. `business/ResumeAdvisor.py` — local resume parsing and recommendation.
10. `tests/test_duplicates.py` and `tests/test_resume_advisor.py` — executable behavior contracts.
