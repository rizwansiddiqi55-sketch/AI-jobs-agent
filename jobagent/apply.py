"""Prepare applications and enforce the human-approval gate.

Nothing here submits anything on its own. `submit()` needs an interactive terminal and
the user typing the exact approval phrase; there is no flag or env var that bypasses it.
"""
import html
import json
import re
import sys
from pathlib import Path

from . import config, db, matcher, scam, tailor

LEGAL = re.compile(r"(declar|i agree|consent|terms|certify|true and (accurate|correct)|background check|"
                   r"privacy|gdpr|legally|bound|authori[sz]e)", re.I)
CURRENT_SALARY = re.compile(r"(current|present|last)\s+(salary|ctc|pay|compensation)", re.I)
APPROVAL_PHRASE = "SUBMIT"
# Job boards forbid automated applying and need your login/captcha: never automate these, use the employer's own site.
BLOCKED_HOSTS = ("indeed.com", "linkedin.com", "bayt.com", "glassdoor.com", "gulftalent.com", "naukrigulf.com",
                 "naukri.com", "monster", "founditgulf.com", "freehire.me", "bebee.com", "wuzzuf.net", "ziprecruiter")


def target_url(row) -> str:
    """The employer's own application page (apply_url). Refuses job boards and missing URLs."""
    from urllib.parse import urlsplit
    url = (row["apply_url"] or "").strip()
    if not url:
        raise RuntimeError(f"No employer application URL for job {row['id']}. Open the company's own careers page, "
                           f"find this role, then run: jobagent set-url {row['id']} <that URL>")
    host = urlsplit(url).netloc.lower()
    if any(b in host for b in BLOCKED_HOSTS):
        raise RuntimeError(f"{host} is a job board; automated applying there is not allowed (terms, login, captcha). "
                           "Use the employer's own careers page URL instead.")
    if not url.startswith(("http://", "https://", "file://")):
        raise RuntimeError("apply_url must start with https://")
    return url



def answer_question(question: str, profile: dict):
    """-> (answer, status). status: auto | needs_answer | needs_confirmation. Never guesses."""
    if LEGAL.search(question):
        return "", "needs_confirmation"  # legal declarations are always yours to confirm
    if CURRENT_SALARY.search(question):
        return "", "needs_answer"  # disclosure is your call, not the agent's
    for pattern, ans in profile.get("screening_answers", {}).items():
        if re.search(pattern, question, re.I):
            return (ans, "auto") if not ans.startswith("TO CONFIRM") else ("", "needs_answer")
    return "", "needs_answer"


def job_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def packet_dir(job_id: int) -> Path:
    return config.output_dir() / f"job_{job_id}"


def prepare(con, job_id: int, questions: list[str] | None = None, draft: bool = False) -> dict:
    row = db.get(con, job_id)
    job = job_dict(row)
    profile = config.load_profile()
    problems = []
    if row["application_date"]:
        raise RuntimeError(f"Already applied on {row['application_date']} - not preparing another application.")
    if row["status"] == "Closed":
        raise RuntimeError("Job is marked Closed (expired).")
    flags = scam.check(f"{job['title']}\n{job['description']}")
    if flags:
        problems.append("SCAM WARNING: " + "; ".join(flags))
    m = matcher.score(job, profile)
    if m.recommendation.startswith("SKIP"):
        problems.append(f"Matcher recommends skipping: {m.recommendation}")

    master = config.master_cv_path().read_text(encoding="utf-8")
    cv_text, report = tailor.tailor_cv(master, job)
    if report["placeholders_remaining"] and not draft:
        raise RuntimeError(
            "Master CV still has [FILL IN] placeholders: "
            f"{report['placeholders_remaining']}. Complete data/master_cv.md (or pass --draft).")
    letter = tailor.cover_letter(job, profile, m.matching, master)

    qa = [dict(question=q, **dict(zip(("answer", "status"), answer_question(q, profile)))) for q in questions or []]
    d = packet_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cv.md").write_text(cv_text, encoding="utf-8")
    (d / "cover_letter.md").write_text(letter, encoding="utf-8")
    (d / "screening_answers.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    (d / "tailoring_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    ready = render_ready(job, m, problems, qa, d)
    (d / "application_ready.md").write_text(ready, encoding="utf-8")
    db.update(con, job_id, match_pct=m.score, match_json=json.dumps(m.to_dict()),
              scam_flags="; ".join(flags))
    db.set_status(con, job_id, "Ready to Apply" if not problems else "Review Required",
                  "; ".join(problems))
    return {"ready": ready, "problems": problems, "dir": d}


def render_ready(job, m, problems, qa, d) -> str:
    unanswered = [q for q in qa if q["status"] != "auto"]
    lines = [
        "# Application Ready", "",
        f"**Company:** {job['company']}", f"**Position:** {job['title']}",
        f"**Location:** {job['location'] or 'n/a'}", f"**Match:** {m.score:.0f}%",
        f"**Salary:** {job['salary'] or 'not stated'}",
        f"**Key requirements:** {', '.join(m.matching + m.missing) or 'n/a'}",
        f"**Matching skills:** {', '.join(m.matching) or 'none'}",
        f"**Missing skills:** {', '.join(m.missing) or 'none'}",
        "**Potential concerns:** " + ("; ".join(m.concerns + problems) or "none"),
        f"**CV used:** {d / 'cv.md'}", f"**Cover letter:** {d / 'cover_letter.md'}",
        "**Screening answers:**",
    ]
    for q in qa:
        a = q["answer"] if q["status"] == "auto" else f"<{q['status'].upper().replace('_', ' ')}>"
        lines.append(f"  - {q['question']} -> {a}")
    if not qa:
        lines.append("  - (none supplied)")
    if unanswered:
        lines.append(f"\n{len(unanswered)} question(s) need YOUR answer/confirmation before submitting.")
    lines += [f"**Application URL:** {job['url'] or 'n/a'}", "",
              f"**[Submit Application]**  ->  run: `python -m jobagent apply submit {job['id']}` "
              f"and type {APPROVAL_PHRASE} to approve."]
    return "\n".join(lines)


def submit(con, job_id: int, stdin=None, stdout=None) -> str:
    """Approval gate. Returns the outcome message."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    if not stdin.isatty():
        raise PermissionError("Submission requires an interactive terminal: a human must approve.")
    row = db.get(con, job_id)
    if row["application_date"]:
        return f"Already applied on {row['application_date']}; nothing submitted."
    again = db.already_applied(con, job_dict(row))
    if again and again["id"] != job_id:
        return f"Duplicate of job {again['id']} (applied {again['application_date']}); nothing submitted."
    d = packet_dir(job_id)
    ready = d / "application_ready.md"
    if not ready.exists():
        raise RuntimeError("No prepared packet. Run `apply prepare` first.")
    qa = json.loads((d / "screening_answers.json").read_text())
    if any(q["status"] != "auto" for q in qa):
        raise RuntimeError("Unanswered/unconfirmed screening questions remain. Fill them in "
                           f"{d / 'screening_answers.json'} (set status to \"auto\" once YOU have answered/confirmed).")
    print(ready.read_text(encoding="utf-8"), file=stdout)
    print(f"\nType {APPROVAL_PHRASE} to approve this application, anything else to cancel: ",
          end="", file=stdout, flush=True)
    if stdin.readline().strip() != APPROVAL_PHRASE:
        return "Cancelled - nothing submitted."
    print(f"Open {row['apply_url'] or row['url']} and submit with the prepared files. Type DONE once submitted: ",
          end="", file=stdout, flush=True)
    if stdin.readline().strip() != "DONE":
        return "Not recorded as applied."
    fu = db.mark_applied(con, job_id)
    return f"Recorded as Applied. Follow-up due {fu.isoformat()}."


def go(con, job_id: int, stdin=None, stdout=None, session_factory=None) -> str:
    """One command: open the employer form pre-filled -> you review in the browser -> you type SUBMIT -> it clicks submit."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    if not stdin.isatty():
        raise PermissionError("Needs an interactive terminal: a human must approve.")
    row = db.get(con, job_id)
    if row["application_date"]:
        return f"Already applied on {row['application_date']}; nothing to do."
    again = db.already_applied(con, job_dict(row))
    if again and again["id"] != job_id:
        return f"Duplicate of job {again['id']} (applied {again['application_date']}); nothing submitted."
    url = target_url(row)
    d = packet_dir(job_id)
    if not (d / "application_ready.md").exists():
        prepare(con, job_id)
    ready = (d / "application_ready.md").read_text(encoding="utf-8")
    print(ready, file=stdout)
    letter = (d / "cover_letter.md").read_text(encoding="utf-8")
    profile = config.load_profile()
    if session_factory is None:
        from .browser import FormSession
        session_factory = FormSession
    session = session_factory()
    try:
        session.open(url, profile, d, letter)
        print(f"\nOpened {url}\nFilled: {len(session.filled)} field(s). Left blank for YOU: "
              f"{session.left_blank or 'none'}", file=stdout)
        print("Check every field in the browser, answer anything blank, and tick any declarations yourself.",
              file=stdout)
        print(f"Type {APPROVAL_PHRASE} here to click the site's submit button, anything else to cancel: ",
              end="", file=stdout, flush=True)
        if stdin.readline().strip() != APPROVAL_PHRASE:
            return "Cancelled - nothing submitted."
        session.click_submit()
        print("Clicked submit. Did the site confirm the application? Type DONE to record it: ",
              end="", file=stdout, flush=True)
        if stdin.readline().strip() != "DONE":
            return "Not recorded as applied (check the browser, then run `jobagent status <id> Applied`)."
    finally:
        session.close()
    fu = db.mark_applied(con, job_id)
    return f"Recorded as Applied. Follow-up due {fu.isoformat()}."


def md_to_html(md: str) -> str:
    out = ["<html><meta charset='utf-8'><style>body{font:11pt Arial;margin:36px}h1{font-size:18pt}"
           "h2{font-size:12pt;border-bottom:1px solid #444}h3{font-size:11pt}</style><body>"]
    in_ul = False
    for line in md.splitlines():
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(line))
        if line.startswith("- "):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{esc[2:]}</li>")
            continue
        if in_ul:
            out.append("</ul>"); in_ul = False
        for n in (3, 2, 1):
            if line.startswith("#" * n + " "):
                out.append(f"<h{n}>{esc[n + 1:]}</h{n}>"); break
        else:
            out.append(f"<p>{esc}</p>" if line.strip() else "")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out) + "</body></html>"
