#!/usr/bin/env python3
"""
Fetch LaTeX source and PDF from arXiv.

Usage:
    python fetch_arxiv.py <arxiv_id_or_url> [--output-dir <dir>] [--delay <seconds>]

Examples:
    python fetch_arxiv.py 2301.12345
    python fetch_arxiv.py https://arxiv.org/abs/2301.12345 --output-dir ./papers
    python fetch_arxiv.py hep-th/0601234 --delay 5
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from html.parser import HTMLParser


# --------------------------------------------------------------------------- #
#  arXiv ID parsing
# --------------------------------------------------------------------------- #

def parse_arxiv_id(raw: str) -> str:
    """Extract a canonical arXiv ID from any common format.

    Accepts:
      - bare new-style IDs:  2301.12345, 2301.12345v2
      - bare old-style IDs:  hep-th/0601234, math.AG/0601234v1
      - full URLs:           https://arxiv.org/abs/2301.12345
      - arXiv: prefix:       arXiv:2301.12345
    """
    raw = raw.strip()

    # Strip URL prefix
    url_match = re.search(
        r'arxiv\.org/(?:abs|pdf|src|e-print)/(.+?)(?:\?|#|$)', raw, re.IGNORECASE
    )
    if url_match:
        raw = url_match.group(1).strip('/')

    # Strip arXiv: prefix
    raw = re.sub(r'^arxiv:\s*', '', raw, flags=re.IGNORECASE)

    # Validate
    new_style = re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', raw)
    old_style = re.fullmatch(r'[\w.-]+/\d{7}(?:v\d+)?', raw)

    if new_style or old_style:
        return raw

    raise ValueError(
        f"Cannot parse arXiv ID from: {raw!r}. "
        "Expected formats: 2301.12345, hep-th/0601234, or an arxiv.org URL."
    )


# --------------------------------------------------------------------------- #
#  Minimal HTML metadata scraper (no external deps)
# --------------------------------------------------------------------------- #

class ArxivAbsParser(HTMLParser):
    """Extracts title, authors, abstract, categories from an arXiv abs page."""

    def __init__(self):
        super().__init__()
        self._tag_stack = []
        self._capture = None  # which field we're capturing
        self.title = ""
        self.authors = []
        self.abstract = ""
        self.categories = ""
        self._in_authors_block = False
        self._current_author = ""
        self._meta = {}

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        self._tag_stack.append((tag, attrs_d))

        if tag == "meta":
            name = attrs_d.get("name", "")
            prop = attrs_d.get("property", "")
            content = attrs_d.get("content", "")
            if name == "citation_title":
                self.title = content
            elif name == "citation_author":
                self.authors.append(content)
            elif prop == "og:description":
                self.abstract = content
            self._meta[name or prop] = content

        cls = attrs_d.get("class", "")
        if tag == "span" and "primary-subject" in cls:
            self._capture = "categories"

    def handle_data(self, data):
        if self._capture == "categories":
            self.categories += data

    def handle_endtag(self, tag):
        if self._capture == "categories" and tag == "span":
            self._capture = None
        if self._tag_stack:
            self._tag_stack.pop()


def fetch_metadata(arxiv_id: str) -> dict:
    """Fetch metadata from the arXiv abstract page."""
    url = f"https://arxiv.org/abs/{arxiv_id}"
    html = _http_get(url).decode("utf-8", errors="replace")

    parser = ArxivAbsParser()
    parser.feed(html)

    # Fallback: try to extract abstract from blockquote if meta tag missed it
    if not parser.abstract:
        m = re.search(
            r'<blockquote[^>]*class="abstract[^"]*"[^>]*>\s*(?:<span[^>]*>Abstract:</span>)?\s*(.*?)</blockquote>',
            html, re.DOTALL | re.IGNORECASE
        )
        if m:
            # Strip HTML tags from abstract
            parser.abstract = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    return {
        "arxiv_id": arxiv_id,
        "title": parser.title.strip(),
        "authors": parser.authors,
        "abstract": parser.abstract.strip(),
        "primary_category": parser.categories.strip(),
        "abs_url": url,
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "src_url": f"https://arxiv.org/src/{arxiv_id}",
    }


# --------------------------------------------------------------------------- #
#  HTTP helpers
# --------------------------------------------------------------------------- #

USER_AGENT = (
    "Mozilla/5.0 (compatible; academic-paper-fetcher/1.0; "
    "+https://github.com/shocklab/co-scientist-toolkit)"
)


def _http_get(url: str, max_retries: int = 3, backoff: float = 2.0) -> bytes:
    """GET with retries and exponential backoff."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff ** (attempt + 1)
            print(f"  Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
            time.sleep(wait)


# --------------------------------------------------------------------------- #
#  Source extraction
# --------------------------------------------------------------------------- #

def _inside(path: Path, root: Path) -> bool:
    """True if path, once resolved, is root or lies under it."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _member_is_safe(member: tarfile.TarInfo, dest: Path) -> bool:
    """Refuse absolute paths, '..', special files and links that leave dest."""
    name = member.name
    if name.startswith("/") or ".." in Path(name).parts or ".." in name:
        return False
    if not (member.isreg() or member.isdir() or member.issym() or member.islnk()):
        return False
    if not _inside(dest / name, dest):
        return False
    if member.issym():
        target = Path(member.linkname)
        if target.is_absolute():
            return False
        return _inside(dest / Path(name).parent / target, dest)
    if member.islnk():
        target = Path(member.linkname)
        if target.is_absolute():
            return False
        return _inside(dest / target, dest)
    return True


def _extract_members(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract a tar archive into dest, skipping unsafe members.

    Uses tarfile's own "data" filter where this Python has it (3.12, and the
    security releases of 3.8 to 3.11); otherwise applies _member_is_safe and
    drops setuid, setgid and sticky bits.
    """
    has_filter = hasattr(tarfile, "data_filter")
    for member in tar.getmembers():
        if not _member_is_safe(member, dest):
            print(f"  WARNING: skipping suspicious path: {member.name}")
            continue
        if has_filter:
            tar.extract(member, dest, filter="data")
        else:
            member.mode &= 0o777
            tar.extract(member, dest)


TEX_MARK = re.compile(r"\\(documentclass|documentstyle|begin|input|def|bye|title|section|magnification)\b")


def _looks_like_tex(text: str) -> bool:
    return bool(TEX_MARK.search(text[:200000]))


def extract_source(data: bytes, dest: Path) -> bool:
    """Extract arXiv source into dest directory.

    arXiv source can be:
    1. A gzipped tar archive (most common)
    2. A single gzipped file (older papers)
    3. A plain tex file (rare)

    Returns True if source was successfully extracted.
    """
    dest.mkdir(parents=True, exist_ok=True)

    # Try as tar.gz first
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            _extract_members(tar, dest)
            return True
    except (tarfile.TarError, gzip.BadGzipFile, EOFError):
        pass

    # Try as plain tar (uncompressed)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            _extract_members(tar, dest)
            return True
    except (tarfile.TarError, EOFError):
        pass

    # Try as single gzipped file
    try:
        decompressed = gzip.decompress(data)
        # Check if it looks like tex (LaTeX, or plain TeX such as harvmac papers)
        text = decompressed.decode("utf-8", errors="replace")
        if _looks_like_tex(text):
            (dest / "main.tex").write_bytes(decompressed)
            return True
    except (gzip.BadGzipFile, EOFError):
        pass

    # Try as plain text (some very old papers)
    try:
        text = data.decode("utf-8")
        if _looks_like_tex(text):
            (dest / "main.tex").write_bytes(data)
            return True
    except UnicodeDecodeError:
        pass

    return False


def find_main_tex(source_dir: Path) -> str | None:
    """Identify the main .tex file (the one containing \\documentclass)."""
    candidates = []
    for tex_file in source_dir.rglob("*.tex"):
        content = tex_file.read_text(errors="replace")
        if re.search(r'\\documentclass', content):
            candidates.append(tex_file)

    if not candidates:
        # Fallback: any .tex file
        all_tex = list(source_dir.rglob("*.tex"))
        if all_tex:
            return str(all_tex[0].relative_to(source_dir))
        return None

    if len(candidates) == 1:
        return str(candidates[0].relative_to(source_dir))

    # Multiple candidates: prefer one named main.tex, paper.tex, or the shortest name
    for name in ["main.tex", "paper.tex", "manuscript.tex", "article.tex"]:
        for c in candidates:
            if c.name.lower() == name:
                return str(c.relative_to(source_dir))

    # Shortest path as tiebreaker (top-level files preferred)
    candidates.sort(key=lambda p: len(p.parts))
    return str(candidates[0].relative_to(source_dir))


# --------------------------------------------------------------------------- #
#  Main fetch function
# --------------------------------------------------------------------------- #

def fetch_arxiv_paper(
    raw_id: str,
    output_dir: str = ".",
    delay: float = 3.0,
) -> dict:
    """Fetch an arXiv paper's source and PDF.

    Args:
        raw_id: arXiv ID, URL, or arXiv:-prefixed string.
        output_dir: Parent directory for output. Paper goes into a subdirectory.
        delay: Seconds to wait between HTTP requests (be nice to arXiv).

    Returns:
        dict with keys: arxiv_id, paper_dir, main_tex, metadata, source_available, pdf_path
    """
    arxiv_id = parse_arxiv_id(raw_id)
    safe_dirname = arxiv_id.replace("/", "_")
    paper_dir = Path(output_dir) / safe_dirname
    paper_dir.mkdir(parents=True, exist_ok=True)
    source_dir = paper_dir / "source"

    result = {
        "arxiv_id": arxiv_id,
        "paper_dir": str(paper_dir),
        "main_tex": None,
        "metadata": {},
        "source_available": False,
        "pdf_path": None,
    }

    # 1. Metadata
    print(f"[1/3] Fetching metadata for {arxiv_id}...")
    try:
        metadata = fetch_metadata(arxiv_id)
        result["metadata"] = metadata
        (paper_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False)
        )
        print(f"  Title: {metadata.get('title', '(unknown)')}")
        print(f"  Authors: {', '.join(metadata.get('authors', []))}")
    except Exception as e:
        print(f"  WARNING: Could not fetch metadata: {e}")

    time.sleep(delay)

    # 2. Source
    print(f"[2/3] Fetching source for {arxiv_id}...")
    try:
        src_url = f"https://arxiv.org/src/{arxiv_id}"
        src_data = _http_get(src_url)

        if extract_source(src_data, source_dir):
            result["source_available"] = True
            main_tex = find_main_tex(source_dir)
            if main_tex:
                result["main_tex"] = str(source_dir / main_tex)
                print(f"  Main .tex: {main_tex}")
            else:
                print("  WARNING: No .tex file found in source")

            # List all files
            all_files = [
                str(f.relative_to(source_dir))
                for f in source_dir.rglob("*")
                if f.is_file()
            ]
            print(f"  Extracted {len(all_files)} files")
        else:
            print("  Source not available or unrecognised format")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("  Source not available (PDF-only submission)")
        else:
            print(f"  WARNING: HTTP {e.code} fetching source: {e}")
    except Exception as e:
        print(f"  WARNING: Could not fetch source: {e}")

    time.sleep(delay)

    # 3. PDF
    print(f"[3/3] Fetching PDF for {arxiv_id}...")
    try:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        pdf_data = _http_get(pdf_url)
        pdf_path = paper_dir / "paper.pdf"
        pdf_path.write_bytes(pdf_data)
        result["pdf_path"] = str(pdf_path)
        print(f"  PDF saved ({len(pdf_data) / 1024:.0f} KB)")
    except Exception as e:
        print(f"  WARNING: Could not fetch PDF: {e}")

    # 4. Write manifest
    manifest = {
        "arxiv_id": arxiv_id,
        "source_available": result["source_available"],
        "main_tex": result["main_tex"],
        "pdf_path": result["pdf_path"],
        "all_source_files": (
            [str(f.relative_to(source_dir)) for f in source_dir.rglob("*") if f.is_file()]
            if source_dir.exists()
            else []
        ),
    }
    (paper_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    # 5. Licence: license.json beside the paper, so reading any file here later
    #    shows what the licence allows (the papers plugin's tools/license-check). Non-fatal.
    checker = Path(__file__).resolve().parents[3] / "tools" / "license-check" / "license_check.py"
    if checker.exists():
        import subprocess
        try:
            r = subprocess.run(
                [sys.executable, str(checker), "check", arxiv_id, "--rights",
                 "--write", str(paper_dir / "license.json")],
                capture_output=True, text=True, timeout=30,
            )
            print(f"Licence: {r.stdout.strip() or 'not determined'}")
        except Exception as e:
            print(f"Licence check skipped: {e}")

    print(f"\nDone. Output in: {paper_dir}")
    return result


# --------------------------------------------------------------------------- #
#  Batch fetch
# --------------------------------------------------------------------------- #

def fetch_multiple(
    ids: list[str],
    output_dir: str = ".",
    delay: float = 3.0,
) -> list[dict]:
    """Fetch multiple papers with rate limiting."""
    results = []
    for i, raw_id in enumerate(ids):
        print(f"\n{'='*60}")
        print(f"Paper {i+1}/{len(ids)}: {raw_id}")
        print(f"{'='*60}")
        try:
            result = fetch_arxiv_paper(raw_id, output_dir=output_dir, delay=delay)
            results.append(result)
        except Exception as e:
            print(f"ERROR fetching {raw_id}: {e}")
            results.append({"arxiv_id": raw_id, "error": str(e)})
        if i < len(ids) - 1:
            time.sleep(delay)
    return results


# --------------------------------------------------------------------------- #
#  Extract arXiv IDs from text (bib files, tex bibliographies)
# --------------------------------------------------------------------------- #

def extract_arxiv_ids_from_text(text: str) -> list[str]:
    """Extract arXiv IDs from arbitrary text (bib entries, tex files, etc.)."""
    patterns = [
        r'arxiv\.org/(?:abs|pdf|src)/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arxiv\.org/(?:abs|pdf|src)/([\w.-]+/\d{7}(?:v\d+)?)',
        r'arXiv[:\s]+(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arXiv[:\s]+([\w.-]+/\d{7}(?:v\d+)?)',
    ]
    ids = set()
    for pattern in patterns:
        ids.update(re.findall(pattern, text, re.IGNORECASE))
    return sorted(ids)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Fetch LaTeX source and PDF from arXiv"
    )
    parser.add_argument(
        "ids",
        nargs="+",
        help="arXiv ID(s) or URL(s). Can also be a path to a .bib or .tex file.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=3.0,
        help="Delay between requests in seconds (default: 3)",
    )
    parser.add_argument(
        "--from-file", "-f",
        action="store_true",
        help="Treat arguments as file paths and extract arXiv IDs from them",
    )
    args = parser.parse_args()

    # If --from-file, read files and extract IDs
    if args.from_file:
        all_ids = []
        for filepath in args.ids:
            text = Path(filepath).read_text(errors="replace")
            found = extract_arxiv_ids_from_text(text)
            print(f"Found {len(found)} arXiv IDs in {filepath}: {found}")
            all_ids.extend(found)
        if not all_ids:
            print("No arXiv IDs found in the provided files.")
            sys.exit(1)
        ids = sorted(set(all_ids))
    else:
        ids = args.ids

    if len(ids) == 1:
        result = fetch_arxiv_paper(ids[0], output_dir=args.output_dir, delay=args.delay)
    else:
        results = fetch_multiple(ids, output_dir=args.output_dir, delay=args.delay)
        # Summary
        print(f"\n{'='*60}")
        print(f"Summary: {len(results)} papers")
        for r in results:
            status = "✓" if r.get("source_available") else "✗ (no source)"
            if "error" in r:
                status = f"✗ ERROR: {r['error']}"
            print(f"  {r['arxiv_id']}: {status}")


if __name__ == "__main__":
    main()
