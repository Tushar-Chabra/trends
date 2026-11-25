#!/usr/bin/env python3
"""Daily snapshot archive. Usage (run from repo root with python3 -I):
  snapshot.py today      copy index.html to archive/<DATA_ISO>.html, refresh archive/data.json and archive/index.html
  snapshot.py history    rebuild old days from git history of index.html (one page per date, newest commit wins)
Only writes inside archive/. Reads only index.html and git history of index.html. Never runs code from pages."""
import datetime, json, os, re, subprocess, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC = os.path.join(ROOT, "archive")
OPEN = '<script type="application/json" id="radar-data">'
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# Archive list page style: same colours and fonts as the main page (sketch look), light + dark.
ARC_CSS = """:root{--bg:#fbfaf7;--dot:#d9d6ce;--paper:#fff;--ink:#1e1e1e;--muted:#5f5b55;--line:#1e1e1e;--accent:#6965db;--hl:#fff3a3;--hand:"Patrick Hand","Comic Sans MS","Segoe Print",cursive;--body:"Patrick Hand","Comic Sans MS","Segoe Print",cursive}
@media(prefers-color-scheme:dark){:root{--bg:#121212;--dot:#2c2c2c;--paper:#1c1c1e;--ink:#e3e3e3;--muted:#a3a09a;--line:#cfcfcf;--accent:#a8a5ff;--hl:#4a4318;color-scheme:dark}}
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;background:var(--bg) radial-gradient(var(--dot) 1px,transparent 1px) 0 0/22px 22px;color:var(--ink);font:16px/1.5 var(--body)}
a{color:inherit}
.bar{position:sticky;top:0;z-index:5;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px max(16px,calc((100% - 760px)/2 + 16px));background:var(--bg);border-bottom:2px solid var(--line)}
.brand{display:inline-flex;align-items:center;gap:8px;min-height:44px;text-decoration:none;font:700 1.2rem var(--hand)}
.bm{width:32px;height:32px;display:grid;place-items:center;border-radius:9px 5px 10px 6px;background:var(--accent);color:var(--paper);font:900 .82rem var(--body)}
.today{display:inline-flex;align-items:center;min-height:44px;padding:0 14px;font-weight:800;text-decoration:none;background:var(--hl);border:2px solid var(--line);border-radius:12px 6px 14px 8px;white-space:nowrap}
main{max-width:760px;margin:0 auto;padding:24px 16px 56px}
h1{font:700 clamp(2rem,6vw,2.8rem)/1.1 var(--hand);margin:0}
.u{background:linear-gradient(transparent 60%,var(--hl) 60%)}
.sub{color:var(--muted);margin:.5rem 0 0;max-width:60ch}
h2{font:700 1.4rem var(--hand);margin:1.8rem 0 .7rem}
ul{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.day{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center;padding:12px 14px;text-decoration:none;background:var(--paper);border:2px solid var(--line);border-radius:14px 6px 16px 8px;transition:transform .15s,box-shadow .15s}
.day:hover{transform:translate(-2px,-2px);box-shadow:4px 4px 0 var(--line)}
.day:focus-visible,.today:focus-visible,.brand:focus-visible,.foot a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.dn{display:grid;justify-items:center;width:3rem}
.dn b{font:700 1.8rem/1 var(--hand);color:var(--accent)}
.dn small{font-size:.75rem;font-weight:800;color:var(--muted)}
.dt{display:grid;gap:2px;min-width:0}
.d1{font-weight:800}
.d2{color:var(--muted);font-size:.92rem;overflow-wrap:anywhere}
.d2 b{color:var(--ink);font-weight:700}
.d2 em{font-style:normal;white-space:nowrap}
.new{margin-left:8px;font-size:.72rem;font-weight:800;padding:.05rem .5rem;border-radius:999px;background:var(--hl);border:1.5px solid var(--line);vertical-align:middle}
.go{font-weight:800;font-size:1.2rem;color:var(--muted)}
.foot{margin-top:2.2rem;color:var(--muted);font-size:.9rem}
@media(max-width:420px){.bt{display:none}}
@media(prefers-reduced-motion:reduce){.day{transition:none}}"""


def data_of(t):
    s = t.find(OPEN)
    if s < 0 or t.count(OPEN) != 1:
        return None
    s += len(OPEN)
    e = t.find("</script>", s)
    try:
        return json.loads(t[s:e])
    except Exception:
        return None


def snap_html(t):
    # archive pages live one folder deeper: keep the icon link working
    return t.replace('href="apple-touch-icon.png"', 'href="../apple-touch-icon.png"')


def save_day(t):
    d = data_of(t)
    if not d or not ISO.match(str(d.get("DATA_ISO", ""))):
        return None
    day = d["DATA_ISO"]
    os.makedirs(ARC, exist_ok=True)
    with open(os.path.join(ARC, day + ".html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(snap_html(t))
    return day, d.get("L", {})


def load_data():
    p = os.path.join(ARC, "data.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"days": {}}


def write_all(data):
    days = data["days"]
    with open(os.path.join(ARC, "data.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"note": "Each day: lists as shown on the page (daily/weekly/monthly/yearly rows = [repo, period stars]).",
                   "days": {k: days[k] for k in sorted(days)}}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    groups = []  # [(month label, [list items])], newest first
    for day in sorted(days, reverse=True):
        if not os.path.exists(os.path.join(ARC, day + ".html")):
            continue
        dl = days[day].get("daily", {}).get("rows") or []
        top = html.escape(str(dl[0][0])) if dl else "-"
        stars = html.escape(str(dl[0][1])) if dl and len(dl[0]) > 1 and dl[0][1] else ""
        dt = datetime.date.fromisoformat(day)
        month = f"{MONTHS[dt.month - 1]} {dt.year}"
        if not groups or groups[-1][0] != month:
            groups.append((month, []))
        tag = '<span class="new">Latest</span>' if not any(g[1] for g in groups) else ""
        star_txt = f' <em>&#9733; +{stars}</em>' if stars else ""
        groups[-1][1].append(
            f'<li><a class="day" href="{day}.html"><span class="dn"><b>{dt.day}</b><small>{DOW[dt.weekday()]}</small></span>'
            f'<span class="dt"><span class="d1">{dt.day} {MONTHS[dt.month - 1][:3]} {dt.year}{tag}</span>'
            f'<span class="d2">Top daily: <b>{top}</b>{star_txt}</span></span>'
            '<span class="go" aria-hidden="true">&#8594;</span></a></li>')
    body = "".join(f'<section><h2>{html.escape(m)}</h2><ul>{"".join(items)}</ul></section>' for m, items in groups)
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src \'self\'">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">'
            '<title>GitHub Trends Archive</title>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap">'
            '<style>' + ARC_CSS + '</style></head><body>'
            '<nav class="bar" aria-label="GitHub Trends"><a class="brand" href="../"><span class="bm" aria-hidden="true">GT</span>'
            '<span class="bt">GitHub Trends</span></a><a class="today" href="../">Today\'s trends &#8594;</a></nav>'
            '<main><h1>Past <span class="u">trends</span></h1>'
            '<p class="sub">Every day&#39;s page is saved here. Tap a day to see what was trending on GitHub then.</p>'
            + body +
            '<p class="foot"><a href="data.json">Download all data (JSON)</a></p></main></body></html>\n')
    with open(os.path.join(ARC, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True, timeout=120)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = load_data()
    if mode == "history":
        seen = set()
        for sha in git("log", "--format=%H", "--", "index.html").stdout.split():
            r = git("show", sha + ":index.html")
            if r.returncode:
                continue
            d = data_of(r.stdout)
            day = str((d or {}).get("DATA_ISO", ""))
            if not ISO.match(day) or day in seen:
                continue
            seen.add(day)  # log is newest first, so the newest commit of a day wins
            res = save_day(r.stdout)
            if res:
                data["days"][res[0]] = res[1]
        print("history days saved:", len(seen))
    elif mode == "today":
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            res = save_day(f.read())
        if not res:
            print("SNAPSHOT FAILED: index.html has no valid data block"); sys.exit(1)
        data["days"][res[0]] = res[1]
        print("snapshot saved:", res[0])
    else:
        print("usage: snapshot.py today|history"); sys.exit(2)
    write_all(data)


main()
