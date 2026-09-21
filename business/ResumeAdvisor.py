"""Local resume reading and job-based dispatch; existing public helpers stay compatible."""
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from business import TechnicalResumeMatcher as technical
from business import GeneralResumeMatcher as general
from business.TechnicalResumeMatcher import (
    SKILLS, SKILL_ALIASES, SPECIALIZATIONS, ROLE_LABELS,
    core_job_description, detected_skills, detected_specializations,
    job_sections, resume_profile,
)


def matching_engine(description, title=None):
    """Route by owned software duties or explicit software title, never tools alone."""
    profile = technical.job_profile(description, title)
    title = profile["title"]
    explicit = re.search(
        r"\b(?:software (?:engineer|developer)|full[ -]?stack|front[ -]?end|back[ -]?end|sdet|"
        r"(?:java|mobile|android|ios|web) developer|"
        r"(?:quality|test) (?:engineering|automation)|"
        r"(?:qa|quality assurance) (?:engineer|developer|analyst))\b",
        title, re.I)
    software_context = re.compile(
        r"\b(?:full[ -]?stack|front[ -]?end|back[ -]?end|software|"
        r"apis?|web interfaces|database connectors?|test automation|"
        r"automated tests|regression tests|mobile (?:apps?|applications)|"
        r"android|flutter|react native|(?:python|java|node) services)\b", re.I)
    software_duties = any(
        software_context.search(source)
        for role, sources in profile["role_evidence"].items()
        if role in {"full stack", "frontend", "backend", "mobile", "qa"}
        for source in sources)
    return technical if explicit or software_duties else general


def job_profile(description, title=None):
    return matching_engine(description, title).job_profile(description, title)


def local_recommendation(description, resumes, job_title=None, resume_profiles=None):
    return matching_engine(description, job_title).local_recommendation(
        description, resumes, job_title, resume_profiles)


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
