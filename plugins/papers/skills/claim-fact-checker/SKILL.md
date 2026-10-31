---
name: claim-fact-checker
description: >-
  Fan-out fact-checking workflow that checks the claims its extractor lists in a deliverable against
  archived sources, with one isolated verifier subagent per claim plus a source-quality skeptic, and
  writes a findings + fix-plan pair. Use this whenever the user wants to fact-check, claims-audit,
  source-check, or verify a document or an academic paper review against its sources before committing
  or publishing. Trigger on phrases like "fact-check this report", "verify the claims", "audit the
  sources", "check this review against the paper", or when finishing a report or paper review that
  has a folder of sources. Built on Claude Code dynamic workflows, so it stays accurate on long
  deliverables where a single context window tends to degrade.
---

# Claim fact-checker

## What this is and why it exists

A factual claim in a document or paper review needs a real source that supports it. When one agent checks a 50-claim document in one context window, its judgements tend to become less reliable: it tires, trusts its earlier judgements and often stops before checking the whole list.

An extractor lists the claims. A verifier subagent checks exactly one claim in a clean context, and a source-quality skeptic re-checks its cited source. No single context contains the whole job. The workflow checks only the claims the extractor lists, so any claim it misses remains unchecked.

The skill produces a findings file and a fix-plan file without editing the document or review. Apply the plan separately, yourself or through a fixer agent, to keep the audit trail independent of the author.

## When NOT to use (hand off)

- To check whether citations exist, DOIs resolve or metadata is correct, use `papers:reference-verifier`. This skill checks whether a source's content supports a claim, not whether the source exists.
- If sources still need to be gathered from the web, do that research first. This skill checks an existing document or review against archived sources and does no open web research.
- To critique a paper draft, use `papers:paper-review`. Its claims-audit template can refer the per-claim checks to this skill, which checks an already-written report or review.

## Presets

| Preset | Deliverable | Sources verified against |
|---|---|---|
| `paper-review` | a review of one paper, named by the user | that paper's output from `papers:academic-pdf-to-mkd` (`{paper_id}-fulltext.md`, `figures/`, `tables/`), plus the `source/` folder from `papers:arxiv-fetcher` if it fetched the paper |
| `document` | any document the user names | a folder of sources the user names |

Presets are stored in `${CLAUDE_SKILL_DIR}/presets/<name>.json`. They set the source-quality strictness (`primaryRule`), domain context, source patterns and output names. Neither preset assumes a folder layout for the document or review. If the user has not named its location, ask.

## How to run it

Resolve paths inline first, as the workflow has no filesystem access. Then pass the resolved lists to the `Workflow` tool.

1. Choose the preset and read `${CLAUDE_SKILL_DIR}/presets/<name>.json`.
2. Resolve the paths. Ask for the target file(s) if none were given, and for the sources folder. For `paper-review`, use the folder written by `papers:academic-pdf-to-mkd`; for `document`, use the folder the user names. Expand the preset's `sourcesGlob` into absolute file lists. If there are no archived sources, tell the user that the run will mark every claim unsourced. That is itself a finding.
3. Tell the user the cost and wait for a go-ahead. Read the target(s) and report the extracted claim count, or estimate it from the text if extraction has not run. Count two agents per claim (verifier and skeptic), one extractor per target file and one synthesis agent. For example, 40 claims in one file requires 82 agents. Do not launch until the user says to go ahead in chat.
4. Read `${CLAUDE_SKILL_DIR}/workflows/fact-check.workflow.js` and run it by passing its whole text inline: `Workflow({ script: "<the file's text>", args })`. Do not use `scriptPath`, which is refused for a file outside the working directory. `args` is:

   ```json
   {
     "label": "paper-review: smith-2023 review",
     "domain": "paper-review",
     "targets": ["/abs/path/smith-2023-review.md"],
     "sources": ["/abs/path/smith-2023-fulltext.md", "/abs/path/tables/smith-2023-table-01.md"],
     "primaryRule": "moderate",
     "guidance": "<the preset's guidance string>",
     "verdictsPath": "<absolute path of ${CLAUDE_SKILL_DIR}/references/verdicts.md>"
   }
   ```

   Pass `args` as a JSON object, not a stringified one. `verdictsPath` is required and must be
   absolute: the subagents read the verdict rubric from that path and cannot resolve a path
   relative to the skill. Resolve `${CLAUDE_SKILL_DIR}` to its actual value before passing it.
   Set `domain` to `paper-review` or `document`, and `primaryRule` to `strict`, `moderate` or
   `quote-verbatim`.
5. Write the outputs. The workflow returns `{ summary, counts, flaggedCount, factcheckMd, fixplanMd }` without writing files, so the run never depends on a subagent's write permissions. Write `factcheckMd` and `fixplanMd` beside the document or review, using the preset's `outputNames` and a `YYYYMMDD-HHMMSS` timestamp for `{ts}`.
6. Report the summary and flagged count, and offer to apply the fix-plan.

## Token cost

Each claim requires two subagents (verifier and skeptic), so a 40-claim report needs about 80 subagent calls. This cost suits a pre-publication audit of a high-value document or review, but not a quick sanity check. Reduce it by passing only the review, item or section you changed. For a handful of claims, checking the text against its sources yourself is cheaper.

## Verdicts

Read `${CLAUDE_SKILL_DIR}/references/verdicts.md` for the verdicts (verified, verified-secondary, unsourced, contradicted, misattributed, quote-mismatch, prescription-detected) and source tiers. Judge the meaning of each claim against its source. Keyword matches alone do not establish a verdict.
