---
name: library-search
description: "Search across the user's own papers on this machine: the Markdown that academic-pdf-to-mkd writes and the LaTeX that arxiv-fetcher downloads, indexed passage by passage with SQLite full-text search. Use when the user wants to find where a result, method, definition or phrase appears in their papers, asks which of their papers discusses something, wants a passage they half-remember, or wants a folder of converted papers made searchable. Triggers include: 'search my papers', 'which paper said', 'find where I read about', 'search the library', 'index these papers', 'is there anything in my papers on'. Refused papers (subscription papers and manuscripts under review, by the licence check's records) are found by title only, never by their text."
---

# Library search

Finds passages across a library of papers already on this machine. It indexes `*-fulltext.md`
files from academic-pdf-to-mkd and `*.tex` files from arxiv-fetcher under the folders the user
names, splits them into passages of about a paragraph, and ranks passages with SQLite's full-text
index (BM25 with English stemming). It needs only Python 3, and nothing leaves the machine.

## Commands

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/library_search.py" index ~/papers ~/project/papers
python3 "${CLAUDE_SKILL_DIR}/scripts/library_search.py" search "renormalisation group flow of the coupling"
python3 "${CLAUDE_SKILL_DIR}/scripts/library_search.py" status
python3 "${CLAUDE_SKILL_DIR}/scripts/library_search.py" forget ~/project/papers
```

- `index ROOT...` adds the folders to the library and indexes them; `index` with no folder
  updates every folder already added. Only new or changed files are read again, so run it before
  a search session or after converting or fetching papers.
- `search "QUERY" [-k N] [--json]` returns the best passages, at most two per paper, each with its
  file, line range and section heading.
- The index lives at `~/.local/state/library-search/library.sqlite`; `--db FILE` (before the
  command) uses another, for example one per project.

Always run the script by the `${CLAUDE_SKILL_DIR}` path above, written out in full in each
command (not through a shell variable, which the hook cannot see through), and run each command on
its own rather than chaining it with others. The licence hook lets this copy run over folders that
hold refused papers, because the script applies the licence records itself; it refuses the same
command run through a variable or through a copy of the script anywhere else.

## Searching well

The ranking matches words, with stemming (`scattering` finds `scatter`), so a query works best in
the vocabulary a paper would use. When a first search misses, try again with the field's terms or
a likely phrase from the paper rather than a description of the idea, and try two or three
wordings before saying the library has nothing on it. A miss means no passage matched those
words in the indexed folders; say which folders were searched.

Each hit gives `file:line_start-line_end`. Read those lines from the file before quoting or
relying on a passage: the snippet in the search output is cut at 500 characters.

## Refused papers

A folder whose `license.json` refuses its paper (a subscription paper or a manuscript under
review, with no allow recorded) is indexed by its title and identifiers only, and its text is
never read. A search that matches its title returns it with the note "its licence record refuses
its text here: title and identifiers only", and no file or lines. Tell the user the paper is in
their library and that its text is not available here; do not try to read the file another way.

The records are read again at every search. After the user allows a paper with
`license-check allow`, the next `index` adds its text; after `license-check revoke`, its text is
hidden at once and removed from the index file at the next `index`.

## What it reads

- `*-fulltext.md` and `fulltext.md` (academic-pdf-to-mkd), after the front matter.
- `*.tex` (arxiv-fetcher), between `\begin{document}` and `\end{document}`, without comments.
- Folders named `figures`, `tables`, `pages`, `media` and hidden folders are skipped.
