"""SQLite store: jobs, application history, duplicate detection."""
import re
import sqlite3
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL, title TEXT NOT NULL, location TEXT DEFAULT '',
  salary TEXT DEFAULT '', experience_required TEXT DEFAULT '',
  source TEXT DEFAULT '', posted_date TEXT DEFAULT '', url TEXT DEFAULT '',
  job_ref TEXT DEFAULT '', description TEXT DEFAULT '',
  remote INTEGER DEFAULT 0, visa_sponsorship TEXT DEFAULT '',
  match_pct REAL, match_json TEXT DEFAULT '', scam_flags TEXT DEFAULT '',
  status TEXT DEFAULT 'New', application_date TEXT DEFAULT '', followup_date TEXT DEFAULT '',
  url_key TEXT, ref_key TEXT, sig_key TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_url ON jobs(url_key);
CREATE INDEX IF NOT EXISTS ix_ref ON jobs(ref_key);
CREATE INDEX IF NOT EXISTS ix_sig ON jobs(sig_key);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, at TEXT, event TEXT, detail TEXT
);
"""


def connect() -> sqlite3.Connection:
    config.HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.db_path())
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _norm(s: str) -> str:
    s = re.sub(r"\b(llc|ltd|limited|inc|fz|fzco|fze|pjsc|l\.l\.c|co)\b\.?", " ", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def url_key(url: str) -> str:
    if not url:
        return ""
    p = urlsplit(url.strip().lower())
    return f"{p.netloc.removeprefix('www.')}{p.path.rstrip('/')}"


def keys(job: dict) -> dict:
    ref = (job.get("job_ref") or "").strip().lower()
    city = _norm(job.get("location", "")).split(" ")[0] if job.get("location") else ""
    return {
        "url_key": url_key(job.get("url", "")),
        "ref_key": f"{_norm(job.get('company', ''))}|{ref}" if ref else "",
        "sig_key": f"{_norm(job.get('company', ''))}|{_norm(job.get('title', ''))}|{city}",
    }


def find_duplicate(con, job: dict):
    """Return an existing row with the same URL, job ID, or company+title(+city)."""
    k = keys(job)
    for col in ("url_key", "ref_key", "sig_key"):
        if k[col]:
            row = con.execute(f"SELECT * FROM jobs WHERE {col}=? ORDER BY id LIMIT 1", (k[col],)).fetchone()
            if row:
                return row
    # Same company + title applied for in a different city is still the same application.
    comp_title = f"{_norm(job.get('company', ''))}|{_norm(job.get('title', ''))}|"
    return con.execute(
        "SELECT * FROM jobs WHERE sig_key LIKE ? AND status NOT IN ('New','Review Required','Closed') LIMIT 1",
        (comp_title + "%",)).fetchone()


COLS = ["company", "title", "location", "salary", "experience_required", "source", "posted_date",
        "url", "job_ref", "description", "remote", "visa_sponsorship"]


def add_job(con, job: dict):
    """Insert unless duplicate. Returns (row, created)."""
    dup = find_duplicate(con, job)
    if dup:
        return dup, False
    k = keys(job)
    vals = {c: job.get(c, "") for c in COLS}
    vals["remote"] = 1 if job.get("remote") else 0
    vals.update(k, created_at=datetime.now().isoformat(timespec="seconds"))
    cur = con.execute(
        f"INSERT INTO jobs ({','.join(vals)}) VALUES ({','.join('?' * len(vals))})", list(vals.values()))
    con.commit()
    log(con, cur.lastrowid, "added", job.get("source", ""))
    return get(con, cur.lastrowid), True


def get(con, job_id: int):
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise KeyError(f"No job with id {job_id}")
    return row


def log(con, job_id, event, detail=""):
    con.execute("INSERT INTO history (job_id, at, event, detail) VALUES (?,?,?,?)",
                (job_id, datetime.now().isoformat(timespec="seconds"), event, detail))
    con.commit()


def set_status(con, job_id: int, status: str, detail: str = ""):
    if status not in config.STATUSES:
        raise ValueError(f"Unknown status {status!r}. Use one of: {', '.join(config.STATUSES)}")
    con.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    con.commit()
    log(con, job_id, f"status:{status}", detail)


def update(con, job_id: int, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE jobs SET {sets} WHERE id=?", [*fields.values(), job_id])
    con.commit()


def add_business_days(start: date, n: int) -> date:
    """Mon-Fri business days (UAE weekend is Sat/Sun since 2022)."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def mark_applied(con, job_id: int, when: date | None = None, followup_days: int = 5):
    when = when or date.today()
    fu = add_business_days(when, followup_days)
    update(con, job_id, application_date=when.isoformat(), followup_date=fu.isoformat())
    set_status(con, job_id, "Applied", f"follow-up {fu.isoformat()}")
    return fu


def already_applied(con, job: dict):
    """Row for an application already submitted to the same job, else None."""
    dup = find_duplicate(con, job)
    if dup and dup["application_date"]:
        return dup
    return None
