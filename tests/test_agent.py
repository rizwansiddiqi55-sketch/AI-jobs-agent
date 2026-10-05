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

from jobagent import apply as ap, config, countries, db, importer, matcher, recruiter, scam, tailor  # noqa: E402
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

    def test_dc_core_is_not_full_ccnp_dc(self):
        m = matcher.score({**GOOD, "description": "CCNP Data Center required. Cisco Nexus."}, PROFILE)
        self.assertTrue(any("CCNP Data Center" in c for c in m.concerns))

    def test_required_vs_preferred_certs(self):
        d = "Fortinet certifications required: NSE 4 (minimum); NSE 5-7 strongly preferred. Cisco, BGP."
        m = matcher.score({**GOOD, "description": d, "salary": ""}, PROFILE)
        req = [c for c in m.concerns if c.startswith("REQUIRED")]
        self.assertEqual(len(req), 1)
        self.assertIn("NSE4", req[0])
        self.assertTrue(m.recommendation.startswith("REVIEW"))
        d2 = "Cisco, BGP. NSE 4 is a plus. Preferably PCNSE."
        m2 = matcher.score({**GOOD, "description": d2, "salary": ""}, PROFILE)
        self.assertFalse([c for c in m2.concerns if c.startswith("REQUIRED")])

    def test_expired_nse7_not_counted(self):
        m = matcher.score({**GOOD, "description": "NSE4 required. NSE7 preferred. Fortinet firewall."}, PROFILE)
        self.assertEqual(m.breakdown["certifications"]["points"], 0)
        self.assertTrue(any("NSE" in c for c in m.concerns))
        self.assertNotIn("NSE7", " ".join(PROFILE["certifications"]))

    def test_cv_lists_nse7_as_expired(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        cv, _ = tailor.tailor_cv(master, GOOD)
        self.assertIn("Fortinet NSE7 (expired)", cv)
        self.assertNotIn("NSE7 certified", cv)
        self.assertNotIn("NSE7", tailor.cover_letter(GOOD, PROFILE, []))

    def test_ccna_covered_by_ccnp(self):
        m = matcher.score({**GOOD, "description": "CCNA required. Cisco routing."}, PROFILE)
        self.assertEqual(m.breakdown["certifications"]["points"], 10)

    def test_low_salary_concern(self):
        m = matcher.score({**GOOD, "salary": "AED 12,000 - 15,000"}, PROFILE)
        self.assertEqual(m.breakdown["salary"]["points"], 0)

    def test_far_below_salary_is_skip(self):
        m = matcher.score({**GOOD, "salary": "AED 6,000 - 8,000 per month"}, PROFILE)
        self.assertLessEqual(m.score, 59)
        self.assertTrue(m.recommendation.startswith("SKIP"))

    def test_slightly_below_salary_is_review_not_apply(self):
        m = matcher.score({**GOOD, "salary": "AED 17,000 - 19,000 per month"}, PROFILE)
        self.assertLessEqual(m.score, 79)
        self.assertTrue(m.recommendation.startswith("REVIEW"))

    def test_unheld_vendor_skills_lower_score(self):
        d = "Requirements:\n- Cisco, BGP\n- VMware NSX, Infoblox, F5 APM, vSphere"
        m = matcher.score({**GOOD, "description": d}, PROFILE)
        self.assertIn("infoblox", m.missing)
        self.assertIn("vmware nsx", m.missing)
        self.assertLess(m.breakdown["technical"]["points"], 30)

    def test_sysadmin_title_mismatch_flagged(self):
        m = matcher.score({**GOOD, "description": "Windows Server, CCTV, PABX, firewalls, switches"}, PROFILE)
        self.assertTrue(any("sysadmin" in c for c in m.concerns))

    def test_many_missing_required_downgrades_apply(self):
        d = "Requirements:\n- Cisco, BGP, OSPF, Fortinet, Palo Alto, Infoblox, VMware NSX, vSphere"
        m = matcher.score({**GOOD, "description": d, "salary": ""}, PROFILE)
        self.assertTrue(m.recommendation.startswith("REVIEW"))

    def test_cancelled_visa_requiring_existing_visa(self):
        m = matcher.score({**GOOD, "description": GOOD["description"] + "\nMust have a valid UAE visa. No visa sponsorship provided."}, PROFILE)
        self.assertLessEqual(m.breakdown["visa"]["points"], 1)
        self.assertTrue(any("cancelled" in c for c in m.concerns))

    def test_valid_emirates_id_required(self):
        m = matcher.score({**GOOD, "description": GOOD["description"] + "\nCurrently based in the UAE with a valid Emirates ID."}, PROFILE)
        self.assertLessEqual(m.breakdown["visa"]["points"], 1)
        self.assertTrue(m.recommendation.startswith("SKIP for now"))

    def test_cancelled_visa_preferred_residency(self):
        m = matcher.score({**GOOD, "description": GOOD["description"] + "\nUAE residency preferred."}, PROFILE)
        self.assertEqual(m.breakdown["visa"]["points"], 3)

    def test_cancelled_visa_unstated_is_minor(self):
        m = matcher.score(GOOD, PROFILE)
        self.assertEqual(m.breakdown["visa"]["points"], 4)

    def test_three_year_role_is_below_level(self):
        m = matcher.score({**GOOD, "title": "Network Engineer", "salary": "", "experience_required": "3 years",
                           "description": "3 years experience. CCNA mandatory. Cisco switching, VLAN, STP."}, PROFILE)
        self.assertLessEqual(m.score, 59)
        self.assertTrue(m.recommendation.startswith("SKIP"))

    def test_five_year_minimum_is_only_a_note(self):
        m = matcher.score({**GOOD, "experience_required": "5+ years"}, PROFILE)
        self.assertGreaterEqual(m.score, 80)
        self.assertTrue(any("possibly below your level" in c for c in m.concerns))

    def test_ot_ics_role_is_a_different_specialism(self):
        d = ("Lead OT Cyber Security Engineer for industrial control systems. IEC 62443 gap assessments. "
             "Hands-on experience configuring switches, routers and firewalls. Relevant IEC/ISA, GICSP certification is essential.")
        m = matcher.score({**GOOD, "title": "Lead Engineer - OT Cyber Security", "description": d, "salary": ""}, PROFILE)
        self.assertLessEqual(m.score, 59)
        self.assertTrue(any("OT/industrial" in c for c in m.concerns))
        self.assertTrue(any(c.startswith("REQUIRED certification") and "GICSP" in c for c in m.concerns))
        self.assertTrue(m.recommendation.startswith("SKIP"))

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
        self.assertIn("## Key Projects", cv)
        self.assertNotIn("[FILL IN", cv)
        self.assertNotIn("Juniper", cv)
        self.assertNotIn("Terraform", cv)
        self.assertIn("juniper", rep["jd_skills_not_in_cv_not_added"])
        for line in cv.splitlines():  # every bullet must exist in the master CV
            if line.startswith("- ") and "**" not in line:
                self.assertIn(line[2:], master)

    def test_ise_job_surfaces_takreer_project_and_letter_quotes_cv(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        job = {**GOOD, "title": "Network & Security Engineer",
               "description": "Cisco ISE, 802.1X, MAB, TACACS+ NAC deployment. Cisco ASA, Firepower."}
        cv, _ = tailor.tailor_cv(master, job)
        self.assertIn("TAKREER", cv)
        title, bullet = tailor.best_project(master, job)
        self.assertIn("TAKREER", title)
        self.assertIn(bullet, master)  # verbatim from master, nothing invented
        letter = tailor.cover_letter(job, PROFILE, ["cisco ise", "nac"], master)
        self.assertIn("TAKREER", letter)
        self.assertIn("new UAE work visa", letter)

    def test_parenthesised_commas_kept_together(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        cv, _ = tailor.tailor_cv(master, GOOD)
        self.assertIn("Palo Alto NGFW (PA-800, PA-3000, VM-50, Panorama)", cv)

    def test_letter_does_not_overstate_from_one_keyword(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        t = tailor.cover_letter(GOOD, PROFILE, ["fortinet", "switching"], master)
        self.assertNotIn("centres on Fortinet", t)
        self.assertIn("enterprise network and security operations", t)
        stressed = {**GOOD, "description": "Palo Alto firewalls (Panorama). Palo Alto policies. Fortinet FortiGate. Fortinet HA. BGP."}
        t2 = tailor.cover_letter(stressed, PROFILE, ["fortinet", "palo alto", "bgp"], master)
        self.assertIn("centres on", t2)
        self.assertIn("Palo Alto", t2.split("centres on")[1].split(".")[0])

    def test_letter_focus_follows_what_the_posting_stresses(self):
        job = {**GOOD, "title": "Network Engineer (Hybrid Infrastructure & Cloud)",
               "description": "Design Azure network connectivity, hub and spoke, cloud networking governance, secure cloud network "
                              "architectures, cloud firewall policies. Firewalls, IPS and VPN gateways. Desirable: Fortinet NSE 4."}
        t = tailor.cover_letter(job, PROFILE, ["fortinet", "firewall", "cloud networking", "vpn"], (ROOT / "data" / "master_cv.md").read_text())
        focus = t.split("centres on")[1].split(".")[0]
        self.assertIn("cloud and hybrid networking", focus)
        self.assertNotIn("Fortinet", focus)  # named once, only as a desirable certification

    def test_letter_has_company_and_title(self):
        master = (ROOT / "data" / "master_cv.md").read_text()
        t = tailor.cover_letter(GOOD, PROFILE, ["cisco", "bgp"], master)
        self.assertIn("Acme", t)
        self.assertIn("available immediately", t)
        self.assertIn("Senior Network Security Engineer", t)


class Approval(unittest.TestCase):
    def setUp(self):
        self.con = fresh_db()
        self.row, _ = db.add_job(self.con, GOOD)
        self.id = self.row["id"]

    def test_placeholders_block_final(self):
        mp = config.master_cv_path()
        orig = mp.read_text()
        mp.write_text(orig.replace("Dubai, UAE |", "[FILL IN phone] | Dubai, UAE |", 1))
        try:
            with self.assertRaises(RuntimeError):
                ap.prepare(self.con, self.id)
        finally:
            mp.write_text(orig)

    def test_screening_rules(self):
        self.assertEqual(ap.answer_question("What is your notice period?", PROFILE)[1], "auto")
        self.assertEqual(ap.answer_question("I declare the above is true and accurate", PROFILE)[1], "needs_confirmation")
        self.assertEqual(ap.answer_question("Current salary?", PROFILE)[1], "needs_answer")
        self.assertEqual(ap.answer_question("Do you have Juniper JNCIE?", PROFILE)[1], "needs_answer")
        a, s = ap.answer_question("Do you have the right to work in UAE?", PROFILE)
        self.assertEqual(s, "auto")
        self.assertIn("cancelled", a)
        a, s = ap.answer_question("Do you require visa sponsorship?", PROFILE)
        self.assertTrue(a.startswith("Yes"))
        a, s = ap.answer_question("Are you willing to relocate?", PROFILE)
        self.assertEqual(s, "auto")
        self.assertIn("sponsor", a)

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


class EmployerApply(unittest.TestCase):
    def setUp(self):
        self.con = fresh_db()
        self.row, _ = db.add_job(self.con, GOOD)
        self.id = self.row["id"]

    def test_job_boards_are_never_automated(self):
        for url in ("https://to.indeed.com/aab6", "https://www.linkedin.com/jobs/view/1", "https://www.bayt.com/en/x"):
            with self.assertRaises(RuntimeError):
                ap.target_url({"id": 1, "apply_url": url})
        with self.assertRaises(RuntimeError):
            ap.target_url({"id": 1, "apply_url": ""})
        self.assertEqual(ap.target_url({"id": 1, "apply_url": "https://careers.acme.example/job/9"}),
                         "https://careers.acme.example/job/9")

    def test_choose_value_rules(self):
        from jobagent.browser import choose_value, _values
        v = _values(PROFILE)
        self.assertEqual(choose_value("First name", v, PROFILE, "L")[0], "Rizwan")
        self.assertEqual(choose_value("Cover letter", v, PROFILE, "LETTER")[0], "LETTER")
        self.assertIn("sponsor", choose_value("Do you require visa sponsorship?", v, PROFILE, "L")[0])
        self.assertIsNone(choose_value("What is your current salary?", v, PROFILE, "L")[0])
        self.assertIsNone(choose_value("I declare this is true and accurate", v, PROFILE, "L")[0])

    def test_go_needs_url_tty_and_exact_phrase(self):
        class Fake:
            def __init__(self): self.filled, self.left_blank, self.clicked, self.closed = ["x"], [], False, False
            def open(self, *a): return self
            def click_submit(self): self.clicked = True
            def close(self): self.closed = True
        with self.assertRaises(RuntimeError):  # no employer URL yet
            ap.go(self.con, self.id, stdin=TTY("SUBMIT\n"), stdout=io.StringIO(), session_factory=Fake)
        db.update(self.con, self.id, apply_url="https://careers.acme.example/job/9")
        with self.assertRaises(PermissionError):
            ap.go(self.con, self.id, stdin=io.StringIO("SUBMIT\nDONE\n"), stdout=io.StringIO(), session_factory=Fake)
        s = Fake()
        out = ap.go(self.con, self.id, stdin=TTY("submit\n"), stdout=io.StringIO(), session_factory=lambda: s)
        self.assertIn("Cancelled", out)
        self.assertFalse(s.clicked)
        self.assertTrue(s.closed)
        s = Fake()
        out = ap.go(self.con, self.id, stdin=TTY("SUBMIT\nDONE\n"), stdout=io.StringIO(), session_factory=lambda: s)
        self.assertTrue(s.clicked)
        self.assertIn("Recorded as Applied", out)
        self.assertEqual(db.get(self.con, self.id)["status"], "Applied")
        self.assertIn("Already applied", ap.go(self.con, self.id, stdin=TTY(""), stdout=io.StringIO(), session_factory=Fake))

    def test_real_browser_prefill_and_gate(self):
        try:
            import playwright  # noqa: F401
            from jobagent.browser import FormSession
        except ImportError:
            self.skipTest("playwright not installed")
        db.update(self.con, self.id, apply_url=(ROOT / "tests/fixtures/apply_form.html").as_uri())
        ap.prepare(self.con, self.id, [])
        d = ap.packet_dir(self.id)
        s = FormSession(headless=True)
        try:
            try:
                s.open((ROOT / "tests/fixtures/apply_form.html").as_uri(), PROFILE, d, (d / "cover_letter.md").read_text())
            except Exception as e:  # no usable Chromium on this machine
                if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
                    self.skipTest("Chromium not available (set JOBAGENT_CHROMIUM)")
                raise
            p = s.page
            self.assertEqual(p.input_value("#fn"), "Rizwan")
            self.assertEqual(p.input_value("#ln"), "Siddiqi")
            self.assertEqual(p.input_value("#em"), PROFILE["email"])
            self.assertEqual(p.input_value("#np"), "Immediate")
            self.assertIn("21,000", p.input_value("#es"))
            self.assertTrue(p.input_value("#vs").startswith("Yes"))
            self.assertIn("Dear Hiring Team", p.input_value("#cl"))
            self.assertEqual(p.input_value("#cs"), "")          # current salary: left for the human
            self.assertFalse(p.is_checked("#decl"))             # declaration: never ticked
            self.assertEqual(p.title(), "Apply - Test Employer")  # not submitted yet
            self.assertTrue(any("current salary" in b.lower() for b in s.left_blank))
            self.assertTrue(p.evaluate("document.getElementById('cv').files.length") == 1)
            s.click_submit()
            self.assertEqual(p.title(), "SUBMITTED")
        finally:
            s.close()


class Dashboard(unittest.TestCase):
    def test_html_links_each_row_to_its_kit_and_has_no_personal_details(self):
        from jobagent import dashboard
        con = fresh_db()
        row, _ = db.add_job(con, GOOD)
        rows = con.execute("SELECT * FROM jobs").fetchall()
        html_ = dashboard.to_html(rows, "https://claude.ai/artifact/abc")
        self.assertIn(f"https://claude.ai/artifact/abc#job-{row['id']}", html_)
        self.assertIn("Open Apply Kit", html_)
        self.assertIn("noindex", html_)
        self.assertIn("prefers-color-scheme:dark", html_)
        for secret in (PROFILE["phone"], PROFILE["email"]):
            self.assertNotIn(secret, html_)
        self.assertNotIn("Open Apply Kit", dashboard.to_html(rows))


class DailyUpdate(unittest.TestCase):
    def _kit_dir(self):
        d = Path(tempfile.mkdtemp()) / "jobs"
        d.mkdir(parents=True)
        docs = [
            {"id": 1, "company": "Acme", "title": "Senior Network Engineer", "location": "Dubai, UAE", "url": "https://to.indeed.com/a1",
             "status": "Applied", "appliedOn": "2026-10-03", "followUp": "2026-10-09", "match": 90, "source": "Indeed"},
            {"id": 2, "company": "Beta Corp", "title": "Network Security Engineer", "location": "Abu Dhabi", "url": "https://to.indeed.com/b2",
             "status": "Closed", "match": 70},
            {"id": "li_x1", "company": "Gamma", "title": "Firewall Engineer", "location": "Dubai", "url": "https://www.linkedin.com/jobs/view/9",
             "status": "New", "match": 80, "source": "LinkedIn (pasted)"},
        ]
        for x in docs:
            (d / f"job_{x['id']}.json").write_text(json.dumps({"id": f"job_{x['id']}", "data": x, "version": 2}))
        return d.parent

    def test_restore_keeps_ids_statuses_and_dedupes(self):
        from jobagent import restore
        con = fresh_db()
        r = restore.restore(con, str(self._kit_dir()))
        self.assertEqual((r["restored"], r["foreign"], r["max_id"]), (3, 1, 2))
        self.assertEqual(db.get(con, 1)["status"], "Applied")
        self.assertEqual(db.get(con, 1)["followup_date"], "2026-10-09")
        incoming = [
            {"company": "ACME LLC", "title": "Senior Network Engineer", "location": "Dubai", "url": "https://to.indeed.com/NEWLINK", "posted_date": "2026-10-01"},
            {"company": "Beta Corp", "title": "Network Security Engineer", "location": "Abu Dhabi", "url": "https://x/other", "posted_date": "2026-10-01"},
            {"company": "Gamma", "title": "Firewall Engineer", "location": "Dubai", "url": "https://y", "posted_date": "2026-10-01"},
            {"company": "Delta", "title": "Senior Network Engineer", "location": "Dubai", "url": "https://d", "posted_date": date.today().isoformat()},
            {"company": "Old Co", "title": "Network Engineer", "location": "Dubai", "url": "https://o", "posted_date": "2025-01-01"},
            {"company": "Kid Co", "title": "Junior Network Engineer", "location": "Dubai", "url": "https://k", "posted_date": date.today().isoformat()},
            {"company": "Bakery", "title": "Pastry Chef", "location": "Dubai", "url": "https://p", "posted_date": date.today().isoformat()},
        ]
        res = restore.filter_new(con, incoming)
        self.assertEqual([j["company"] for j in res["new"]], ["Delta"])
        self.assertEqual(len(res["duplicates"]), 3)  # same company+title re-posted with a new link is still a duplicate
        self.assertEqual((len(res["too_old"]), len(res["not_relevant"])), (1, 2))

    def test_rescore_never_touches_restored_jobs_without_a_description(self):
        from jobagent import restore
        con = fresh_db()
        restore.restore(con, str(self._kit_dir()))
        before = con.execute("SELECT id, match_pct FROM jobs ORDER BY id").fetchall()
        importer.rescore(con)
        after = con.execute("SELECT id, match_pct FROM jobs ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after])

    def test_new_jobs_continue_numbering_and_kit_new_only_exports_them(self):
        from jobagent import restore
        con = fresh_db()
        restore.restore(con, str(self._kit_dir()))
        row, created = db.add_job(con, {**GOOD, "company": "Fresh Co", "url": "https://fresh/1", "job_ref": "F1"})
        self.assertTrue(created)
        self.assertEqual(row["id"], 3)  # restored real ids were 1 and 2; the phone-only job has a negative id
        self.assertLess(con.execute("SELECT id FROM jobs WHERE company='Gamma'").fetchone()[0], 0)
        out = Path(tempfile.mkdtemp()) / "kit.json"
        split = Path(tempfile.mkdtemp()) / "split"
        docs = restore.kit_new(con, 3, str(out), split_dir=str(split))
        self.assertEqual([d["company"] for d in docs], ["Fresh Co"])
        self.assertIn("kit", docs[0])
        writes = json.loads((split / "writes.json").read_text())
        self.assertEqual([w["doc_id"] for w in writes], ["job_3"])
        self.assertTrue(Path(writes[0]["file_path"]).exists())

    def test_dashboard_export_skips_phone_only_rows(self):
        from jobagent import restore, dashboard
        con = fresh_db()
        restore.restore(con, str(self._kit_dir()))
        rows = con.execute("SELECT * FROM jobs WHERE id > 0").fetchall()
        self.assertNotIn("Gamma", dashboard.to_html(rows, "https://claude.ai/artifact/x"))


class Import(unittest.TestCase):
    def test_sample_file(self):
        con = fresh_db()
        s = importer.ingest(con, importer.load_file(str(ROOT / "data/samples/sample_jobs.json")))
        self.assertEqual(s["added"], 4)
        self.assertEqual(len(s["scam_flagged"]), 1)
        s2 = importer.ingest(con, importer.load_file(str(ROOT / "data/samples/sample_jobs.json")))
        self.assertEqual(s2["added"], 0)
        self.assertEqual(len(s2["duplicates"]), 4)


class Countries(unittest.TestCase):
    def test_country_of(self):
        self.assertEqual(countries.country_of("Dubai, UAE"), "uae")
        self.assertEqual(countries.country_of("Abu Dhabi"), "uae")
        self.assertEqual(countries.country_of("Remote"), "uae")
        self.assertEqual(countries.country_of("Cork, Ireland"), "ireland")

    def test_openings_valid(self):
        d = countries.load_openings()
        for o in d["openings"]:
            self.assertIn(o["country"], countries.BY_NAME)
            self.assertIn(o["sponsorship"], ("yes", "no", "not stated"))
            self.assertIn(o["fit"], ("strong", "partial", "blocked"))
            self.assertTrue(o["url"].startswith("https://"))
            if o["sponsorship"] == "no":
                self.assertEqual(o["fit"], "blocked")  # never suggest a role that refuses sponsorship

    def test_build_site(self):
        out = Path(tempfile.mkdtemp())
        written = countries.build_site([], out)
        self.assertEqual(len(written), 1 + len(countries.COUNTRIES))
        for c in countries.COUNTRIES:
            page = (out / "countries" / f"{c['slug']}.html").read_text(encoding="utf-8")
            self.assertIn("noindex", page)
            self.assertIn("official sites", page)
            self.assertNotIn("@", page.replace("@media", ""))  # no email addresses
        shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()
