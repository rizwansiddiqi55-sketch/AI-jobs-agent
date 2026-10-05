"""Dashboard renderers: terminal table, Markdown, self-contained HTML."""
import html
from datetime import date

COLS = [("Company", "company"), ("Position", "title"), ("Location", "location"), ("Salary", "salary"),
        ("Experience Required", "experience_required"), ("Match", "match_pct"), ("Source", "source"),
        ("Posted Date", "posted_date"), ("Application Status", "status"),
        ("Application Date", "application_date"), ("Follow-up Date", "followup_date"), ("Job URL", "url")]


def _cell(row, key):
    v = row[key]
    if key == "match_pct":
        return f"{v:.0f}%" if v is not None else "-"
    return str(v) if v not in (None, "") else "-"


def rows_to_matrix(rows):
    return [["ID"] + [h for h, _ in COLS]] + [[str(r["id"])] + [_cell(r, k) for _, k in COLS] for r in rows]


def to_text(rows, short=True) -> str:
    cols = ["ID", "Company", "Position", "Location", "Match", "Application Status", "Follow-up Date"] if short else None
    m = rows_to_matrix(rows)
    idx = [m[0].index(c) for c in cols] if cols else range(len(m[0]))
    data = [[row[i][:38] for i in idx] for row in m]
    w = [max(len(r[j]) for r in data) for j in range(len(data[0]))]
    fmt = lambda r: " | ".join(c.ljust(w[j]) for j, c in enumerate(r))
    return "\n".join([fmt(data[0]), "-+-".join("-" * x for x in w), *map(fmt, data[1:])]) if len(data) > 1 else "No jobs."


def to_markdown(rows) -> str:
    m = rows_to_matrix(rows)
    esc = lambda s: s.replace("|", "\\|")
    return "\n".join(["| " + " | ".join(m[0]) + " |", "|" + "---|" * len(m[0]),
                      *("| " + " | ".join(esc(c) for c in r) + " |" for r in m[1:])]) + "\n"


def to_html(rows, kit_url: str = "", nav_html: str = "") -> str:
    """Self-contained dashboard page. With kit_url, every row links to that job's card in the Apply Kit
    (the page there opens '#job-<id>'). The page holds no CV, phone or email."""
    m = rows_to_matrix(rows)
    head = "".join(f"<th>{html.escape(h)}</th>" for h in m[0]) + ("<th>Apply Kit</th>" if kit_url else "")
    body = ""
    for r, row in zip(m[1:], rows):
        cells = "".join(
            f"<td><a href='{html.escape(c)}'>link</a></td>" if h == "Job URL" and c.startswith("http")
            else f"<td>{html.escape(c)}</td>" for h, c in zip(m[0], r))
        if kit_url:
            cells += f"<td><a class='kit' href='{html.escape(kit_url)}#job-{row['id']}'>Open kit</a></td>"
        body += f"<tr>{cells}</tr>"
    top = (f"<p><a class='btn' href='{html.escape(kit_url)}'>Open Apply Kit</a> "
           "<span class='hint'>Cover letters, CV text and copy-paste answers for each job, on your phone.</span></p>"
           if kit_url else "")
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content='noindex,nofollow'><title>Job Dashboard</title>"
            "<style>:root{--bg:#F2F6F7;--fg:#14232B;--line:#D3DDE1;--head:#E5EDEF;--accent:#0B6E6E;--ink:#fff;--muted:#566870}"
            "@media (prefers-color-scheme:dark){:root{--bg:#0E1A1F;--fg:#E6EEF1;--line:#27393F;--head:#1D3037;--accent:#4FC3BD;--ink:#06201F;--muted:#93A6AE;color-scheme:dark}}"
            "body{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;margin:0;padding:16px}"
            "h2{margin:0 0 12px}table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:6px 10px;text-align:left}"
            "th{background:var(--head)}a{color:var(--accent)}.wrap{overflow-x:auto}"
            "nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}nav a{border:1px solid var(--line);border-radius:999px;padding:6px 12px;text-decoration:none;font-size:13px}nav a.on{background:var(--accent);color:var(--ink);border-color:var(--accent);font-weight:600}"
            ".btn,.kit{display:inline-block;background:var(--accent);color:var(--ink);padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:600}"
            ".kit{padding:6px 10px;white-space:nowrap;font-size:13px}.hint{color:var(--muted);font-size:13px;margin-left:8px}</style>"
            f"{nav_html}<h2>Job Dashboard - {date.today()}</h2>{top}<div class='wrap'><table><tr>{head}</tr>{body}</table></div>")
