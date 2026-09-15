import re
import zipfile
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
}

SPECIALIZATIONS = {
    "full stack": (
        "fullstack", "full stack", "full-stack", "web developer",
        "web development", "web application", "web applications",
    ),
    "java": ("java",),
    "qa": (
        "qa", "quality assurance", "quality engineer", "quality engineering",
        "software quality", "quality automation", "automation tools",
        "test automation", "automation tester", "automation engineer",
        "test engineer", "software engineer in test", "sdet", "tester",
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


def core_job_description(description):
    """Remove job-board recommendation/search content appended after the JD."""
    return re.split(
        r"\n\s*(?:show more show less|seniority level|similar jobs|people also viewed|similar searches)\b",
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
            source = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", " ", source)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError("PDF support requires: pip install pypdf") from error
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    raise ValueError("Supported formats: PDF, DOCX, TXT, MD")


def local_recommendation(description, resumes):
    description = core_job_description(description)
    job_text = description.casefold()
    lines = description.splitlines()
    job_title = lines[0] if lines else description
    # Some postings use a generic title (for example, "Software Engineer")
    # and state the actual track in the opening description. Include the
    # opening section so a Full Stack/QA role is not matched to an unrelated
    # resume merely because of generic skills such as Git or Python.
    title_specializations = detected_specializations(job_title)
    if not title_specializations:
        title_specializations = detected_specializations(description)
    job_skills = {skill for skill in SKILLS if skill in job_text}
    qualification_text = job_text.split("qualifications", 1)[-1]
    required_skills = {
        skill for skill in job_skills
        if any(skill in sentence and any(marker in sentence for marker in ("strong", "minimum", "required", "must"))
               for sentence in re.split(r"[.\n]", qualification_text))
    }
    weights = {skill: (3 if skill in required_skills else .5 if skill in ("agile", "scrum", "git", "leadership") else 1) for skill in job_skills}
    total_weight = sum(weights.values()) or 1
    minimum_years_match = re.search(r"minimum\s+(\d+)\+?\s+years", job_text)
    minimum_years = int(minimum_years_match.group(1)) if minimum_years_match else 0
    ranked = []
    for path, text in resumes:
        resume_text = text.casefold()
        overlap = sorted(job_skills & {skill for skill in SKILLS if skill in resume_text})
        skill_ratio = sum(weights[skill] for skill in overlap) / total_weight
        name = Path(path).stem.casefold()
        resume_specializations = detected_specializations(name)
        specialization_bonus = 0
        if title_specializations:
            # A clear role direction in the title must outweigh generic
            # technology overlap. Otherwise a broad Full Stack resume can
            # beat a QA resume simply by listing more shared tools.
            specialization_bonus = 8 if title_specializations & resume_specializations else -4 if resume_specializations else 0
        elif detected_specializations(job_text) & resume_specializations:
            specialization_bonus = 1.5
        ranked.append((skill_ratio * 10 + specialization_bonus, path, overlap, resume_text))
    ranked.sort(reverse=True, key=lambda item: item[0])
    if not ranked:
        return None
    rank_score, path, overlap, resume_text = ranked[0]
    score = round(min(10, 2.5 + rank_score * .6), 1) if overlap else 2.5
    missing_required = sorted(required_skills - set(overlap))
    lacks_experience = bool(minimum_years and (
        "intern" in resume_text and not re.search(rf"\b{minimum_years}\+?\s+years", resume_text)
    ))
    if lacks_experience:
        score = min(score, 4.9)
    if len(missing_required) >= 2:
        score = min(score, 5.4)
    recommendation = "Apply" if score >= 7 else "Consider" if score >= 5 else "Skip"
    priority = "Tier 1 — Apply" if recommendation == "Apply" else "Tier 2 — Consider" if recommendation == "Consider" else "Tier 3 — Skip"
    if lacks_experience:
        summary = f"Requires {minimum_years}+ years excluding internships; the resume does not show that experience."
    elif missing_required:
        summary = "Missing required: " + ", ".join(missing_required[:4]) + "."
    elif overlap:
        summary = "Strong overlap in " + ", ".join(overlap[:4]) + "."
    else:
        summary = "The resume does not show the role's core skills."
    return {
        "file": Path(path).name,
        "score": score,
        "modification_needed": recommendation != "Skip" and score < 8,
        "recommendation": recommendation,
        "priority": priority,
        "summary": summary,
        "source": "Local match",
    }


def recommend(description, paths, model=None):
    readable, errors = [], []
    for path in paths:
        try:
            text = read_resume(path)
            if text.strip():
                readable.append((path, text))
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            errors.append(f"{Path(path).name}: {error}")
    return (local_recommendation(description, readable) if readable else None), errors
