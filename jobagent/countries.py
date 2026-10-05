"""Per-country pages for the Vercel dashboard: tracker jobs (UAE) + curated openings from data/countries.json,
plus general work-visa route notes with links to the official government sites.
The notes are orientation only: rules and thresholds change, so each page tells the reader to confirm on the official site.
The pages contain no CV, phone or email."""
import html
import json
from datetime import date
from pathlib import Path

from . import config, dashboard

COUNTRIES = [
    {"slug": "uae", "name": "UAE", "route": "You are already in the market here. With your visa cancelled, an employer files a new employment visa and work permit, so offers need the employer to start that process. Dubai and Abu Dhabi come first in your search priorities.",
     "links": [("UAE government portal: visas and residency", "https://u.ae/en/information-and-services/visa-and-emirates-id"), ("ICP (Federal Authority for Identity and Citizenship)", "https://icp.gov.ae")]},
    {"slug": "singapore", "name": "Singapore", "route": "Foreign professionals usually come in on an Employment Pass, which the employer applies for and which is assessed on salary and qualifications (including a points framework). An employer who is open to hiring from abroad is the key signal.",
     "links": [("Ministry of Manpower: Employment Pass", "https://www.mom.gov.sg/passes-and-permits/employment-pass")]},
    {"slug": "uk", "name": "United Kingdom", "route": "The usual route is the Skilled Worker visa, which needs a job offer from a Home Office licensed sponsor at an eligible occupation and salary level. Check the employer is on the register of licensed sponsors before applying.",
     "links": [("GOV.UK: Skilled Worker visa", "https://www.gov.uk/skilled-worker-visa"), ("Register of licensed sponsors", "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers")]},
    {"slug": "usa", "name": "United States", "route": "Employment visas such as H-1B depend on employer sponsorship and annual limits, and many roles (federal, banking, defence) are restricted to citizens or green-card holders. Postings that state no sponsorship cannot be pursued.",
     "links": [("USCIS: H-1B specialty occupations", "https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations"), ("USCIS: working in the US", "https://www.uscis.gov/working-in-the-united-states")]},
    {"slug": "ireland", "name": "Ireland", "route": "The Critical Skills Employment Permit is the main route for in-demand roles, with a job offer and a minimum salary threshold; the General Employment Permit covers other roles. Both are applied for with an employer offer.",
     "links": [("Department of Enterprise: Employment permits", "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/"), ("Critical Skills Employment Permit", "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/")]},
    {"slug": "germany", "name": "Germany", "route": "Qualified IT professionals can use the EU Blue Card or the skilled-worker residence permit with a job offer; the Opportunity Card lets some people look for work on arrival. Degree recognition and salary thresholds apply.",
     "links": [("Make it in Germany: visa and residence", "https://www.make-it-in-germany.com/en/visa-residence"), ("Federal Foreign Office: work visas", "https://www.auswaertiges-amt.de/en/visa-service")]},
    {"slug": "netherlands", "name": "Netherlands", "route": "The Highly Skilled Migrant permit requires an employer that is a recognised sponsor and a salary above the published threshold. Many local postings expect Dutch, so check the language line.",
     "links": [("IND: Highly skilled migrant", "https://ind.nl/en/residence-permits/work/highly-skilled-migrant"), ("IND: public register of recognised sponsors", "https://ind.nl/en/public-register-recognised-sponsors")]},
    {"slug": "china", "name": "China", "route": "Foreign employees need a work permit and a Z visa arranged by the employer, and the permit is assessed by a points-style classification. Postings are mostly in Chinese and often expect Mandarin.",
     "links": [("National Immigration Administration", "https://en.nia.gov.cn"), ("China visa application service (MFA)", "https://www.visaforchina.cn")]},
    {"slug": "thailand", "name": "Thailand", "route": "The employer typically sponsors a Non-Immigrant B visa and work permit, and the Smart Visa or Long-Term Resident visa exist for some skilled professionals. Confirm which applies with the employer and the official sites.",
     "links": [("Department of Employment: work permits", "https://www.doe.go.th/prd/alien/eng"), ("Thai e-Visa", "https://thaievisa.go.th")]},
]
BY_SLUG = {c["slug"]: c for c in COUNTRIES}
BY_NAME = {c["name"]: c for c in COUNTRIES}
BY_NAME.update({"UK": BY_SLUG["uk"], "USA": BY_SLUG["usa"]})

_UAE = ("dubai", "abu dhabi", "sharjah", "ajman", "ras al", "fujairah", "umm al", "al ain", "uae", "emirates", "إمارات")


def country_of(location: str) -> str:
    """Country slug for a tracker location string. Tracker jobs are UAE unless the text says otherwise."""
    loc = (location or "").lower()
    if any(k in loc for k in _UAE):
        return "uae"
    for c in COUNTRIES:
        if c["name"].lower() in loc or c["slug"] in loc:
            return c["slug"]
    return "uae" if not loc.strip() or "remote" in loc else "other"


def load_openings(path: Path | None = None) -> dict:
    p = path or (config.ROOT / "data" / "countries.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"openings": [], "none_found": {}}


CSS = ("<style>:root{--bg:#F2F6F7;--fg:#14232B;--line:#D3DDE1;--head:#E5EDEF;--accent:#0B6E6E;--ink:#fff;--muted:#566870;--warn:#8A3B12;--ok:#14663A}"
       "@media (prefers-color-scheme:dark){:root{--bg:#0E1A1F;--fg:#E6EEF1;--line:#27393F;--head:#1D3037;--accent:#4FC3BD;--ink:#06201F;--muted:#93A6AE;--warn:#F0A877;--ok:#7FD8A4;color-scheme:dark}}"
       "body{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;margin:0;padding:16px;max-width:980px}"
       "h1,h2{margin:16px 0 8px}h3{margin:0 0 4px;font-size:15px}a{color:var(--accent)}.muted,.hint{color:var(--muted);font-size:13px}"
       "nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}nav a{border:1px solid var(--line);border-radius:999px;padding:6px 12px;text-decoration:none;font-size:13px}"
       "nav a.on{background:var(--accent);color:var(--ink);border-color:var(--accent);font-weight:600}"
       ".card{border:1px solid var(--line);border-radius:10px;padding:12px;margin:0 0 10px}.tag{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:1px 8px;font-size:12px;margin-right:6px}"
       ".strong{color:var(--ok)}.blocked{color:var(--warn)}.wrap{overflow-x:auto}table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:6px 10px;text-align:left}th{background:var(--head)}"
       ".btn,.kit{display:inline-block;background:var(--accent);color:var(--ink);padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:600}.kit{padding:6px 10px;white-space:nowrap;font-size:13px}</style>")


def nav(active: str, prefix: str) -> str:
    """prefix is '' on the index page and '../' on country pages."""
    items = [("Dashboard", f"{prefix}index.html", active == "")]
    items += [(c["name"], f"{prefix}countries/{c['slug']}.html", active == c["slug"]) for c in COUNTRIES]
    return "<nav>" + "".join(f"<a{' class=on' if on else ''} href='{u}'>{html.escape(n)}</a>" for n, u, on in items) + "</nav>"


def _opening(o) -> str:
    fit = {"strong": ("Strong match", "strong"), "partial": ("Partial match", ""), "blocked": ("Not open to you", "blocked")}[o["fit"]]
    spons = {"no": "Sponsorship: refused", "yes": "Sponsorship: offered", "not stated": "Sponsorship: not stated"}[o["sponsorship"]]
    return (f"<div class='card'><h3><a href='{html.escape(o['url'])}' rel='noopener'>{html.escape(o['title'])}</a></h3>"
            f"<div>{html.escape(o['company'])} · {html.escape(o['location'])} · {html.escape(o['type'])} · posted {html.escape(o['posted'])}</div>"
            f"<div><span class='tag {fit[1]}'>{fit[0]}</span><span class='tag'>{spons}</span></div>"
            f"<div class='muted'>{html.escape(o['note'])}</div></div>")


def country_page(c: dict, openings: list, none_msg: str, tracker_rows: list, kit_url: str, checked: str) -> str:
    sec = ""
    if tracker_rows:
        sec += "<h2>Tracked jobs</h2><div class='wrap'><table><tr><th>Company</th><th>Position</th><th>Location</th><th>Match</th><th>Status</th>" + ("<th>Apply Kit</th>" if kit_url else "") + "</tr>"
        for r in tracker_rows:
            kit = f"<td><a class='kit' href='{html.escape(kit_url)}#job-{r['id']}'>Open kit</a></td>" if kit_url else ""
            m = f"{r['match_pct']:.0f}%" if r["match_pct"] is not None else "-"
            sec += (f"<tr><td>{html.escape(r['company'] or '-')}</td><td>{html.escape(r['title'] or '-')}</td><td>{html.escape(r['location'] or '-')}</td>"
                    f"<td>{m}</td><td>{html.escape(r['status'] or '-')}</td>{kit}</tr>")
        sec += "</table></div>"
    if openings:
        order = {"strong": 0, "partial": 1, "blocked": 2}
        sec += f"<h2>Openings seen (checked {html.escape(checked)})</h2>" + "".join(_opening(o) for o in sorted(openings, key=lambda o: order[o["fit"]]))
    if not tracker_rows and not openings:
        sec += f"<h2>Openings</h2><div class='card'>{html.escape(none_msg or 'No suitable openings found yet.')}</div>"
    links = "".join(f"<li><a href='{html.escape(u)}' rel='noopener'>{html.escape(t)}</a></li>" for t, u in c["links"])
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<meta name=robots content='noindex,nofollow'><title>{html.escape(c['name'])} Jobs</title>{CSS}"
            f"{nav(c['slug'], '../')}<h1>{html.escape(c['name'])}</h1>"
            f"<div class='card'><h3>Work-visa route (general orientation)</h3><div>{html.escape(c['route'])}</div>"
            "<p class='muted'>Rules, thresholds and fees change. Confirm everything on the official sites below, and ask the employer whether they sponsor before you spend time on an application.</p>"
            f"<ul>{links}</ul></div>{sec}"
            "<p class='hint'>Listings are links to the job posting; the agent applies only after you approve each application, and never through job boards.</p>")


def build_site(rows: list, outdir: Path, kit_url: str = "", openings_path: Path | None = None) -> list[Path]:
    """Write index.html (with country nav) and countries/<slug>.html under outdir. Returns paths written."""
    data = load_openings(openings_path)
    outdir = Path(outdir)
    (outdir / "countries").mkdir(parents=True, exist_ok=True)
    written = []
    index = outdir / "index.html"
    index.write_text(dashboard.to_html(rows, kit_url, nav_html=nav("", "")), encoding="utf-8")
    written.append(index)
    for c in COUNTRIES:
        ops = [o for o in data["openings"] if BY_NAME.get(o["country"], {}).get("slug") == c["slug"]]
        trk = [r for r in rows if country_of(r["location"]) == c["slug"]]
        p = outdir / "countries" / f"{c['slug']}.html"
        p.write_text(country_page(c, ops, data.get("none_found", {}).get(c["name"], ""), trk, kit_url, data.get("checked", "")), encoding="utf-8")
        written.append(p)
    return written
