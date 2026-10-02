"""Import jobs gathered from legitimate sources (JSON/CSV).

Live searching is done outside this package (see docs/SOURCES.md): a Claude Code session using
its Indeed/web tools, or you pasting postings. Both end up here, so scoring, scam checks and
duplicate prevention are applied identically.
"""
import csv
import json
from pathlib import Path

from . import db, matcher, scam
from .config import load_profile

ALIASES = {"job_title": "title", "position": "title", "company_name": "company", "link": "url",
           "job_url": "url", "posted": "posted_date", "date_posted": "posted_date", "id": "job_ref",
           "job_id": "job_ref", "experience": "experience_required", "source_site": "source"}


def load_file(path: str) -> list[dict]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        data = data if isinstance(data, list) else data.get("jobs", [])
    else:
        with p.open(newline="", encoding="utf-8") as f:
            data = list(csv.DictReader(f))
    return [{ALIASES.get(k.strip().lower(), k.strip().lower()): v for k, v in d.items()} for d in data]


def ingest(con, jobs: list[dict]) -> dict:
    profile = load_profile()
    stats = {"added": 0, "duplicates": [], "scam_flagged": [], "skipped_invalid": 0}
    for j in jobs:
        if not j.get("company") or not j.get("title"):
            stats["skipped_invalid"] += 1
            continue
        row, created = db.add_job(con, j)
        if not created:
            stats["duplicates"].append(f"{j['company']} - {j['title']} (existing #{row['id']})")
            continue
        stats["added"] += 1
        m = matcher.score(dict(row), profile)
        flags = scam.check(f"{j['title']}\n{j.get('description', '')}")
        db.update(con, row["id"], match_pct=m.score, match_json=json.dumps(m.to_dict()),
                  scam_flags="; ".join(flags))
        db.set_status(con, row["id"], "Review Required" if flags or m.recommendation.startswith("REVIEW") else "New",
                      "scam flags" if flags else "")
        if flags:
            stats["scam_flagged"].append(f"#{row['id']} {j['company']}: {'; '.join(flags)}")
    return stats
