#!/usr/bin/env python3
"""Daily snapshot archive. Usage (run from repo root with python3 -I):
  snapshot.py today      copy index.html to archive/<DATA_ISO>.html, refresh archive/data.json and archive/index.html
  snapshot.py history    rebuild old days from git history of index.html (one page per date, newest commit wins)
Only writes inside archive/. Reads only index.html and git history of index.html. Never runs code from pages."""
import json, os, re, subprocess, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC = os.path.join(ROOT, "archive")
OPEN = '<script type="application/json" id="radar-data">'
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    rows = []
    for day in sorted(days, reverse=True):
        if not os.path.exists(os.path.join(ARC, day + ".html")):
            continue
        dl = days[day].get("daily", {}).get("rows") or []
        top = html.escape(str(dl[0][0])) if dl else "-"
        stars = html.escape(str(dl[0][1])) if dl and len(dl[0]) > 1 else ""
        rows.append(f'<li><a href="{day}.html">{day}</a><span>Top daily: {top} <em>+{stars}</em></span></li>')
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'self\'">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>GitHub Trends Archive</title>'
            '<style>:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--ln:#ddd;--ac:#0b5cd5}'
            '@media(prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#999;--ln:#333;--ac:#7ab7ff}}'
            'body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:720px;padding:24px 16px}'
            'a{color:var(--ac)}ul{list-style:none;padding:0}li{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--ln);padding:10px 0}'
            'span{color:var(--mut)}em{font-style:normal}</style></head><body>'
            '<h1>GitHub Trends Archive</h1><p>One saved page for every day. <a href="../">Open today\'s page</a> · '
            '<a href="data.json">Download all data (JSON)</a></p><ul>' + "".join(rows) + '</ul></body></html>\n')
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
