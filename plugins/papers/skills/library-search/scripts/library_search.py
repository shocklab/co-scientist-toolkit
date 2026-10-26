#!/usr/bin/env python3
"""Search across a library of papers on this machine.

    library_search.py --db DB index [ROOT ...]      add roots and (re)index every root
    library_search.py --db DB search "QUERY" [-k N] [--json]
    library_search.py --db DB status
    library_search.py --db DB forget ROOT

Indexes the Markdown that academic-pdf-to-mkd writes (*-fulltext.md) and the LaTeX that
arxiv-fetcher downloads (*.tex) under each root, in passages of about a paragraph, with SQLite's
full-text index (FTS5, BM25 ranking, English stemming). Python's standard library only.

Papers are judged by the licence check's own records: a folder whose license.json refuses its
paper (a subscription paper or a manuscript under review, with no allow recorded) is indexed by
its title and identifiers only, never its text, and every search re-reads the records, so a later
revoke hides text at once and a later allow takes effect at the next index. Nothing leaves the
machine.
"""
import argparse, hashlib, json, os, re, sqlite3, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "license-check"))
try:
    import license_check as lc
except ImportError:
    lc = None

CHUNK = 1200          # characters per passage, roughly
SKIP_DIRS = {"figures", "tables", "pages", ".git", "__pycache__", "media", "node_modules", ".venv"}
STOP = set("a an and are as at be by for from has have in is it its of on or that the this to was "
           "were which with what how why when where do does did can we our you your i".split())


# ---------------------------------------------------------------- licence

def licence_state(path):
    """(refused, record) for a file, from the nearest license.json, as the hook judges it."""
    if lc is None:
        return False, None
    lj = lc.find_license_json(path)
    if not lj:
        return False, None
    r = lc.lj_record(lj)
    if not r:
        return False, None
    if not lc.lj_blocks(r):
        return False, r
    folder = os.path.dirname(lj)
    allowed = lc.find_allow(r, extra=["path:" + os.path.realpath(path), "path:" + folder])
    return (not allowed), r


def paper_folder(path):
    if lc is not None:
        lj = lc.find_license_json(path)
        if lj:
            return os.path.dirname(lj)
    d = os.path.dirname(path)
    return os.path.dirname(d) if os.path.basename(d) == "source" else d


# ---------------------------------------------------------------- reading

def title_of(folder, path, text):
    for name in ("license.json", "metadata.json"):
        p = os.path.join(folder, name)
        try:
            j = json.load(open(p, encoding="utf-8"))
            t = j.get("name") or j.get("title")
            if t:
                return re.sub(r"\s+", " ", t).strip()
        except (OSError, ValueError, AttributeError):
            pass
    if text:
        m = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{(.+?)\}\s*$", text, re.M | re.S)
        if m:
            return re.sub(r"\s+", " ", re.sub(r"\\[a-zA-Z]+|[{}]", " ", m.group(1))).strip()[:300]
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m:
            return m.group(1).strip()
        m = re.match(r"---\n(.*?)\n---", text, re.S)                # academic-pdf-to-mkd front matter
        if m:
            fm = dict(re.findall(r'^(\w+):\s*"?(.*?)"?\s*$', m.group(1), re.M))
            if fm.get("title"):
                return fm["title"]
            if fm.get("source_pdf"):
                return os.path.splitext(os.path.basename(fm["source_pdf"]))[0]
    return os.path.basename(folder)


def ids_of(folder):
    out = {}
    for name in ("license.json", "metadata.json"):
        try:
            j = json.load(open(os.path.join(folder, name), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for k in ("doi", "arxiv", "arxiv_id", "id"):
            v = j.get(k)
            if isinstance(v, str) and v:
                out.setdefault("arxiv" if k.startswith("arxiv") or k == "id" else k, v)
    return out


def chunks_md(lines):
    out, heading, buf, start, i = [], "", [], None, 0
    if lines and lines[0].strip() == "---":                       # YAML front matter
        for j in range(1, min(len(lines), 200)):
            if lines[j].strip() == "---":
                i = j + 1
                break

    def flush(end):
        nonlocal buf, start
        text = "\n".join(buf).strip()
        if text:
            out.append((heading, start, end, text))
        buf, start = [], None

    for n in range(i, len(lines)):
        ln = lines[n]
        if re.match(r"^#{1,6}\s", ln):
            flush(n)
            heading = ln.lstrip("#").strip()
            continue
        if not ln.strip() and sum(len(b) for b in buf) >= CHUNK:
            flush(n)
            continue
        if start is None and ln.strip():
            start = n + 1
        if start is not None:
            buf.append(ln)
    flush(len(lines))
    return out


SECTION = re.compile(r"^\s*\\(part|chapter|section|subsection|subsubsection|paragraph|newsec|subsec)\*?\s*(?:\[[^\]]*\])?\s*\{(.*)\}")


def chunks_tex(lines):
    out, heading, buf, start = [], "", [], None
    begin = next((n for n, l in enumerate(lines) if "\\begin{document}" in l), -1)

    def flush(end):
        nonlocal buf, start
        text = "\n".join(buf).strip()
        if text:
            out.append((heading, start, end, text))
        buf, start = [], None

    for n in range(begin + 1, len(lines)):
        ln = re.sub(r"(?<!\\)%.*$", "", lines[n])                 # LaTeX comments
        if "\\end{document}" in ln:
            break
        m = SECTION.match(ln)
        if m:
            flush(n)
            heading = re.sub(r"\\[a-zA-Z]+|[{}$]", "", m.group(2)).strip()
            continue
        if not ln.strip() and sum(len(b) for b in buf) >= CHUNK:
            flush(n)
            continue
        if start is None and ln.strip():
            start = n + 1
        if start is not None:
            buf.append(ln)
    flush(len(lines))
    return out


def wanted(name):
    return name.endswith("-fulltext.md") or name == "fulltext.md" or name.endswith(".tex")


# ---------------------------------------------------------------- store

def connect(db):
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    c = sqlite3.connect(db)
    c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS roots(path TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS papers(id INTEGER PRIMARY KEY, folder TEXT UNIQUE, title TEXT,
            ids TEXT, refused INTEGER);
        CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, paper INTEGER, sig TEXT, refused INTEGER);
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, paper INTEGER, path TEXT,
            heading TEXT, line_start INTEGER, line_end INTEGER, text TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, heading, content='chunks',
            content_rowid='id', tokenize='porter unicode61');
        CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
    """)
    return c


def drop_file(c, path):
    for cid, text, heading in c.execute("SELECT id, text, heading FROM chunks WHERE path=?", (path,)).fetchall():
        c.execute("INSERT INTO chunks_fts(chunks_fts, rowid, text, heading) VALUES('delete', ?, ?, ?)",
                  (cid, text, heading))
    c.execute("DELETE FROM chunks WHERE path=?", (path,))
    c.execute("DELETE FROM files WHERE path=?", (path,))


def add_chunk(c, paper, path, heading, a, b, text):
    cur = c.execute("INSERT INTO chunks(paper, path, heading, line_start, line_end, text) "
                    "VALUES(?,?,?,?,?,?)", (paper, path, heading, a, b, text))
    c.execute("INSERT INTO chunks_fts(rowid, text, heading) VALUES(?,?,?)", (cur.lastrowid, text, heading))


def cmd_index(c, roots, allow_empty=False):
    for r in roots:
        r = os.path.realpath(os.path.expanduser(r))
        if not os.path.isdir(r):
            sys.exit(f"not a folder: {r}")
        c.execute("INSERT OR IGNORE INTO roots VALUES(?)", (r,))
    roots = [row[0] for row in c.execute("SELECT path FROM roots")]
    if not roots and not allow_empty:
        sys.exit("no roots yet: give one or more folders to index")
    seen, changed, skipped, refused = set(), 0, 0, 0
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for name in files:
                if not wanted(name):
                    continue
                path = os.path.realpath(os.path.join(d, name))
                seen.add(path)
                st = os.stat(path)
                is_refused, rec = licence_state(path)
                sig = f"{st.st_mtime_ns}:{st.st_size}"
                row = c.execute("SELECT sig, refused FROM files WHERE path=?", (path,)).fetchone()
                if row and row[0] == sig and bool(row[1]) == is_refused:
                    skipped += 1
                    continue
                drop_file(c, path)
                folder = paper_folder(path)
                text = None if is_refused else open(path, encoding="utf-8", errors="replace").read()
                title = title_of(folder, path, text)
                ids = json.dumps(ids_of(folder))
                c.execute("INSERT INTO papers(folder, title, ids, refused) VALUES(?,?,?,?) "
                          "ON CONFLICT(folder) DO UPDATE SET title=excluded.title, ids=excluded.ids, "
                          "refused=excluded.refused", (folder, title, ids, int(is_refused)))
                pid = c.execute("SELECT id FROM papers WHERE folder=?", (folder,)).fetchone()[0]
                if is_refused:
                    refused += 1
                    parts = []
                else:
                    lines = text.splitlines()
                    parts = chunks_tex(lines) if name.endswith(".tex") else chunks_md(lines)
                for h, a, b, t in parts:
                    add_chunk(c, pid, path, h, a, b, t)
                c.execute("INSERT INTO files VALUES(?,?,?,?)", (path, pid, sig, int(is_refused)))
                changed += 1
        c.commit()
    gone = [p for (p,) in c.execute("SELECT path FROM files") if p not in seen]
    for p in gone:
        drop_file(c, p)
    # one metadata passage per paper (title and identifiers), the only passage a refused paper has
    for pid, title, ids in c.execute("SELECT id, title, ids FROM papers").fetchall():
        if not c.execute("SELECT 1 FROM files WHERE paper=?", (pid,)).fetchone():
            c.execute("DELETE FROM papers WHERE id=?", (pid,))
            continue
        old = c.execute("SELECT id, text, heading FROM chunks WHERE paper=? AND path=''", (pid,)).fetchall()
        for cid, t, h in old:
            c.execute("INSERT INTO chunks_fts(chunks_fts, rowid, text, heading) VALUES('delete', ?, ?, ?)", (cid, t, h))
        c.execute("DELETE FROM chunks WHERE paper=? AND path=''", (pid,))
        meta = title + " " + " ".join(json.loads(ids or "{}").values())
        add_chunk(c, pid, "", "title", 0, 0, meta)
    c.commit()
    c.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
    c.commit()
    c.execute("VACUUM")
    n_p, n_c = c.execute("SELECT COUNT(*) FROM papers").fetchone()[0], c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"indexed {changed} file(s), {skipped} unchanged, {len(gone)} removed; {refused} refused by "
          f"their licence record (title only). Library: {n_p} papers, {n_c} passages.")


# ---------------------------------------------------------------- search

def fts_query(q):
    words = [w for w in re.findall(r"\w+", q.lower()) if w not in STOP and len(w) > 1]
    return " OR ".join(f'"{w}"' for w in words)


def cmd_search(c, q, k, as_json):
    mq = fts_query(q)
    best = [cid for (cid,) in c.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? "
                                        "ORDER BY bm25(chunks_fts) LIMIT 200", (mq,))] if mq else []
    hits, per_paper = [], {}
    for cid in best:
        pid, path, heading, a, b, text = c.execute(
            "SELECT paper, path, heading, line_start, line_end, text FROM chunks WHERE id=?", (cid,)).fetchone()
        if per_paper.get(pid, 0) >= 2:
            continue
        folder, title, ids, was_refused = c.execute("SELECT folder, title, ids, refused FROM papers WHERE id=?",
                                                   (pid,)).fetchone()
        probe = path or os.path.join(folder, "_")
        now_refused, _ = licence_state(probe)
        h = {"rank": len(hits) + 1, "title": title, "folder": folder, "ids": json.loads(ids or "{}")}
        if now_refused:
            h.update(refused=True, note="its licence record refuses its text here: title and identifiers only")
        elif was_refused:
            h.update(note="allowed since it was indexed: run index to include its text")
        elif path:
            snippet = re.sub(r"\s+", " ", text)
            h.update(file=path, lines=[a, b], heading=heading, text=snippet[:500])
        else:
            h.update(note="matched on its title")
        per_paper[pid] = per_paper.get(pid, 0) + 1
        hits.append(h)
        if len(hits) >= k:
            break
    if as_json:
        print(json.dumps(hits, indent=1, ensure_ascii=False))
        return
    if not hits:
        print("no matches")
    for h in hits:
        where = f"{h['file']}:{h['lines'][0]}-{h['lines'][1]}" if "file" in h else h["folder"]
        print(f"{h['rank']}. {h['title']}\n   {where}" + (f"  [{h['heading']}]" if h.get("heading") else ""))
        print(f"   {h['text']}" if "text" in h else f"   ({h['note']})")


def cmd_status(c):
    for (r,) in c.execute("SELECT path FROM roots"):
        print("root:", r)
    p, f, ch, rf = (c.execute(q).fetchone()[0] for q in (
        "SELECT COUNT(*) FROM papers", "SELECT COUNT(*) FROM files", "SELECT COUNT(*) FROM chunks",
        "SELECT COUNT(*) FROM papers WHERE refused=1"))
    print(f"{p} papers ({rf} title only), {f} files, {ch} passages")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(os.path.expanduser("~/.local/state/library-search"), "library.sqlite"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("index"); i.add_argument("roots", nargs="*")
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("-k", type=int, default=10)
    s.add_argument("--json", action="store_true")
    sub.add_parser("status")
    fg = sub.add_parser("forget"); fg.add_argument("root")
    a = ap.parse_args()
    if lc is None:
        sys.exit("the papers plugin's license-check was not found beside this script, so licence records "
                 "cannot be applied; run the copy installed with the papers plugin")
    c = connect(a.db)
    if a.cmd == "index":
        cmd_index(c, a.roots)
    elif a.cmd == "search":
        cmd_search(c, a.query, a.k, a.json)
    elif a.cmd == "status":
        cmd_status(c)
    elif a.cmd == "forget":
        c.execute("DELETE FROM roots WHERE path=?", (os.path.realpath(os.path.expanduser(a.root)),))
        c.commit()
        cmd_index(c, [], allow_empty=True)


if __name__ == "__main__":
    main()
