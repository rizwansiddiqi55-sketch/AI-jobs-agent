"""Classify recruiter messages and draft replies (drafts only - never sent)."""
import re

from . import scam

CLASSES = [
    ("Suspicious/scam message", None),  # decided by scam.check
    ("Rejection", r"(unfortunately|regret to inform|not (be )?moving forward|other candidates|unsuccessful|not selected)"),
    ("Interview invitation", r"(interview|schedule a (call|meeting)|availability for|teams link|zoom link|meet with)"),
    ("Screening request", r"(screening|assessment|questionnaire|expected salary|notice period|current ctc|updated cv|send your cv|technical test)"),
    ("Follow-up", r"(following up|checking in|any update|circling back|reminder)"),
    ("Job opportunity", r"(opportunity|vacancy|opening|role|position|hiring|requirement)"),
]


def classify(text: str):
    flags = scam.check(text)
    if len(flags) >= 2 or any("fee" in f.lower() or "send money" in f.lower() for f in flags):
        return "Suspicious/scam message", flags
    for name, pat in CLASSES[1:]:
        if re.search(pat, text, re.I):
            return name, flags
    return "Recruiter outreach", flags


def draft_reply(kind: str, text: str, profile: dict) -> str:
    name = profile["name"]
    sal = profile["salary_expectation_aed"]
    sign = f"\n\nKind regards,\n{name}\n{profile['linkedin']}"
    if kind.startswith("Suspicious"):
        return ("DO NOT REPLY. Do not share documents, ID or payment. Report/block the sender.\n"
                "If you want to verify: contact the company via its official website, not the details in the message.")
    drafts = {
        "Job opportunity": "Hello,\n\nThank you for reaching out. I am interested in learning more. Could you share the "
                           "company name, location, full job description, salary range and whether it is permanent/on-site "
                           f"or hybrid? I am a Senior Network Engineer with 15+ years' experience, available {profile['notice_period'].lower()}."
                           + sign,
        "Interview invitation": "Hello,\n\nThank you for the invitation. I am happy to attend. [PROPOSE 2-3 SLOTS FROM YOUR CALENDAR]. "
                                "Please share the interview format, panel and any technical topics to prepare." + sign,
        "Screening request": "Hello,\n\nThank you. My updated CV is attached. Notice period: "
                             f"{profile['notice_period']}. Expected salary: AED {sal['min']:,}-{sal['max']:,} per month, "
                             "negotiable with the overall package. [CONFIRM visa status and any other answers before sending]." + sign,
        "Rejection": "Hello,\n\nThank you for letting me know and for your time. I remain interested in future network and "
                     "network-security roles at your company; please keep my profile on file." + sign,
        "Follow-up": "Hello,\n\nThank you for following up. [ANSWER THEIR SPECIFIC QUESTION]. I remain interested and available." + sign,
    }
    return drafts.get(kind, "Hello,\n\nThank you for contacting me. Could you share the role details, "
                            "location and salary range so I can consider it?" + sign)
