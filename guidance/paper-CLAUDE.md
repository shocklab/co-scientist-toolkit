<!--
Template for a reproducible paper or analysis project in Claude Code.
Copy this file into the project as `CLAUDE.md`, fill in the {{PLACEHOLDERS}}, and delete this
comment. Adapted from Dominik Lukeš's agents-for-reproducibility course.
-->

# {{PAPER SHORT TITLE}}: working context

{{One line on what this paper is about and its current stage.}}
Read this file and `notes/decision-log.md` before doing anything else.

## Where things live

- `source-material/`: papers, datasets and other inputs this work depends on. Never edit. Convert
  PDFs into Markdown here with `academic-pdf-to-mkd`, or fetch arXiv source with `arxiv-fetcher`.
- `data/raw/`: raw data exactly as received. Never edit. Derived data goes in `data/processed/`,
  made by a script.
- `scripts/`: every transformation, analysis and figure generator. Outputs are never edited by
  hand.
- `outputs/` and `figures/`: generated files only. Each figure is made by a script that takes an
  explicit input path and writes a sidecar (`figures/<name>.source.txt`) naming the results folder
  and the commit it came from.
- `results/<run>/`: each run folder holds a `MANIFEST.txt` written by the job itself, recording its
  inputs, code commit, configuration, seeds, start and end times and exit status. Broken or
  superseded runs move to `_ARCHIVE/` with a `DO_NOT_USE.md`, out of reach of every figure script.
- `notes/`: working notes, literature notes and drafts. `notes/decision-log.md` records choices
  (format below).
- `CONTEXT.md`: a glossary of the project's terms. Update it when a term is defined or changes
  meaning.
- `paper/`: the manuscript, and `paper/provenance.tsv`, which ties each number and fact in it to the
  calculation, file or citation behind it (the `paper-provenance` skill sets out the format).

If this file holds anything you would not publish, keep it out of git by listing `CLAUDE.md` in your
global gitignore.

## Working rules

- Read the relevant files before proposing a change, and explain the change before making it.
- When summarising or citing, name the files you used.
- Record uncertainty instead of filling gaps by invention. Make no claim about a real person, study
  or institution without a source in `source-material/`.
- Never edit `source-material/` or `data/raw/`. To change an output, change the script and rerun.
- The conversation is not the archive: sources, scripts, outputs and decisions go on disk.
- Every number and fact written into the manuscript gets a row in `paper/provenance.tsv` in the same
  edit, and `scripts/` holds the calculation for each computed number. Run the `paper-provenance`
  check before saying a section is finished.
- Data that matters never lives only in `/tmp` or on scratch space without a backup.

## Evidence and tests

- Say which kind of evidence a result is: reproducibility, numerical convergence, statistical
  uncertainty, accuracy against a justified reference, or scientific validity. Agreement between
  methods that share data, assumptions or code does not verify the shared part; note in the
  decision log what each comparison tests.
- A run that finished is not a result. A zero exit code or a valid output file shows the code ran.
  A failed, missing or unresolved prerequisite check blocks every conclusion built on it. Scripts
  refuse bad input rather than pass it through; test that with negative controls, known cases and
  deliberately corrupted inputs.
- Before an expensive run, decide what to keep: inputs, code commit, configuration, seeds, logs,
  failures, and the intermediate outputs needed to check or extend the result. A summary metric
  alone is rarely enough.
- To repair a defective test, justify the repair from theory or the requirements, keep the original
  verdict on record, and validate the replacement on known cases, synthetic controls or preserved
  data. Log it as a retrospective reassessment, not fresh evidence. Never loosen a criterion to get
  a pass.
- Exploration may change the method, and its findings are labelled exploratory. Confirmatory
  predictions, comparisons and decision rules are fixed and written down before the results that
  test them are examined.

## Decision log (`notes/decision-log.md`)

`| Date | Decision | Reason | Evidence / files used |`: one row for each choice that matters (a
modelling assumption, a dropped dataset, a change of framing). Mark exploratory method changes,
departures from a fixed protocol, and test repairs as such in the Decision column.

## Skills

- A PDF or preprint: `academic-pdf-to-mkd`, or `arxiv-fetcher` for arXiv source.
- Critique the draft: `paper-review`.
- Check claims against sources: `claim-fact-checker`. Check that the references exist and match:
  `reference-verifier`. Trace each number and fact to its source: `paper-provenance`.

## Corrections

On a correction, say back the rule you think I am asserting, confirm it, then edit it at the
narrowest scope: this file for project rules, a skill's `SKILL.md` for that skill's behaviour,
`~/.claude/CLAUDE.md` for everything. Change the rule rather than adding notes.
