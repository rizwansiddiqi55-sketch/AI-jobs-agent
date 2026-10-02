import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_home = tempfile.mkdtemp()
os.environ["JOBAGENT_HOME"] = _home
for f in ("profile.json", "master_cv.md"):
    shutil.copy(ROOT / "data" / f, _home)

from jobagent import apply as ap, config, db, importer, matcher, recruiter, scam, tailor  # noqa: E402
from jobagent.salary import parse_aed_monthly  # noqa: E402

PROFILE = config.load_profile()
GOOD = {"company": "Acme", "title": "Senior Network Security Engineer", "location": "Dubai",
        "url": "https://acme.example/jobs/9?utm=x", "job_ref": "J9", "salary": "AED 25,000 per month",
        "description": "Requirements:\n- 8+ years\n- Cisco, BGP, OSPF, Fortinet, Palo Alto\n- CCNP\nPreferred:\n- Python"}


class TTY(io.StringIO):
    def isatty(self):
        return True


def fresh_db():
    p = config.db_path()
    if p.exists():
        p.unlink()
    return db.connect()


class Matching(unittest.TestCase):
    def test_strong_match(self):
        m = matcher.score(GOOD, PROFILE)
        self.assertGreaterEqual(m.score, 85)
        self.assertIn("python automation", m.missing)
        self.assertTrue(m.recommendation.startswith("APPLY"))

    def test_junior_capped(self):
        m = matcher.score({**GOOD, "title": "Junior Network Engineer"}, PROFILE)
        self.assertLessEqual(m.score, 40)
        self.assertTrue(m.recommendation.startswith("SKIP"))

    def test_international_needs_sponsorship(self):
        j = {**GOOD, "location": "London, UK"}
        self.assertTrue(matcher.score(j, PROFILE).recommendation.startswith("SKIP"))
        self.assertTrue(matcher.score({**j, "visa_sponsorship": "yes"}, PROFILE).score >= 65)

    def test_unheld_cert_flagged(self):
        m = matcher.score({**GOOD, "description": GOOD["description"] + "\nCCIE required"}, PROFILE)
        self.assertTrue(any("CCIE" in c for c in m.concerns))

    def test_ccna_covered_by_ccnp(self):
        m = matcher.score({**GOOD, "description": "CCNA required. Cisco routing."}, PROFILE)
        self.assertEqual(m.breakdown["certifications"]["points"], 10)

    def test_low_salary_concern(self):
        m = matcher.score({**GOOD, "salary": "AED 12,000 - 15,000"}, PROFILE)
        self.assertEqual(m.breakdown["salary"]["points"], 0)

    def test_scam_capped(self):
        m = matcher.score({**GOOD, "description": "Pay a registration fee. WhatsApp only."}, PROFILE)
        self.assertLessEqual(m.score, 20)


class Utilities(unittest.TestCase):
    def test_salary(self):
        self.assertEqual(parse_aed_monthly("AED 20k - 25k"), (20000, 25000))
        self.assertEqual(parse_aed_monthly("AED 300,000 per annum"), (25000, 25000))
        self.assertIsNone(parse_aed_monthly("$5000"))

    def test_business_days(self):
        self.assertEqual(db.add_business_days(date(2026, 10, 2), 5), date(2026, 10, 9))  # Fri -> next Fri

    def test_scam(self):
        self.assertTrue(scam.check("Send a visa fee via western union"))
        self.assertFalse(scam.check("We are hiring a network engineer in Dubai. Apply on our careers page."))

    def test_recruiter(self):
        self.assertEqual(recruiter.classify("Unfortunately we are not moving forward")[0], "Rejection")
        self.assertEqual(recruiter.classify("Can we schedule a call for an interview?")[0], "Interview invitation")
        self.assertEqual(recruiter.classify("Pay a processing fee and send your passport copy via WhatsApp")[0],
                         "Suspicious/scam message")


class Duplicates(unittest.TestCase):
    def test_same_url_ref_and_title(self):
        con = fresh_db()
        _, c1 = db.add_job(con, GOOD)
        self.assertTrue(c1)
        _, c2 = db.add_job(con, {**GOOD, "url": "https://www.acme.example/jobs/9/"})
        self.assertFalse(c2)
        _, c3 = db.add_job(con, {**GOOD, "url": "https://other/1", "job_ref": "J9"})
        self.assertFalse(c3)
        _, c4 = db.add_job(con, {**GOOD, "url": "https://other/2", "job_ref": "", "company": "ACME LLC"})
        self.assertFalse(c4)
        _, c5 = db.add_job(con, {**GOOD, "url": "https://o/3", "job_ref": "", "title": "Network Engineer"})
        self.assertTrue(c5)


class Tailoring(unittest.TestCase):
    def test_only_master_facts(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        cv, rep = tailor.tailor_cv(master, {**GOOD, "title": "SD-WAN Engineer",
                                            "description": "Fortinet SD-WAN, Terraform, Juniper"})
        self.assertIn("Fortinet SD-WAN", cv)
        self.assertNotIn("Juniper", cv)
        self.assertNotIn("Terraform", cv)
        self.assertIn("juniper", rep["jd_skills_not_in_cv_not_added"])
        for line in cv.splitlines():  # every bullet must exist in the master CV
            if line.startswith("- ") and "**" not in line:
                self.assertIn(line[2:], master)

    def test_letter_has_company_and_title(self):
        t = tailor.cover_letter(GOOD, PROFILE, ["cisco", "bgp"])
        self.assertIn("Acme", t)
        self.assertIn("Senior Network Security Engineer", t)


class Approval(unittest.TestCase):
    def setUp(self):
        self.con = fresh_db()
        self.row, _ = db.add_job(self.con, GOOD)
        self.id = self.row["id"]

    def test_placeholders_block_final(self):
        with self.assertRaises(RuntimeError):
            ap.prepare(self.con, self.id)

    def test_screening_rules(self):
        self.assertEqual(ap.answer_question("What is your notice period?", PROFILE)[1], "auto")
        self.assertEqual(ap.answer_question("I declare the above is true and accurate", PROFILE)[1], "needs_confirmation")
        self.assertEqual(ap.answer_question("Current salary?", PROFILE)[1], "needs_answer")
        self.assertEqual(ap.answer_question("Do you have Juniper JNCIE?", PROFILE)[1], "needs_answer")
        self.assertEqual(ap.answer_question("Do you have the right to work in UAE?", PROFILE)[1], "needs_answer")

    def test_submit_needs_tty_and_phrase(self):
        ap.prepare(self.con, self.id, ["Notice period?"], draft=True)
        with self.assertRaises(PermissionError):
            ap.submit(self.con, self.id, stdin=io.StringIO("SUBMIT\nDONE\n"), stdout=io.StringIO())
        out = ap.submit(self.con, self.id, stdin=TTY("no\n"), stdout=io.StringIO())
        self.assertIn("Cancelled", out)
        self.assertEqual(db.get(self.con, self.id)["application_date"], "")
        out = ap.submit(self.con, self.id, stdin=TTY("SUBMIT\nDONE\n"), stdout=io.StringIO())
        self.assertIn("Recorded as Applied", out)
        row = db.get(self.con, self.id)
        self.assertEqual(row["status"], "Applied")
        self.assertTrue(row["followup_date"])
        with self.assertRaises(RuntimeError):  # no second application
            ap.prepare(self.con, self.id, draft=True)
        self.assertIn("Already applied", ap.submit(self.con, self.id, stdin=TTY(""), stdout=io.StringIO()))

    def test_unanswered_questions_block_submit(self):
        ap.prepare(self.con, self.id, ["Current salary?"], draft=True)
        with self.assertRaises(RuntimeError):
            ap.submit(self.con, self.id, stdin=TTY("SUBMIT\n"), stdout=io.StringIO())


class Import(unittest.TestCase):
    def test_sample_file(self):
        con = fresh_db()
        s = importer.ingest(con, importer.load_file(str(ROOT / "data/samples/sample_jobs.json")))
        self.assertEqual(s["added"], 4)
        self.assertEqual(len(s["scam_flagged"]), 1)
        s2 = importer.ingest(con, importer.load_file(str(ROOT / "data/samples/sample_jobs.json")))
        self.assertEqual(s2["added"], 0)
        self.assertEqual(len(s2["duplicates"]), 4)


if __name__ == "__main__":
    unittest.main()
