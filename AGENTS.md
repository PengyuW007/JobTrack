# Repository privacy rules

- Never commit, stage, print, or paste the contents of OAuth credentials, access tokens, API keys, local databases, or personal resumes.
- Keep `credentials.json`, `credentials*.json`, `client_secret*.json`, `token.json`, `token*.json`, `.env*`, `tracker.db`, `*.sqlite*`, `resumes/`, `private/`, `*.pdf`, and `*.docx` out of Git.
- API keys must remain in the operating system credential store through `keyring`; never add a key to source code, settings files, tests, logs, screenshots, or documentation.
- Before committing or pushing, inspect tracked files and Git history for secret patterns. Report only affected file paths and commit identifiers; never print a discovered secret value.
- Treat resume text, application history, email content, and generated local databases as private user data.
- GitHub releases must contain application code and public documentation only. Users must supply their own Google OAuth credentials and authorization token locally.
- Windows may use `Start JobTrack.vbs`. Do not present that launcher as compatible with macOS or Linux.
- Browser-based parsing must not require Google Chrome specifically. Prefer automatic selection among supported installed browsers and document any browser automation requirements.

# Commit message rules

Follow the Areone Development Handbook commit standard for every commit:
https://github.com/PengyuW007/Areone-Development-Handbook/blob/main/Guidance/Commit_Message_Guide.md

- Use the format `<type>: <short summary>`.
- Use one of these types: `feat`, `fix`, `refactor`, `perf`, `docs`, `style`, `test`, `chore`, `build`, `ci`, `ops`, or `revert`.
- Write the summary in English, in imperative mood, and describe the concrete change.
- Keep the summary between 50 and 72 characters when practical.
- Do not end the summary with a period.
- Keep each commit limited to one logical change. Split unrelated work into separate commits.
- For larger commits, add a concise body with bullet points describing the major changes.
- Before committing, confirm that the project builds, compilation succeeds, tests pass, debug code is removed, and no secrets or passwords are staged.
