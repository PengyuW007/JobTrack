import re
import zipfile
from xml.etree import ElementTree
from pathlib import Path

SKILLS = {
    "account management", "accounting", "agile", "analytics", "aws", "azure",
    "budgeting", "business analysis", "c#", "c++", "care planning", "case management",
    "ci/cd", "clinical", "communication", "content marketing", "crm", "customer service",
    "data analysis", "design patterns", "digital marketing", "docker", "domain-driven design",
    "e-commerce", "excel", "financial analysis", "gcp", "git", "graphic design", "healthcare",
    "human resources", "inventory", "java", "javascript", "kubernetes", "lead generation",
    "leadership", "linux", "machine learning", "marketing", "microsoft office", ".net", "node",
    "operations", "pandas", "patient care", "payroll", "power bi", "project management",
    "python", "react", "recruiting", "rest", "sales", "salesforce", "scheduling", "scrum",
    "social media", "spark", "sql", "supply chain", "tableau", "teaching", "terraform",
    "typescript", "user research", "ux", "vue", "writing",
    "flutter", "android", "ios", "swift", "kotlin", "playwright",
    "api testing", "regression testing", "test automation", "fastapi", "postgres",
    "react native", "next.js", "graphql", "mongodb", "express", "spring boot",
    "spring", "angular", "html", "css", "redis", "mysql", "selenium", "pytest",
    "jdbc", "cdc", "query optimization", "schema evolution", "replication", "etl",
}

SKILL_ALIASES = {
    "node": ("node", "node.js", "nodejs"),
    "next.js": ("next.js", "nextjs", "next js"),
    "postgres": ("postgres", "postgresql"),
    "javascript": ("javascript",),
    "typescript": ("typescript",),
    "spring boot": ("spring boot", "springboot"),
    "rest": ("rest", "restful"),
    "cdc": ("cdc", "change data capture"),
    "ci/cd": ("ci/cd", "ci cd", "continuous integration", "continuous delivery"),
}

SPECIALIZATIONS = {
    "full stack": (
        "fullstack", "full stack", "full-stack",
    ),
    "frontend": ("frontend", "front end", "front-end", "web frontend", "web interfaces"),
    "backend": ("backend", "back end", "back-end", "server side", "backend api"),
    "mobile": ("mobile", "android", "ios", "flutter", "react native"),
    "software": ("sde", "software developer", "software engineer"),
    "qa": (
        "qa", "quality assurance", "quality engineer", "quality engineering",
        "software quality", "quality automation", "automation tools",
        "test automation", "automation tester", "automation engineer",
        "test engineer", "software engineer in test", "sdet", "tester",
        "api testing", "regression testing",
    ),
    "data": ("data", "analytics"),
    "finance": ("finance", "financial", "accounting", "bookkeeper"),
    "marketing": ("marketing", "content", "seo", "social media"),
    "sales": ("sales", "account executive", "business development"),
    "operations": ("operations", "supply chain", "logistics", "procurement"),
    "human resources": ("human resources", "hr", "recruiter", "talent acquisition"),
    "healthcare": ("healthcare", "nurse", "clinical", "patient care"),
    "design": ("designer", "design", "ux", "ui"),
    "customer service": ("customer service", "customer success", "support specialist"),
    "project management": ("project manager", "program manager", "project management"),
}

ROLE_LABELS = tuple(label for label in SPECIALIZATIONS if label != "software")
_HEADINGS = re.compile(
    r"^[ \t]*(nice[ -]to[ -]have|preferred qualifications|preferred skills|bonus points|"
    r"what we offer|benefits|about [^\n:]+|our values|we are challengers|we are united|we care|"
    r"what.s in it for you|please note|what you (?:can )?bring|"
    r"our engineering culture|fraud warning|to all recruitment agencies|"
    r"what we.re looking for|what you(?:.ll| will) need|required qualifications|requirements|qualifications|must[ -]have|"
    r"what you(?:.ll| will) do(?: in a typical day)?|responsibilities|your responsibilities|the role)[ \t]*(?::|$)",
    re.IGNORECASE | re.MULTILINE,
)
_OPTIONAL = {"nice to have", "preferred qualifications", "preferred skills", "bonus points"}
_IGNORE = {"what we offer", "benefits", "about us", "about the company", "our values",
           "we are challengers", "we are united", "we care", "what’s in it for you",
           "what's in it for you", "our engineering culture", "fraud warning",
           "to all recruitment agencies"}
_ACTION = re.compile(
    r"\b(build(?:s|ing)?|built|develop(?:s|ed|ing)?|deliver(?:s|ed|ing)?|"
    r"implement(?:s|ed|ing)?|maintain(?:s|ed|ing)?|creat(?:e|es|ed|ing)|"
    r"automat(?:e|es|ed|ing)|test(?:s|ed|ing)?(?!\s+(?:automation|engineer|tools))|"
    r"design(?:s|ed|ing)?(?!\s+(?:patterns|systems))|deploy(?:s|ed|ing)?|led|"
    r"lead(?:s|ing)?|manage(?:s|d)?|managing|plan(?:s|ned|ning)?|"
    r"support(?:s|ed|ing)?|writ(?:e|es|ing)|wrote|debug(?:s|ged|ging)?|"
    r"troubleshoot(?:s|ing)?|diagnos(?:e|ed|ing)|responsible for)\b", re.IGNORECASE,
)


def core_job_description(description):
    """Remove job-board recommendation/search content appended after the JD."""
    return re.split(
        r"(?:\n\s*|\s{2,})(?:show more show less|seniority level|similar jobs|people also viewed|similar searches)\b",
        description or "",
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]


def detected_specializations(text):
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", text.casefold())
    padded = f" {normalized} "
    detected = set()
    for label, aliases in SPECIALIZATIONS.items():
        for alias in aliases:
            alias_normalized = re.sub(r"[^a-z0-9+#.]+", " ", alias.casefold()).strip()
            if f" {alias_normalized} " in padded:
                detected.add(label)
                break
    return detected


def read_resume(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join("".join(node.itertext()) for node in document.findall(".//w:p", namespace))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import DependencyError, PyPdfError
        except ImportError as error:
            raise ValueError("PDF support requires: pip install pypdf") from error
        try:
            return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        except (DependencyError, PyPdfError) as error:
            raise ValueError("PDF text could not be extracted") from error
    raise ValueError("Supported formats: PDF, DOCX, TXT, MD")


def detected_skills(text):
    # React Native is a separate skill; it does not prove Web React experience.
    text = re.sub(r"\breact\s+native\b", "react_native", text, flags=re.IGNORECASE)
    found = {skill for skill in SKILLS
             if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.IGNORECASE)
                    for alias in SKILL_ALIASES.get(skill, (skill,)))}
    if "react_native" in text.casefold():
        found.add("react native")
    if "spring boot" in found:
        found.discard("spring")
    return found


def job_sections(description):
    core, optional = [], []
    for heading, body in _section_blocks(description):
        if heading in _OPTIONAL:
            optional.append(body)
        elif heading not in _IGNORE:
            for sentence in _sentences(body):
                if re.search(r"\b(?:not required|not necessary|do not need)\b", sentence, re.I) and not re.search(r"\b(?:but|and|however)\b|;", sentence, re.I):
                    continue
                if re.search(r"\b(?:preferred|nice[ -]to[ -]have|a plus|big plus|optional)\b", sentence, re.I) and not re.search(r"\b(?:must|required|essential)\b", sentence, re.I):
                    optional.append(sentence)
                else:
                    core.append(sentence)
    return "\n".join(core), "\n".join(optional)


def _section_blocks(description):
    parts = _HEADINGS.split(description)
    return [("", parts[0])] + [("the role" if heading.strip().casefold() in
                               {"about this role", "about the role", "about this position", "about the position", "about the job"} else
                               "about us" if heading.casefold().startswith("about ") else
                               "requirements" if heading.strip().casefold() in {"what you bring", "what you can bring", "what you'll need", "what you’ll need", "what you will need", "required qualifications"} else heading.strip().casefold().replace("-", " "), body)
                               for heading, body in zip(parts[1::2], parts[2::2])]


def _sentences(text):
    # Preserve dots inside .NET, Next.js and version names.
    return [sentence.strip(" \t\r•-*:") for sentence in
            re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", text) if sentence.strip()]


def _role_evidence(text, duties_only=False):
    evidence = {}
    for sentence in _sentences(text):
        # A collaboration target is not the work owned by this role.
        owned = re.split(r"\b(?:collaborat\w*|partner\w*|work(?:ing) with)\b", sentence,
                         maxsplit=1, flags=re.IGNORECASE)[0]
        if duties_only and re.search(r"\b(?:years?\b.*\bexperience|experience\s+(?:in|as|with)|background in)\b", owned, re.I):
            continue
        if duties_only and not _ACTION.search(owned):
            continue
        if duties_only and re.match(r"support\w*\s+(?:colleagues|teams|developers)", owned, re.I):
            continue
        roles = detected_specializations(owned) - {"software"}
        if duties_only:
            roles &= {"full stack", "frontend", "backend", "mobile", "qa"}
        if _ACTION.search(owned):
            if re.search(r"\b(?:web (?:interfaces|ui|screens)|frontend)\b", owned, re.I) or (
                    "react" in detected_skills(owned) and re.search(r"\b(?:web|interfaces?|screens?|frontend)\b", owned, re.I)):
                roles.add("frontend")
            if re.search(r"\b(?:apis?|endpoints?|microservices|server-side|backend|(?:python|java|node) services|(?:database|jvm(?:-based)?) connectors?|connector code)\b", owned, re.I):
                roles.add("backend")
            if re.search(r"\b(?:build|built|develop\w*|maintain\w*|creat\w*)\s+(?:\w+\s+){0,2}(?:automated tests|test automation|regression tests|api tests)\b", owned, re.I):
                roles.add("qa")
        # Routine design/data words are not career directions in engineering prose.
        if _ACTION.search(owned) and "design" in roles and not re.search(r"\b(?:ux|ui|designer|user research|graphic design)\b", owned, re.I):
            roles.discard("design")
        if "data" in roles and not re.search(r"\b(?:data (?:analyst|scientist|engineer|analysis|pipelines)|analytics)\b", owned, re.I):
            roles.discard("data")
        for role in roles:
            evidence.setdefault(role, []).append(sentence)
    if {"frontend", "backend"} <= evidence.keys():
        evidence.setdefault("full stack", evidence["frontend"] + evidence["backend"])
    return evidence


def _requirements(description):
    required, optional = [], []
    for heading, body in _section_blocks(description):
        if heading in _IGNORE:
            continue
        for sentence in _sentences(body):
            is_optional = heading in _OPTIONAL or bool(re.search(r"\b(?:preferred|nice[ -]to[ -]have|a plus|big plus|bonus|optional)\b", sentence, re.I))
            is_required = heading in {"requirements", "qualifications", "must have", "what we’re looking for", "what we're looking for"} or bool(re.search(r"\b(?:required|must|strong|minimum|essential)\b", sentence, re.I))
            skills = detected_skills(sentence)
            if is_optional and re.search(r"\b(?:required|must|minimum|essential)\b", sentence, re.I) and not re.search(r"\b(?:not required|not necessary)\b", sentence, re.I):
                required.append({"skills": sorted(skills), "source": sentence, "uncertain": True})
                continue
            if re.search(r"\b(?:not required|not necessary|no .*? required|do not need)\b", sentence, re.I):
                if len(skills) > 1 and re.search(r"\b(?:but|and|however)\b|;", sentence, re.I):
                    required.append({"skills": sorted(skills), "source": sentence, "uncertain": True})
                continue
            if not skills:
                if re.match(r"(?:friendly\b|love for data\b)", sentence, re.I):
                    continue
                duration_only = bool(re.search(r"\b\d+\s*(?:\+|[-–]\s*\d+)?\s+years?\b", sentence, re.I)) and not re.search(
                    r"\b(?:degree|bachelor|master|certificat\w*|licen[sc]e|authori[sz]ation|citizen\w*)\b", sentence, re.I)
                if is_required and not is_optional and not duration_only:
                    required.append({"skills": [], "source": sentence, "uncertain": True})
                continue
            # Only interpret simple coordinated alternatives. Mixed AND/OR clauses
            # remain uncertain rather than inventing an incorrect requirement tree.
            alternatives = bool(re.search(r"\b(?:or|either)\b", sentence, re.I))
            # An Oxford-comma list ending in OR is one alternative group.
            # A comma after OR, or an AND clause, remains ambiguous.
            mixed = alternatives and bool(re.search(r"\band\b|;|\bor\b[^;]*,", sentence, re.I))
            residual = sentence
            for skill in sorted(skills, key=len, reverse=True):
                for alias in SKILL_ALIASES.get(skill, (skill,)):
                    residual = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", " ", residual, flags=re.I)
            prose_words = {"strong", "required", "minimum", "must", "experience", "proficiency", "proficient",
                           "knowledge", "excellent", "solid", "good", "hands-on", "ability", "working",
                           "build", "develop", "you", "the", "professional", "least", "years", "skills",
                           "with", "using", "apis", "api", "web", "frontend", "backend", "full", "stack",
                           "software", "development", "engineering", "experienced", "be"}
            unknown_terms = [term for term in re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{2,}\b", residual)
                             if term.casefold() not in prose_words]
            clauses = re.split(r"\band\b|[,;]", sentence, flags=re.I)
            unknown_clause = len(clauses) > 1 and any(clause.strip() and not detected_skills(clause)
                and not re.search(r"\b\d+\s*\+?\s+years?\b", clause, re.I) for clause in clauses)
            if (mixed or unknown_terms or unknown_clause) and is_required and not is_optional:
                required.append({"skills": sorted(skills), "source": sentence, "uncertain": True})
                continue
            groups = [skills] if alternatives else [{skill} for skill in sorted(skills)]
            if is_optional:
                optional.extend({"skills": sorted(group), "source": sentence} for group in groups)
            elif is_required:
                required.extend({"skills": sorted(group), "source": sentence, "uncertain": False} for group in groups)
    return required, optional


def job_profile(description, title=None):
    cleaned = core_job_description(description)
    if title is None:
        lines = cleaned.splitlines()
        title, cleaned = (lines[0], "\n".join(lines[1:])) if len(lines) > 1 else ("", cleaned)
    core, optional = job_sections(cleaned)
    title_roles = detected_specializations(title or "") - {"software"}
    # Titles establish the principal direction. Duties supplement generic titles.
    duties = _role_evidence(core, duties_only=True)
    roles = title_roles or set(duties)
    if "qa" in title_roles:
        # Testing a full-stack product is still a QA role when the title
        # explicitly identifies testing as the principal responsibility.
        roles = {"qa"}
    elif "full stack" in roles:
        roles -= {"frontend", "backend", "qa"}
    elif not title_roles and roles & {"frontend", "backend", "mobile"}:
        # Routine automated tests accompany software delivery; they alone
        # do not turn a generic developer vacancy into a QA vacancy.
        roles.discard("qa")
    required, preferred = _requirements(cleaned)
    experience_text = "\n".join(sentence for heading, body in _section_blocks(cleaned)
                                if heading not in _IGNORE | _OPTIONAL
                                for sentence in _sentences(body)
                                if not re.match(r"(?:our |the company|we have|we bring)", sentence, re.I)
                                and (heading in {"requirements", "qualifications", "must have"} or
                                     re.search(r"\b(?:experience|minimum|at least)\b", sentence, re.I)))
    year_statements = list(re.finditer(r"\b(?:(?:minimum(?: of)?|at least)\s+)?(\d+)\s*(?:\+|[-–]\s*\d+)?\s+years?\b", experience_text, re.I))
    years = year_statements[0] if year_statements else None
    numeric_years = int(years.group(1)) if years else None
    experience_source = next((sentence for sentence in _sentences(experience_text) if years and years.group(0) in sentence), "")
    if years and re.search(r"\b(?:preferred|nice to have|a plus|optional)\b", next((line for line in _sentences(core) if years.group(0) in line), ""), re.I):
        numeric_years = None
    unsupported_years = bool(re.search(r"\b(?:minimum|at least)\s+\w+\s+years\b", experience_text, re.I)) and not years
    return {
        "title": title or "", "description": cleaned, "core": core,
        "roles": sorted(roles), "role_evidence": duties,
        "skills": sorted(detected_skills("\n".join(
            re.split(r"\b(?:collaborat\w*|partner\w*|work(?:ing) with)\b", sentence, maxsplit=1, flags=re.I)[0]
            for sentence in _sentences(core)))), "optional_skills": sorted(detected_skills(optional)),
        "required": required, "preferred": preferred, "minimum_years": numeric_years,
        "experience_skills": sorted(detected_skills(experience_source)),
        "experience_roles": sorted(detected_specializations(experience_source) - {"software"}),
        "experience_uncertain": unsupported_years or len(year_statements) > 1,
        "input_ready": bool(core.strip() and _ACTION.search(core) and
                            (detected_skills(core) or duties)),
    }


def resume_profile(text, roles=()):
    owned_sentences = [sentence for sentence in _sentences(text) if not re.search(
        r"\b(?:not|never|no experience|want to|would like|looking for|seeking|"
        r"learning|interested in|will build|will develop|requirements|must|required)\b", sentence, re.I)]
    evidence = _role_evidence("\n".join(owned_sentences))
    skills = detected_skills(text)
    project_skills = {}
    for sentence in owned_sentences:
        if _ACTION.search(sentence):
            for skill in detected_skills(sentence):
                project_skills.setdefault(skill, []).append(sentence)
    # Explicit professional-duration statements only. Dates and internships are
    # not guessed into a total, and a numeric mismatch is not a proof of inability.
    years = re.search(r"\b(\d+)\+?\s+years?\s+(?:(?:of\s+)?(?:professional|commercial|industry)\s+experience)(?:\s+(?:in|with|using)\s+[^.\n]+)?", "\n".join(owned_sentences), re.I)
    return {"roles": sorted(evidence), "confirmed_roles": sorted(set(roles) & set(ROLE_LABELS)),
            "role_evidence": evidence, "skills": sorted(skills),
            "project_skills": project_skills, "professional_years": int(years.group(1)) if years else None,
            "experience_skills": sorted(detected_skills(years.group(0))) if years else [],
            "experience_roles": sorted(detected_specializations(years.group(0)) - {"software"}) if years else []}


def local_recommendation(description, resumes, job_title=None, resume_profiles=None):
    job = job_profile(description, job_title)
    job_roles = set(job["roles"])
    generic = {"agile", "scrum", "git", "leadership", "communication"}
    core_skills = set(job["skills"]) - generic
    alternative_groups = [set(item["skills"]) for item in job["required"]
                          if not item["uncertain"] and len(item["skills"]) > 1]
    for sentence in _sentences(job["core"]):
        if re.search(r"\bor\b", sentence, re.I) and not re.search(r"\band\b|;|,", sentence, re.I):
            group = detected_skills(sentence) & core_skills
            if len(group) > 1:
                alternative_groups.append(group)
    alternative_skills = set().union(*alternative_groups) if alternative_groups else set()
    core_groups = [set(group) for group in sorted({tuple(sorted(group)) for group in alternative_groups})]
    core_groups += [{skill} for skill in sorted(core_skills - alternative_skills)]
    profiles, candidates = resume_profiles or {}, []
    for path, text in resumes:
        metadata = profiles.get(str(path), {})
        profile = resume_profile(text, metadata.get("roles", ()))
        skills, evidence = set(profile["skills"]), profile["project_skills"]
        role_sources = [source for role in job_roles for source in profile["role_evidence"].get(role, [])]
        grounded_role = any(_ACTION.search(source) for source in role_sources)
        content_compatible = bool(job_roles & set(profile["roles"]))
        grounded_roles = {role for role in job_roles
                          if any(_ACTION.search(source)
                                 for source in profile["role_evidence"].get(role, []))}
        role_coverage = len(grounded_roles) / max(len(job_roles), 1)
        confirmed = set(profile["confirmed_roles"])
        label_conflict = bool(confirmed and job_roles and not (confirmed & job_roles))
        compatibility = (2 if content_compatible else 1 if job_roles & confirmed else
                         -1 if job_roles and profile["roles"] else 0)
        requirements, missing, uncertain = [], [], []
        for requirement in job["required"]:
            group = set(requirement["skills"])
            label = requirement["source"] if requirement["uncertain"] else " or ".join(sorted(group))
            status = ("uncertain" if requirement["uncertain"] else
                      "project evidence" if group & evidence.keys() else
                      "listed only" if group & skills else "not evidenced")
            requirements.append({**requirement, "status": status})
            if status == "not evidenced":
                missing.append(label)
            elif status in {"uncertain", "listed only"}:
                uncertain.append(label)
        years = job["minimum_years"]
        experience_verified = years is None or (
            profile["professional_years"] is not None and profile["professional_years"] >= years and
            set(job["experience_skills"]) <= set(profile["experience_skills"]) and
            set(job["experience_roles"]) <= set(profile["experience_roles"]))
        gaps = ["No resume evidence found for: " + item for item in missing]
        gaps += ["Verify requirement: " + item for item in uncertain]
        if not experience_verified or job["experience_uncertain"]:
            gaps.append(f"Professional experience not verified (JD: {years}+ years)." if years else
                        "The JD experience requirement needs manual review.")
        if label_conflict:
            gaps.append("Confirmed direction differs from the JD; review the resume's project evidence.")
        if not job_roles:
            gaps.append("The JD's principal direction needs manual review.")
        elif len(job_roles) > 1:
            gaps.append("The JD contains multiple principal directions; verify the responsibilities before choosing.")
        elif not grounded_role:
            gaps.append("No delivery evidence establishing the JD's direction was found.")
        unevidenced_core = [" or ".join(sorted(group)) for group in core_groups if not group & evidence.keys()]
        if unevidenced_core:
            gaps.append("Core skills without project evidence: " + ", ".join(unevidenced_core))
        project_overlap = sorted(core_skills & evidence.keys())
        overlap = sorted(core_skills & skills)
        ratio = sum(bool(group & skills) for group in core_groups) / max(len(core_groups), 1)
        project_ratio = sum(bool(group & evidence.keys()) for group in core_groups) / max(len(core_groups), 1)
        required_ratio = sum(item["status"] == "project evidence" for item in requirements) / max(len(requirements), 1)
        if not requirements:
            required_ratio = project_ratio
        eligible = bool(job["input_ready"] and job_roles and grounded_role and
                        not gaps and core_groups and all(group & evidence.keys() for group in core_groups))
        optional_matches = sorted(set(job["optional_skills"]) & skills)
        candidate = {
            "path": str(path), "file": Path(path).name, "name": metadata.get("name", Path(path).stem),
            "roles": profile["roles"], "confirmed_roles": profile["confirmed_roles"],
            "compatibility": compatibility, "eligible": eligible,
            "overlap": overlap, "project_overlap": project_overlap,
            "requirements": requirements, "gaps": gaps, "optional_matches": optional_matches,
            "evidence": list(dict.fromkeys(role_sources + [source for skill in project_overlap
                            for source in evidence[skill]]))[:6],
            "score": round(ratio * 10, 1),
            "project_match_ratio": project_ratio,
            "required_match_ratio": required_ratio,
            "role_coverage": role_coverage,
            "rank": (compatibility, role_coverage, int(eligible), required_ratio, project_ratio, ratio,
                     sum(bool(set(item["skills"]) & skills) for item in job["preferred"])),
        }
        candidates.append(candidate)
    if not candidates:
        return None
    # Names stabilize presentation only. Evidence rank remains the sole basis
    # for matching, and exact ties stay in the same tier.
    candidates.sort(key=lambda item: item["name"].casefold())
    candidates.sort(key=lambda item: item["rank"], reverse=True)
    best = candidates[0]
    top_ties = [candidate for candidate in candidates if candidate["rank"] == best["rank"]]
    viable = [candidate for candidate in candidates if candidate["compatibility"] >= 0 and candidate["overlap"]]
    # A close comparison cannot be resolved by input order or optional tool counts.
    close = len(viable) > 1 and viable[0]["rank"][:3] == viable[1]["rank"][:3] and all(
        abs(a - b) < .1 for a, b in zip(viable[0]["rank"][3:6], viable[1]["rank"][3:6]))
    if not job["input_ready"] or not core_groups:
        state, summary = "insufficient", "Add the full JD with responsibilities and requirements before choosing a resume."
    elif not viable:
        state, summary = "none", "No suitable role evidence found among the readable resumes."
    elif close:
        state, summary = "close", "Two resumes have similar evidence; review their responsibilities before choosing."
    elif best["eligible"]:
        state, summary = "recommended", "The resume shows the role's responsibilities and core skills. Verify any qualifications not assessed locally."
    else:
        state, summary = "provisional", "The leading resume needs verification; the available evidence does not support a clear recommendation."
    unsupported_required = [" or ".join(item["skills"]) for item in job["required"]
                            if not item["uncertain"] and item["skills"] and not any(
                                requirement["source"] == item["source"] and
                                requirement["skills"] == item["skills"] and
                                requirement["status"] == "project evidence"
                                for candidate in candidates for requirement in candidate["requirements"])]
    if unsupported_required and state not in {"none", "insufficient"}:
        state = "skip"
        summary = "Skip this job: no resume demonstrates the explicit core requirement(s): " + ", ".join(dict.fromkeys(unsupported_required)) + "."
    elif state not in {"none", "insufficient"} and best["project_match_ratio"] < .25:
        state = "skip"
        summary = "Skip this job: the strongest resume demonstrates fewer than one quarter of the JD's core skills in project work."
    recommendation = "Apply" if state == "recommended" else "Skip" if state in {"none", "skip"} else "Consider"
    return {
        "file": best["file"] if state not in {"none", "insufficient", "skip"} else None,
        "name": best["name"] if state not in {"none", "insufficient", "skip"} else None,
        "closest_resume": best["name"] if state == "skip" and len(top_ties) == 1 else None,
        "closest_resumes": [candidate["name"] for candidate in top_ties] if state == "skip" else [],
        "score": best["score"], "state": state, "job": job, "candidates": candidates,
        "alternatives": [candidate["name"] for candidate in viable[:2]] if close else [],
        "modification_needed": state == "provisional", "recommendation": recommendation,
        "priority": "Review locally" if state != "recommended" else "Resume evidence supported",
        "summary": summary, "source": "Local match",
    }


def recommend(description, paths, model=None, job_title=None, resume_profiles=None):
    readable, errors = [], []
    for path in dict.fromkeys(paths):
        try:
            text = read_resume(path)
            if text.strip():
                readable.append((path, text))
            else:
                errors.append(f"{Path(path).name}: no extractable text; use a text-based PDF, DOCX or TXT.")
        except (OSError, ValueError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
            errors.append(f"{Path(path).name}: could not read resume ({type(error).__name__}).")
    result = local_recommendation(description, readable, job_title, resume_profiles) if readable else None
    if result:
        result["readable_count"], result["requested_count"] = len(readable), len(set(paths))
        result["errors"] = errors
        if errors and result["state"] == "recommended":
            result["state"], result["recommendation"] = "provisional", "Consider"
            result["summary"] = "Comparison is incomplete: one or more resumes could not be read."
    return result, errors
