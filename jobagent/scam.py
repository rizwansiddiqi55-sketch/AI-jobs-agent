"""Heuristic scam / suspicious-message detector for job posts and recruiter messages."""
import re

RULES = [
    (r"(registration|processing|training|visa|security|application|medical)\s+(fee|deposit|charges?)",
     "Asks for a fee/deposit (legitimate employers never charge candidates)"),
    (r"(pay|transfer|send)\b.{0,40}\b(fee|deposit|money|amount)", "Asks you to send money"),
    (r"\b(western union|moneygram|crypto|bitcoin|usdt|gift ?cards?)\b", "Unusual payment method mentioned"),
    (r"\b(whatsapp|telegram|signal)\b.{0,60}\b(only|contact|apply|interview|number)\b",
     "Pushes you to WhatsApp/Telegram for the process"),
    (r"(interview|hiring)\s+(is|will be)?\s*(done\s*)?(only\s*)?(via|on|through)\s+(telegram|whatsapp|chat)",
     "Interview only via chat app"),
    (r"(passport|emirates id|bank (account|details)|card (number|details)|cvv|otp)\b.{0,40}\b(copy|scan|send|share|details|number)",
     "Requests ID/bank/card details before any formal offer"),
    (r"\b(no experience (needed|required)|earn \$?\d+.{0,10}(per day|daily|weekly)|guaranteed (job|income|visa))\b",
     "Too-good-to-be-true promise"),
    (r"\b(offer letter|visa)\b.{0,40}\b(immediately|guaranteed|same day)\b", "Guaranteed offer/visa claims"),
    (r"@(gmail|yahoo|hotmail|outlook|aol|proton)\.(com|me)\b.{0,0}", "Free-mail address used for recruiter contact (verify company domain)"),
    (r"\b(urgent(ly)? hiring|immediate joining).{0,40}(!!|100%)", "Aggressive urgency language"),
    (r"(wire|advance) payment|processing fee", "Advance payment language"),
]


def check(text: str, company_domain: str | None = None) -> list[str]:
    t = text or ""
    flags = []
    for pat, msg in RULES:
        if re.search(pat, t, re.I | re.S) and msg not in flags:
            flags.append(msg)
    if company_domain:
        emails = re.findall(r"[\w.+-]+@([\w-]+\.[\w.-]+)", t)
        bad = [d for d in emails if company_domain.lower() not in d.lower()
               and not re.match(r"(gmail|yahoo|hotmail|outlook)\.", d, re.I)]
        if bad:
            flags.append(f"Contact email domain(s) {sorted(set(bad))} do not match company domain {company_domain}")
    return flags
