# Setting up the Co-Scientist toolkit

Start Claude Code in any folder and paste:

> Run curl -fsSL https://raw.githubusercontent.com/shocklab/co-scientist-toolkit/main/SETUP.md to read the setup guide, then take me through it.

Claude will ask about your work, install only the tools you choose, and explain each step.
The rest of this file is instructions for Claude.

---

You are helping a researcher set up this toolkit. They may never have used a terminal, git or a
package manager. Follow the steps in order and keep to these rules throughout:

- Ask one or two questions at a time, and wait for the answer.
- Before each command, explain what it does in one plain line. Explain any unfamiliar term
  the first time you use it.
- Check what is already installed before installing anything. Skip what is there.
- Before any download, say what it is and roughly how large it is, and ask for permission.
- Leave every sign-in, password and macOS permission dialog to the user. Tell them what to click
  or type, and wait until they say it is done. Never ask for a password or token in the
  conversation.
- Never overwrite a file the user already has. Add to it, and show them what you added.
- Keep a list of what was installed, what was skipped and what the user still has to do.
  Report this in step 8.

## 1. Check the computer

Run `sw_vers`, `uname -m`, and `command -v brew git python3 uv`. Tell the user what you found
in a sentence or two.

The toolkit is written for macOS on Apple silicon, where `uname -m` prints `arm64`.
On any other computer, explain this and stop unless the user wants to continue.
The meeting tool needs macOS 15 or later.

If Homebrew is missing, explain that it is a free tool from brew.sh for installing software
on a Mac. Most of the steps below use it. Its installation asks for the Mac's password,
so tell the user to run the command from brew.sh themselves in the Terminal app.
Wait until `brew --version` works before continuing.

## 2. Git and GitHub

Ask: "Do you use git and GitHub already?"

- If they do, check `git --version` and `gh auth status`, then continue.
- If they have heard of them but do not use them, or have not heard of them, explain them
  in a few sentences using `guidance/git-for-research.md`. Git records the versions of a
  project folder that you choose to save, so you can restore an earlier version. GitHub
  is a website that holds a copy of that record for backup and sharing. With Claude Code,
  you can ask in ordinary words without learning the commands. Ask whether they want to
  set it up now. If they do, follow the guide's "Setting up, once" section.
  `xcode-select --install` opens a macOS dialog, and `gh auth login` opens a browser
  sign-in. The user must complete both.

If git is installed, ask where the user wants to keep a copy of this repository.
Suggest `~/co-scientist-toolkit`, then clone it in the chosen location with
`git clone https://github.com/shocklab/co-scientist-toolkit.git`.
Read the guidance files from that copy. Without git, read them from
`https://raw.githubusercontent.com/shocklab/co-scientist-toolkit/main/<path>`.

The meeting tool needs this copy. The commands it installs run from that location,
so the copy must stay there.

## 3. Add the toolkit to Claude Code

Run `claude plugin marketplace add shocklab/co-scientist-toolkit`.
This tells Claude Code where to find the toolkit's plugins. It installs nothing yet.

## 4. Choose the tools

Ask about the user's work one area at a time. Use the README to explain what each tool
does and what it needs. Install each chosen plugin with
`claude plugin install <plugin>@co-scientist-toolkit`.
Installing a plugin installs all of its skills. The questions below decide only which extra
software to install. In your report, list every skill in each installed plugin as installed,
and say which skills still need extra software before they work.
Then install only the software needed by the skills the user chooses from that plugin.

Papers. Ask: "Do you read or write papers with Claude?" If yes, install `papers`.
Explain that it includes an automatic check before Claude reads a PDF. The check looks up
the paper's licence and refuses the full text of subscription papers and manuscripts
under review.

The check needs `python3` from Apple's command-line tools (`xcode-select --install`)
and poppler (`brew install poppler`). jq (`brew install jq`) makes the check start faster.

Then ask these questions one at a time:

- "Do you want Claude to check the references in your papers against the publication databases?"
  This uses `reference-verifier`, which needs uv (`brew install uv`). pandoc reads Word
  manuscripts; macOS's built-in `textutil` can read them without pandoc.
- "Do you want PDFs converted to text, with the maths as LaTeX, on your own computer?"
  This uses `academic-pdf-to-mkd`, which needs uv. The first use downloads about 0.5 GB
  of models. The maths engine, MinerU, downloads 4.5 GB more.
- "Do you use Zotero?" `zotero-import` needs the Zotero 7 or later desktop app.

`arxiv-fetcher`, `library-search`, `paper-provenance`, `paper-review` and `claim-fact-checker` need
nothing more.
`paper-review` uses LaTeX if it is installed.

Meetings and interviews. Ask: "Do you record calls, or transcribe interviews or lectures?"
If yes, install `meetings`. Follow `tools/meeting/README.md` in the copy from step 2,
one numbered step at a time. If there is no copy yet, set up git and clone the repository
first, as in step 2. The whisper model is 3.1 GB.

The user must create the Hugging Face account, sign in, accept the speaker model's terms
and complete the OBS permissions in System Settings. Read the README's consent section
to them: everyone on a call must be told it is recorded and agree before recording starts.

Then ask whether they want NextUp, the menu bar app that shows the next meeting with a
button to record it. If they do, build it using `apps/nextup/README.md`.

Audio. Ask: "Would you like papers read aloud, or speech made from text?"
If yes, install `audio`, then the two commands it uses, `tts` and `pdf2audio`:
`brew install uv ffmpeg`, then
`uv tool install --python 3.12 git+https://github.com/jonstraveladventures/pdf2audio`.
If `tts` is not found afterwards, run `uv tool update-shell` and open a new terminal.
Ask whether they want the equations in papers explained in words. If they do, install
Ollama (https://ollama.com) and run `ollama pull qwen3.5:35b-a3b` (about 23 GB).
Speech from text needs no Ollama.

Research practice. Use the README to explain each of the five skills in one line.
Ask whether the user wants to install `research`. Only `mathematica` needs additional
software: Mathematica or the Wolfram Engine with `wolframscript`.
If neither is installed, explain that the other four skills work without it.

Documents. Ask: "Do you make slide decks, typeset PDFs, HTML documents, or narrated
explainer videos?"
If yes, install `documents`. Decks and PDFs need pandoc, XeLaTeX, LibreOffice, poppler
(`brew install poppler`) and the Python packages `python-pptx` and `matplotlib`. XeLaTeX comes
from a TeX distribution: recommend MacTeX, a download of several gigabytes. A user who has
BasicTeX instead needs
`sudo tlmgr install sectsty mdframed enumitem newunicodechar zref needspace soul`,
which asks for the Mac's password, so the user runs it in the Terminal app.
Single-file HTML needs Node.js 20.19 or later (or 22.12 or later) and npm.
Binding a course website into a PDF needs Chrome or Chromium and poppler.
Explainer videos need Manim (`uv tool install --python 3.12 manim`), ffmpeg, a TeX distribution
and the `tts` command from pdf2audio (the Audio question above gives its install command). The
voice model is a download of under 400 MB on first use.
Install only what the chosen skills need.

After each installation, check that it worked using `--version` or the check given in
the tool's README. Explain what the result shows.

## 5. Working rules

Ask whether the user wants rules for Claude's research work: checking its own results, stating what it did and did not verify, putting decisions to the user, and handing work between sessions.

If yes, read `guidance/CLAUDE-starter.md` and the user's `~/.claude/CLAUDE.md` if it exists. Leave out any section that repeats a rule they already have. Offer the sections in three parts, without asking the user to choose among all seventeen.

### Core rules

For anyone. Explain each section's purpose in one line, then ask whether to add the set, leaving out any section the user wants to drop:

- Acting on corrections
- Questions are not change requests
- Doing the work
- Verifying work
- Writing
- Searching the web
- Files I mention
- Memory

### Rules based on earlier answers

Add these without a separate question. Name them when showing the user what was added:

- Papers and licences, and Research papers, if they installed `papers`.
- Decisions, if they installed `research`, which contains the `decision-page` skill.
- Git and Projects, if they use git or set it up in step 2.

### Rules for heavier use

Ask: "Do you run long analyses, or work on one project across many sessions?"

If yes, add Shell commands, Subagents, Reasoning effort and Long sessions.

Append the chosen sections to `~/.claude/CLAUDE.md` under the heading `# From the Co-Scientist toolkit`, so the user can find them later. Create the file if needed. Never overwrite its existing contents. Show the user what you added and tell them they can edit or remove any of it.

## 6. A project to start with

Ask whether the user has a research project they would like to set up now.
If they do, offer the templates in `guidance/`:

- `paper-CLAUDE.md` for a paper or analysis project.
- `handoff-CURRENT.md` for the handoff a new session reads first.
- `facts-registry.md` for the project's settled facts.

Copy the templates they choose into the project folder as `CLAUDE.md`,
`handoffs/CURRENT.md` and `facts-registry.md`, respectively.
If they set up git, offer to make the folder a repository and use a `.gitignore`
to keep data and outputs out of it.

## 7. Start a new session

Plugins load when Claude Code starts. Ask the user to start a new session and ask Claude
there to list the skills it has from the toolkit.
`claude plugin list` shows what is installed.

## 8. Report

Give the user the list you kept: what was installed, what was skipped and what they still
need to do themselves, such as a sign-in or a permission in System Settings.
Point them to `PRIVACY.md` for what each tool sends and where it sends it.
