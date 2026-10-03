"""Export the tracker as a phone-friendly 'apply kit': per-job tailored cover letter, CV text and
copy-paste answers, plus your quick-copy profile. Read by the mobile page; contains personal data."""
import json
import re
from pathlib import Path

from . import config, matcher, tailor
from .apply import answer_question

QUESTIONS = [
    "What is your notice period?",
    "What is your expected salary?",
    "How many years of experience do you have?",
    "What is your visa status?",
    "Do you require visa sponsorship?",
    "Are you willing to relocate?",
    "What is your LinkedIn profile?",
    "What is your current salary?",
    "I declare that the information provided is true and accurate.",
]
NEEDS_YOU = {"What is your current salary?": "Your call. Not pre-filled.",
             "I declare that the information provided is true and accurate.": "Tick this yourself."}


def answers(profile: dict) -> list:
    out = []
    for q in QUESTIONS:
        a, status = answer_question(q, profile)
        out.append({"q": q, "a": a if status == "auto" else "", "needs": NEEDS_YOU.get(q, "") if status != "auto" else ""})
    return out


def profile_doc(profile: dict, master: str) -> dict:
    sal = profile["salary_expectation_aed"]
    return {
        "name": profile["name"], "email": profile["email"], "phone": profile["phone"],
        "location": profile["location"], "linkedin": profile["linkedin"],
        "notice": profile["notice_period"],
        "salary": f"AED {sal['min']:,} - {sal['max']:,} per month",
        "salaryMin": sal["min"], "years": profile["years_experience"],
        "workAuth": profile["work_authorization"],
        "relocation": "Yes, open to relocation, subject to the employer sponsoring a work visa.",
        "certifications": profile["certifications"], "expired": profile.get("expired_certifications", []),
        "education": profile["education"], "answers": answers(profile),
        "cvMaster": re.sub(r"<!--.*?-->", "", master, flags=re.S).strip(),
    }


def build(con, kit_min: float = 65) -> dict:
    profile = config.load_profile()
    master = config.master_cv_path().read_text(encoding="utf-8")
    jobs = []
    for r in con.execute("SELECT * FROM jobs ORDER BY id"):
        job = {k: r[k] for k in r.keys()}
        m = matcher.score(job, profile)
        doc = {
            "id": r["id"], "company": r["company"], "title": r["title"], "location": r["location"],
            "salary": r["salary"] or "", "experience": r["experience_required"] or "",
            "match": round(m.score), "status": r["status"], "source": r["source"], "posted": r["posted_date"] or "",
            "url": r["url"] or "", "applyUrl": r["apply_url"] or "", "appliedOn": r["application_date"] or "",
            "followUp": r["followup_date"] or "", "recommendation": m.recommendation,
            "concerns": m.concerns, "matching": m.matching, "missing": m.missing,
        }
        if m.score >= kit_min:
            cv, _ = tailor.tailor_cv(master, job)
            doc["kit"] = {"coverLetter": tailor.cover_letter(job, profile, m.matching, master), "cv": cv,
                          "answers": answers(profile)}
        jobs.append(doc)
    return {"profile": profile_doc(profile, master), "jobs": jobs}


def write(con, path: str, kit_min: float = 65) -> dict:
    data = build(con, kit_min)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data
