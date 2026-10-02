"""Optional Playwright form filler (best effort - every site differs).

`fill()` pre-populates and STOPS; the user reviews in the visible browser.
`fill_and_submit()` is only reachable via apply.submit() after the human typed the approval phrase.
"""
from pathlib import Path

from .apply import md_to_html

FIELD_MAP = [  # (label regex, profile key)
    (r"first name", "first"), (r"(last|family|sur) ?name", "last"), (r"full name|^name", "name"),
    (r"e-?mail", "email"), (r"phone|mobile", "phone"), (r"linkedin", "linkedin"),
    (r"notice", "notice"), (r"expected.*(salary|ctc)|salary expectation", "salary"),
    (r"location|city", "location"),
]


def _values(profile):
    first, _, last = profile["name"].partition(" ")
    sal = profile["salary_expectation_aed"]
    return {"first": first, "last": last, "name": profile["name"], "email": profile["email"],
            "phone": profile["phone"], "linkedin": profile["linkedin"], "notice": profile["notice_period"],
            "salary": f"AED {sal['min']:,}-{sal['max']:,} per month", "location": profile["location"]}


def _make_pdf(page, md_path: Path) -> Path:
    pdf = md_path.with_suffix(".pdf")
    page.set_content(md_to_html(md_path.read_text(encoding="utf-8")))
    page.pdf(path=str(pdf), format="A4")
    return pdf


def fill(url, profile, packet: Path, qa, submit=False, headless=False):
    import re
    from playwright.sync_api import sync_playwright
    vals = _values(profile)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless)
        page = b.new_page()
        cv_pdf = _make_pdf(page, packet / "cv.md")
        page.goto(url)
        for el in page.query_selector_all("input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]), textarea"):
            label = " ".join(filter(None, [el.get_attribute("aria-label"), el.get_attribute("placeholder"),
                                           el.get_attribute("name"), el.get_attribute("id")])).lower()
            for pat, key in FIELD_MAP:
                if re.search(pat, label) and vals.get(key) and not el.input_value():
                    el.fill(vals[key]); break
            else:
                for q in qa:  # only pre-approved answers
                    if q["status"] == "auto" and q["question"].lower()[:30] in label:
                        el.fill(q["answer"])
        for f in page.query_selector_all("input[type=file]"):
            f.set_input_files(str(cv_pdf))
        if submit:
            page.get_by_role("button", name=re.compile(r"submit|apply", re.I)).first.click()
            page.wait_for_timeout(3000)
            b.close()
        else:
            input("Review the form in the browser. Press Enter here to close it (nothing was submitted)...")
            b.close()


def fill_and_submit(url, profile, packet, qa):
    fill(url, profile, packet, qa, submit=True, headless=False)
