"""Command-line entry: python -m jobagent <command>."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import apply as apply_mod
from . import config, dashboard, db, importer, kit, matcher, recruiter, scam, tailor


def _rows(con, where="1=1", args=()):
    return con.execute(f"SELECT * FROM jobs WHERE {where} ORDER BY match_pct DESC NULLS LAST, id", args).fetchall()


def cmd_import(a, con):
    s = importer.ingest(con, importer.load_file(a.file))
    print(f"Added {s['added']}, duplicates {len(s['duplicates'])}, invalid {s['skipped_invalid']}")
    for d in s["duplicates"]:
        print("  duplicate:", d)
    for f in s["scam_flagged"]:
        print("  SCAM WARNING:", f)


def cmd_doctor(a, con):
    import importlib.util
    ok = True

    def check(good, msg, fix=""):
        nonlocal ok
        print(("  ok    " if good else "  FIX   ") + msg + ("" if good else f"  -> {fix}"))
        ok &= good
    p = config.load_profile()
    master = config.master_cv_path().read_text(encoding="utf-8")
    print(f"Data folder: {config.HOME}")
    check(sys.version_info >= (3, 11), f"Python {sys.version.split()[0]}", "install Python 3.11+")
    check(bool(p["phone"]), "Phone in profile.json", "add your phone number")
    check(not p["work_authorization"].startswith("TO CONFIRM"), "Work authorisation wording set",
          "edit work_authorization in data/profile.json (visa answers are left blank until then)")
    check(not tailor.placeholders(master), "Master CV has no [FILL IN] placeholders", "complete data/master_cv.md")
    check(all(not str(v).startswith("TO CONFIRM") for v in p["screening_answers"].values()),
          "Screening answers set (relocation / work authorisation)",
          "edit screening_answers in profile.json, or you will be asked each time")
    print("  info  browser form-filling " + ("available" if importlib.util.find_spec("playwright")
          else "not installed (optional: rerun installer with --browser)"))
    n = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"  info  {n} jobs in tracker ({config.db_path()})")
    print("Ready." if ok else "Fix the items above, then run `jobagent doctor` again.")


def cmd_export_kit(a, con):
    d = kit.write(con, a.out, a.kit_min)
    n = sum(1 for j in d['jobs'] if 'kit' in j)
    print(f"wrote {a.out}: {len(d['jobs'])} jobs, {n} with a full kit (contains personal data: keep it private)")


def cmd_rescore(a, con):
    print(f"Re-scored {importer.rescore(con)} jobs")


def cmd_add(a, con):
    desc = Path(a.description_file).read_text(encoding="utf-8") if a.description_file else ""
    job = dict(company=a.company, title=a.title, location=a.location, url=a.url, salary=a.salary or "",
               description=desc, source=a.source, job_ref=a.job_ref or "", posted_date=a.posted or "",
               remote=a.remote, visa_sponsorship=a.visa or "", experience_required=a.experience or "")
    s = importer.ingest(con, [job])
    print(s)


def cmd_list(a, con):
    where, args = ["1=1"], []
    if a.min_match is not None:
        where.append("match_pct >= ?"); args.append(a.min_match)
    if a.status:
        where.append("status = ?"); args.append(a.status)
    if a.location:
        where.append("lower(location) LIKE ?"); args.append(f"%{a.location.lower()}%")
    if a.title:
        where.append("lower(title) LIKE ?"); args.append(f"%{a.title.lower()}%")
    if a.today:
        where.append("date(created_at) = ?"); args.append(date.today().isoformat())
    print(dashboard.to_text(_rows(con, " AND ".join(where), args), short=not a.full))


def cmd_show(a, con):
    row = db.get(con, a.id)
    m = matcher.score({k: row[k] for k in row.keys()}, config.load_profile())
    print(f"#{row['id']} {row['company']} - {row['title']} ({row['location']})  status: {row['status']}")
    print(f"\nJob Match: {m.score:.0f}%")
    for k, v in m.breakdown.items():
        print(f"  {k:15} {v['points']:>5}/{v['max']:<3} {v['note']}")
    print("Matching skills:", ", ".join(m.matching) or "none")
    print("Missing skills: ", ", ".join(m.missing) or "none")
    print("Certs mentioned:", ", ".join(m.required_certs) or "none")
    for c in m.concerns:
        print("  concern:", c)
    if row["scam_flags"]:
        print("  SCAM WARNING:", row["scam_flags"])
    print("Recommendation:", m.recommendation)


def cmd_status(a, con):
    db.set_status(con, a.id, a.status, a.note or "")
    if a.status == "Applied" and not db.get(con, a.id)["application_date"]:
        print("Follow-up:", db.mark_applied(con, a.id))
    print("ok")


def cmd_prepare(a, con):
    qs = Path(a.questions).read_text().splitlines() if a.questions else []
    r = apply_mod.prepare(con, a.id, [q for q in qs if q.strip()], draft=a.draft)
    print(r["ready"])
    for p in r["problems"]:
        print("!!", p)


def cmd_submit(a, con):
    print(apply_mod.submit(con, a.id))


def cmd_go(a, con):
    print(apply_mod.go(con, a.id))


def cmd_set_url(a, con):
    row = db.get(con, a.id)
    probe = dict(row, apply_url=a.url)
    apply_mod.target_url(probe)  # validates: employer site only, no job boards
    db.update(con, a.id, apply_url=a.url)
    db.log(con, a.id, "apply_url", a.url)
    print(f"Employer application URL saved for #{a.id} {row['company']}. Run: jobagent apply go {a.id}")


def cmd_followups(a, con):
    rows = _rows(con, "followup_date != '' AND followup_date <= ? AND status IN ('Applied','Assessment','Interview','Follow-up Required')",
                 (date.today().isoformat(),))
    print(dashboard.to_text(rows) if rows else "Nothing due.")


def cmd_followup_draft(a, con):
    row, p = db.get(con, a.id), config.load_profile()
    body = (f"Subject: Following up - {row['title']} application\n\nDear Hiring Team at {row['company']},\n\n"
            f"I applied for the {row['title']} position on {row['application_date'] or '[date]'} and wanted to confirm "
            "my application was received. I remain very interested and would be glad to provide anything further.\n\n"
            f"Kind regards,\n{p['name']}\n{p['email']}\n\n[DRAFT - not sent. Review before sending.]")
    print(body)


def cmd_recruiter(a, con):
    text = Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    kind, flags = recruiter.classify(text)
    print("Classification:", kind)
    for f in flags:
        print("  flag:", f)
    print("\n--- Draft reply (NOT sent) ---\n" + recruiter.draft_reply(kind, text, config.load_profile()))


def cmd_export(a, con):
    rows = _rows(con)
    out = Path(a.out)
    kit_url = config.load_profile().get("apply_kit_url", "")
    render = {"md": dashboard.to_markdown, "html": lambda r: dashboard.to_html(r, kit_url)}[out.suffix[1:]]
    out.write_text(render(rows), encoding="utf-8")
    print("wrote", out)


def cmd_history(a, con):
    for r in con.execute("SELECT * FROM history WHERE job_id=? ORDER BY id", (a.id,)):
        print(r["at"], r["event"], r["detail"])


def build_parser():
    p = argparse.ArgumentParser(prog="jobagent", description=__doc__)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("import", help="import jobs from JSON/CSV"); s.add_argument("file"); s.set_defaults(f=cmd_import)
    s = sp.add_parser("export-kit", help="export the phone apply-kit JSON (personal data)"); s.add_argument("out"); s.add_argument("--kit-min", type=float, default=65); s.set_defaults(f=cmd_export_kit)
    s = sp.add_parser("doctor", help="check your setup"); s.set_defaults(f=cmd_doctor)
    s = sp.add_parser("rescore", help="re-run matching on all stored jobs"); s.set_defaults(f=cmd_rescore)
    s = sp.add_parser("add", help="add one job manually")
    for n in ("company", "title"):
        s.add_argument(n)
    s.add_argument("--location", default=""); s.add_argument("--url", default="")
    s.add_argument("--salary"); s.add_argument("--source", default="manual"); s.add_argument("--job-ref")
    s.add_argument("--posted"); s.add_argument("--remote", action="store_true"); s.add_argument("--visa")
    s.add_argument("--experience"); s.add_argument("--description-file"); s.set_defaults(f=cmd_add)
    s = sp.add_parser("list", help="dashboard"); s.add_argument("--min-match", type=float)
    s.add_argument("--status", choices=config.STATUSES); s.add_argument("--location"); s.add_argument("--title")
    s.add_argument("--today", action="store_true"); s.add_argument("--full", action="store_true"); s.set_defaults(f=cmd_list)
    s = sp.add_parser("show", help="match breakdown for one job"); s.add_argument("id", type=int); s.set_defaults(f=cmd_show)
    s = sp.add_parser("status", help="update a job's status"); s.add_argument("id", type=int)
    s.add_argument("status", choices=config.STATUSES); s.add_argument("--note"); s.set_defaults(f=cmd_status)
    ap = sp.add_parser("apply", help="prepare / fill / submit (approval-gated)").add_subparsers(dest="sub", required=True)
    s = ap.add_parser("prepare"); s.add_argument("id", type=int); s.add_argument("--questions", help="file with one screening question per line")
    s.add_argument("--draft", action="store_true", help="allow [FILL IN] placeholders (drafts only)"); s.set_defaults(f=cmd_prepare)
    s = ap.add_parser("go", help="ONE COMMAND: open employer form pre-filled, you approve, it clicks submit"); s.add_argument("id", type=int); s.set_defaults(f=cmd_go)
    s = ap.add_parser("submit", help="record an application you submitted yourself (approval-gated)"); s.add_argument("id", type=int); s.set_defaults(f=cmd_submit)
    s = sp.add_parser("set-url", help="save the employer's own application page for a job"); s.add_argument("id", type=int); s.add_argument("url"); s.set_defaults(f=cmd_set_url)
    s = sp.add_parser("followups", help="applications due for follow-up"); s.set_defaults(f=cmd_followups)
    s = sp.add_parser("followup-draft", help="draft (not send) a follow-up email"); s.add_argument("id", type=int); s.set_defaults(f=cmd_followup_draft)
    s = sp.add_parser("recruiter", help="classify a recruiter message and draft a reply"); s.add_argument("file", nargs="?"); s.set_defaults(f=cmd_recruiter)
    s = sp.add_parser("export", help="export dashboard (.md or .html)"); s.add_argument("out"); s.set_defaults(f=cmd_export)
    s = sp.add_parser("history", help="audit trail for a job"); s.add_argument("id", type=int); s.set_defaults(f=cmd_history)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    con = db.connect()
    try:
        a.f(a, con)
    except (KeyError, RuntimeError, PermissionError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
