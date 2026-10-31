#!/usr/bin/env python3
"""Check that every number in a manuscript has a recorded route to its source.

    check_provenance.py MANUSCRIPT [MANUSCRIPT ...] --ledger paper/provenance.tsv
                        [--root DIR] [--bib FILE ...] [--no-run] [--sentences]

The ledger is a tab-separated file with the header  text  value  kind  source

    text    words copied from the manuscript that contain the number or state the fact
    value   the number as printed in that text; empty for a fact with no number; * for every
            number in the text, or in the whole table when the text is inside a table
    kind    calculation: source is a command, run from --root, that prints the number
            file:        source is a path, relative to --root, holding the value as printed
            citation:    source is a citation key the manuscript cites, then optionally a colon
                         and a location (needs --bib)
            exempt:      source is the reason, in words, that this number needs no source

Exit code 0 means every digit-written number in the manuscripts sits inside the text of a row
that records it, and every row checks out. Exit code 1 lists what failed. Display equations, code,
comments and front matter are not scanned. Commands in the ledger are run with the shell, so run this only on a ledger you trust, or pass --no-run. Python's
standard library only.
"""
import argparse, csv, decimal, os, re, subprocess, sys

KINDS = {"calculation", "file", "citation", "exempt"}
WITHDRAWN = "_ARCHIVE"
CMD_TIMEOUT = 600

MASK_ENVS = r"equation|align|alignat|gather|multline|eqnarray|displaymath|math|thebibliography|verbatim|lstlisting|tikzpicture"
MASK_ARG_CMDS = (r"label|ref|eqref|autoref|cref|Cref|pageref|cite[a-zA-Z]*|[a-zA-Z]*cite|includegraphics|input|include|"
                 r"bibliography|bibliographystyle|url|href|begin|end|hypersetup|usepackage|documentclass|vspace|hspace|"
                 r"setlength|addtolength|setcounter|multicolumn|multirow|cline|cmidrule")
_ITEM = r"\(?\[?[A-Z]?\d+(?:\.\d+)*[a-z]?\)?\]?"
NUMBER_REF = re.compile(
    r"\b(?:Figure|Fig\.?|Table|Tab\.?|Section|Sec\.?|Equation|Eq\.?|Appendix|Chapter|Ch\.?|Theorem|Thm\.?|Lemma|"
    r"Proposition|Prop\.?|Corollary|Definition|Def\.?|Algorithm|Alg\.?|Step|Ref\.?|Page)(?:~|\s)*" + _ITEM +
    r"(?:\s*(?:and|-+|–)\s*" + _ITEM + r")?"
    r"|\b(?:Figures|Figs\.?|Tables|Tabs\.?|Sections|Secs\.?|Equations|Eqs\.?|Appendices|Chapters|Theorems|Lemmas|"
    r"Propositions|Definitions|Algorithms|Steps|Refs\.?|Pages|pp\.|p\.)(?:~|\s)*" + _ITEM +
    r"(?:\s*(?:,|and|&|-+|–)\s*" + _ITEM + r")*")
NAME_NUMBER = re.compile(r"\b[A-Za-z][A-Za-z]*-\d[\w.-]*")
CITE_YEAR = re.compile(r"(?:et al\.?,?\s*\(?|[A-Z][a-z]+,\s*|\b[A-Z][a-z]+\s+\()(?:19|20)\d\d[a-z]?\)?")
NUMBER = re.compile(r"(?<![\w.\\])(?=\.?\d)(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][-+]?\d+)?(?:\\?%)?"
                    r"(?:[A-Za-zμµ]{1,4})?(?![\w])")
CORE = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][-+]?\d+)?")
DIMENSION = re.compile(r"^\d[Dd]$")
MACRO_VALUE = re.compile(r"\\(?:new|renew|provide)command\*?\s*\{?\\[A-Za-z]+\}?\s*\{[^{}]*\d[^{}]*\}|\\def\\[A-Za-z]+\{[^{}]*\d[^{}]*\}")
LAYOUT = re.compile(r"\\(?:re)?newcommand\*?\s*\{?\\(?:arraystretch|baselinestretch|tabcolsep)\}?\s*\{[^{}]*\}|\\setcounter\{[^{}]*\}\{[^{}]*\}")
TABLE_ENV = re.compile(r"\\begin\{(table|tabular|longtable)\*?\}.*?\\end\{\1\*?\}", re.S)
WORDS = ("two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
         "eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion "
         "half third quarter twice double").split()
NUMBER_WORD = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.I)


def blank(text, start, end):
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def blank_re(text, pattern, flags=0):
    for m in reversed(list(re.finditer(pattern, text, flags))):
        text = blank(text, m.start(), m.end())
    return text


def blank_arg_cmds(text):
    """Blank \\cmd[opt]{arg}, including the brace group when it nests."""
    for m in reversed(list(re.finditer(r"\\(?:" + MASK_ARG_CMDS + r")\*?(?:\[[^\]]*\])*(?=\{|\b)", text))):
        i, depth = m.end(), 0
        if i < len(text) and text[i] == "{":
            for i in range(m.end(), len(text)):
                depth += (text[i] == "{") - (text[i] == "}")
                if depth == 0:
                    i += 1
                    break
        text = blank(text, m.start(), i)
    return text


def inline_math(text):
    """In inline maths keep decimals and numbers stated after a relation; blank the rest (x^2, N_1)."""
    def walk(m):
        body = m.group(0)
        out = list(re.sub(r"[^\n]", " ", body))
        bare = re.sub(r"\\[a-zA-Z]+", lambda c: " " * len(c.group(0)), body)     # \pm0.7, \times10
        for n in NUMBER.finditer(bare):
            before = body[:n.start()].rstrip()
            after = body[n.end():]
            stated = ("." in n.group(0) or re.search(r"(=|<|>|\\approx|\\sim|\\simeq|\\leq?|\\geq?|\\pm|\\times)\s*$", before)
                      or (before == "$" and re.match(r"\s*(\\,|\\pm|\\%|\\mathrm|\\text|\\times|\$)", after)))
            subscript = re.search(r"[_^]\{?\s*$", before)
            if stated and not subscript:
                out[n.start():n.end()] = list(n.group(0))
        return "".join(out)
    return re.sub(r"(?<![\\$])\$(?!\$)[^$\n]*\$", walk, text)


def mask_tex(text):
    macros = [m.span() for m in MACRO_VALUE.finditer(text)]
    begin = text.find("\\begin{document}")
    if begin >= 0:
        original = text
        text = blank(text, 0, begin)
        for a, b in macros:                                       # numbers kept in macros are results too
            if b <= begin:
                text = text[:a] + original[a:b] + text[b:]
    end = text.find("\\end{document}")
    if end >= 0:
        text = blank(text, end, len(text))
    text = blank_re(text, r"(?<!\\)%.*$", re.M)
    text = blank_re(text, r"\\begin\{(" + MASK_ENVS + r")\*?\}.*?\\end\{\1\*?\}", re.S)
    text = blank_re(text, r"\\\[.*?\\\]", re.S)
    text = blank_re(text, r"\$\$.*?\$\$", re.S)
    text = blank_re(text, LAYOUT.pattern)
    text = blank_re(text, r"\\begin\{(?:tabular|longtable)\*?\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}")
    text = blank_re(text, r"\\newcolumntype.*$", re.M)
    text = blank_arg_cmds(text)
    text = blank_re(text, r"https?://\S+")
    text = blank_re(text, r"\[[\d,\s]+\]")
    return inline_math(text)


def mask_md(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            text = blank(text, 0, end + 4)
    text = blank_re(text, r"^(```|~~~).*?^\1\s*$", re.M | re.S)
    text = blank_re(text, r"<!--.*?-->", re.S)
    text = blank_re(text, r"`[^`\n]*`")
    text = blank_re(text, r"\$\$.*?\$\$", re.S)
    text = blank_re(text, r"(?<=\])\([^)\n]*\)")                  # the link's address, not its words
    text = blank_re(text, r"https?://\S+")
    text = blank_re(text, r"\[(?:-?@[^\]\n]*|[\d,\s]+)\]")
    text = blank_re(text, r"^\s*(?:\d+\.|\d+\))(?=\s)", re.M)
    text = blank_re(text, r"^#{1,6}\s+[\d.]+(?=\s)", re.M)
    return inline_math(text)


def mask(path, text):
    text = mask_tex(text) if path.endswith(".tex") else mask_md(text)
    for pattern in (NUMBER_REF, NAME_NUMBER, CITE_YEAR):
        text = blank_re(text, pattern.pattern)
    return text


def flatten(text):
    """Whitespace-collapsed text and, for each of its characters, the offset in the original."""
    out, where, gap = [], [], False
    for i, ch in enumerate(text):
        if ch.isspace():
            gap = bool(out)
            continue
        if gap:
            out.append(" "); where.append(i)
            gap = False
        out.append(ch); where.append(i)
    return "".join(out), where


def plain(token):
    """The number in a token, without sign, percent, unit or thousands commas."""
    token = token.replace("\\", "").replace(" ", "").lstrip("+-−")
    return CORE.match(token).group(0).replace(",", "")


def number_of(token):
    sign = -1 if token.strip().startswith(("-", "−")) else 1
    return sign * decimal.Decimal(plain(token))


def numbers_in(text):
    bare = re.sub(r"\\[a-zA-Z]+", lambda c: " " * len(c.group(0)), text)
    return [plain(m.group(0)) for m in NUMBER.finditer(bare)]


def tex_keys(paths):
    keys = set()
    for p in paths:
        try:
            keys |= set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", open(p, encoding="utf-8", errors="replace").read()))
            keys |= set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", open(p, encoding="utf-8", errors="replace").read()))
        except OSError:
            pass
    return keys


def run(cmd, root):
    try:
        p = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    if p.returncode:
        return None, f"exit code {p.returncode}: {p.stderr.strip()[-200:]}"
    found = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", p.stdout)
    if not found:
        return None, "printed no number"
    return decimal.Decimal(found[-1]), p.stdout


def in_source(token, body):
    """Is the printed number in the source, exactly or rounded to the printed precision?"""
    want = decimal.Decimal(token)
    step = decimal.Decimal(1).scaleb(want.as_tuple().exponent) / 2
    for f in re.findall(r"\d*\.?\d+(?:[eE][-+]?\d+)?", body.replace(",", "")):
        if abs(abs(decimal.Decimal(f)) - want) <= step:
            return True
    return False


def names_a_file(cmd, root):
    return any(os.path.isfile(os.path.join(root, t.strip("'\"")))
               for t in re.split(r"[\s=<>|;]+", cmd) if t and not t.startswith("-"))


def check_row(n, r, root, keys, args, fail, cited, manuscripts):
    text, value, kind, source = ((r.get(k) or "").strip() for k in ("text", "value", "kind", "source"))
    if kind not in KINDS:
        fail(f"row {n}: unknown kind {kind!r}")
        return
    if not text or not source:
        fail(f"row {n}: text and source are both required")
        return
    if value and value != "*" and plain(value) not in numbers_in(text):
        fail(f"row {n}: value {value} is not in its text: {text}")
    if kind in ("calculation", "file") and WITHDRAWN in source:
        fail(f"row {n}: {source} reads a withdrawn run")
        return
    if kind == "exempt" and len(source.split()) < 2:
        fail(f"row {n}: an exempt row needs a reason in words")
    if kind == "calculation":
        if not value:
            fail(f"row {n}: a calculation needs a value")
            return
        for d in re.findall(r"results/[^/\s'\"]+", source):
            if os.path.isdir(os.path.join(root, d)) and not os.path.exists(os.path.join(root, d, "MANIFEST.txt")):
                fail(f"row {n}: {d} has no MANIFEST.txt")
        if args.no_run:
            return
        got, out = run(source, root)
        if got is None:
            fail(f"row {n}: calculation for {value}: {out}")
            return
        if not names_a_file(source, root):
            fail(f"row {n}: the calculation names no project file: {source}")
        if value == "*":
            r["_body"] = out
            return
        want = number_of(value)
        step = decimal.Decimal(1).scaleb(want.as_tuple().exponent) / 2
        if abs(got - want) > step:
            fail(f"row {n}: printed {value}, calculation gives {got}: {text}")
    elif kind == "file":
        path = source.split(":")[0]
        p = os.path.realpath(os.path.join(root, path))
        if p in manuscripts:
            fail(f"row {n}: {path} is the manuscript itself")
            return
        try:
            body = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            fail(f"row {n}: cannot read {source}")
            return
        if value == "*":
            r["_body"] = body
        elif value and not in_source(plain(value), body):
            fail(f"row {n}: {value} is not in {source}")
    elif kind == "citation":
        key = source.split(":")[0].strip()
        if keys is None:
            fail(f"row {n}: a citation row needs --bib")
        elif key not in keys:
            fail(f"row {n}: citation key {key} is not in the bibliography")
        elif key not in cited:
            fail(f"row {n}: the manuscript never cites {key}")


def with_inputs(paths):
    """The manuscripts and the .tex files they \\input or \\include."""
    out, todo = [], list(paths)
    while todo:
        p = todo.pop(0)
        if os.path.realpath(p) in [os.path.realpath(q) for q in out]:
            continue
        if not p.endswith((".tex", ".md")):
            sys.exit(f"a manuscript must be .tex or .md: {p}")
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
        except OSError as e:
            sys.exit(f"cannot read the manuscript: {e}")
        out.append(p)
        if p.endswith(".tex"):
            for name in re.findall(r"^[^%\n]*\\(?:input|include)\{([^}]+)\}", raw, re.M):
                for c in (name, name + ".tex"):
                    q = os.path.join(os.path.dirname(p), c)
                    if q.endswith(".tex") and os.path.isfile(q):
                        todo.append(q)
                        break
    return out


def table_around(path, raw, a, b):
    """The table that holds this span, or the span itself."""
    if path.endswith(".tex"):
        for m in TABLE_ENV.finditer(raw):
            if m.start() <= a and b <= m.end():
                return m.span()
        return a, b
    start = raw.rfind("\n", 0, a) + 1
    end = raw.find("\n", b)
    end = len(raw) if end < 0 else end
    if not raw[start:end].lstrip().startswith("|"):
        return a, b
    while start > 0:
        prev = raw.rfind("\n", 0, start - 1) + 1
        if not raw[prev:start].lstrip().startswith("|"):
            break
        start = prev
    while end < len(raw):
        nxt = raw.find("\n", end + 1)
        nxt = len(raw) if nxt < 0 else nxt
        if not raw[end + 1:nxt].lstrip().startswith("|"):
            break
        end = nxt
    return start, end


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("manuscripts", nargs="+")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--bib", nargs="*", default=None)
    ap.add_argument("--no-run", action="store_true", help="check records without running their commands")
    ap.add_argument("--sentences", action="store_true", help="list sentences with no citation and no record, for review")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    problems, warnings = [], []
    try:
        rows = list(csv.DictReader(open(args.ledger, encoding="utf-8", newline=""), delimiter="\t", quoting=csv.QUOTE_NONE))
    except OSError as e:
        sys.exit(f"cannot read the ledger: {e}")
    if rows and not {"text", "value", "kind", "source"} <= set(rows[0]):
        sys.exit("the ledger's header must be: text value kind source")
    keys = tex_keys(args.bib) if args.bib else None
    args.manuscripts = with_inputs(args.manuscripts)
    cited = " ".join(open(p, encoding="utf-8", errors="replace").read() for p in args.manuscripts)
    manuscripts = {os.path.realpath(p) for p in args.manuscripts}
    for n, r in enumerate(rows, 2):
        check_row(n, r, root, keys, args, problems.append, cited, manuscripts)

    docs = []
    for path in args.manuscripts:
        raw = open(path, encoding="utf-8", errors="replace").read()
        visible = mask(path, raw)
        docs.append((path, raw, visible, *flatten(raw)))
    placed = [False] * len(rows)
    for path, raw, visible, flat, where in docs:
        covered = []
        for i, r in enumerate(rows):
            snippet = " ".join((r.get("text") or "").split())
            if not snippet:
                continue
            value = (r.get("value") or "").strip()
            for m in re.finditer(re.escape(snippet), flat):
                placed[i] = True
                a, b = where[m.start()], where[m.end() - 1] + 1
                if value == "*":
                    a, b = table_around(path, raw, a, b)
                covered.append((a, b, "*" if value == "*" else plain(value) if value else "", i))
        tagged = [(a, b) for a, b, v, i in covered]
        for m in NUMBER.finditer(visible):
            if DIMENSION.match(m.group(0)):
                continue
            token = plain(m.group(0))
            rows_here = [i for a, b, v, i in covered if a <= m.start() and m.end() <= b and v in (token, "*")]
            ok = bool(rows_here)
            for i in rows_here:
                body = rows[i].get("_body")
                if body is not None and not in_source(token, body):
                    line = raw.count("\n", 0, m.start()) + 1
                    problems.append(f"{os.path.basename(path)}:{line}: {m.group(0)} is not in the source of row {i + 2}")
            if not ok:
                line = raw.count("\n", 0, m.start()) + 1
                ctx = " ".join(raw[max(0, m.start() - 40):m.end() + 30].split())
                problems.append(f"{os.path.basename(path)}:{line}: no record for {m.group(0)} in: ...{ctx}...")
        for m in NUMBER_WORD.finditer(visible):
            if not any(a <= m.start() and m.end() <= b for a, b in tagged):
                line = raw.count("\n", 0, m.start()) + 1
                warnings.append(f"{os.path.basename(path)}:{line}: number word '{m.group(0)}' has no record")
        if args.sentences:
            for s in re.finditer(r"[A-Z][^.!?\n]*(?:\n[^.!?\n]+)*[.!?]", visible):
                has_cite = re.search(r"\\\w*cite|\[@", raw[s.start():s.end()])
                if len(s.group(0).split()) >= 5 and not has_cite and not any(a < s.end() and b > s.start() for a, b in tagged):
                    line = raw.count("\n", 0, s.start()) + 1
                    print(f"unrecorded sentence {os.path.basename(path)}:{line}: {' '.join(s.group(0).split())[:120]}")
    for i, r in enumerate(rows):
        if not placed[i] and (r.get("text") or "").strip():
            problems.append(f"row {i + 2}: its text is no longer in the manuscript: {r['text'].strip()}")

    for w in warnings:
        print("warning:", w)
    for p in problems:
        print("FAIL:", p)
    print(f"{len(rows)} records, {len(problems)} failures, {len(warnings)} warnings")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
