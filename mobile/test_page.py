import json, os, sys
from playwright.sync_api import sync_playwright
SP = os.environ.get("KIT_DIR", os.path.dirname(os.path.abspath(__file__)))
kit = json.load(open(f"{SP}/kit.json"))
body = open(f"{SP}/apply_kit.html", encoding="utf-8").read()
page_html = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
             '<style>:root{color-scheme:light;padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0)}body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>' + body + '</body></html>')
open(f"{SP}/page_test.html", "w", encoding="utf-8").write(page_html)

MOCK = """
(() => {
  const store = {jobs: {}, profile: {}};
  const subs = [];
  const SEED = %s;
  SEED.jobs.forEach(j => store.jobs['job_' + j.id] = j);
  store.profile.me = SEED.profile;
  const snapDoc = (id, data) => ({id, exists: data !== undefined, data: () => data});
  const notify = () => subs.forEach(f => f());
  const docRef = path => { const [c, id] = path.split('/'); return {
    get: async () => snapDoc(id, store[c][id]),
    set: async d => { store[c][id] = JSON.parse(JSON.stringify(d)); notify(); },
    update: async d => { if (!store[c][id]) throw {code:'invalid_argument'}; Object.assign(store[c][id], JSON.parse(JSON.stringify(d))); notify(); },
    onSnapshot: (next) => { const f = () => next(snapDoc(id, store[c][id])); subs.push(f); setTimeout(f, 0); return () => {}; } }; };
  const colRef = c => ({ onSnapshot: (next) => { const f = () => next({docs: Object.entries(store[c]).map(([id, d]) => snapDoc(id, d))}); subs.push(f); setTimeout(f, 0); return () => {}; } });
  const sample = { json: async (prompt) => { window.__lastPrompt = prompt; return {match: 81, recommendation: 'APPLY', matching: ['Cisco ISE','Fortinet'], missing: ['SASE'], concerns: ['Check visa requirement'], cover_letter: 'Dear Hiring Team, test letter.'}; } };
  window.__store = store;
  window.claude = { use: async (n) => n === 'db' ? {doc: docRef, collection: colRef} : n === 'sample' ? Object.assign(async()=>({}), sample) : null };
})();
""" % json.dumps(kit)

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS " if cond else "FAIL ") + name, extra)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=os.environ.get("JOBAGENT_CHROMIUM"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "fonts" not in m.text and "net::" not in m.text else None)
    page.add_init_script(MOCK)
    page.goto("file://" + f"{SP}/page_test.html")
    page.wait_for_selector(".card")
    check("no script errors", not errs, str(errs)[:200])
    check("tabs all visible at 390px", page.evaluate("(()=>{const n=document.getElementById('tabs');return n.scrollWidth<=n.clientWidth+1})()"))
    cards = page.locator(".card")
    n_open = sum(1 for j in kit["jobs"] if j["status"] not in ("Applied","Closed") and not j["recommendation"].upper().startswith(("SKIP","DO NOT")))
    check("cards shown = non-skip open jobs", cards.count() == n_open, f"{cards.count()} vs {n_open}")
    check("best match first (Darwinbox 92)", "Darwinbox" in cards.first.inner_text() and "92" in cards.first.inner_text())
    check("no horizontal scroll", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    cards.first.locator(".head").click()
    page.wait_for_selector(".detail")
    det = page.locator(".detail").first
    txt = det.inner_text()
    check("open link labelled Indeed", "Open on Indeed" in txt)
    check("board note says you apply yourself", "Nothing here applies for you" in txt)
    check("cover letter shown", "Dear Hiring Team at Darwinbox" in txt)
    check("current salary left to you", "Your call" in txt and "Tick this yourself" in txt)
    href = det.locator("a.btn.primary").get_attribute("href")
    check("link is the https job url", href.startswith("https://to.indeed.com/"), href)
    det.locator(".blk").first.locator("button", has_text="Copy").click()
    page.wait_for_timeout(200)
    clip = page.evaluate("navigator.clipboard.readText()")
    check("copy puts cover letter on clipboard", clip.startswith("Dear Hiring Team at Darwinbox"))
    check("no [object] text from bad children", "[object" not in page.locator("body").inner_text())
    check("skill chips rendered", det.locator(".chips span").count() >= 3)
    page.screenshot(path=f"{SP}/shot_detail_light.png", full_page=False)
    det.locator("button", has_text="I applied").click()
    page.wait_for_timeout(200)
    st = page.evaluate("window.__store.jobs['job_9']")
    check("db updated: Applied + dates", st["status"] == "Applied" and st["appliedOn"] and st["followUp"] > st["appliedOn"], f"{st['appliedOn']} -> {st['followUp']}")
    check("card left To apply", "Darwinbox" not in page.locator("#main").inner_text())
    page.locator("nav button", has_text="Applied").click()
    check("shows in Applied with follow-up", "Darwinbox" in page.locator("#main").inner_text() and "Follow up" in page.locator("#main").inner_text())
    page.screenshot(path=f"{SP}/shot_applied.png")
    # undo
    if page.locator("button", has_text="Undo applied").count() == 0:
        page.locator("#main .head").first.click()
    page.locator("button", has_text="Undo applied").click(); page.wait_for_timeout(200)
    check("undo restores", page.evaluate("window.__store.jobs['job_9'].status") != "Applied")
    # skip another
    page.locator("nav button", has_text="To apply").click()
    page.locator(".head").nth(1).click(); page.locator("button", has_text="Skip").first.click(); page.wait_for_timeout(200)
    check("skip closes job", any(j["status"] == "Closed" for j in page.evaluate("Object.values(window.__store.jobs)")))
    # low matches toggle
    page.locator("button.more").click()
    check("low matches revealed", page.locator(".card").count() > n_open - 1)
    # check tab
    page.locator("nav button", has_text="Add job").click()
    page.fill("#ck-company", "Acme Networks"); page.fill("#ck-title", "Senior Network Engineer"); page.fill("#ck-link", "https://www.linkedin.com/jobs/view/123")
    page.fill("#ck-text", "We need a senior network engineer with Cisco ISE, Fortinet and SASE experience. " * 3)
    page.locator("button[type=submit]").click()
    page.wait_for_selector("text=test letter")
    prompt = page.evaluate("window.__lastPrompt")
    check("prompt carries CV + visa/NSE rules", "CANCELLED" in prompt and "EXPIRED" in prompt and "RIZWAN SIDDIQI" in prompt)
    check("no [object] in check result", "[object" not in page.locator("body").inner_text())
    check("estimate result rendered", "81" in page.locator("#main").inner_text() and "not on your cv" in page.locator("#main").inner_text().lower())
    page.screenshot(path=f"{SP}/shot_check.png", full_page=True)
    page.locator("button", has_text="Save to my list").click(); page.wait_for_timeout(300)
    saved = [j for j in page.evaluate("Object.values(window.__store.jobs)") if j["company"] == "Acme Networks"]
    check("pasted job saved as LinkedIn", saved and saved[0]["source"] == "LinkedIn (pasted)" and saved[0]["url"].startswith("https://www.linkedin.com"))
    check("saved job visible in To apply", "Acme Networks" in page.locator("#main").inner_text())
    # me tab + dark
    page.locator("nav button", has_text="Me").click()
    check("my details has phone", "+971" in page.locator("#main").inner_text())
    check("expired cert noted, not claimed", "Fortinet NSE7" in page.locator("#main").inner_text())
    check("no horizontal scroll (me)", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    page.emulate_media(color_scheme="dark")
    page.locator("nav button", has_text="To apply").click()
    page.locator(".head").first.click()
    page.screenshot(path=f"{SP}/shot_dark.png")
    check("no errors at end", not errs, str(errs)[:200])
    b.close()
bad = [r for r in results if not r[1]]
print("\n%d checks, %d failed" % (len(results), len(bad)))
sys.exit(1 if bad else 0)
