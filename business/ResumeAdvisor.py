import json
import os
import re
import zipfile
from pathlib import Path

import requests

SKILLS = {"python", "java", "javascript", "typescript", "react", "angular", "vue", "sql", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "spark", "pandas", "machine learning", "data analysis", "power bi", "tableau", "excel", "salesforce", "node", "c++", "c#", ".net", "rest", "graphql", "git", "linux", "agile", "scrum", "leadership", "ci/cd", "devops", "domain-driven design", "design patterns"}

SPECIALIZATIONS = {
    "full stack": ("fullstack", "full stack", "full-stack"),
    "java": ("java",),
    "qa": ("qa", "quality assurance"),
    "data": ("data", "analytics"),
}


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
    job_text = description.casefold()
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
        specialization_bonus = max(
            (1.5 for label, aliases in SPECIALIZATIONS.items()
             if label in job_text and any(alias in name for alias in aliases)),
            default=0,
        )
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
        "summary": summary,
        "source": "Local match",
    }


def ai_recommendation(description, resumes):
    fallback = local_recommendation(description, resumes)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback
    resume_text = "\n\n".join(f"RESUME: {Path(path).name}\n{text[:12000]}" for path, text in resumes)
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "score": {"type": "number", "minimum": 0, "maximum": 10},
            "modification_needed": {"type": "boolean"},
            "recommendation": {"type": "string", "enum": ["Apply", "Consider", "Skip"]},
            "summary": {"type": "string"},
        },
        "required": ["file", "score", "modification_needed", "recommendation", "summary"],
        "additionalProperties": False,
    }
    payload = {
        "model": os.getenv("JOBTRACK_OPENAI_MODEL", "gpt-5.4-mini"),
        "store": False,
        "input": [
            {"role": "developer", "content": "Choose the strongest resume and assess whether the candidate should apply. Score job fit from 0 to 10 using only supplied evidence. Recommend Apply, Consider, or Skip. Set modification_needed only when tailoring could materially improve a viable application. Keep summary under 25 words."},
            {"role": "user", "content": f"JOB DESCRIPTION:\n{description[:18000]}\n\n{resume_text}"},
        ],
        "text": {"format": {"type": "json_schema", "name": "resume_choice", "strict": True, "schema": schema}},
    }
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        output_text = data.get("output_text")
        if not output_text:
            output_text = next(
                part["text"]
                for item in data.get("output", [])
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
        result = json.loads(output_text)
        if result.get("file") not in {Path(path).name for path, _ in resumes}:
            return fallback
        result["score"] = round(float(result["score"]), 1)
        result["source"] = "AI"
        return result
    except (requests.RequestException, KeyError, ValueError, TypeError, StopIteration, json.JSONDecodeError):
        return fallback


def recommend(description, paths):
    readable, errors = [], []
    for path in paths:
        try:
            text = read_resume(path)
            if text.strip():
                readable.append((path, text))
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            errors.append(f"{Path(path).name}: {error}")
    return (ai_recommendation(description, readable) if readable else None), errors
