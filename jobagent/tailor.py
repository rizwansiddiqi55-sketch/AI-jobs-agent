"""CV tailoring and cover letters. Selection and ordering only - never adds facts.

The master CV is parsed into sections; for a given job we (a) re-rank skills lines and
experience bullets by relevance to the job description, (b) re-order summary sentences,
(c) set the headline to the target title. Output text is built exclusively from master text.
"""
import re
from pathlib import Path

from . import config
from . import skills as sk

PLACEHOLDER = re.compile(r"\[FILL IN[^\]]*\]")


def parse_master(text: str) -> dict:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.strip().splitlines()
    cv = {"name": lines[0].lstrip("# ").strip(), "contact": lines[1].strip(), "sections": {}}
    cur = None
    for line in lines[2:]:
        if line.startswith("## "):
            cur = line[3:].strip()
            cv["sections"][cur] = []
        elif cur:
            cv["sections"][cur].append(line)
    return cv


def _hits(text: str, jd_skills: set, jd_words: set) -> int:
    s = len(sk.find_skills(text) & jd_skills) * 3
    w = len(set(re.findall(r"[a-z0-9\-\.]{3,}", text.lower())) & jd_words)
    return s + w


def _jd_words(jd: str) -> set:
    stop = {"the", "and", "for", "with", "you", "our", "will", "are", "have", "this", "that", "from",
            "your", "work", "team", "experience", "years", "ability", "skills", "knowledge"}
    return {w for w in re.findall(r"[a-z0-9\-\.]{3,}", jd.lower()) if w not in stop}


def placeholders(master_text: str) -> list:
    body = re.sub(r"<!--.*?-->", "", master_text, flags=re.S)
    return PLACEHOLDER.findall(body)


def tailor_cv(master_text: str, job: dict) -> tuple[str, dict]:
    cv = parse_master(master_text)
    jd = f"{job.get('title', '')}\n{job.get('description', '')}"
    jd_sk, jd_w = sk.find_skills(jd), _jd_words(jd)
    sec = cv["sections"]
    out = [f"# {cv['name']}", cv["contact"], "", f"**{job['title']}**", ""]

    # Summary: same sentences, most relevant first (first sentence kept as the anchor).
    summ = " ".join(l.strip() for l in sec.get("Summary", []) if l.strip())
    sents = re.split(r"(?<=\.)\s+", summ)
    if len(sents) > 2:
        sents = [sents[0]] + sorted(sents[1:], key=lambda s: -_hits(s, jd_sk, jd_w))
    out += ["## Professional Summary", " ".join(sents), ""]

    # Skills: relevant lines first; relevant items first inside each line.
    skill_lines = [l.strip()[2:] for l in sec.get("Technical Skills", []) if l.strip().startswith("- ")]
    skill_lines.sort(key=lambda l: -_hits(l, jd_sk, jd_w))
    out.append("## Technical Skills")
    for l in skill_lines:
        head, _, items = l.partition(":")
        parts = [p.strip() for p in re.split(r",(?![^()]*\))", items) if p.strip()]
        parts.sort(key=lambda p: -_hits(p, jd_sk, jd_w))
        out.append(f"- **{head.strip()}:** {', '.join(parts)}")
    out.append("")

    # Experience: roles keep master order (chronology); bullets are ranked, top 7 kept.
    out.append("## Professional Experience")
    role, bullets = None, []

    def flush():
        if role:
            out.append(f"### {role}")
            bullets.sort(key=lambda b: -_hits(b, jd_sk, jd_w))  # stable: ties keep master order
            out.extend(f"- {b}" for b in bullets[:7])
            out.append("")

    for line in sec.get("Experience", []):
        if line.startswith("### "):
            flush()
            role, bullets = line[4:].strip(), []
        elif line.strip().startswith("- "):
            bullets.append(line.strip()[2:])
    flush()

    projects, cur = [], None
    for line in sec.get("Key Projects", []):
        if line.startswith("### "):
            cur = [line[4:].strip(), []]
            projects.append(cur)
        elif cur and line.strip().startswith("- "):
            cur[1].append(line.strip()[2:])
    projects.sort(key=lambda p: -_hits(p[0] + " " + " ".join(p[1]), jd_sk, jd_w))
    if projects:
        out.append("## Key Projects")
        for ptitle, pb in projects[:4]:
            out += [f"### {ptitle}", *[f"- {b}" for b in pb], ""]

    for name in ("Certifications", "Education"):
        items = [l.strip() for l in sec.get(name, []) if l.strip()]
        if items:
            out += [f"## {name}", *items, ""]

    cv_text = "\n".join(out).strip() + "\n"
    covered = sorted(jd_sk & sk.find_skills(master_text))
    absent = sorted(jd_sk - sk.find_skills(master_text))
    report = {"jd_skills_covered_by_cv": covered, "jd_skills_not_in_cv_not_added": absent,
              "placeholders_remaining": placeholders(master_text)}
    return cv_text, report


def cover_letter(job: dict, profile: dict, matching: list) -> str:
    """Short factual letter. Only states profile facts; skills limited to ones the job asks for AND the profile has."""
    top = [m for m in matching if m in {"cisco", "fortinet", "palo alto", "sd-wan", "bgp", "ospf", "mpls",
                                        "cisco ise", "clearpass", "cisco asa", "cisco ftd", "firewall",
                                        "network security", "aruba", "nac", "wireless", "catalyst center",
                                        "cisco catalyst", "cisco wlc"}][:5]
    pretty = {"cisco": "Cisco", "fortinet": "Fortinet", "palo alto": "Palo Alto", "sd-wan": "SD-WAN",
              "bgp": "BGP", "ospf": "OSPF", "mpls": "MPLS", "cisco ise": "Cisco ISE", "clearpass": "ClearPass",
              "cisco asa": "Cisco ASA", "cisco ftd": "Cisco FTD", "firewall": "firewalls",
              "network security": "network security", "aruba": "Aruba", "nac": "NAC", "wireless": "wireless",
              "catalyst center": "Catalyst Center", "cisco catalyst": "Cisco Catalyst", "cisco wlc": "Cisco WLC"}
    skill_txt = ", ".join(pretty[t] for t in top) if top else "routing, switching and network security"
    certs = ", ".join(profile["certifications"])
    return f"""Dear Hiring Team at {job['company']},

I am applying for the {job['title']} position{(' in ' + job['location']) if job.get('location') else ''}. I have {profile['years_experience']}+ years in routing, switching and network security, and I am based in {profile['location'].split(',')[0]} and available {'immediately' if profile['notice_period'].lower().startswith('immediate') else 'with ' + profile['notice_period'] + ' notice'}.

Your description calls for {skill_txt}. That is the core of my day-to-day work: I have implemented, migrated and troubleshot enterprise networks across healthcare, government, oil & gas and critical-infrastructure environments, with hands-on Cisco, Fortinet and Palo Alto security platforms.

I hold {certs}, and a BS in Computer Science. I would welcome a conversation about how I can support {job['company']}'s network and security objectives.

Kind regards,
{profile['name']}
{profile['email']} | {profile['linkedin']}
"""
