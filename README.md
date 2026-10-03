# AI Job Application Agent

A local, approval-gated job-search assistant for network / network-security roles (UAE first).
Python 3.11+, standard library only (Playwright optional for form filling).

```
Find -> Filter -> Match -> Tailor CV -> Cover letter -> Fill -> Approve -> Submit -> Track -> Follow up
```

## Install on your own computer (recommended)
```bash
git clone <your private repo URL> && cd AI-jobs-agent
./install.sh            # Windows: install.bat      (add --browser for form pre-filling)
source .venv/bin/activate   # Windows: .venv\Scripts\activate
jobagent doctor         # tells you what is left to fill in
jobagent list
```
Needs Python 3.11+. Your data stays in `data/` (the tracker `data/jobs.db` is never committed). Back it up by copying that file.
Because submitting needs you to type SUBMIT in a terminal, run the agent locally for that step.

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
python -m jobagent set-url 1 https://careers.example.com/apply/123   # the EMPLOYER's own application page
python -m jobagent apply go 1                             # ONE COMMAND: opens it pre-filled, you check it, type SUBMIT, it clicks
python -m jobagent apply submit 1                         # only to RECORD an application you submitted yourself
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

## One-click applying (employer sites)
`jobagent apply go <id>` opens the employer's own careers page in a visible browser, fills your name, contact details,
notice period, salary, sponsorship answer, cover letter and uploads your tailored CV, then waits. You check the form,
answer anything left blank, tick any declarations yourself, and type `SUBMIT` in the terminal; only then does it click the
site's submit button. Then type `DONE` to record it and schedule the follow-up.
- Works on employer career pages you save with `jobagent set-url`. It refuses job boards (Indeed, LinkedIn, Bayt,
  Glassdoor, GulfTalent, Naukri...) because they forbid automated applying and need your login/captcha.
- Needs `./install.sh --browser` (Playwright). If you already have Chrome/Chromium, set `JOBAGENT_CHROMIUM=/path/to/chrome`.
- Form layouts differ; fields it can't recognise are listed and left blank for you.

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

## Optional read-only dashboard on Vercel
`site/index.html` is a static snapshot of the tracker (company, role, match, status, links; no CV, phone or email).
It is deployed to the Vercel project `ai-jobs-dashboard` with **Vercel Authentication on for all deployments**, so only
logged-in members of your Vercel team can open it. Refresh it with `jobagent export site/index.html`, then redeploy
(`vercel --prod` from `site/`, or ask Claude Code to redeploy). It is a snapshot, not a live view: the agent, the
database and the SUBMIT approval step all stay on your own computer.

## Phone version (Apply Kit)
A private mobile page keeps your tracker on your phone: ranked jobs, and for each one a tailored cover letter, CV text and
copy-paste screening answers, an **Open** button to the job on its own site, **I applied** (records the date and a
follow-up 5 business days later) and **Skip**. **Add job** takes any posting you paste (LinkedIn or anywhere else), asks
Claude to compare it with your CV, and drafts a letter. It never applies for you and never logs in to a job site.
The Vercel dashboard (`jobagent export site/index.html`) has an **Open kit** button on every row that opens that job's card in the Apply Kit (`#job-<id>`); set the Apply Kit link in `apply_kit_url` in `data/profile.json`.
`jobagent export-kit kit.json` rebuilds the data (it contains personal details; keep it private).
LinkedIn, Indeed and other job boards forbid bots, so on those you apply yourself in their app, with the answers copied from here.
