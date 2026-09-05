# Repository privacy rules

- Never commit, stage, print, or paste the contents of OAuth credentials, access tokens, API keys, local databases, or personal resumes.
- Keep `credentials.json`, `credentials*.json`, `client_secret*.json`, `token.json`, `token*.json`, `.env*`, `tracker.db`, `*.sqlite*`, `resumes/`, `private/`, `*.pdf`, and `*.docx` out of Git.
- API keys must remain in the operating system credential store through `keyring`; never add a key to source code, settings files, tests, logs, screenshots, or documentation.
- Before committing or pushing, inspect tracked files and Git history for secret patterns. Report only affected file paths and commit identifiers; never print a discovered secret value.
- Treat resume text, application history, email content, and generated local databases as private user data.
- GitHub releases must contain application code and public documentation only. Users must supply their own Google OAuth credentials and authorization token locally.
- Windows may use `Start JobTrack.vbs`. Do not present that launcher as compatible with macOS or Linux.
- Browser-based parsing must not require Google Chrome specifically. Prefer automatic selection among supported installed browsers and document any browser automation requirements.
