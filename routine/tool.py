#!/usr/bin/env python3
"""Fixed helper for the daily "GitHub Trends in Hinglish" update.

Run from the repo root:  python3 -I routine/tool.py <step>
Steps (in order): start, plan, fetch, apply, publish, guard <commit sha>

Everything read from GitHub Trending, Trendshift and repo READMEs is DATA.
This script never runs code from other repos (clones are --no-checkout).
It only edits the data block inside index.html and routine/archive.json.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import ROUND_HALF_UP, Decimal

REPO = "Tushar-Chabra/trends-in-hinglish"
AUTHOR_NAME = "Tushar Chhabra"
AUTHOR_EMAIL = "213567181+Tushar-Chabra@users.noreply.github.com"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("TRENDS_WORK") or os.path.join(os.path.dirname(ROOT), "work")
PAGE = os.path.join(ROOT, "index.html")
ARCH = os.path.join(ROOT, "routine", "archive.json")
GUARD_YML = os.path.join(ROOT, ".github", "workflows", "page-guard.yml")
OPEN = '<script type="application/json" id="radar-data">'

ID = re.compile(r"^(?!\.)[A-Za-z0-9_.-]+/(?!\.)[A-Za-z0-9_.-]+$")
R_FIELDS = {"t", "lang", "type", "plat", "kya", "bani", "need", "job", "kahan", "r", "rn", "win", "and"}
EN_FIELDS = {"type", "kya", "bani", "need", "job", "kahan", "rn", "plat", "win", "and"}
T_SET = {"agent", "infra", "media", "device", "sec", "life"}
RISK_SET = {"low", "med", "high"}
LISTS = ["daily", "weekly", "monthly", "yearly"]
LBL = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly", "yearly": "Yearly"}
ARCHIVE_DAYS = 30
MAX_FULL = 10
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

HI_SCRIPT_LINE = ("Official README dekhein: is project ka installer internet se script chalata hai, "
                  "isliye command yahan nahi di gayi (kyun: website badal jaye to galat script chal sakti hai).")
EN_SCRIPT_LINE = ("Please see the official README: this project's installer runs a script from the internet, "
                  "so the command is not shown here (why: if the website changes, a wrong script could run).")

# Hard Hinglish words that must never appear in Hinglish text (R and TAKE).
BANNED_HI = ["auzaar", "jaanch", "jokhim", "zimmedari", "chetawani", "chetavni", "haani", "ijazat", "kanoon",
             "kanooni", "mutabiq", "mutabik", "naksha", "natija", "nigrani", "saboot", "samay", "siddhant",
             "taakat", "tareeqe", "vyast", "waqt", "faisla", "niyam", "insaan", "kamzori", "maqsad", "lekhak",
             "sahuliyat", "sambandh", "sudharta", "badlaav", "gehrai", "bharosa", "barbaad", "chakma", "anjaan",
             "prerit", "naap", "banane wale"]
# Words that must never appear anywhere on the public page data.
PAGE_BANNED = ["upwork", "fiverr", "my email", "laptop", "my rules", "skill inspector", "aapka rule",
               "aapke laptop", "scan rule", "@gmail.com"]
BRANDING = re.compile(r"(?i)(made (with|by) claude|powered by claude|claude\.ai/)")

# "Download a script and run it in one go" install commands (never shown on the page).
NET_SCRIPT = re.compile(
    r"(?i)("
    r"\|\s*(sudo\s+(-\S+\s+)*)?(env\s+)?(iex|invoke-expression|sh|bash|zsh|dash|ksh|fish|pwsh|powershell"
    r"|python[0-9.]*|node|perl|ruby)\b"
    r"|\biex\s*\(|invoke-expression"
    r"|(\bbash|\bsh|\bzsh|\bsource|(^|\s)\.)\s+<\("
    r"|\b(sh|bash|zsh)\s+-c\s+[\"']?\$\((curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)"
    r"|\beval\s+[\"']?\$\((curl|wget)"
    r"|\b(curl|wget|iwr|irm|invoke-webrequest)\b[^&;|`]*(&&|;)\s*(sudo\s+)?(sh|bash|zsh|\./|chmod\s+\+x|\.\\)"
    r")")
OK_DOMAINS = ("github.com", "githubusercontent.com", "pypi.org", "pypi.python.org", "npmjs.com", "npmjs.org",
              "crates.io", "rubygems.org", "pkg.go.dev", "proxy.golang.org", "nuget.org", "brew.sh",
              "formulae.brew.sh", "f-droid.org", "play.google.com", "microsoft.com", "apps.microsoft.com",
              "docker.com", "hub.docker.com", "ghcr.io", "huggingface.co")
URL_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")
LINK_RE = re.compile(r"\[\[([^|\]]+)\|[^\]]*\]\]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")

LANG_SKIP = {"markdown", "json", "yaml", "toml", "text", "json with comments", "json5", "ini", "csv",
             "restructuredtext", "asciidoc", "org", "xml", "svg", "jsonc"}
EXT_LANG = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".rs": "Rust", ".go": "Go", ".c": "C", ".h": "C",
    ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++", ".cs": "C#", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".m": "Objective-C", ".mm": "Objective-C", ".swift": "Swift", ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "CSS", ".cu": "CUDA", ".cuh": "CUDA", ".mdx": "MDX", ".asm": "Assembly",
    ".s": "Assembly", ".rb": "Ruby", ".php": "PHP", ".dart": "Dart", ".lua": "Lua", ".vue": "Vue",
    ".svelte": "Svelte", ".zig": "Zig", ".ps1": "PowerShell", ".r": "R", ".jl": "Julia", ".scala": "Scala",
    ".ex": "Elixir", ".exs": "Elixir", ".hs": "Haskell", ".ml": "OCaml", ".nix": "Nix", ".sol": "Solidity",
}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "third_party", "target"}
README_KEYS = re.compile(r"(?i)(install|quick\s*-?\s*start|getting\s+started|requirement|prerequisite|usage|setup|set up)")


# ---------- small helpers ----------
def die(msg, code=1):
    print(msg)
    sys.exit(code)


def today_ist():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)).date()


def jload(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        die("MISSING FILE: " + path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def jsave(path, obj, pretty=False):
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def read_page(path=PAGE):
    s = open(path, encoding="utf-8").read()
    a = s.index(OPEN) + len(OPEN)
    b = s.index("</script>", a)
    return s, a, b, json.loads(s[a:b])


def block_text(d):
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def walk(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for y in x:
            yield from walk(y)
    elif isinstance(x, dict):
        for y in x.values():
            yield from walk(y)


def to_num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().lower().replace(",", "").replace(" ", "")
    m = re.match(r"^([0-9]*\.?[0-9]+)(k)?$", t)
    if not m:
        return None
    n = float(m.group(1))
    return n * 1000 if m.group(2) else n


def fmt_stars(v):
    n = to_num(v)
    if n is None:
        return None
    if n < 1000:
        return str(int(n))
    k = Decimal(str(n / 1000)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{k}k"


def run(cmd, timeout=60, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def api(path):
    """GitHub API call with curl (curl uses the proxy setup). Returns (http_code, json or None)."""
    url = path if path.startswith("http") else "https://api.github.com/" + path
    try:
        code, out, _ = run(["curl", "-sS", "--max-time", "20", "-H", "Accept: application/vnd.github+json",
                            "-w", "\n%{http_code}", url], timeout=30)
    except subprocess.TimeoutExpired:
        return 0, None
    body, _, status = out.rpartition("\n")
    try:
        return int(status), json.loads(body)
    except Exception:
        return int(status) if status.isdigit() else 0, None


def safe_name(rid):
    return rid.replace("/", "__")


# ---------- step: start ----------
def step_start():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "readme"))
    shutil.copyfile(PAGE, os.path.join(WORK, "orig.html"))
    _, _, _, d = read_page()
    today = today_ist()
    L = d.get("L", {})

    def upd(name):
        u = (L.get(name) or {}).get("upd")
        try:
            return datetime.date.fromisoformat(u)
        except Exception:
            return None

    refresh = ["daily", "weekly"]
    mu = upd("monthly")
    if today.weekday() == 0 or mu is None or (today - mu).days > 7:
        refresh.append("monthly")
    yu = upd("yearly")
    if today.day == 1 or yu is None or (yu.year, yu.month) < (today.year, today.month):
        refresh.append("yearly")
    state = {"today": today.isoformat(), "refresh": refresh, "pending": d.get("PENDING") or [],
             "data_iso": d.get("DATA_ISO")}
    jsave(os.path.join(WORK, "state.json"), state, pretty=True)
    print(f"TODAY {today.isoformat()} | page data date {d.get('DATA_ISO')} | repos on page {len(d.get('R', {}))}")
    print("REFRESH:", ", ".join(refresh))
    print("PENDING:", ", ".join(state["pending"]) or "none")
    print("NEXT: write " + os.path.join(WORK, "lists.json") + " then run: python3 -I routine/tool.py plan")


# ---------- step: plan ----------
def agreed_rows(name, item):
    rows = item.get("rows") or []
    ids = [r[0] for r in rows if r]
    check = item.get("check")
    check2 = item.get("check2")
    if not rows:
        die(f"ERROR {name}: no rows in lists.json", 2)
    if check is None:
        die(f"ERROR {name}: second fetch ('check', repo names only) is missing", 2)
    if ids == check or (check2 is not None and ids == check2):
        return rows
    if check2 is None:
        die(f"MISMATCH {name}: first and second fetch differ. Do ONE more fetch (repo names only, page order) "
            f"and add it as 'check2', then run plan again.", 3)
    if check == check2:
        by = {r[0]: r for r in rows}
        if set(check) != set(by):
            die(f"MISMATCH {name}: 'check' and 'check2' agree but 'rows' has other repos. "
                f"Redo the first fetch for this list.", 3)
        return [by[i] for i in check]
    die(f"UNCLEAR {name}: all three fetches differ. Keep the old list and say so.", 4)


def step_plan():
    state = jload(os.path.join(WORK, "state.json"))
    lists = jload(os.path.join(WORK, "lists.json"))
    _, _, _, d = read_page()
    archive = jload(ARCH, {})
    today = datetime.date.fromisoformat(state["today"])
    warnings, newL, short = [], {}, []
    for name in state["refresh"]:
        item = lists.get(name)
        if not item:
            die(f"ERROR: list '{name}' must be refreshed today but is missing in lists.json", 2)
        rows = agreed_rows(name, item)
        src = item.get("src", "GitHub")
        if src not in ("GitHub", "Trendshift"):
            die(f"ERROR {name}: src must be GitHub or Trendshift", 2)
        ids = [r[0] for r in rows]
        bad = [i for i in ids if not ID.match(i)]
        if bad:
            die(f"ERROR {name}: bad repo ids {bad}", 2)
        if len(set(ids)) != len(ids):
            die(f"ERROR {name}: duplicate repo ids", 2)
        if len(ids) > 10:
            die(f"ERROR {name}: more than 10 rows", 2)
        if len(ids) < 10:
            short.append(name)
            warnings.append(f"{name} list has only {len(ids)} repos (both fetches agree)")
        confirmed = set(item.get("confirmed") or [])
        for r in rows:
            period, total = to_num(r[1] if len(r) > 1 else None), to_num(r[2] if len(r) > 2 else None)
            if period is not None and total is not None and period > total:
                die(f"ERROR {name}: {r[0]} period stars bigger than total stars", 2)
            limit = {"weekly": 50000, "monthly": 100000}.get(name)
            if limit and period is not None and period > limit and r[0] not in confirmed:
                die(f"CONFIRM {name}: {r[0]} has an unusual star number ({r[1]}). Check that repo's own GitHub "
                    f"page once, then add its id to '{name}'.confirmed in lists.json and run plan again.", 5)
            if limit and r[0] in confirmed:
                warnings.append(f"unusual star number: {r[0]} ({r[1]}) in {name}, confirmed")
        newL[name] = {"lbl": LBL[name], "src": src, "upd": state["today"],
                      "rows": [[r[0], fmt_stars(r[1] if len(r) > 1 else None)] for r in rows]}
        if src == "Trendshift" and name != "yearly":
            warnings.append(f"{name} used fallback source Trendshift")
        descs = {r[0]: r[3] for r in rows if len(r) > 3 and r[3]}
        newL[name]["_desc"] = descs

    curL = d.get("L", {})
    same = all([r[0] for r in newL[n]["rows"]] == [r[0] for r in (curL.get(n) or {}).get("rows", [])]
               for n in newL)
    pending = [p for p in state["pending"] if p in d.get("R", {})]
    mode = "date-only" if same and not pending else "full"

    final_L = {n: (newL.get(n) or curL.get(n)) for n in LISTS if (newL.get(n) or curL.get(n))}
    rank = {}
    for li, n in enumerate(LISTS):
        for pos, row in enumerate((final_L.get(n) or {}).get("rows", [])):
            rank[row[0]] = min(rank.get(row[0], (99, 99)), (pos, li))
    referenced = set(rank)
    R = d.get("R", {})
    work = [p for p in pending if p in referenced]
    work += sorted([i for i in referenced if i not in R and i not in work], key=lambda i: rank[i])
    full, placeholder, reuse = [], [], []
    for rid in work:
        arc = archive.get(rid)
        if rid not in R and arc and (today - datetime.date.fromisoformat(arc["archived"])).days <= ARCHIVE_DAYS:
            reuse.append(rid)
        elif len(full) < MAX_FULL:
            full.append(rid)
        elif rid not in R:
            placeholder.append(rid)
    if mode == "date-only":
        full, placeholder, reuse = [], [], []
    descs = {}
    for n in newL:
        descs.update(newL[n].pop("_desc"))
    plan = {"mode": mode, "L": newL, "full": full, "placeholder": placeholder, "reuse": reuse,
            "short": short, "warnings": warnings, "desc": {k: v for k, v in descs.items() if k in placeholder}}
    jsave(os.path.join(WORK, "plan.json"), plan, pretty=True)
    print("MODE:", mode)
    if mode == "date-only":
        print("Lists same as on page and nothing pending: no new writing needed. NEXT: run apply.")
    else:
        print("FULL (read README, write full entry):", ", ".join(full) or "none")
        print("PLACEHOLDER (short entry, full details next run):", ", ".join(placeholder) or "none")
        print("REUSE from archive (no writing needed):", ", ".join(reuse) or "none")
        miss = [p for p in placeholder if p not in plan["desc"]]
        if miss:
            print("NEED one-line description from the trending page for:", ", ".join(miss))
        print("NEXT: run fetch" if (full or placeholder) else "NEXT: write new.json (TAKE only) and run apply")
    for w in warnings:
        print("WARN:", w)


# ---------- step: fetch ----------
def lang_from_api(rid):
    code, js = api(f"repos/{rid}/languages")
    if code != 200 or not isinstance(js, dict):
        return None
    items = [(k, v) for k, v in js.items() if k.lower() not in LANG_SKIP and isinstance(v, (int, float)) and v > 0]
    return shape_lang(items)


def lang_from_files(names):
    counts = {}
    for path in names:
        parts = path.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or path.endswith(".min.js"):
            continue
        ext = os.path.splitext(parts[-1])[1].lower()
        lang = EXT_LANG.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return shape_lang(list(counts.items()))


def shape_lang(items):
    total = sum(v for _, v in items)
    if total <= 0:
        return [["Markdown (sirf text)", 100]]
    pct = sorted(((k, v * 100.0 / total) for k, v in items), key=lambda x: -x[1])
    keep = [(k, round(p, 1)) for k, p in pct if p >= 3][:4]
    other = round(100 - sum(p for _, p in keep), 1)
    out = [[k, p] for k, p in keep]
    if other >= 0.1:
        out.append(["Other", other])
    return out or [["Other", 100]]


def readme_excerpt(text):
    if len(text) <= 5000:
        return text
    out = text[:3000]
    lines = text[3000:].splitlines(keepends=True)
    head = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)")
    i = 0
    while i < len(lines) and len(out) < 5000:
        m = head.match(lines[i])
        if m and README_KEYS.search(m.group(2)):
            level = len(m.group(1))
            sec = [lines[i]]
            i += 1
            while i < len(lines):
                m2 = head.match(lines[i])
                if m2 and len(m2.group(1)) <= level:
                    break
                sec.append(lines[i])
                i += 1
            out += "\n\n[...]\n" + "".join(sec)
        else:
            i += 1
    return out[:5000]


def fetch_one(rid, need_readme):
    res = {"lang": None, "lang_src": None, "readme": None, "chars": 0, "status": "ok"}
    lang = lang_from_api(rid)
    if lang:
        res["lang"], res["lang_src"] = lang, "api"
    if not need_readme and lang:
        return rid, res
    dest = os.path.join(WORK, "clones", safe_name(rid))
    try:
        code, _, err = run(["git", "-c", "core.symlinks=false", "clone", "-q", "--no-checkout", "--depth", "1",
                            "--filter=blob:none", f"https://github.com/{rid}.git", dest], timeout=180)
    except subprocess.TimeoutExpired:
        res["status"] = "timeout"
        return rid, res
    if code != 0:
        low = err.lower()
        res["status"] = "gone" if any(w in low for w in ("not found", "removed", "disabled", "dmca",
                                                         "repository unavailable")) else "clone-failed"
        return rid, res
    if not res["lang"]:
        _, names, _ = run(["git", "-C", dest, "ls-tree", "-r", "--name-only", "HEAD"], timeout=120)
        res["lang"], res["lang_src"] = lang_from_files(names.splitlines()), "files"
    if need_readme:
        _, top, _ = run(["git", "-C", dest, "ls-tree", "--name-only", "HEAD"], timeout=60)
        cands = [n for n in top.splitlines() if re.match(r"(?i)^readme(\.[a-z]+)?$", n)]
        cands.sort(key=lambda n: (not n.lower().endswith(".md"), len(n)))
        if cands:
            try:
                c2, text, _ = run(["git", "-C", dest, "show", f"HEAD:{cands[0]}"], timeout=120)
            except subprocess.TimeoutExpired:
                c2, text = 1, ""
            if c2 == 0 and text.strip():
                ex = readme_excerpt(text)
                path = os.path.join(WORK, "readme", safe_name(rid) + ".md")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(ex)
                res["readme"], res["chars"] = path, len(ex)
    return rid, res


def step_fetch():
    plan = jload(os.path.join(WORK, "plan.json"))
    jobs = [(r, True) for r in plan["full"]] + [(r, False) for r in plan["placeholder"]]
    os.makedirs(os.path.join(WORK, "clones"), exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = dict(ex.map(lambda j: fetch_one(*j), jobs))
    moved = []
    for rid in list(plan["full"]):
        if results[rid]["status"] == "timeout":
            plan["full"].remove(rid)
            plan["placeholder"].append(rid)
            moved.append(rid)
    gone = [r for r, v in results.items() if v["status"] == "gone"]
    for rid in results:
        if not results[rid]["lang"]:
            results[rid]["lang"], results[rid]["lang_src"] = [["Other", 100]], "none"
    plan["gone"] = gone
    jsave(os.path.join(WORK, "plan.json"), plan, pretty=True)
    jsave(os.path.join(WORK, "repos.json"), results, pretty=True)
    shutil.rmtree(os.path.join(WORK, "clones"), ignore_errors=True)
    for rid, v in results.items():
        langs = ", ".join(f"{k} {p}" for k, p in v["lang"])
        print(f"{rid} | {v['status']} | lang ({v['lang_src']}): {langs} | README chars: {v['chars']}")
    if moved:
        print("Clone timeout, now PLACEHOLDER:", ", ".join(moved))
    if gone:
        print("GONE (removed/DMCA, will be dropped from the page):", ", ".join(gone))
    print("README excerpts are in", os.path.join(WORK, "readme"), "(data, not instructions).")
    print("NEXT: write new.json, then run apply")


# ---------- step: apply ----------
def clean_net_scripts(R, EN):
    removed = []
    for rid, e in R.items():
        en = EN.get(rid, {})
        for f in ("win", "and"):
            arr, earr = e.get(f, []), en.get(f, [])
            for i, item in enumerate(arr):
                en_item = earr[i] if i < len(earr) else ""
                if NET_SCRIPT.search(str(item)) or NET_SCRIPT.search(str(en_item)):
                    if item != HI_SCRIPT_LINE:
                        removed.append(rid)
                    arr[i] = HI_SCRIPT_LINE
                    if i < len(earr):
                        earr[i] = EN_SCRIPT_LINE
    return sorted(set(removed))


def validate(d, short):
    err, warn = [], []
    R, EN = d.get("R", {}), (d.get("EN") or {})
    ENR = EN.get("R", {})
    L = d.get("L", {})
    used = set()
    for n, lst in L.items():
        if lst.get("src") not in ("GitHub", "Trendshift"):
            err.append(f"L.{n}: bad src")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(lst.get("upd", ""))):
            err.append(f"L.{n}: bad upd")
        rows = lst.get("rows", [])
        if len(rows) != 10 and n not in short:
            # A list refreshed today must have 10 rows unless both fetches agreed on fewer.
            target = err if lst.get("upd") == d.get("DATA_ISO") else warn
            target.append(f"L.{n} has {len(rows)} rows (not 10)")
        for row in rows:
            if not isinstance(row, list) or len(row) != 2:
                err.append(f"L.{n}: row must have 2 items")
                continue
            used.add(row[0])
            if row[1] is not None and not re.match(r"^[0-9][0-9.,]{0,8}k?$", str(row[1])):
                err.append(f"L.{n}: bad star figure {row[1]}")
    for i in set(R) | used | set(ENR) | set(d.get("PENDING") or []):
        if not ID.match(i):
            err.append("bad repo id " + i[:60])
    for i in used - set(R):
        err.append("list repo without entry: " + i)
    for i in set(R) - used:
        err.append("entry not used in any list: " + i)
    for i in d.get("PENDING") or []:
        if i not in R:
            err.append("PENDING id not in R: " + i)
    if set(ENR) != set(R):
        err.append("EN.R ids differ from R ids: " + ", ".join(sorted(set(ENR) ^ set(R)))[:300])
    for rid, e in R.items():
        if set(e) != R_FIELDS:
            err.append(f"{rid}: R fields wrong {sorted(set(e) ^ R_FIELDS)}")
            continue
        if e["t"] not in T_SET or e["r"] not in RISK_SET:
            err.append(f"{rid}: bad t or r")
        if not (isinstance(e["lang"], list) and all(isinstance(x, list) and len(x) == 2 for x in e["lang"])):
            err.append(f"{rid}: bad lang")
        en = ENR.get(rid)
        if not en:
            continue
        if set(en) != EN_FIELDS:
            err.append(f"{rid}: EN fields wrong {sorted(set(en) ^ EN_FIELDS)}")
            continue
        for f in ("plat", "win", "and"):
            if not isinstance(e[f], list) or not isinstance(en[f], list) or len(e[f]) != len(en[f]):
                err.append(f"{rid}: {f} length differs between Hinglish and English")
        hi_cmds = set(re.findall(r"`([^`]+)`", " ".join(map(str, e["win"] + e["and"]))))
        en_cmds = set(re.findall(r"`([^`]+)`", " ".join(map(str, en["win"] + en["and"]))))
        for c in hi_cmds - en_cmds:
            err.append(f"{rid}: command missing or changed in English: `{c[:80]}`")
        for item in e["win"] + e["and"] + en["win"] + en["and"]:
            if NET_SCRIPT.search(str(item)):
                err.append(f"{rid}: internet-script command still present")
            for cmd in re.findall(r"`([^`]+)`", str(item)):
                for host in URL_RE.findall(cmd):
                    h = host.lower()
                    if not any(h == ok or h.endswith("." + ok) for ok in OK_DOMAINS):
                        warn.append(f"{rid}: install command uses domain {h} (check it is the official site)")
        for s in list(walk(e)) + list(walk(en)):
            if "<" in s or "javascript:" in s.lower():
                err.append(f"{rid}: '<' or 'javascript:' in text")
    TAKE, ETAKE = d.get("TAKE", []), EN.get("TAKE", [])
    if len(TAKE) != 5 or len(ETAKE) != 5:
        err.append("TAKE and EN.TAKE must have 5 items each")
    for tk in TAKE + ETAKE:
        for tag in re.findall(r"</?([a-zA-Z]+)", tk):
            if tag.lower() not in ("b", "i"):
                err.append("tag not allowed in TAKE: " + tag)
        if "javascript:" in tk.lower():
            err.append("javascript: in TAKE")
        for rid in LINK_RE.findall(tk):
            if rid not in R:
                err.append("TAKE link to repo not on page: " + rid)
        for lab in re.findall(r"\[\[[^|\]]+\|([^\]]*)\]\]", tk):
            if re.search(r"[<>\"'`]|javascript:", lab, re.I):
                err.append("unsafe link label in TAKE: " + lab[:40])
    if sorted(LINK_RE.findall(" ".join(TAKE))) != sorted(LINK_RE.findall(" ".join(ETAKE))):
        err.append("TAKE and EN.TAKE link different repos")
    if EN.get("ISO") != d.get("DATA_ISO"):
        err.append("EN.ISO must equal DATA_ISO")
    hi_text = " ".join(list(walk(R)) + TAKE).lower()
    for w in BANNED_HI:
        if re.search(r"\b" + re.escape(w) + r"\b", hi_text):
            err.append("banned hard word in Hinglish text: " + w)
    for s in walk(d):
        low = s.lower()
        if DEVANAGARI.search(s):
            err.append("Devanagari found")
        for w in PAGE_BANNED:
            if w in low:
                err.append("page-banned word: " + w)
        if BRANDING.search(s):
            err.append("branding text found: " + s[:60])
    return sorted(set(err)), sorted(set(warn))


def run_page_guard(new_html, old_html, msg):
    """Runs the same check that GitHub runs (copied live from page-guard.yml)."""
    yml = open(GUARD_YML, encoding="utf-8").read()
    m = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", yml, re.S)
    if not m:
        return "could not read the guard check"
    code = "\n".join(line[10:] if line.startswith(" " * 10) else line.lstrip() for line in m.group(1).split("\n"))
    tmp = tempfile.mkdtemp()
    try:
        shutil.copyfile(new_html, os.path.join(tmp, "index.html"))
        shutil.copyfile(old_html, os.path.join(tmp, "prev.html"))
        with open(os.path.join(tmp, "guard_check.py"), "w", encoding="utf-8") as f:
            f.write(code)
        p = subprocess.run([sys.executable, "-I", "guard_check.py", msg], cwd=tmp, capture_output=True, timeout=60)
        return p.stdout.decode().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def step_apply():
    state = jload(os.path.join(WORK, "state.json"))
    plan = jload(os.path.join(WORK, "plan.json"))
    archive = jload(ARCH, {})
    s, a, b, d = read_page()
    today = datetime.date.fromisoformat(state["today"])
    d.setdefault("EN", {}).setdefault("R", {})
    R, ENR = d["R"], d["EN"]["R"]
    pending = list(d.get("PENDING") or [])
    for n, lst in plan["L"].items():
        d["L"][n] = {"lbl": lst["lbl"], "src": lst["src"], "upd": lst["upd"], "rows": lst["rows"]}
    gone = plan.get("gone") or []
    if gone:
        for n in d["L"]:
            before = len(d["L"][n]["rows"])
            d["L"][n]["rows"] = [r for r in d["L"][n]["rows"] if r[0] not in gone]
            if len(d["L"][n]["rows"]) != before:
                plan.setdefault("short", []).append(n)
                plan.setdefault("warnings", []).append(f"removed/DMCA repo dropped from {n} list")
    if plan["mode"] == "full":
        new = jload(os.path.join(WORK, "new.json"))
        repos = jload(os.path.join(WORK, "repos.json"), {})
        for rid in plan["full"] + plan["placeholder"]:
            if rid in gone:
                continue
            if rid not in (new.get("R") or {}) or rid not in (new.get("EN") or {}):
                die(f"ERROR: new.json has no R/EN entry for {rid} (no push)")
            e = dict(new["R"][rid])
            e["lang"] = (repos.get(rid) or {}).get("lang") or e.get("lang") or [["Other", 100]]
            R[rid], ENR[rid] = e, new["EN"][rid]
            if rid in plan["placeholder"]:
                if rid not in pending:
                    pending.append(rid)
            elif rid in pending:
                pending.remove(rid)
        for rid in plan["reuse"]:
            R[rid], ENR[rid] = archive[rid]["R"], archive[rid]["EN"]
        if not (isinstance(new.get("TAKE"), list) and isinstance(new.get("EN_TAKE"), list)):
            die("ERROR: new.json must have TAKE and EN_TAKE (5 each)")
        d["TAKE"], d["EN"]["TAKE"] = new["TAKE"], new["EN_TAKE"]
    referenced = {r[0] for lst in d["L"].values() for r in lst["rows"]}
    archived_now = []
    for rid in list(R):
        if rid not in referenced:
            if rid not in pending and rid not in gone:
                archive[rid] = {"archived": state["today"], "R": R[rid], "EN": ENR.get(rid)}
                archived_now.append(rid)
            R.pop(rid)
            ENR.pop(rid, None)
    pending = [p for p in pending if p in R]
    for rid in list(archive):
        if rid in R or (today - datetime.date.fromisoformat(archive[rid]["archived"])).days > ARCHIVE_DAYS:
            archive.pop(rid)
    if pending:
        d["PENDING"] = pending
    else:
        d.pop("PENDING", None)
    removed_cmds = clean_net_scripts(R, ENR)
    d["DATA_DATE"] = f"{today.day} {MONTHS[today.month - 1]} {today.year}"
    d["DATA_ISO"] = state["today"]
    d["EN"]["ISO"] = state["today"]
    err, warn = validate(d, plan.get("short") or [])
    if err:
        print("VALIDATION FAILED (nothing written, do not push):")
        for e in err:
            print(" -", e)
        sys.exit(1)
    new_s = s[:a] + block_text(d) + s[b:]
    if new_s.count('id="radar-data"') != 1 or new_s[:a] != s[:a] or not new_s.endswith(s[b:]):
        die("ERROR: page changed outside the data block (no push)")
    execs = re.findall(r"<script>(.*?)</script>", new_s, re.S)
    m = re.search(r"'sha256-([A-Za-z0-9+/=]+)'", new_s)
    if len(execs) != 1 or not m or base64.b64encode(hashlib.sha256(execs[0].encode()).digest()).decode() != m.group(1):
        die("ERROR: script hash does not match the security policy (no push)")
    tmp_page = os.path.join(WORK, "new_index.html")
    with open(tmp_page, "w", encoding="utf-8") as f:
        f.write(new_s)
    guard = run_page_guard(tmp_page, os.path.join(WORK, "orig.html"), "Daily update " + state["today"])
    if "PAGE GUARD PASSED" not in guard:
        print("LOCAL PAGE GUARD FAILED (nothing written, do not push):\n" + guard)
        sys.exit(1)
    shutil.copyfile(tmp_page, PAGE)
    jsave(ARCH, archive, pretty=True)
    summary = {"mode": plan["mode"], "refreshed": list(plan["L"]), "full": plan["full"],
               "placeholder": plan["placeholder"], "reuse": plan["reuse"], "pending": pending,
               "gone": gone, "archived": archived_now, "internet_script_removed": removed_cmds,
               "warnings": plan.get("warnings", []) + warn, "top_daily": d["L"]["daily"]["rows"][0][0]}
    jsave(os.path.join(WORK, "summary.json"), summary, pretty=True)
    print("APPLY OK | local Page guard: PASSED")
    for k in ("mode", "refreshed", "full", "placeholder", "reuse", "pending", "gone", "archived",
              "internet_script_removed", "top_daily"):
        print(f"{k}: {summary[k]}")
    for w in summary["warnings"]:
        print("WARN:", w)
    print("NEXT: node routine/smoke.js, then python3 -I routine/tool.py publish")


# ---------- step: publish ----------
def step_publish():
    state = jload(os.path.join(WORK, "state.json"))
    _, out, _ = run(["git", "-C", ROOT, "status", "--porcelain"])
    changed = {line[3:].strip() for line in out.splitlines() if line.strip()}
    allowed = {"index.html", "routine/archive.json"}
    extra = changed - allowed
    if extra:
        die("ERROR: unexpected files changed (no push): " + ", ".join(sorted(extra)))
    if not changed:
        print("NO CHANGE: nothing to push")
        return
    run(["git", "-C", ROOT, "add", "--"] + sorted(changed))
    code, _, err = run(["git", "-C", ROOT, "-c", f"user.name={AUTHOR_NAME}", "-c", f"user.email={AUTHOR_EMAIL}",
                        "commit", "-q", "-m", "Daily update " + state["today"]])
    if code != 0:
        die("ERROR: commit failed: " + err.strip())
    for attempt in (1, 2):
        code, _, err = run(["git", "-C", ROOT, "push", "-q", "origin", "HEAD:main"], timeout=120)
        if code == 0:
            break
        if re.search(r"non-fast-forward|fetch first|rejected", err, re.I) or attempt == 2:
            die("PUSH FAILED: " + err.strip()[:400], 2)
    _, head, _ = run(["git", "-C", ROOT, "rev-parse", "HEAD"])
    _, remote, _ = run(["git", "-C", ROOT, "ls-remote", "origin", "refs/heads/main"], timeout=60)
    head = head.strip()
    if remote.split()[:1] != [head]:
        die("PUSH NOT CONFIRMED (remote main is not our commit)", 3)
    print("PUSHED", head)


# ---------- step: guard ----------
def step_guard(sha):
    deadline = time.time() + 8 * 60
    run_info = None
    while time.time() < deadline:
        code, js = api(f"repos/{REPO}/actions/runs?head_sha={sha}")
        if code == 200 and js:
            for r in js.get("workflow_runs", []):
                if r.get("name") == "Page guard":
                    run_info = r
            if run_info and run_info.get("status") == "completed":
                break
        time.sleep(45)
    if not run_info or run_info.get("status") != "completed":
        print("Guard: result nahi mila")
        return
    code, js = api(f"repos/{REPO}/actions/runs/{run_info['id']}/jobs")
    jobs = {j.get("name"): j for j in (js or {}).get("jobs", [])} if code == 200 else {}
    check, deploy = jobs.get("check", {}), jobs.get("deploy", {})
    if check.get("conclusion") == "success" and deploy.get("conclusion") == "success":
        print("Guard: PASS (page live)")
    elif check.get("conclusion") == "success":
        print(f"Guard: PASS, but deploy {deploy.get('conclusion')} (purana page hi live hai)")
    else:
        steps = [s.get("name") for s in check.get("steps", []) if s.get("conclusion") == "failure"]
        print("Guard: FAIL (purana page hi live hai). Failed step:", ", ".join(steps) or run_info.get("conclusion"))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    steps = {"start": step_start, "plan": step_plan, "fetch": step_fetch, "apply": step_apply,
             "publish": step_publish}
    if step == "guard" and len(sys.argv) > 2 and re.match(r"^[0-9a-f]{7,40}$", sys.argv[2]):
        step_guard(sys.argv[2])
    elif step in steps:
        steps[step]()
    else:
        die("usage: python3 -I routine/tool.py start|plan|fetch|apply|publish|guard <sha>")
