# license-check

A Claude Code hook that works out what a paper's licence allows whenever one comes into a
session, tells Claude and you, and refuses the material no licence lets you send to an AI
service.

## The rule

A subscription paper's full text goes to no AI service, Claude included, whoever's licence gave
you access. Your library's licence lets you read the paper; it does not let you send the text to
a third party's servers, and some publishers (Elsevier, IOP Publishing, SAGE) say so outright.
Work from the title, abstract and short quotes, or from an open copy, which the hook looks for
and names.

## Verdicts

| Material | Verdict |
|---|---|
| A copy under a Creative Commons licence or in the public domain (from the file's own licence line, arXiv, or OpenAlex) | allowed, with a card |
| An arXiv paper under arXiv's default licence | allowed, with a card |
| A subscription paper: the publisher's copy with no open licence, from any publisher | refused; an open copy is offered |
| The Markdown, figures and tables extracted from a refused paper (a folder whose `license.json` records it) | refused |
| A manuscript under review (an Editorial Manager or ScholarOne cover, "Anonymous Author(s)", "do not distribute", or a folder named for refereeing or examining) with no DOI or arXiv number | refused |
| An author manuscript, a publisher's free-to-read copy with no licence (except from Elsevier, IOP and SAGE, whose terms cover all their content), a paper with no licence found | allowed, with a card |
| A PDF built from a source file beside it (`main.pdf` next to `main.tex`), or one with nothing that identifies a published paper | silent |

The card lists what that licence allows: reading and analysing, quoting, figures in talks,
sharing the file, adapting, commercial use, and sending the full text to another AI service.
You see a one-line notice. Publisher AI terms, with their sources and the date each was read, are
in `publishers.json`; an entry more than six months old is flagged in the card, and corrections
are welcome as pull requests.

## Where it runs

The papers plugin registers `hook.sh <event>` for these events:

- PreToolUse on Read, Grep and Bash refuses the classes listed under Verdicts. For Read, it checks
  PDFs and any file within three levels of a `license.json`. For Grep, it checks searches whose
  path is a PDF or is covered by a `license.json`. If the search has no path, it checks the working
  directory on the same basis. For Bash, it examines commands that mention a PDF or name a file,
  folder or glob within three levels of a `license.json` or holding one in a subfolder. It
  refuses a command that names a refused PDF or a file or folder covered by a `license.json`. Commands made only of file-handling programs such as `ls`,
  `mv`, `cp`, `rm` and `git`, and `license-check` itself, are passed. Before an identified PDF is
  read, the hook looks it up in OpenAlex. The first lookup takes up to ten seconds and is cached
  for 30 days.
- PreToolUse on WebFetch and the browser navigation tools refuses PDF links on a listed
  publisher's own site, including through a library's EZproxy, unless OpenAlex says the article
  is open.
- PostToolUse on the same tools: shows the card, once per paper per session. A browser page for a
  subscription paper gets a note to use only the title, abstract and metadata.
- UserPromptSubmit: keeps your prompt for two hours (for allows, below) and adds a one-line
  licence for up to five arXiv IDs or DOIs in it.

## Overriding a refusal

You may have a licence the hook cannot see. A refusal lifts only when you say so in the chat, and
Claude records it with

    license-check allow <path|folder|doi|arxiv-id|url> --quote '<your words>'

The command succeeds only if the quote appears in a prompt you typed in the last two hours. A
quote under four words ("yes", "go ahead") counts only if you typed it after a refusal of that
same paper, since a bare yes may be answering something else. Text in a file, a web page or tool
output therefore cannot lift a refusal. `license-check allows` lists what you have allowed and
`license-check revoke <target>` withdraws it.

## Command line

    license-check check <pdf|doi|arxiv-id|url> [--json] [--write FILE] [--rights] [--offline]
    license-check allow <target> --quote '<your words>'
    license-check allows
    license-check revoke <target>

`check` exits 3 when the material would be refused. `--write` saves the verdict as a
`license.json`, which `arxiv-fetcher` and `academic-pdf-to-mkd` put beside their output.

## What it sends and keeps

To identify a paper, the hook sends its DOI, arXiv ID or publisher item number, never its text,
to OpenAlex, Crossref, Semantic Scholar and arXiv. Everything else stays on your machine in
`~/.local/state/license-check`: a 30-day lookup cache, your prompts from the last two hours,
your allows, the refusals, and which cards each session has seen. The hook and the `license-check`
command use the same folder, including when `academic-pdf-to-mkd` runs the command.

## What it checks

- A PDF is identified from its DOI, its arXiv stamp, a publisher's mark or its licence line.
- A manuscript under review is recognised from the markers listed under Verdicts and from folder
  names for refereeing or examining; a paper already on arXiv is treated as the public preprint.
- When OpenAlex cannot be reached, a PDF from a listed publisher, or one whose own metadata carries
  a DOI, is refused until the lookup works, and a refusal made while OpenAlex is turning away
  requests is retried after ten minutes.
- The hook checks files extracted from a refused paper when Claude reads or searches them. It
  also checks Bash commands that name those files, their folders or a glob over them.
- Reading a PDF needs poppler (`brew install poppler` on a Mac), with `pdftotext` and `pdfinfo`
  on the PATH. If either is missing, the hook refuses the PDF with a message saying that it needs
  poppler to check it.
- On the web, a PDF link on a listed publisher's site is refused before it is fetched; any other
  page gets the card afterwards, and a browser page for a subscription paper gets the instruction
  to use only its title, abstract and metadata.
- Only words you typed can lift a refusal, so text in a file, a page or tool output cannot.

This is a reading of licence terms, not legal advice. Your institution's licences may allow more
or less than this hook assumes.
