# JobTrack Single Source of Truth

**Status:** Active  
**Owner:** Project owner  
**Last reviewed:** 2026-09-20  
**Review cadence:** Update during every AI-assisted repository task that makes a decision or change; review the complete document quarterly.

This root document is the authoritative source for JobTrack's product charter, scope, architecture decisions, delivery roadmap, ownership, decisions, implementation changes, verification results, and RAID log. Every AI-assisted repository task must update the applicable current-state section and append its decisions and changes to the log before the task is considered complete.

## Authority boundaries

| Information | Authoritative source |
| --- | --- |
| Product vision, scope, decisions, roadmap, ownership, and RAID | This document |
| Agent working rules, privacy constraints, and commit rules | `AGENTS.md` |
| Repository structure, integration points, and change routing | `REPO_MAP.md` |
| Installation and end-user instructions | `README.md` |
| Implemented behavior | Application code and passing tests |

If these sources disagree, do not silently select one. Record the discrepancy as an Issue in the RAID log, determine whether the implementation or the intended product behavior is wrong, and update all affected documents in the same logical change.

## 1. Core and context

### Project charter

**Vision:** Give job seekers a private desktop workspace for checking opportunities, reviewing prior applications, and selecting the most relevant local resume from evidence they can inspect.

**Business goals:**

- Reduce accidental duplicate applications by searching complete local application history.
- Reduce the effort required to choose among a user's existing resumes.
- Keep resumes, job descriptions, Gmail content, and application history local unless a future feature introduces an explicit consent flow.
- Provide conservative, explainable assistance rather than hiring predictions or unsupported claims of eligibility.

**Primary deliverables:**

- A cross-platform Python desktop application with local application tracking and funnel reporting.
- Read-only Gmail synchronization for application evidence.
- Public job-page and pasted-JD analysis with duplicate/repost detection.
- Local deterministic resume comparison for software and general occupations.

### Product requirements and scope

**In scope:**

- Local management of PDF, DOCX, TXT, and Markdown resumes.
- Comparison of every enabled and readable resume before choosing a leading candidate.
- A dedicated technical matcher that preserves the established software-role behavior.
- A separate general matcher that accepts unknown English occupation and tool names, compares responsibilities and requirements, and treats missing evidence as review rather than rejection.
- Explicit handling of duties, transferable skills, tools, credentials or licences, education, experience duration, Must-have requirements, and Nice-to-have requirements.
- Rejection of unfilled recruiting placeholders, preference for complete visible JD content over stale structured templates, JSON-LD and schema.org HTML microdata parsing, and separation of assessment content from company, compensation, benefits, culture, and equity text.
- Existing workbench presentation for both matchers; matcher expansion does not require additional panels or controls. The summary limits compact tags rather than expanding into the Review JD control or adding rows.

**Out of scope for the current General Resume Matching initiative:**

- Changes to the workbench layout or new resume-analysis UI controls.
- Changes to the established technical matcher's ranking and Skip behavior.
- External AI or transmission of job descriptions, resumes, email content, or application records.
- Automatic job applications, resume rewriting, recruiter scoring, or predictions of hiring outcomes.
- Claims of reliable support for every language. The current deterministic general matcher supports English and reports unsupported input as unable to assess.
- Automatic verification of credential validity, licence jurisdiction, education equivalence, or work authorization.

## 2. Execution and standards

### Architecture and infrastructure

JobTrack is a local Tkinter application. `JobTrack.pyw` calls `main.main()`, which creates the SQLite data layer and workbench. Gmail synchronization and public job-page retrieval are the only routine network operations. Resume matching runs locally.

Resume analysis has three boundaries:

1. `business/ResumeAdvisor.py` reads resume files, selects one matcher for the complete comparison, and preserves the workbench result contract.
2. `business/TechnicalResumeMatcher.py` owns the established software-role rules and ranking.
3. `business/GeneralResumeMatcher.py` owns conservative open-vocabulary matching for other occupations.

Routing must use explicit software titles or owned software duties. A tool name by itself must not route an accounting, healthcare, sales, manufacturing, or other general occupation to the technical matcher.

Public-page retrieval treats placeholder descriptions as incomplete, parses JSON-LD and schema.org HTML microdata, can recover a complete visible description from known job-content containers, and retries the next installed supported browser after a browser runtime failure. General-job parsing recognizes common job-board responsibility and qualification headings, excludes non-assessment sections, normalizes English inflectional forms, recognizes professional designations, and supplies separate responsibility and compact qualification lists to the existing workbench.

**Environments:**

| Environment | Purpose | Data and deployment |
| --- | --- | --- |
| Development | Feature branches in the saved local checkout | Synthetic test data; no private resumes, databases, OAuth files, or tokens. Use a linked worktree only when the project owner explicitly requests isolated parallel work |
| Test | Local `unittest` and compile checks | Temporary and synthetic fixtures; there is no shared staging service |
| Production | An authorized user's local checkout | Local SQLite database, resumes, and OAuth files supplied by that user |

**External dependencies and network boundaries:**

- Gmail API through read-only OAuth.
- Public job pages through guarded HTTP retrieval and supported headless browsers.
- Local libraries listed in `requirements.txt`, including Matplotlib, pypdf, Requests, and Selenium.
- No network dependency for resume comparison.

### Standard operating procedure

1. Start repository work by reading `REPO_MAP.md`, then this document and the relevant source and tests.
2. Define the requested outcome and smallest expected file set.
3. Create or select the approved feature branch from the intended base before editing application code.
4. Preserve unrelated and user-owned working-tree changes.
5. Update tests that express the changed behavior. Use synthetic data and never add private resumes or application content.
6. Run the narrowest relevant tests, then the complete suite when practical. Inspect the diff for scope creep.
7. During every AI-assisted repository task, update this document for each product, scope, architecture, behavior, implementation, test, risk, assumption, issue, or dependency decision and change. Record the outcome and verification before finishing the task.
8. Update `REPO_MAP.md` when architecture or change routing changes, and update `README.md` when installation or user-visible behavior changes.
9. Follow the commit, privacy, and external-analysis rules in `AGENTS.md`.

## 3. Timeline and resources

### Master roadmap

| Milestone | Status | Exit criteria |
| --- | --- | --- |
| Local application tracking and Gmail evidence | Delivered | Local schema, read-only sync, consolidation, and funnel behavior are covered by tests |
| Duplicate and repost checking | Delivered | Exact URL and evidence-based likely repost checks operate across complete history |
| Technical resume matching | Delivered | Existing software-role regression suite passes |
| General resume matcher isolation | In progress | Advisor dispatches between isolated technical and general matchers without changing the workbench |
| Cross-industry validation | Delivered for the fixed set | Nine industries, 18 role cases, adversarial input boundaries, filename/order invariance, and technical golden regression meet the recorded acceptance thresholds |
| General matcher hardening | In progress | Requirement parsing, experience scope, credential review, routing boundaries, and false-positive cases meet acceptance tests; additional real-world job-board fixtures remain useful |
| Additional language packs | Unscheduled | A language is enabled only after dedicated parsing and regression fixtures exist |

### RACI matrix

| Activity | Responsible | Accountable | Consulted | Informed |
| --- | --- | --- | --- | --- |
| Product vision and scope | Project owner | Project owner | Repository contributors | Authorized users |
| Architecture and implementation | Repository contributor performing the change | Project owner | Reviewers | Authorized users |
| Privacy and release approval | Project owner | Project owner | Repository contributors | Authorized users |
| Tests and technical documentation | Repository contributor performing the change | Project owner | Reviewers | Authorized users |
| SSOT maintenance | Repository contributor changing a governed fact | Project owner | Reviewers | Authorized users |

One person may occupy several roles. Accountability remains with the project owner.

## 4. Records and changes

### AI decision and change log

Append one row for every AI-assisted task that makes a decision or changes repository content. Combine closely related edits into one task-level row, and record the outcome and verification. Commands, file reads, formatting-only actions, and abandoned experiments do not require separate rows. Git history remains the line-by-line code history.

| Date | Decision or change | Reason | Outcome and verification | Decision owner |
| --- | --- | --- | --- | --- |
| 2026-09-20 | Established this repository SSOT and its governance links | Prevent product, architecture, and delivery decisions from drifting across documents | SSOT created and linked from `AGENTS.md`, `README.md`, and `REPO_MAP.md`; references validated | Project owner |
| 2026-09-20 | Isolated technical and general resume matching behind `ResumeAdvisor` | Preserve established software-job behavior while supporting other occupations | Technical functions stayed structurally identical; full suite passed 102 tests with 1 skip before SSOT-only edits | Project owner |
| 2026-09-20 | Kept the current workbench unchanged for general matching | The existing result presentation already communicates the feature without extra UI | `visualization/Workbench.py` remained unchanged and formatter compatibility is tested | Project owner |
| 2026-09-20 | Made missing or unrecognized evidence a review outcome in the general matcher | Absence of resume text is not reliable proof of a mismatch | General matcher returns Consider or unable to assess for unsupported evidence; cross-industry tests pass | Project owner |
| 2026-09-20 | Moved `SSOT.md` to the repository root and required task-level AI logging | Match the project's EventGo-Ops-style operating model and make the authority immediately visible | All repository references updated; Markdown references and diff checks validated | Project owner |
| 2026-09-20 | Moved the General Resume Matching task to the saved local checkout and removed its linked worktree | Keep PyCharm, GitHub Desktop, Codex, and branch switching in `D:/4 - Projects/2026/JobTrack` | Local checkout contains the feature branch and all 8 changes; old worktree was clean before removal and no longer appears in `git worktree list` | Project owner |
| 2026-09-20 | Created an ignored local synthetic marketing resume for functional testing | Let the project owner exercise general-occupation resume import and matching without using personal data | TXT resume stored under the Git-ignored `resumes/` directory; local reader and marketing-JD assessment verified | Project owner |
| 2026-09-20 | Hardened public JD retrieval and general-job section presentation | Stale structured templates and unrecognized job-board headings caused complete visible JDs to be missed and non-assessment text to fill Core skills | Placeholder structured text now yields to complete visible content or browser fallback; browser runtime failures try the next candidate; general responsibilities and qualifications exclude metadata, company, benefits, culture, and equity sections and render as bullets; targeted suite ran 59 tests with 58 passed and 1 display-only skip, full suite ran 110 tests with 109 passed and 1 display-only skip, and compilation passed | Project owner |
| 2026-09-20 | Added a fixed nine-industry validation gate and tested 18 current public company postings | Measure general matching against explicit acceptance criteria without treating volatile web pages or copied vacancy text as a reproducible benchmark | Technical golden cases remained 10/10; fixed cross-industry top-choice permutations scored 68/72 (94.44%) and failed the 95% gate because education delivery containing `learning` was filtered; Must-have/Nice-to-have and requirement-type labels scored 53/54 (98.15%); unresolved Must-have false Recommended, false Skip for unknown/missing/unsupported input, evidence traceability, and low-quality input gates all passed. JobTrack retrieved 0/18 SmartRecruiters pages even though the public pages were discoverable, so live acquisition remains a blocking issue. These are fixed-set engineering metrics, not real-world hiring accuracy | Project owner |
| 2026-09-20 | Fixed inflectional evidence filtering and professional-designation classification | Delivered education evidence such as `planned learning activities` was being dropped, and `CPA designation` was not classified as a credential | Added conservative intent-only learning detection, doubled-consonant normalization for English `-ed/-ing` forms, and designation/accreditation recognition; fixed validation now passes 18/18 top choices, 100% filename/input-order invariance, 54/54 requirement classifications, and the technical golden cases remain 10/10 | Project owner |
| 2026-09-20 | Added schema.org HTML microdata fallback for public job pages | Current SmartRecruiters pages expose JobPosting microdata instead of the JSON-LD script shape used by the original parser | `DuplicateService` now reads microdata title, organization, and description before browser fallback; the SmartRecruiters validation set was re-run with current accessible company postings and returned complete descriptions for 18/18 pages; the parser regression suite and full suite pass | Project owner |
| 2026-09-20 | Created a local synthetic marketing manual-test pack | Give the project owner a safe, repeatable UI smoke test without using personal resumes or real applicant data | Added one fictional JD plus matched, transferable-skills, and unrelated TXT resumes under ignored `private/manual_test/` and `resumes/` paths; local recommendation returned the matched resume as Recommended and retained gaps for the other two; files are intentionally not tracked or uploaded | Project owner |
| 2026-09-20 | Corrected long job-tag layout and zero-evidence general resume ties | Long qualification tags could extend beneath Review JD, while incidental word overlap could label unrelated technical resumes as two comparable options for a marketing job | Existing tags now wrap in a bounded two-column grid; an explicitly supplied title is removed from the JD body when duplicated; equally ranked zero-delivery-evidence comparisons remain Review without naming arbitrary options, while a uniquely relevant candidate can still be named for review; targeted suite passed 38 tests with 1 display-only skip, full suite passed 118 tests with 1 display-only skip, and compilation passed | Project owner |
| 2026-09-20 | Replaced multi-row job tags with a bounded single-row summary | Manual UI verification showed that wrapped tags consumed vertical space and were clipped at the panel boundary | Job summary now displays at most two tags, truncates each compact label to 24 characters, and leaves complete requirements available through Review JD; the zero-evidence five-resume result was confirmed as the intended conservative Review outcome; targeted suite passed 38 tests with 1 display-only skip, full suite passed 118 tests with 1 display-only skip, and compilation passed | Project owner |
| 2026-09-20 | Reserved Shift+Enter for line breaks in the Paste/Edit JD editor | The key combination propagated to the dialog submit binding and closed the editor during multiline editing | The text widget now inserts a newline and stops propagation for main-keyboard and keypad Shift+Enter; Analyze JD, Ctrl+Enter, and Command+Enter remain the explicit submission paths; workbench suite passed 21 tests with 1 display-only skip, full suite passed 119 tests with 1 display-only skip, and compilation passed | Project owner |
| 2026-09-20 | Made Analyze JD the editor's only submission action | The current editor has an explicit button, so keyboard Enter combinations should remain exclusively available for multiline editing | Removed dialog-level Ctrl+Enter and Command+Enter submission bindings and the no-longer-needed Shift+Enter override; ordinary Text widget editing now owns all Enter variants; workbench suite passed 20 tests with 1 display-only skip, full suite passed 118 tests with 1 display-only skip, and compilation passed | Project owner |

### RAID log

| ID | Type | Status | Description | Mitigation or next action | Owner |
| --- | --- | --- | --- | --- | --- |
| R-001 | Risk | Open | Routing a general occupation to the technical matcher could change its ranking behavior | Require explicit software context and maintain boundary regression tests | Engineering |
| R-002 | Risk | Open | Open-vocabulary overlap can confuse similar words with equivalent duties | Require owned responsibility evidence and add adversarial cross-industry fixtures | Engineering |
| R-003 | Risk | Accepted | The general matcher currently supports deterministic English rules only | Return unable to assess for unsupported language; add language packs only with tests | Product owner |
| R-004 | Risk | Open | PDF extraction order or image-only documents can hide resume evidence | Report unreadable or empty extraction and prevent an unqualified recommendation | Engineering |
| A-001 | Assumption | Active | Enabled resumes are the complete set the user wants compared for the current check | Continue comparing every enabled readable resume and report unreadable files | Product owner |
| A-002 | Assumption | Active | A pasted or retrieved JD contains enough responsibilities and requirements to support comparison | Return more information needed when input is incomplete | Product owner |
| I-001 | Issue | Open | There is no shared staging environment or automated CI workflow | Use the documented local test command; reassess when packaging or release automation begins | Engineering |
| D-001 | Dependency | Active | Gmail sync depends on Google OAuth and the Gmail API | Keep credentials user-supplied and local; retain read-only scope | Product owner |
| D-002 | Dependency | Active | Some job pages depend on an installed supported browser and site behavior | Preserve guarded direct retrieval, visible-content recovery, automatic browser retry, and Paste JD fallback | Engineering |
| I-002 | Issue | Resolved | Current SmartRecruiters pages exposed schema.org HTML microdata rather than the JSON-LD shape used by the original parser | Parse schema.org microdata and retain browser/Paste JD fallback; current validation returned complete descriptions for 18/18 pages | Engineering |
| I-003 | Issue | Resolved | The general matcher treated the word `learning` as aspirational even inside delivered education experience | Scope aspiration detection to intent phrases and normalize doubled consonants in English inflectional forms; fixed validation now passes 18/18 top choices and filename/order invariance | Engineering |
| I-004 | Issue | Resolved | `CPA designation` was classified as a general responsibility rather than a professional credential | Recognize professional designations and accreditation terms; requirement classification now passes 54/54 fixed cases | Engineering |

## Maintenance rules

- Use ISO dates (`YYYY-MM-DD`).
- Append every task-level AI decision and repository change to the log; do not rewrite history to make a later decision appear original.
- Give every RAID entry a stable ID and update its status rather than creating duplicates.
- Update the current-state sections as behavior evolves, then append the task outcome and verification to the AI decision and change log.
- Keep line-by-line implementation history in Git commits and tests. The SSOT records why a task changed the repository and what result was verified.
- Never place credentials, tokens, personal resume content, email content, application history, or other private user data in this document.
