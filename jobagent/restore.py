"""Daily-update helpers. The Apply Kit (phone page) holds the real statuses, so a fresh machine rebuilds the
tracker from its job documents, finds only NEW postings, and exports kits for just those."""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from . import db

# Jobs added from the phone ("li_..." ids) get NEGATIVE ids: they still dedupe, never collide with real ids,
# and new jobs keep counting up from the highest real id.

RELEVANT = re.compile(r"network|security|firewall|infrastructure|sd-?wan|cisco|fortinet|palo ?alto|\bise\b|\bnac\b|wireless|noc\b", re.I)
JUNIOR = re.compile(r"\b(junior|jr\.?|intern(ship)?|graduate|trainee|entry[- ]level|fresher)\b", re.I)


def _doc(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("data", d) if isinstance(d.get("data", None), dict) else d


def restore(con, directory: str) -> dict:
    """Load Apply Kit job docs (files saved by ArtifactData list --out_dir) into the tracker, keeping ids."""
    files = sorted(Path(directory).rglob("job_*.json"))
    n = foreign = 0
    next_foreign = 0
    for f in files:
        d = _doc(f)
        if not d.get("company"):
            continue
        jid = d.get("id")
        if not isinstance(jid, int):
            next_foreign -= 1
            jid, foreign = next_foreign, foreign + 1
        job = {"company": d["company"], "title": d.get("title", ""), "location": d.get("location", ""), "url": d.get("url", "")}
        k = db.keys(job)
        con.execute(
            "INSERT OR REPLACE INTO jobs (id, company, title, location, salary, experience_required, source, posted_date, url, apply_url,"
            " match_pct, status, application_date, followup_date, url_key, ref_key, sig_key, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (jid, d["company"], d.get("title", ""), d.get("location", ""), d.get("salary", ""), d.get("experience", ""),
             d.get("source", ""), d.get("posted", ""), d.get("url", ""), d.get("applyUrl", ""), d.get("match"),
             d.get("status", "New"), d.get("appliedOn", ""), d.get("followUp", ""), k["url_key"], k["ref_key"], k["sig_key"]))
        n += 1
    con.commit()
    mx = con.execute("SELECT COALESCE(MAX(id),0) FROM jobs").fetchone()[0]
    return {"restored": n, "foreign": foreign, "max_id": mx}


def _posted_ok(text: str, days: int) -> bool:
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(text.strip(), fmt).date() >= date.today() - timedelta(days=days)
        except ValueError:
            continue
    return True  # unknown date: keep, the matcher and a human decide


def filter_new(con, jobs: list[dict], max_age_days: int = 45) -> dict:
    """Keep postings that are not already tracked, are recent, look relevant and are not junior."""
    keep, dup, old, off = [], [], [], []
    seen = set()
    for j in jobs:
        label = f"{j.get('company')} - {j.get('title')}"
        probe = {"company": j.get("company", ""), "title": j.get("title", ""), "location": j.get("location", ""),
                 "url": j.get("url", ""), "job_ref": ""}
        sig = db.keys(probe)["sig_key"]
        if sig in seen or db.find_duplicate(con, probe):
            dup.append(label)
        elif not _posted_ok(j.get("posted_date", ""), max_age_days):
            old.append(label)
        elif not RELEVANT.search(j.get("title", "")) or JUNIOR.search(j.get("title", "")):
            off.append(label)
        else:
            keep.append(j)
        seen.add(sig)
    return {"new": keep, "duplicates": dup, "too_old": old, "not_relevant": off}


def kit_new(con, min_id: int, out: str, kit_min: float = 65, split_dir: str | None = None) -> list:
    """Kit documents for jobs added since the restore (id >= min_id), ready to write into the Apply Kit database."""
    from . import kit as kitmod
    data = kitmod.build(con, kit_min)
    docs = [j for j in data["jobs"] if j["id"] >= min_id]
    Path(out).write_text(json.dumps(docs, indent=1, ensure_ascii=False), encoding="utf-8")
    if split_dir:  # one file per document + a batch list ready for the ArtifactData tool (50 writes max per call)
        d = Path(split_dir)
        d.mkdir(parents=True, exist_ok=True)
        writes = []
        for doc in docs:
            f = d / f"job_{doc['id']}.json"
            f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            writes.append({"op": "set", "collection": "jobs", "doc_id": f"job_{doc['id']}", "file_path": str(f.resolve())})
        (d / "writes.json").write_text(json.dumps(writes), encoding="utf-8")
    return docs
