# AI Job Application Agent

A local, approval-gated job-search assistant for network / network-security roles (UAE first).
Python 3.11+, standard library only (Playwright optional for form filling).

```
Find -> Filter -> Match -> Tailor CV -> Cover letter -> Fill -> Approve -> Submit -> Track -> Follow up
```

## Setup
1. Edit `data/profile.json` (add your phone; set `work_authorization` honestly).
2. Edit `data/master_cv.md`: replace every `[FILL IN ...]` with real employers, dates and achievements.
   The agent only reorders/selects text from this file, it never invents content.
3. Optional form filling: `pip install playwright` (browsers are managed separately).

## Usage
```bash
python -m jobagent import data/samples/sample_jobs.json   # score + scam check + dedupe on the way in
python -m jobagent list --min-match 80                    # dashboard (--status, --location, --today, --full)
python -m jobagent show 1                                 # transparent match breakdown
python -m jobagent apply prepare 1 --questions q.txt      # tailored CV, cover letter, "Application Ready" packet
python -m jobagent apply fill 1                           # pre-fill form in a browser; never submits
python -m jobagent apply submit 1                         # interactive; you type SUBMIT to approve
python -m jobagent followups                              # due follow-ups (5 business days after applying)
python -m jobagent followup-draft 1                       # draft only, never sent
python -m jobagent recruiter msg.txt                      # classify + draft reply, never sent
python -m jobagent export dashboard.html                  # or .md
python -m jobagent history 1                              # audit trail
```

## Match score (100 pts, every point explained by `show`)
technical skills 40 (required 1.0 / preferred 0.5) - years 15 - seniority 10 - location 10 -
certifications 10 - industry 5 - visa 5 - salary 5. Junior titles, scam indicators and international
roles without sponsorship are capped low. Unknowns score neutral, with a concern noted.

## Safety design
- `apply submit` needs a real TTY and the exact word `SUBMIT`; no flag bypasses it. Unanswered screening questions block it.
- Legal declarations, work authorisation, current salary and relocation answers are never auto-filled.
- Duplicate check by URL, company+job ID, and company+title; an applied job can't be prepared again.
- CV export is blocked while `[FILL IN]` placeholders remain (`--draft` overrides, for previews only).
- Emails and recruiter replies are drafts only.

## Finding jobs
Live searching is not scraped here (LinkedIn/Indeed terms forbid it). In a Claude Code session, ask
"Find new jobs today": it searches via the connected tools, writes a JSON file and imports it. See `CLAUDE.md`.
Import format: a JSON list (or CSV) with `company, title, location, salary, url, job_ref, posted_date, source, description, remote, visa_sponsorship`.

Status values: New, Review Required, Ready to Apply, Applied, Assessment, Interview, Follow-up Required, Rejected, Offer, Closed.
