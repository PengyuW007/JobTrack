import json
import os
import re
import zipfile
from pathlib import Path

import requests

SKILLS = {"python", "java", "javascript", "typescript", "react", "angular", "vue", "sql", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "spark", "pandas", "machine learning", "data analysis", "power bi", "tableau", "excel", "salesforce", "node", "c++", "c#", ".net", "rest", "graphql", "git", "linux", "agile", "scrum", "leadership"}


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
    job_skills = {skill for skill in SKILLS if skill in description.casefold()}
    ranked = []
    for path, text in resumes:
        overlap = sorted(job_skills & {skill for skill in SKILLS if skill in text.casefold()})
        ranked.append((len(overlap) / max(len(job_skills), 1), path, overlap))
    ranked.sort(reverse=True, key=lambda item: item[0])
    if not ranked:
        return None
    score, path, overlap = ranked[0]
    reason = "Matching skills: " + ", ".join(overlap[:6]) if overlap else "No clear skill match found"
    return {"file": Path(path).name, "reason": reason, "source": "Local match", "score": round(score * 100)}


def ai_recommendation(description, resumes):
    fallback = local_recommendation(description, resumes)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback
    resume_text = "\n\n".join(f"RESUME: {Path(path).name}\n{text[:12000]}" for path, text in resumes)
    schema = {"type": "object", "properties": {"file": {"type": "string"}, "reason": {"type": "string"}}, "required": ["file", "reason"], "additionalProperties": False}
    payload = {
        "model": os.getenv("JOBTRACK_OPENAI_MODEL", "gpt-5.4-mini"),
        "store": False,
        "input": [
            {"role": "developer", "content": "Choose the strongest resume for this job using only supplied evidence. Keep the reason under 25 words."},
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
        result.update(source="AI", score=None)
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
