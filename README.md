# Co-Scientist toolkit

Claude Code plugins and working guidance from the Shocklab at the University of Cape Town, for
researchers who use Claude in their work. They come out of daily use on our own research.

- `papers` (plugin): turns papers into text Claude can read well, checks references, and keeps the
  full text of subscription papers out of the conversation.
- `meetings` (plugin), with `tools/meeting` and `apps/nextup`: records and transcribes calls, and
  transcribes any other recording, on your own Mac.
- `audio` (plugin): speech from text, and papers read aloud, on your own Mac.
- `research` (plugin): assessing whether an idea is worth pursuing, checking whether revisions
  are converging, working through hard problems with five gates, making decision pages, and using
  Mathematica.
- `documents` (plugin): slide decks, typeset PDFs, single-file HTML documents, courses bound
  as books, and narrated explainer videos.
- `guidance/`: a starter `CLAUDE.md` with the working rules we have found most useful, a template
  for reproducible analysis projects, a guide to git for researchers, and templates for a project's
  handoff and facts registry.

## Reading papers

The `papers` plugin turns a paper into text on your machine, and Claude reads the text:

1. A paper on arXiv: `arxiv-fetcher` downloads the authors' LaTeX source.
2. Any other PDF: `academic-pdf-to-mkd` converts it to Markdown, with the maths as LaTeX and the
   figures and tables as separate files. It picks an engine for each paper. The maths engine,
   MinerU, took just under three minutes for a 12-page paper on an Apple M5 Max, and needs a
   one-time 4.5 GB model download.
3. Claude reads the Markdown a section at a time, searches it with `grep`, and can come back to it
   in a later session without converting it again.

`library-search` indexes the converted Markdown and the arXiv source under the folders you name, a
passage at a time, so Claude can find which of your papers discusses something and go to the lines.
It uses SQLite's full-text search and needs only Python. A paper the licence check refuses is
indexed by its title and identifiers, never its text.

`reference-verifier` checks a bibliography against Crossref, OpenAlex, Semantic Scholar and arXiv.
It accepts a `.bib` or `.tex` file, or a PDF or Word manuscript's reference list, which Claude first
copies into a `.bib`. It reports references it cannot find and details that disagree with the
record. `paper-review` reviews a draft with six agents in parallel, one each for theory,
experiments, writing, positioning, internal consistency and the strongest objection to the main
claim. It reconciles
their reviews and applies changes with your approval at each round. `claim-fact-checker` checks
each factual claim in a report against its sources, with one agent checking the claim and a second
checking the source's quality. `paper-provenance` keeps a record tying each number and fact in a paper to the calculation, file or
citation behind it, and a script fails if a number has no record or its calculation no longer gives
what the paper prints. `zotero-import` imports a folder of downloaded papers into a Zotero
collection with real metadata. It reads each PDF on your machine, looks it up by DOI, arXiv ID or
title, and skips papers already in your library. Claude receives a report to review, without the
papers themselves.

### Licences

A university subscription is a licence to read. Whether it also permits sending a paper's full text
to an AI company depends on agreements most readers never see. Elsevier's
[FAQ on the commercial use of its content with generative AI](https://elsevier.support/dataasaservice/news/faqs-on-the-commercial-use-of-elsevier-content-with-generative-ai)
says its legal agreements "do not permit its content and products to be processed through
public AI tools", giving public chat assistants as the example. The `papers` plugin keeps the full
text of subscription papers out of Claude and any other AI service, whoever's licence gave access.
Use an open copy, or work from the title, abstract and short quotes.

A hook applies the rule. Before Claude reads a PDF, or the Markdown converted from one, it
identifies the paper from its DOI or arXiv ID, looks up its licence, and refuses subscription copies
and manuscripts under review. Open-access papers and arXiv preprints go through with a short note
of what their licence permits, and publishers' article pages fetched from the web are checked too.
Its [README](plugins/papers/tools/license-check/README.md) sets out what it
checks. It is not legal advice.

## Recording and transcribing

`tools/meeting` records a call on your Mac. OBS records your microphone and the call's audio on
separate tracks, Whisper transcribes each track, and pyannote works out who on the other side said
what. Nothing is uploaded, pyannote's usage metrics are switched off, and the audio is moved to the
Bin once its transcript has passed its checks and 30 days have gone by. The `meetings` plugin
teaches Claude to use it, and tells Claude never to start a recording you did not ask for and never
to read a transcript marked private. `apps/nextup` is a menu bar app that shows your next meeting
from macOS Calendar, with buttons to join it and to record it.

Transcription runs OpenAI's Whisper large-v3 model locally: whisper.cpp runs it on the Mac's GPU
from a model file on disk, with a voice-activity filter so that silence is skipped. No audio leaves
the machine, so it suits interview recordings whose ethics approval rules out third-party services.
On our Apple M5 Max, a 57-minute call took 5.4 minutes to transcribe and label: Whisper took 135 and
114 seconds for the two tracks, and pyannote 77 seconds. Names and jargon passed to Whisper as a
prompt (`--vocab`) fix most misspelt technical terms. The `transcribe-audio` skill uses the same
model for any other recording, such as an interview, a lecture or a voice memo.

Tell everyone on a call that you are recording it, and get their agreement first.

## Speech from text

For speech from text we use [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), an
82-million-parameter model under Apache-2.0. It runs on the Mac's GPU through
[mlx-audio](https://github.com/Blaizzy/mlx-audio) and has American and British English voices.
A command takes a few seconds, mostly to load the model. A batch of phrases in one command takes
little longer than one phrase. No text or audio leaves the machine. Each run asks Hugging Face
whether the model has changed, sending the model's name and your IP address. The licence permits
including the audio in an app. Our
[pdf2audio](https://github.com/jonstraveladventures/pdf2audio) repository packages it as two
commands, and the `audio` plugin teaches Claude to use them:

- `text-to-audio` turns short text into an audio file with `tts`: voice prompts and sounds for an
  app, narration, sample lines to compare voices.
- `paper-to-audio` narrates a paper to an MP3 with `pdf2audio`, and explains each displayed
  equation in words with a local model through [Ollama](https://ollama.com). The narration runs
  on your machine, and Claude does not read the paper.

## Research practice

The `research` plugin holds the working habits we use on our own projects:

- `pre-register` decides whether an idea is worth the time or compute before any goes into it,
  and records predictions before the first pilot.
- `convergence-check` looks at a run of revisions (a paper, an experiment, an abstract) and says
  whether it is converging or going round in circles.
- `fable-mode` takes a hard problem through five gates (scope, evidence, attack, verify, report),
  so that a smaller model works with the discipline of a larger one.
- `decision-page` puts three or more decisions on a private page in your Claude account. Each
  decision has a card with Claude's recommendation, the detail you need to answer, the alternatives
  and a comment box. Your ticks and comments are saved to the page for Claude to read back.
- `mathematica` runs Mathematica through `wolframscript` for exact symbolic work and
  high-precision numerics, decides when it beats Python, and writes notebooks.

## Documents

The `documents` plugin makes finished documents from notes and Markdown:

- `polished-docs-and-decks` builds slide decks (`.pptx`) and typeset PDFs, and renders each page
  to an image so that Claude checks the layout before handing it over.
- `single-html-document` builds a self-contained HTML document (a briefing, an explainer, a
  dashboard, a review workbook) that opens in any browser with nothing else installed.
- `course-to-pdf` binds a course or documentation website into one printable PDF, set for print
  rather than the screen.
- `explainer-video` makes a short narrated animation of an idea, derivation or result, in the
  style of 3Blue1Brown: Manim draws it, Kokoro speaks the narration on your Mac, and Claude checks
  that the sound is complete and that no label sits on a line before handing it over.

## Install

To have Claude guide you through installation, start Claude Code in any folder and paste:

> Run curl -fsSL https://raw.githubusercontent.com/shocklab/co-scientist-toolkit/main/SETUP.md to read the setup guide, then take me through it.

Claude asks what you work on and installs only the tools you want. To install by hand, enter these
commands in Claude Code:

```
/plugin marketplace add shocklab/co-scientist-toolkit
/plugin install papers@co-scientist-toolkit
/plugin install meetings@co-scientist-toolkit
/plugin install audio@co-scientist-toolkit
/plugin install research@co-scientist-toolkit
/plugin install documents@co-scientist-toolkit
```

The `papers` plugin needs `python3`, `curl` and poppler (`brew install poppler`). Claude Code also
needs poppler for long PDFs. Installing `jq`, a tool for reading JSON, makes the hook start faster.
`academic-pdf-to-mkd` and `reference-verifier` also need [uv](https://docs.astral.sh/uv/).
On first use, Claude installs the converter's Python environment into the plugin's data folder,
and the default engine downloads about 0.5 GB of models. uv fetches the reference checker's
libraries itself. To read a Word manuscript's reference list, the checker uses pandoc, or the
built-in `textutil` on a Mac without pandoc. `zotero-import` needs the Zotero 7 (or later) desktop
app on the same computer. It also needs PyMuPDF, which the skill installs into the plugin's data
folder. `paper-review` uses your LaTeX installation, if you have one, to rebuild a revised paper.
If you have connected alphaXiv's tools, it uses them to read arXiv papers the draft cites.

The `meetings` plugin holds only the skills. Install the `meeting` command from a clone of this
repository first, following [tools/meeting/README.md](tools/meeting/README.md), and NextUp from
[apps/nextup/README.md](apps/nextup/README.md).

The `audio` plugin needs the `tts` and `pdf2audio` commands from
[pdf2audio](https://github.com/jonstraveladventures/pdf2audio). Install them with
`brew install uv ffmpeg` and
`uv tool install --python 3.12 git+https://github.com/jonstraveladventures/pdf2audio`.
If `~/.local/bin` is not on PATH, run `uv tool update-shell` to add it. Explaining a paper's
equations also needs [Ollama](https://ollama.com) with `qwen3.5:35b-a3b` (about 23 GB).

In the `research` plugin, `mathematica` needs Mathematica or the Wolfram Engine with
`wolframscript`. The other four skills, `pre-register`, `convergence-check`, `fable-mode` and
`decision-page`, need nothing. For decks and PDFs, the `documents` plugin needs pandoc, XeLaTeX,
LibreOffice, poppler (`brew install poppler`, for `pdftoppm` and `pdftotext`) and the Python
packages `python-pptx` and `matplotlib`. Single-file HTML needs Node.js 20.19 or later (or 22.12 or
later). Courses need Chrome or Chromium. Explainer videos need Manim
(`uv tool install --python 3.12 manim`), ffmpeg, LaTeX and the `tts` command from pdf2audio.
MacTeX includes every package the PDF header and Manim's equations load.
For BasicTeX, `polished-docs-and-decks` gives the `tlmgr` command to install the missing packages.

The tools are written for macOS on Apple silicon. The meeting tool and NextUp run only on a Mac.

## Privacy

[PRIVACY.md](PRIVACY.md) lists what each tool sends, and where. Anything Claude reads goes to
Anthropic as part of the conversation, so the tools here are built to keep files on your machine
until you decide otherwise.

## Guidance

- [guidance/CLAUDE-starter.md](guidance/CLAUDE-starter.md): working rules to copy into your own
  `~/.claude/CLAUDE.md`. They cover checking results, reporting what was and was not verified,
  putting decisions to you, writing, handing work between sessions, assigning work to subagents,
  and avoiding shell traps.
- [guidance/paper-CLAUDE.md](guidance/paper-CLAUDE.md): a `CLAUDE.md` for a paper or analysis
  repository, with an immutable `source-material/` folder, a decision log, results manifests, and
  every figure tied to the results and commit it came from.
- [guidance/git-for-research.md](guidance/git-for-research.md): what git and GitHub are, what they
  provide for a research project, and how to use them through Claude without learning the commands.
- [guidance/handoff-CURRENT.md](guidance/handoff-CURRENT.md) and
  [guidance/facts-registry.md](guidance/facts-registry.md): templates for a project's living handoff,
  which a new session reads first, and a register of settled facts with a source for each fact.

## Licence

Code is under the [MIT licence](LICENSE) and text under [CC BY 4.0](LICENSE-docs).
`academic-pdf-to-mkd`, `claim-fact-checker`, `single-html-document` and the templates in
`paper-review` are adapted from Dominik Lukeš's
[agent skills](https://github.com/techczech/dominiks-agent-skills) (MIT).
`single-html-document` includes icons from [Lucide](https://lucide.dev) (ISC) and the Feather
icons they derive from (MIT). Its patterns follow the examples in
[html-effectiveness](https://github.com/ThariqS/html-effectiveness) (Copyright 2026 Anthropic PBC,
Apache License 2.0).
