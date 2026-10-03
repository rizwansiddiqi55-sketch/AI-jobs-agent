"""Playwright form filler for EMPLOYER career pages (best effort - every site differs).

FormSession.open() fills what it can and STOPS. click_submit() is only called by apply.go() after the
human typed the approval phrase. Checkboxes/radios are never touched (legal declarations stay yours),
and anything the profile cannot answer is left blank for you to complete in the visible browser.
"""
import os
import re
from pathlib import Path

from .apply import answer_question, md_to_html

FIELD_MAP = [  # (label regex, value key) - checked before screening answers
    (r"first name|given name", "first"), (r"last name|family name|surname", "last"),
    (r"full name|^name\b|your name", "name"), (r"e-?mail", "email"), (r"phone|mobile|contact number", "phone"),
    (r"linkedin", "linkedin"), (r"current location|city|location", "location"),
]
SKIP_TYPES = "hidden|file|checkbox|radio|submit|button|password|search"


def _values(profile):
    first, _, last = profile["name"].partition(" ")
    return {"first": first, "last": last, "name": profile["name"], "email": profile["email"],
            "phone": profile["phone"], "linkedin": profile["linkedin"], "location": profile["location"]}


_LABEL_JS = """el => [
  ...(el.labels ? [...el.labels].map(l => l.innerText) : []),
  el.getAttribute('aria-label'), el.getAttribute('placeholder'), el.getAttribute('name'), el.id
].filter(Boolean).join(' ')"""


def choose_value(label: str, vals: dict, profile: dict, letter: str):
    """-> (text or None, how). Pure function so it can be unit-tested without a browser."""
    low = label.lower()
    if "cover" in low and "letter" in low:
        return letter, "cover letter"
    for pat, key in FIELD_MAP:
        if re.search(pat, low) and vals.get(key):
            return vals[key], key
    ans, status = answer_question(label, profile)
    return (ans, "screening answer") if status == "auto" and ans else (None, status)


class FormSession:
    def __init__(self, headless=False):
        self.headless = headless
        self._pw = self.browser = self.page = None
        self.filled, self.left_blank = [], []

    def open(self, url, profile, packet: Path, letter: str):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        exe = os.environ.get("JOBAGENT_CHROMIUM") or None  # optional: use an existing Chromium/Chrome binary
        self.browser = self._pw.chromium.launch(headless=self.headless, executable_path=exe)
        self.page = self.browser.new_page()
        cv_pdf, cl_pdf = self._pdf(packet / "cv.md"), self._pdf(packet / "cover_letter.md")
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")
        vals = _values(profile)
        sel = f"input:not([type]), input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio])" \
              f":not([type=submit]):not([type=button]):not([type=password]):not([type=search]), textarea"
        for el in self.page.query_selector_all(sel):
            if not el.is_visible() or el.input_value():
                continue
            label = el.evaluate(_LABEL_JS)
            text, how = choose_value(label, vals, profile, letter)
            if text:
                el.fill(text)
                self.filled.append(f"{label.strip()[:40]} <- {how}")
            else:
                self.left_blank.append(label.strip()[:60] or "(unlabelled field)")
        files = [f for f in self.page.query_selector_all("input[type=file]")]
        for f in files:
            label = f.evaluate(_LABEL_JS).lower()
            f.set_input_files(str(cl_pdf if "cover" in label else cv_pdf))
            self.filled.append(f"{label.strip()[:40] or 'file upload'} <- " + ("cover letter PDF" if "cover" in label else "CV PDF"))
        return self

    def _pdf(self, md_path: Path) -> Path:
        pdf = md_path.with_suffix(".pdf")
        p = self.browser.new_page()
        p.set_content(md_to_html(md_path.read_text(encoding="utf-8")))
        p.pdf(path=str(pdf), format="A4")
        p.close()
        return pdf

    def click_submit(self):
        btn = self.page.get_by_role("button", name=re.compile(r"^\s*(submit|apply|send application)", re.I)).first
        btn.click()
        self.page.wait_for_timeout(3000)

    def close(self):
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()
