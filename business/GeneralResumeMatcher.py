"""Conservative English, open-vocabulary matching without occupational gates.

Missing text is not negative evidence. Qualification equivalence and complex
logical requirements remain for review. Results use the existing workbench API.
"""
import re
import unicodedata
from pathlib import Path


_HEADINGS = {
    "responsibilities": "responsibility", "job responsibilities": "responsibility",
    "key responsibilities": "responsibility", "primary responsibilities": "responsibility",
    "duties": "responsibility", "the role": "responsibility",
    "about the role": "responsibility", "position overview": "responsibility",
    "job overview": "responsibility", "what you will do": "responsibility",
    "what you'll do": "responsibility", "what you’ll do": "responsibility",
    "key technology areas include": "responsibility",
    "requirements": "required", "job requirements": "required",
    "job requirements and competencies": "required",
    "requirements and competencies": "required", "qualifications": "required",
    "skills and qualifications": "required", "skills & qualifications": "required",
    "must have": "required", "must haves": "required",
    "must have candidate qualities": "required",
    "candidates should demonstrate": "required", "required qualifications": "required",
    "nice to have": "optional", "preferred qualifications": "optional",
    "preferred skills": "optional", "bonus points": "optional",
    "benefits": "ignore", "perks": "ignore", "what we offer": "ignore",
    "about us": "ignore", "about the company": "ignore",
    "our culture": "ignore", "team culture": "ignore", "our team culture": "ignore",
    "equity statement": "ignore", "equal opportunity statement": "ignore",
    "position": "ignore", "reports to": "ignore", "location": "ignore",
    "industry": "ignore", "employment type": "ignore", "start date": "ignore",
    "base salary": "ignore", "salary": "ignore", "compensation": "ignore",
    "experience": "experience", "work experience": "experience",
    "professional experience": "experience", "projects": "experience",
    "skills": "listed", "education": "education", "certifications": "credential",
    "licenses": "credential", "summary": "listed", "objective": "ignore",
}
_STOP = set("""a an the and or of to in on for with using use used you your we our
    will must required preferred essential minimum at least have has had be is are
    was were as by from strong excellent ability knowledge proficiency proficient
    experience professional years year skills skill responsible""".split())
_NEGATIVE = re.compile(
    r"\b(?:not|never|no|without|lack\w*|want to|would like|seeking|learning|"
    r"interested in|requirements|required|must)\b", re.I)
_ACTION = re.compile(
    r"\b(?:\w+(?:ed|ing)|led|taught|wrote|ran|built|responsible for)\b", re.I)
_YEARS = re.compile(r"\b(\d+)\s*\+?\s+years?\b", re.I)
_PLACEHOLDER = re.compile(
    r"(?:<{2,}[^>]*(?:to be added|à ajouter)[^>]*>{2,}|"
    r"\b(?:to be added|insert (?:description|requirements?|responsibilities)|tbd)\b)", re.I)


def _terms(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    words = re.findall(r"[a-z][a-z0-9+#]*(?:[.-][a-z0-9]+)*", text)
    terms = set()
    for word in words:
        if word in _STOP:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 4 and word.endswith("ed"):
            word = word[:-2]
        if len(word) > 4 and word.endswith("e"):
            word = word[:-1]
        terms.add(word)
    return terms


def _blocks(text):
    section = ""
    for line in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", text):
        line = line.strip(" \t\r•-*")
        if not line:
            continue
        heading, separator, body = line.partition(":")
        key = heading.casefold().replace("-", " ").strip()
        heading_section = _HEADINGS.get(key)
        if heading_section is None and (
                key.startswith("learn more about ") or
                key.startswith("about ") and key not in {"about the role", "about the position"}):
            heading_section = "ignore"
        if heading_section is not None:
            section = heading_section
            if not separator or not body.strip():
                continue
            line = body.strip()
        yield section, line


def _display_label(source):
    """Keep open-vocabulary labels readable without changing matching evidence."""
    label = " ".join(source.split()).strip(" .:;,-")
    label = re.sub(r"^(?:candidates? should demonstrate|strong|excellent)\s+", "", label, flags=re.I)
    label = re.sub(r"^ability to\s+", "", label, flags=re.I)
    label = re.sub(r"^previous experience (?:in|with)\s+", "", label, flags=re.I)
    if label:
        label = label[0].upper() + label[1:]
    if len(label) > 64:
        label = label[:61].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return label


def job_profile(description, title=None):
    cleaned = re.split(r"\n\s*(?:similar jobs|people also viewed)\b",
                       description or "", flags=re.I)[0]
    if title is None:
        lines = cleaned.splitlines()
        title, cleaned = (lines[0], "\n".join(lines[1:])) if len(lines) > 1 else ("", cleaned)
    criteria = []
    for section, source in _blocks(cleaned):
        if section == "ignore" or _PLACEHOLDER.search(source):
            continue
        explicit_optional = bool(re.search(
            r"\b(?:preferred|nice to have|optional|a plus|an asset|is an asset)\b", source, re.I))
        optional = section == "optional" or explicit_optional
        mandatory = (section == "required" and not explicit_optional) or bool(re.search(
            r"\b(?:must|required|minimum|essential)\b", source, re.I))
        negated = bool(re.search(r"\b(?:not required|no .* required)\b", source, re.I))
        if negated and not re.search(r"\b(?:but|however|and)\b", source, re.I):
            continue
        kind = "responsibility"
        if re.search(r"\b(?:licen[cs]e\w*|certificat\w*|registration)\b", source, re.I):
            kind = "credential"
        elif re.search(r"\b(?:degree|bachelor\w*|master\w*|diploma|education)\b", source, re.I):
            kind = "education"
        elif _YEARS.search(source):
            kind = "experience"
        elif re.search(r"\b(?:communication|leadership|teamwork|problem.solving)\b", source, re.I):
            kind = "transferable"
        elif re.search(r"\b(?:tools?|equipment|software|using|proficien\w*)\b", source, re.I):
            kind = "tool"
        terms = _terms(source)
        uncertain = bool(re.search(r"\b(?:or|equivalent|unless|except)\b", source, re.I))
        uncertain |= negated or (optional and mandatory)
        criteria.append({"source": source, "type": kind, "terms": sorted(terms),
                         "section": section, "label": _display_label(source),
                         "importance": "optional" if optional and not mandatory else
                         "required" if mandatory else "core", "uncertain": uncertain,
                         "skills": [source]})
    core = [item for item in criteria if item["importance"] != "optional"]
    responsibilities = [item["source"] for item in core
                        if item["section"] == "responsibility"]
    qualifications = [item["label"] for item in core
                      if item["section"] in {"required", "listed", "education",
                                              "credential", "experience"}]
    # Language support is explicit: unknown language must never look like a mismatch.
    english = bool(re.search(
        r"\b(?:responsibilities|duties|requirements|qualifications|with|and|the|"
        r"manage|plan|operate|inspect|provide|repair|teach|prepare|required)\b",
        cleaned, re.I))
    return {"title": title or "", "description": cleaned, "core": cleaned,
            "roles": [title] if title else [], "criteria": criteria,
            "required": [item for item in criteria if item["importance"] == "required"],
            "preferred": [item for item in criteria if item["importance"] == "optional"],
            "responsibilities": responsibilities,
            "skills": qualifications or [item["label"] for item in core],
            "optional_skills": [], "input_ready": bool(core and english),
            "language_supported": english}


def _evidence(text):
    evidence = []
    for section, source in _blocks(text):
        if section == "ignore" or _NEGATIVE.search(source):
            continue
        owned = re.split(r"\b(?:collaborat\w* with|partner\w* with)\b",
                         source, flags=re.I)[0]
        delivered = section == "experience" or (
            section != "listed" and not re.match(r"skills\b", owned, re.I)
            and bool(_ACTION.search(owned)))
        evidence.append({"source": source, "terms": _terms(owned),
                         "section": section, "delivered": delivered})
    return evidence


def _assess(criterion, evidence):
    terms = set(criterion["terms"])
    best, ratio = None, 0
    for item in evidence:
        coverage = len(terms & item["terms"]) / max(len(terms), 1)
        if coverage > ratio or (coverage == ratio and item["delivered"]):
            best, ratio = item, coverage
    status = "not evidenced"
    if criterion["uncertain"] or not terms:
        status = "uncertain"
    elif best and ratio == 1:
        if criterion["type"] == "experience":
            needed = _YEARS.search(criterion["source"])
            actual = _YEARS.search(best["source"])
            status = "project evidence" if (
                needed and actual and int(actual[1]) >= int(needed[1])) else "uncertain"
        elif criterion["type"] in {"credential", "education"}:
            # A lexical overlap cannot verify currency, jurisdiction or equivalence.
            status = "listed only"
        else:
            status = "project evidence" if best["delivered"] else "listed only"
    elif best and ratio:
        status = "listed only"
    return {**criterion, "status": status, "coverage": ratio,
            "evidence": best["source"] if best and ratio else ""}


def local_recommendation(description, resumes, job_title=None, resume_profiles=None):
    job = job_profile(description, job_title)
    candidates = []
    for path, text in resumes:
        metadata = (resume_profiles or {}).get(str(path), {})
        evidence = _evidence(text)
        assessed = [_assess(item, evidence) for item in job["criteria"]]
        core = [item for item in assessed if item["importance"] != "optional"]
        required = [item for item in core if item["importance"] == "required"]
        matched = [item for item in core if item["status"] == "project evidence"]
        gaps = ["Verify requirement: " + item["source"] for item in core
                if item["status"] != "project evidence"]
        eligible = bool(job["input_ready"] and core and not gaps)
        coverage = sum(item["coverage"] for item in core) / max(len(core), 1)
        required_ratio = sum(item["status"] == "project evidence" for item in required) / max(len(required), 1)
        project_ratio = len(matched) / max(len(core), 1)
        overlap = [item["source"] for item in core if item["coverage"]]
        project = [item["source"] for item in matched]
        candidates.append({
            "path": str(path), "file": Path(path).name,
            "name": metadata.get("name", Path(path).stem),
            "primary_direction": job["title"] if matched else None,
            "secondary_directions": [], "roles": job["roles"] if matched else [],
            "confirmed_roles": [], "compatibility": 2 if matched else 0,
            "direction_fit": 0, "eligible": eligible, "overlap": overlap,
            "project_overlap": project, "requirements": assessed, "gaps": gaps,
            "optional_matches": [], "evidence": list(dict.fromkeys(
                item["evidence"] for item in assessed if item["evidence"]))[:6],
            "score": round(coverage * 10, 1), "project_match_ratio": project_ratio,
            "required_match_ratio": required_ratio, "role_coverage": project_ratio,
            "rank": (int(eligible), required_ratio, project_ratio, coverage),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item["name"].casefold(), item["path"]))
    candidates.sort(key=lambda item: item["rank"], reverse=True)
    best = candidates[0]
    ties = [item for item in candidates if item["rank"] == best["rank"]]
    if not job["input_ready"]:
        state, summary = "insufficient", "Unable to assess reliably. Provide an English JD with responsibilities and requirements."
    elif len(ties) > 1 and best["overlap"]:
        state, summary = "close", "These resumes have similar evidence; review the requirements before choosing."
    elif best["eligible"]:
        state, summary = "recommended", "The resume contains evidence for the stated responsibilities and requirements."
    else:
        state, summary = "provisional", "Review needed: missing or ambiguous evidence does not establish a mismatch."
    return {
        "file": best["file"] if job["input_ready"] else None,
        "name": best["name"] if job["input_ready"] else None,
        "state": state, "summary": summary, "job": job, "candidates": candidates,
        "score": best["score"], "alternatives": [item["name"] for item in ties] if state == "close" else [],
        "closest_resume": None, "closest_resumes": [],
        "modification_needed": state == "provisional",
        "recommendation": "Apply" if state == "recommended" else "Consider",
        "priority": "Review locally", "source": "Local match",
    }
