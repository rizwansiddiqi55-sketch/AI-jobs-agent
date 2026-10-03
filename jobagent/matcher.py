"""Transparent job-compatibility scoring. Every point is explained in `breakdown`."""
import re
from dataclasses import dataclass, field

from . import scam
from . import skills as sk
from .salary import parse_aed_monthly

WEIGHTS = {"technical": 40, "experience": 15, "seniority": 10, "location": 10,
           "certifications": 10, "industry": 5, "visa": 5, "salary": 5}

JUNIOR = r"\b(junior|jr\.?|intern(ship)?|graduate|trainee|entry[- ]level|fresher|apprentice)\b"
SENIOR = r"\b(senior|sr\.?|lead|principal|staff|specialist|consultant|ccie)\b"
OTHER_TRACK = r"\b(manager|head of|director|vp|architect|presales|pre-sales|sales)\b"


@dataclass
class Match:
    score: float
    breakdown: dict
    matching: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    required_certs: list = field(default_factory=list)
    concerns: list = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self):
        return self.__dict__


def _split_required_preferred(desc: str):
    req_lines, pref_lines = [], []
    pref_mode = False
    for line in desc.splitlines():
        low = line.lower()
        if re.search(r"(preferred|nice to have|desirable|bonus|an advantage|is a plus|good to have)", low):
            pref_mode = True
        elif re.search(r"(requirements?|qualifications|must have|required|responsibilities|what you.ll)", low) \
                and len(line) < 60:
            pref_mode = False
        (pref_lines if pref_mode else req_lines).append(line)
    return "\n".join(req_lines), "\n".join(pref_lines)


REQ_WORDS = re.compile(r"\b(required|requirements?|must|mandatory|minimum|active|essential)\b", re.I)
PREF_SPLIT = re.compile(r"(\bprefer\w*|\bplus\b|\bdesirable\b|\badvantage\b|\bnice to have\b|\bbonus\b)", re.I)


def _required_certs(text: str) -> set:
    """Certs named in a 'required/must/active/minimum' context (text after a 'preferred/plus' cue doesn't count)."""
    out = set()
    for seg in re.split(r"[;\n.]", text):
        before = PREF_SPLIT.split(seg)[0]
        if REQ_WORDS.search(before):
            out |= sk.find_certs(before)
    return out


def _years_required(text: str):
    nums = [int(a) for a in re.findall(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*\d{0,2}\s*\+?\s*years?", text.lower())]
    return min(nums) if nums else None


def _location(job: dict, profile: dict):
    loc = (job.get("location") or "").lower()
    remote = bool(job.get("remote")) or "remote" in loc
    visa = (job.get("visa_sponsorship") or "").lower()
    sponsored = visa in ("yes", "true", "1", "available")
    if any(c in loc for c in sk.UAE_PRIMARY):
        return 10, "Dubai/Abu Dhabi - preferred location", [], "uae"
    if any(c in loc for c in sk.UAE_OTHER):
        return 8, "Other UAE location", [], "uae"
    if remote and not any(c in loc for c in sk.OTHER_COUNTRIES):
        return 8, "Remote", [], "remote"
    if remote:
        return 6, "Remote (confirm you can work for this employer from the UAE)", \
            ["Remote role tied to another country - confirm eligibility/payroll"], "remote"
    if sponsored:
        return 5, "International role with visa sponsorship stated", [], "intl"
    return 0, "International role without stated sponsorship", \
        ["International location with no stated visa sponsorship/relocation - your rules exclude this"], "intl-nosponsor"


def score(job: dict, profile: dict) -> Match:
    desc = job.get("description") or ""
    title = job.get("title") or ""
    full = f"{title}\n{desc}"
    have = {s.lower() for s in profile["skills"]}
    certs_have = {c.lower() for c in profile["certifications_short"]}
    concerns, bd = [], {}

    # --- technical skills (required weighted 1.0, preferred 0.5) ---
    req_text, pref_text = _split_required_preferred(desc)
    req = sk.find_skills(f"{title}\n{req_text}")
    pref = sk.find_skills(pref_text) - req
    matching = sorted((req | pref) & have)
    missing = sorted((req | pref) - have)
    denom = len(req) + 0.5 * len(pref)
    if denom:
        cov = (len(req & have) + 0.5 * len(pref & have)) / denom
        note = f"{len(req & have)}/{len(req)} required, {len(pref & have)}/{len(pref)} preferred skills held"
    else:
        cov, note = 0.5, "No recognisable skills in description (neutral)"
        concerns.append("Description lists no recognisable technical skills - review manually")
    missing_req = sorted(req - have)
    pts = max(0.0, cov * WEIGHTS["technical"] - 2 * len(missing_req))  # each missing required skill costs extra
    if missing_req:
        note += f"; -{2 * len(missing_req)} for missing required: {', '.join(missing_req)}"
    bd["technical"] = (round(pts, 1), note)
    for m in sorted(req - have):
        concerns.append(f"Required skill not in your profile: {m}")

    # --- experience ---
    need = _years_required(job.get("experience_required") or "") or _years_required(desc)
    yrs = profile["years_experience"]
    if need is None:
        pts, note = 0.75 * WEIGHTS["experience"], "Years not stated (neutral-positive)"
    elif yrs >= need:
        pts, note = WEIGHTS["experience"], f"{yrs} yrs vs {need}+ required"
    else:
        pts = WEIGHTS["experience"] * max(0, yrs / need)
        note = f"{yrs} yrs vs {need}+ required"
        concerns.append(f"Asks {need}+ years; you have {yrs}")
    bd["experience"] = (round(pts, 1), note)

    # --- seniority ---
    hard_skip = False
    if re.search(JUNIOR, title, re.I):
        pts, note = 0, "Junior/entry-level title"
        concerns.append("Junior/entry-level role - below your seniority")
        hard_skip = True
    elif re.search(OTHER_TRACK, title, re.I):
        pts, note = 5, "Management/architect/sales-track title"
        concerns.append("Title suggests a different track (management/architecture/pre-sales) - read the JD")
    elif re.search(SENIOR, title, re.I):
        pts, note = 10, "Senior-level title"
    else:
        pts, note = 7, "Mid-level/unspecified title (you are 15+ yrs)"
    bd["seniority"] = (pts, note)

    # --- location / visa ---
    lpts, lnote, lconc, kind = _location(job, profile)
    bd["location"] = (lpts, lnote)
    concerns += lconc
    if kind == "uae":
        needs = profile.get("visa_status") == "cancelled"
        hard = re.search(r"(must|should|need to)\s+(have|hold|possess)[^.\n]{0,30}(uae|valid|own)[^.\n]{0,20}visa|"
                         r"(valid|active|existing|current)\s+(uae\s+)?(residen\w+|visa|employment visa)|"
                         r"transferable\s+visa|visa\s+transfer|own\s+visa|(no|not)\s+(provide|offer|sponsor)\w*[^.\n]{0,20}visa|"
                         r"visa\s+(is\s+)?not\s+(provided|sponsored)", full, re.I)
        soft = re.search(r"(uae\s+)?(residen\w+|work eligibility|visa)[^.\n]{0,30}\bpreferred\b|\bpreferred\b[^.\n]{0,30}(uae\s+)?(residen\w+|work eligibility)", full, re.I)
        if needs and hard and not soft:
            bd["visa"] = (1, "Employer appears to require an existing UAE visa; yours is cancelled")
            concerns.append("Posting seems to require a valid/transferable UAE visa - yours is cancelled; ask before applying")
        elif needs and (hard or soft):
            bd["visa"] = (3, "Existing UAE residency/work eligibility preferred; yours is cancelled")
            concerns.append("Existing UAE residency preferred - you would need new visa sponsorship; say so up front")
        elif needs:
            bd["visa"] = (4, "UAE role - employer must sponsor a new work visa (ask early; not stated either way)")
        else:
            bd["visa"] = (5, "UAE role - confirm your UAE work-visa/transfer status with the employer")
    elif kind == "intl":
        bd["visa"] = (5, "Sponsorship stated")
    elif kind == "remote":
        bd["visa"] = (3, "Remote - authorisation to be confirmed")
    else:
        bd["visa"] = (0, "No sponsorship stated for international role")

    # --- certifications ---
    wanted = sk.find_certs(full)
    held = []
    for c in wanted:
        covered_by = sk.CERT_COVERED_BY.get(c)
        if c.lower() in certs_have or (covered_by and covered_by.lower() in certs_have):
            held.append(c)
    unmet = sorted(wanted - set(held))
    req_unmet = sorted(_required_certs(full) - set(held))
    if wanted:
        pts = WEIGHTS["certifications"] * len(held) / len(wanted)
        note = f"Held/covered: {held or 'none'}; not held: {unmet or 'none'}"
        for c in unmet:
            tag = "REQUIRED certification you do not hold" if c in req_unmet else "Certification mentioned that you do not hold"
            concerns.append(f"{tag}: {c}")
    else:
        pts, note = 0.8 * WEIGHTS["certifications"], "No certifications named"
    bd["certifications"] = (round(pts, 1), note)

    # --- industry ---
    mine = {i.lower() for i in profile["industries"]}
    hit = {i for i, pats in sk.INDUSTRY_KEYWORDS.items() if any(re.search(p, full, re.I) for p in pats)} & mine
    bd["industry"] = ((WEIGHTS["industry"], f"Relevant industry: {sorted(hit)}") if hit
                      else (0.6 * WEIGHTS["industry"], "Industry not stated/not a direct match (neutral)"))

    # --- salary ---
    rng = parse_aed_monthly(job.get("salary") or "")
    lo_exp = profile["salary_expectation_aed"]["min"]
    salary_gap = ""
    if rng and rng[1] < 0.8 * lo_exp:
        salary_gap = "far"
    elif rng and rng[1] < lo_exp:
        salary_gap = "below"
    if rng:
        if rng[1] >= lo_exp:
            bd["salary"] = (5, f"AED {rng[0]:,.0f}-{rng[1]:,.0f}/mo meets your {lo_exp:,} minimum")
        else:
            bd["salary"] = (0, f"AED {rng[0]:,.0f}-{rng[1]:,.0f}/mo is below your {lo_exp:,} minimum")
            concerns.append("Advertised salary below your expectation")
    else:
        bd["salary"] = (2.5, "Salary not stated/not AED-monthly (neutral)")

    sysadmin = False
    # Informational flags (no score impact): requirements the user must judge for themselves.
    if re.search(r"driving licen[cs]e", full, re.I):
        concerns.append("Mentions a UAE driving licence requirement - confirm you meet it")
    langs = re.findall(r"[^.\n]*\b(?:native|fluent|speaker|speakers)\b[^.\n]*\b(?:hindi|arabic|urdu|tagalog|french)\b[^.\n]*|[^.\n]*\b(?:hindi|arabic|urdu)\b[^.\n]*\b(?:speaker|speakers|preferred|must)\b[^.\n]*", full, re.I)
    if langs:
        concerns.append("Language requirement stated (your call whether to apply): " + langs[0].strip()[:80])
    if re.search(r"pre-?sales|rfp|rfi\b", full, re.I):
        concerns.append("Includes pre-sales/solution-architecture duties - read the JD")
    if re.search(r"windows server|cctv|pabx", full, re.I) and not re.search(r"windows server|cctv|pabx", " ".join(profile["skills"]), re.I):
        concerns.append("Systems/CCTV/telephony duties - may be a sysadmin role under a network title")
        sysadmin = True
    total = round(sum(v[0] for v in bd.values()), 1)
    if req_unmet:
        total = min(total, 79)
    if sysadmin:
        total = min(total, 70)
    if salary_gap == "far":
        total = min(total, 59)
        concerns.append("Advertised pay is far below your minimum (less than 80% of it)")
    elif salary_gap == "below":
        total = min(total, 79)
    flags = scam.check(full)
    if flags:
        concerns.append("Possible scam: " + "; ".join(flags))
        total = min(total, 20)
    elif hard_skip:
        total = min(total, 40)  # a hard-rule failure can never look like a good match
    elif kind == "intl-nosponsor":
        total = min(total, 49)
    rec = recommend(total, concerns, hard_skip, kind, salary_gap, len(missing_req), req_unmet)
    return Match(total, {k: {"points": v[0], "max": WEIGHTS[k], "note": v[1]} for k, v in bd.items()},
                 matching, missing, sorted(wanted), concerns, rec)


def recommend(total: float, concerns: list, hard_skip: bool, loc_kind: str, salary_gap: str = "", missing_req: int = 0,
              req_certs_unmet: list | None = None) -> str:
    if any(c.startswith("Possible scam") for c in concerns):
        return "DO NOT APPLY - scam indicators"
    if hard_skip or loc_kind == "intl-nosponsor":
        return "SKIP - fails a hard rule (seniority or location/sponsorship)"
    if salary_gap == "far":
        return "SKIP - advertised pay far below your minimum"
    if salary_gap == "below":
        return "REVIEW - good fit but advertised pay is below your minimum; apply only if negotiable"
    if req_certs_unmet:
        return f"REVIEW - required certification not held ({', '.join(req_certs_unmet)}); check whether it is a hard filter"
    if total >= 80 and missing_req > 2:
        return f"REVIEW - strong overall but {missing_req} required skills are missing; check you can credibly cover them"
    if total >= 80:
        return "APPLY - strong match; prepare tailored CV and cover letter"
    if total >= 65:
        return "REVIEW - decent match; read the concerns before preparing"
    return "SKIP - weak match unless you see something the description misses"
