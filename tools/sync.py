"""Sync NIOS OBE study material: crawl -> detect changes -> download -> embed Kruti Dev -> shrink -> file -> README.

Incremental: state lives in data/manifest.json (url, source signature, output path). Only new/changed PDFs are
re-processed. Files >= BIG bytes are written to <work>/release_stage (uploaded as GitHub Release assets by the workflow);
the rest are written into the repository tree.

  python tools/sync.py [--dry-run] [--force] [--only SUBSTR] [--publish]

--publish = after syncing: upload changed 10 MB+ files to the GitHub release, then commit and push (needs `gh` logged in).
Run it from a machine that can reach nios.ac.in (GitHub-hosted runners cannot).
"""
import argparse, concurrent.futures as cf, datetime, html, io, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse, zipfile

import pymupdf
from curl_cffi import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fix_krutidev  # noqa: E402

BASE = "https://nios.ac.in"
PAGE = BASE + "/departmentsunits/academic/open-basic-education-(obe)/obesimen.aspx"
FONT_ZIP = BASE + "/media/documents/hindi_font_krutidev.zip"
BIG = 10_000_000
pymupdf.TOOLS.mupdf_display_errors(False)


# ---------- crawl ----------
def fetch(u, head=False, stream=False, tries=3):
    """HTTP GET/HEAD with a real-browser TLS fingerprint (curl_cffi, same approach as RivalSearchMCP/Scrapling):
    nios.ac.in drops connections from plain python/urllib clients on cloud IPs. Retries with backoff."""
    last = None
    for n in range(tries):
        try:
            r = (requests.head if head else requests.get)(u, impersonate="chrome", timeout=60, allow_redirects=True,
                                                          **({"stream": True} if stream else {}))
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r
        except Exception as e:
            last = e
            time.sleep(2 * (n + 1))
    raise last


def anchors(url):
    t = fetch(url).content.decode("utf-8", "ignore")
    return [(html.unescape(h), re.sub(r"\s+", " ", re.sub("<[^>]+>", "", html.unescape(x))).strip())
            for h, x in re.findall(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t)]


def norm(h):
    u = urllib.parse.urljoin(BASE + "/", h)
    if u.count("/media/documents/") > 1:  # NIOS typo: duplicated path
        u = BASE + "/media/documents/" + u.split("/media/documents/")[-1]
    return urllib.parse.quote(u, safe=":/%?=")  # "&" in a file name must be %26


MAIN_PDF = re.compile(r"(?i)(Aleveleng|Bleveleng|Cleveleng|ENGAlevel|EngBlevel|engClevel|Level_[ABC]-2023|/[abc]-level)\.pdf$")


def collect():
    """-> list of {url,label,section} in page order (order matters: English medium comes before Hindi)."""
    items, subs = [], []
    for h, x in anchors(PAGE):
        if "SQP_MS_QPD" in h or ("OBE_SLM" in h) or MAIN_PDF.search(h):
            items.append({"url": norm(h), "label": x, "section": "main"})
        elif "open-basic-education-(obe)/" in h and re.search(r"(?i)veda|vijnana|yoga|sanskrit|vocational", h):
            subs.append((h, x))
    for h, x in subs:
        try:
            for a, b in anchors(urllib.parse.urljoin(BASE, h)):
                if re.search(r"(?i)\.pdf(\?|$)", a) and "media/documents" in a:
                    items.append({"url": norm(a), "label": b, "section": "sub:" + x})
        except Exception as e:
            print("WARN subpage failed", h, e)
    seen, out = set(), []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"]); out.append(it)
    return out


def signature(url):
    try:
        h = fetch(url, head=True, tries=2).headers
        return f"{h.get('ETag', '')}|{h.get('Content-Length', '')}|{h.get('Last-Modified', '')}"
    except Exception:
        return None


# ---------- classify ----------
def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clean_name(u):
    return re.sub(r"[^\w.()\-]+", "_", urllib.parse.unquote(u.split("/")[-1]), flags=re.U).strip("_")


def folder_for(it, medium):
    u, label = it["url"], it["label"]
    if it["section"].startswith("sub:"):
        m = re.search(r"\(([ABC])(14[5-9])", it["section"])
        lvl, code = m.group(1).lower(), m.group(2)
        subj = {"145": "veda", "146": "vijnana", "147": "yoga", "148": "sanskrit", "149": "vocational-skills"}[code]
        low = u.split("OBE_indian_knowledge_tradition/")[-1].lower()
        lang = "hindi" if "hindi" in low else "sanskrit" if "sanskrit" in low else "english" if "eng" in low else "common"
        if subj == "sanskrit" and lang == "sanskrit":
            lang = "common"
        return f"indian-knowledge-tradition/level-{lvl}/{subj}-{lvl}{code}/{lang}"
    if re.search(r"SQP_MS_QPD|Level_[ABC]-2023|/[abc]-level\.pdf", u):
        g = re.search(r"Level_([ABC])|OBE-([ABC])|/([abc])-level", u)
        lv = next((x for x in g.groups() if x), "x").lower() if g else "x"
        return f"open-basic-education/sample-question-papers/level-{lv}"
    base = u.split("/")[-1]
    m = re.search(r"\b([ABC])[ -]?level", label, re.I) or re.search(r"Level[_ ]?([ABC])|([abc])level|([ABC])_?level", base, re.I)
    lvl = next((g for g in m.groups() if g), "x").lower() if m else "x"
    L = label.lower()
    subj = ("curriculum" if "curriculum" in L else "cutting-and-tailoring" if "cutting" in L or "कटाई" in label else
            "earthworm-rearing" if "केंचुआ" in label else "bhoti-language" if "bhoti" in L else "bodh-darshan" if "bodh" in L else
            "social-science" if "social" in L or "sst" in L else "science" if "science" in L else "evs" if "evs" in L else
            "basic-computer-skills" if "comput" in L else "mathematics" if "math" in L else "english" if "english" in L else
            "hindi" if "hindi" in L else slug(label)[:40])
    return f"open-basic-education/{medium}-medium/level-{lvl}/{subj}"


def assign_paths(items):
    medium, used, out = "english", set(), []
    for it in items:
        if "ENGAlevel" in it["url"]:
            medium = "hindi"
        d, name = folder_for(it, medium), clean_name(it["url"])
        rel, k = f"{d}/{name}", 2
        while rel.lower() in used:
            rel = f"{d}/{os.path.splitext(name)[0]}_{k}.pdf"; k += 1
        used.add(rel.lower())
        out.append({**it, "rel": rel})
    return out


def asset_name(rel):
    return re.sub(r"[^A-Za-z0-9._-]", "_", rel.replace("open-basic-education/", "").replace("indian-knowledge-tradition/", "ikt/").replace("/", "__"))


# ---------- process ----------
def find_fonts(work):
    d = os.path.join(work, "krutidev")
    if not os.path.exists(os.path.join(d, "K010.TTF")):
        os.makedirs(d, exist_ok=True)
        want = ("K010.TTF", "Kruti Dev 010 Bold.ttf", "Kruti Dev 010 Italic.ttf", "Kruti Dev 010 Bold Italic.ttf")
        with zipfile.ZipFile(io.BytesIO(fetch(FONT_ZIP).content)) as z:
            for i in z.infolist():
                if i.filename.split("/")[-1] in want:
                    open(os.path.join(d, i.filename.split("/")[-1]), "wb").write(z.read(i))
    return d


def process_one(args):
    url, rel, work, fonts, repo = args
    raw = os.path.join(work, "raw", re.sub(r"\W", "_", rel))
    os.makedirs(os.path.dirname(raw), exist_ok=True)
    r = fetch(url, stream=True)
    with open(raw, "wb") as o:
        for chunk in r.iter_content(chunk_size=1 << 20):
            o.write(chunk)
    with open(raw, "rb") as fh:
        head = fh.read(5)
    if head != b"%PDF-":  # an error/redirect page saved as .pdf must never reach the repo
        os.remove(raw)
        return rel, None
    a = os.path.getsize(raw)
    tmp, fixed = raw + ".out.pdf", 0
    try:
        d = pymupdf.open(raw)
        fixed = fix_krutidev.fix(d, fonts)
        if a > 3_000_000:
            d.rewrite_images(dpi_threshold=300, dpi_target=220, quality=80)
        d.ez_save(tmp, garbage=4)
        d.close()
        if os.path.getsize(tmp) >= a and not fixed:
            shutil.copy(raw, tmp)
    except Exception as e:  # keep the original rather than lose the file
        print("WARN processing failed, keeping original:", rel, str(e)[:80])
        shutil.copy(raw, tmp)
    size = os.path.getsize(tmp)
    is_rel = size >= BIG
    dst = os.path.join(work, "release_stage", asset_name(rel)) if is_rel else os.path.join(repo, *rel.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(tmp, dst)
    os.remove(raw)
    return rel, {"size": size, "release": is_rel, "asset": asset_name(rel) if is_rel else None, "fixed_fonts": fixed}


# ---------- readme ----------
SUBJ_ORDER = ["curriculum", "hindi", "english", "mathematics", "evs", "science", "social-science", "basic-computer-skills",
              "cutting-and-tailoring", "earthworm-rearing", "bhoti-language", "bodh-darshan"]
SUBJ_NAME = {"curriculum": "Curriculum", "hindi": "Hindi", "english": "English language", "mathematics": "Mathematics",
             "evs": "EVS (Environmental Studies)", "science": "Science", "social-science": "Social Science",
             "basic-computer-skills": "Basic Computer Skills", "cutting-and-tailoring": "Cutting & Tailoring",
             "earthworm-rearing": "Earthworm rearing (केंचुआ पालन)", "bhoti-language": "Bhoti language",
             "bodh-darshan": "Bodh Darshan", "veda": "Veda", "vijnana": "Vijnana", "yoga": "Yoga", "sanskrit": "Sanskrit",
             "vocational-skills": "Vocational Skills"}
LEVEL = {"a": "Level A (Class 1–3)", "b": "Level B (Class 4–5)", "c": "Level C (Class 6–8)"}
LANG = {"common": "All / mixed", "hindi": "Hindi", "sanskrit": "Sanskrit", "english": "English"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt(iso):
    return iso.replace("T", " ")[:16] + " UTC" if iso else "unknown"


def gen_readme(repo, man, tag, slugname):
    rel_url = f"https://github.com/{slugname}/releases/download/{tag}/"

    def link(e):
        return rel_url + e["asset"] if e["release"] else urllib.parse.quote(e["rel"], safe="/-_.~")

    def size(e):
        s = e["size"]
        return f"{s / 1e6:.0f} MB ⬇" if e["release"] else (f"{s / 1e6:.1f} MB" if s >= 1e6 else f"{max(s // 1000, 1)} KB")

    HEAD = "| Title | Download | Size | Source |\n|---|---|---|---|"
    E = sorted(man.values(), key=lambda e: e["rel"])
    out = []
    w = out.append
    main = [e for e in E if e["rel"].startswith("open-basic-education/") and "/sample-question-papers/" not in e["rel"]]
    for medium, mname in (("english", "English Medium"), ("hindi", "Hindi Medium")):
        w(f"## {mname}\n")
        for lv in "abc":
            items = [e for e in main if f"/{medium}-medium/level-{lv}/" in e["rel"]]
            if not items:
                continue
            w(f"### {LEVEL[lv]}\n"); w(HEAD)
            sk = lambda e: SUBJ_ORDER.index(e["rel"].split("/")[3]) if e["rel"].split("/")[3] in SUBJ_ORDER else 99
            for e in sorted(items, key=sk):
                s = SUBJ_NAME.get(e["rel"].split("/")[3], e["rel"].split("/")[3])
                w(f"| **{s}** | [PDF]({link(e)}) | {size(e)} | [NIOS original]({e['url']}) |")
            w("")
    w("## Indian Knowledge Tradition (भारतीय ज्ञान परम्परा)\n")
    w("Veda, Vijnana, Yoga, Sanskrit and Vocational Skills — each course is published as chapter PDFs, in Hindi and/or Sanskrit/English.\n")
    ikt = [e for e in E if e["rel"].startswith("indian-knowledge-tradition/")]
    for lv in "abc":
        w(f"### {LEVEL[lv]}\n")
        for code, subj in (("145", "veda"), ("146", "vijnana"), ("147", "yoga"), ("148", "sanskrit"), ("149", "vocational-skills")):
            base = f"indian-knowledge-tradition/level-{lv}/{subj}-{lv}{code}/"
            items = [e for e in ikt if e["rel"].startswith(base)]
            if not items:
                continue
            w(f'<details><summary><b>{SUBJ_NAME[subj]} ({lv.upper()}{code})</b> — {len(items)} files · '
              f'<a href="{urllib.parse.quote(base)}">browse folder</a></summary>\n')
            for lg in sorted({e["rel"][len(base):].split("/")[0] for e in items}, key=list(LANG).index):
                w(f"**{LANG[lg]}**\n")
                w("| File | Size | Source |\n|---|---|---|")
                for e in [x for x in items if x["rel"][len(base):].split("/")[0] == lg]:
                    w(f"| [{os.path.basename(e['rel'])}]({link(e)}) | {size(e)} | [NIOS]({e['url']}) |")
                w("")
            w("</details>\n")
    w("## Sample question papers & question paper design\n")
    w("| Level | Download | Size | Source |\n|---|---|---|---|")
    for e in E:
        if "/sample-question-papers/" in e["rel"]:
            w(f"| {e['rel'].split('/')[2].replace('level-', 'Level ')} — {os.path.basename(e['rel'])} | [PDF]({link(e)}) | {size(e)} | [NIOS]({e['url']}) |")
    w("")
    tpl = open(os.path.join(repo, "tools", "README.template.md"), encoding="utf-8").read()
    open(os.path.join(repo, "README.md"), "w", encoding="utf-8", newline="\n").write(
        tpl.replace("{{COUNT}}", str(len(man))).replace("{{SRC}}", PAGE).replace("{{TABLES}}", "\n".join(out)).replace("{{TAG}}", tag)
        .replace("{{UPDATED}}", fmt(max((e.get("updated", "") for e in man.values()), default="")))
        .replace("{{CHECKED}}", fmt(now())))


# ---------- publish ----------
def sh(*cmd, cwd, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def publish(repo, work, tag):
    stage = os.path.join(work, "release_stage")
    files = [os.path.join(stage, f) for f in os.listdir(stage)] if os.path.isdir(stage) else []
    if files:
        if sh("gh", "release", "view", tag, cwd=repo, check=False).returncode:
            sh("gh", "release", "create", tag, "--title", "Large files (10 MB+)",
               "--notes", "NIOS OBE PDFs of 10 MB or more. See the README for the index, sources and copyright notice.", cwd=repo)
        for i in range(0, len(files), 8):  # batches keep each command line short
            print("uploading", len(files[i:i + 8]), "release assets...", flush=True)
            sh("gh", "release", "upload", tag, *files[i:i + 8], "--clobber", cwd=repo)
        shutil.rmtree(stage)
    sh("git", "add", "-A", cwd=repo)
    if sh("git", "diff", "--cached", "--quiet", cwd=repo, check=False).returncode == 0:
        print("nothing to commit"); return
    sh("git", "commit", "-m", f"Sync NIOS study material ({datetime.date.today()})", cwd=repo)
    print(sh("git", "push", "-u", "origin", "HEAD", cwd=repo).stderr.strip().splitlines()[-1])


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="."); ap.add_argument("--work", default=os.path.join(tempfile.gettempdir(), "nios-work"))
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=""); ap.add_argument("--tag", default="large-files-v1")
    ap.add_argument("--slug", default=os.environ.get("GITHUB_REPOSITORY", "getappz/nios-obe-study-material"))
    ap.add_argument("--bootstrap", help="dir holding existing release assets: build manifest from current files, no downloads")
    ap.add_argument("--jobs", type=int, default=3); ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    repo, work = os.path.abspath(a.repo), os.path.abspath(a.work)
    mpath = os.path.join(repo, "data", "manifest.json")
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}

    items = assign_paths(collect())
    print(f"NIOS lists {len(items)} PDFs; manifest has {len(man)}")
    with cf.ThreadPoolExecutor(8) as ex:
        sigs = list(ex.map(lambda i: signature(i["url"]), items))
    todo, unavailable = [], []
    for it, sig in zip(items, sigs):
        if sig is None:
            unavailable.append(it["url"]); continue
        old = man.get(it["url"])
        it["sig"] = sig
        if a.bootstrap:
            p = os.path.join(repo, *it["rel"].split("/")); q = os.path.join(a.bootstrap, asset_name(it["rel"]))
            f = q if os.path.exists(q) else p
            if os.path.exists(f):
                man[it["url"]] = {"url": it["url"], "label": it["label"], "rel": it["rel"], "sig": sig, "updated": now(), "size": os.path.getsize(f),
                                  "release": f == q, "asset": asset_name(it["rel"]) if f == q else None}
            continue
        if a.only and a.only not in it["url"]:
            continue
        if a.force or not old or old["sig"] != sig or old["rel"] != it["rel"]:
            todo.append(it)
    gone = [u for u in man if u not in {i["url"] for i in items}]
    print(f"to (re)process: {len(todo)} | unavailable now: {len(unavailable)} | no longer listed: {len(gone)}")
    for it in todo[:60]:
        print("  ", "NEW" if it["url"] not in man else "CHG", it["rel"])
    if a.dry_run:
        return
    if todo:
        os.makedirs(work, exist_ok=True)
        fonts = find_fonts(work)
        with cf.ProcessPoolExecutor(a.jobs) as ex:
            for rel, info in ex.map(process_one, [(i["url"], i["rel"], work, fonts, repo) for i in todo]):
                it = next(i for i in todo if i["rel"] == rel)
                if info is None:
                    print("WARN not a PDF, skipped:", it["url"]); continue
                old = man.get(it["url"])
                if old and old["rel"] != rel and not old["release"]:  # moved on the site: drop the old copy
                    op = os.path.join(repo, *old["rel"].split("/"))
                    if os.path.exists(op):
                        os.remove(op)
                man[it["url"]] = {"url": it["url"], "label": it["label"], "rel": rel, "sig": it["sig"], "updated": now(), **info}
                print("done", rel, info["size"] // 1000, "KB", "(release)" if info["release"] else "")
    for u in gone:  # keep files, flag them so the maintainer notices
        man[u]["unlisted"] = True
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    json.dump(man, open(mpath, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1, sort_keys=True)
    gen_readme(repo, man, a.tag, a.slug)
    stage = os.path.join(work, "release_stage")
    print("release assets staged:", len(os.listdir(stage)) if os.path.isdir(stage) else 0)
    if a.publish:
        publish(repo, work, a.tag)


if __name__ == "__main__":
    main()
