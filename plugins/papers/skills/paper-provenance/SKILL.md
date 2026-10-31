---
name: paper-provenance
description: "Keep a record tying each number and fact in a paper to the calculation, file or citation behind it, and check the manuscript against that record. Use whenever writing or editing results, tables, abstracts or any paper text that states numbers or facts, and before a paper is shared or submitted. Triggers include: 'where did this number come from', 'check the numbers in the paper', 'trace every number', 'is every figure sourced', 'provenance', 'are the numbers in the draft right', 'prepare for submission'. Works on .tex and .md manuscripts. Boundaries: whether a cited source supports a claim is claim-fact-checker; whether a reference exists is reference-verifier."
---

# Paper provenance

A reader, or you next month, should be able to take any number or fact in the paper and follow it
to where it came from. The record is `paper/provenance.tsv`. A script fails if a number has no
record, or if its calculation no longer gives what the paper prints.

## The record

Tab-separated, with this header. No quoting: a cell cannot contain a tab.

```
text	value	kind	source
```

| Column | Meaning |
|---|---|
| `text` | Words copied exactly from the manuscript that contain the number or state the fact. LaTeX stays as written (`87.79\%`). Copy enough to identify this occurrence; the sentence fragment, not the number alone. |
| `value` | The number as printed. Empty for a fact with no number. `*` for every number in the text, or in the whole table when the text is inside one. |
| `kind` | `calculation`, `file`, `citation` or `exempt`. |
| `source` | Depends on the kind, below. |

- `calculation`: a command, run from the project root, that prints the number in the units printed
  in the paper, and that names a project file (`python3 scripts/stats.py mean-ours`). It must
  recompute from stored results rather than print a saved value. The number is compared at the
  printed precision.
- `file`: a path relative to the project root that holds the value. Use it for a value stated
  directly in a results or data file, and for whole tables with `*`, where every cell is checked
  against the file.
- `citation`: the citation key, optionally followed by a colon and where in the paper
  (`he2016: section 4.2`). Use it for facts and for numbers taken from other papers.
- `exempt`: the reason in words, for numbers that are not results, such as `stride of 2` with
  `architecture setting chosen by us`. Do not use it for results.

```
Our method reached 87.79\% accuracy	87.79\%	calculation	python3 scripts/stats.py mean-ours
The gap is 3.51 points	3.51	calculation	python3 scripts/stats.py gap
Scores by method	*	file	results/run-2/table1.csv
worse than that of their 110-layer network		citation	he2016: section 4.2
```

## While writing

Add the row in the same edit as the sentence. Write the number from the calculation, then record
that calculation; never copy a number from the conversation. Generate a table with a script where
you can, and record the table with one `*` row. A number with no route goes back to the author
rather than into the record: leave it out or mark it in the text for them.

Facts have no digits for a script to find. Give every factual sentence that is not common knowledge
in the field a citation in the text and a `citation` row, and check the sentence against the
cited paper's text (not its abstract) before recording it.

## Before sharing or submitting

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_provenance.py" paper/main.tex --ledger paper/provenance.tsv --root . --bib paper/refs.bib
```

The commands in the record run with the shell, so read a record you did not write before running
it, or pass `--no-run` to check everything else. Exit code 0 means every digit-written number has a
record and every record holds. On failure, fix the paper or the calculation. Never edit a number to
make the check pass without finding out which side is wrong, and never add an `exempt` row for a
result.

Then:

1. `--sentences` lists sentences with no citation and no record. Read them and decide which state
   facts that need a source.
2. Warnings list number words ("five seeds"). Record those that are results.
3. Run `papers:reference-verifier` for the references, and `papers:claim-fact-checker` on the claims
   that matter most.

## Limits

Say these when reporting a pass.

- It scans digit-written numbers in prose, tables, captions, footnotes, inline maths, `\input` files
  and macro definitions. It does not scan display equations, code, comments or front matter, so a
  result stated only there needs a row added by hand.
- It checks that a calculation gives the printed number and names a project file. It cannot show
  that the command uses that file properly, or that the analysis is right.
- For a citation it checks the key, and that the manuscript cites it. Whether the source supports
  the sentence is a judgement: `claim-fact-checker` tests it.
- It refuses records reading `_ARCHIVE`, and calculations on a `results/<run>` with no `MANIFEST.txt`.
