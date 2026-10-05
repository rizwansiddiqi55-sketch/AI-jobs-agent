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


GENERIC = {"cisco", "routing", "switching", "firewall", "network security", "wireless", "vpn",
           "troubleshooting", "layer 3"}


def _mentions(skill: str, jd: str) -> int:
    return sum(len(re.findall(p, jd.lower())) for p in sk.SKILLS[skill])


def project_score(project, jd_sk: set, jd_w: set, jd: str = "") -> float:
    """Distinct JD skills a project demonstrates. Specific skills (Cisco ISE, ClearPass...) outweigh generic ones
    (Cisco, switching...) and skills the posting repeats count more. Small word-overlap tiebreak."""
    text = project[0] + " " + " ".join(project[1])
    score = 0
    for s in sk.find_skills(text) & jd_sk:
        score += (1 if s in GENERIC else 4) * min(3, max(1, _mentions(s, jd)))
    return score + min(_hits(text, set(), jd_w), 9) / 10


def best_project(master_text: str, job: dict):
    """(title, verbatim best bullet) of the master-CV project most relevant to the job."""
    sec = parse_master(master_text)["sections"].get("Key Projects", [])
    projects, cur = [], None
    for line in sec:
        if line.startswith("### "):
            cur = [line[4:].strip(), []]
            projects.append(cur)
        elif cur and line.strip().startswith("- "):
            cur[1].append(line.strip()[2:])
    if not projects:
        return None
    jd = f"{job.get('title', '')}\n{job.get('description', '')}"
    jd_sk, jd_w = sk.find_skills(jd), _jd_words(jd)
    title, bullets = max(projects, key=lambda p: project_score(p, jd_sk, jd_w, jd))
    return title, max(bullets, key=lambda b: _hits(b, jd_sk, jd_w))


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
    projects.sort(key=lambda p: -project_score(p, jd_sk, jd_w, jd))
    if projects:
        out.append("## Key Projects")
        for ptitle, pb in projects[:5]:
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


PRIORITY = ["cisco ise", "clearpass", "nac", "cisco ftd", "cisco asa", "palo alto", "fortinet", "sd-wan",
            "cloud networking", "zero trust", "bgp", "ospf", "mpls", "cisco wlc", "catalyst center", "cisco catalyst",
            "aruba", "wireless", "vpn", "firewall", "network security", "cisco"]
PRETTY = {"cloud networking": "cloud and hybrid networking", "zero trust": "Zero Trust", "vpn": "VPN", "cisco": "Cisco", "fortinet": "Fortinet", "palo alto": "Palo Alto", "sd-wan": "SD-WAN", "bgp": "BGP",
          "ospf": "OSPF", "mpls": "MPLS", "cisco ise": "Cisco ISE", "clearpass": "Aruba ClearPass",
          "cisco asa": "Cisco ASA", "cisco ftd": "Cisco Firepower (FTD)", "firewall": "firewalls",
          "network security": "network security", "aruba": "Aruba", "nac": "802.1X/NAC", "wireless": "wireless",
          "catalyst center": "Catalyst Center", "cisco catalyst": "Cisco Catalyst", "cisco wlc": "Cisco wireless controllers"}


def cover_letter(job: dict, profile: dict, matching: list, master_text: str | None = None) -> str:
    """Short factual letter. Uses only profile facts and verbatim lines from the master CV."""
    # Focus = the topics the posting itself mentions most (a certification named once in passing does not define the role).
    text = f"{job.get('title', '')}\n{job.get('description', '')}".lower()

    def mentions(s):
        return sum(len(re.findall(p, text)) for p in sk.SKILLS.get(s, []))
    ranked = sorted((m for m in PRIORITY if m in matching and mentions(m) >= 2),
                    key=lambda m: (-mentions(m), PRIORITY.index(m)))
    top = ranked[:4]
    # Name specific technologies only when the posting clearly centres on at least two of them.
    skill_txt = ", ".join(PRETTY[t] for t in top) if len(top) >= 2 else "enterprise network and security operations"
    avail = ("immediately" if profile["notice_period"].lower().startswith("immediate")
             else f"with {profile['notice_period']} notice")
    proj = ""
    if master_text:
        bp = best_project(master_text, job)
        if bp:
            title, bullet = bp
            proj = (f"On the {title} project, I "
                    f"{bullet[0].lower() + bullet[1:].rstrip('.')}.\n\n")
    visa = ""
    if profile.get("visa_status") == "cancelled" and profile.get("cover_letter_mentions_visa", True):
        visa = " I would need a new UAE work visa to be sponsored."
    certs = ", ".join(profile["certifications"])
    return f"""Dear Hiring Team at {job['company']},

I am applying for the {job['title']} position{(' in ' + job['location']) if job.get('location') else ''}. I am a network and security engineer with {profile['years_experience']}+ years of enterprise experience, based in {profile['location'].split(',')[0]} and available {avail}.{visa}

The role centres on {skill_txt}. I have worked in healthcare, government, oil & gas and critical-infrastructure environments, and the closest match from my CV is below.

{proj}I hold {certs}, and a BS in Computer Science. I would welcome a conversation about how I can support {job['company']}.

Kind regards,
{profile['name']}
{profile['phone']} | {profile['email']} | {profile['linkedin']}
"""
