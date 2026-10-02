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


def to_html(rows) -> str:
    m = rows_to_matrix(rows)
    head = "".join(f"<th>{html.escape(h)}</th>" for h in m[0])
    body = ""
    for r, row in zip(m[1:], rows):
        cells = "".join(
            f"<td><a href='{html.escape(c)}'>link</a></td>" if h == "Job URL" and c.startswith("http")
            else f"<td>{html.escape(c)}</td>" for h, c in zip(m[0], r))
        body += f"<tr>{cells}</tr>"
    return (f"<!doctype html><meta charset=utf-8><title>Job Dashboard</title>"
            "<style>body{font:14px system-ui;margin:20px}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:4px 8px}th{background:#f2f2f2}</style>"
            f"<h2>Job Dashboard - {date.today()}</h2><table><tr>{head}</tr>{body}</table>")
