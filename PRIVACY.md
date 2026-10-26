# Privacy

What each part of this toolkit sends off your machine, and where. Everything not listed here stays
on your machine.

## Claude Code

Claude Code sends your prompts, Claude's replies, and everything Claude reads (file contents and
command output) to Anthropic. Reading a paper, a transcript or a data file sends its text. The tools
in this repository are built so that nothing reaches the conversation until you or Claude choose to
read it.

On Free, Pro and Max accounts, Anthropic trains future models on your conversations, including
Claude Code sessions, when the model-improvement setting is on. It keeps those conversations for
five years with the setting on, and for 30 days with it off. Check the setting at
[claude.ai/settings/data-privacy-controls](https://claude.ai/settings/data-privacy-controls).
On Team, Enterprise and API accounts, Anthropic does not train on your conversations and keeps
them for 30 days. Claude Code also stores a plain-text transcript of each session on your machine
in `~/.claude/projects/` for 30 days, controlled by `cleanupPeriodDays` in settings. Sessions
started or last continued in the Claude desktop app or Cowork are kept until you delete them,
unless you set `desktopSessionCleanupPeriodDays`. Claude Code sends usage metrics that exclude
your code, prompts and file paths. On Pro and Max, it also sends error reports. Set
`DISABLE_TELEMETRY=1` to turn off metrics and `DISABLE_ERROR_REPORTING=1` to turn off error reports.
Using `/feedback`, `/bug` or `/share` sends a whole session to Anthropic, which keeps it for five
years. Answering Yes when Claude Code asks whether Anthropic may look at a session's transcript
also sends the whole session, which Anthropic keeps for up to six months.
`DISABLE_FEEDBACK_COMMAND=1` turns off those commands.
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` stops the transcript question and turns off metrics
and error reports. These details are from Anthropic's
[data usage](https://code.claude.com/docs/en/data-usage) page. Check it for changes.

## This toolkit

| Part | What leaves your machine | Where it goes | When |
|---|---|---|---|
| Licence-check hook | A paper's DOI, arXiv ID or publisher item number, never its text | OpenAlex, Crossref, Semantic Scholar, arXiv | When Claude reads or converts a PDF whose licence has not been looked up in the last 30 days, fetches a publisher's page or opens an arXiv page; also when a prompt you type contains a DOI or an arXiv number |
| `arxiv-fetcher` | The arXiv ID | arxiv.org; for the licence lookup, OpenAlex, Crossref, Semantic Scholar | Each fetch |
| `academic-pdf-to-mkd` | Nothing about the paper. Model weights are downloaded on first use, and later runs may ask Hugging Face for updates, sending only the model's name; both engines convert papers with the network blocked | Hugging Face (about 0.5 GB; 4.5 GB more for the maths engine) | First use of each engine |
| `library-search` | Nothing. The index stays in `~/.local/state/library-search/` | | |
| `reference-verifier` | Each reference's DOI, arXiv ID, or title and authors. If you set `REFVERIFY_CONTACT_EMAIL`, your email also goes to all four services | Crossref, OpenAlex, Semantic Scholar, arXiv | Each run |
| `zotero-import` | Each PDF's DOI or arXiv ID. For a PDF with neither, up to 200 characters of its title, read from its first page or the PDF's own metadata. The rest of the text is never sent | Crossref, DataCite, OpenAlex, Semantic Scholar, arXiv | Each import |
| `paper-review`, `claim-fact-checker` | The draft and its sources go to Claude. Search queries are also sent. `paper-review` also requests open copies of the papers the draft cites | Anthropic; the web search Claude uses; arXiv and open-access sites; alphaXiv if you have connected it | Each run |
| `meeting` | Nothing. Model weights are downloaded once | Hugging Face (whisper about 3.1 GB, pyannote's speaker model once you accept its terms) | Setup |
| NextUp | Nothing. It reads macOS Calendar on your Mac | | |
| `text-to-audio`, `paper-to-audio` | No text, audio or paper is sent. Model weights are downloaded once. Each run asks Hugging Face whether the model has changed, sending the model's name and your IP address | Hugging Face (Kokoro, under 400 MB); PyPI and GitHub (the packages, and spaCy's English model); Ollama's library (the model that explains equations) | Setup; the Hugging Face check on each run |
| `pre-register` | Search queries about prior work on the idea | alphaXiv if you have connected it, otherwise the web search Claude uses | When it checks prior work |
| `decision-page` | The page's text and your ticks and comments on it | claude.ai, as an Artifact in your account, private to you unless you share it | Each page |
| `convergence-check` | Nothing | | |
| `fable-mode` | Search queries, if Claude looks something up | The web search Claude uses | When it looks something up |
| `mathematica` | Nothing from the toolkit. Wolfram's software checks its licence with Wolfram | Wolfram | As specified by Wolfram's licence |
| `polished-docs-and-decks` | Nothing | | |
| `single-html-document` | Nothing about your documents. Installing the Vite tools downloads packages from the npm registry | The npm registry | Setup |
| `explainer-video` | Nothing about the video. Kokoro's weights are downloaded once, and each narration run asks Hugging Face whether the model has changed, sending the model's name and your IP address | Hugging Face (Kokoro, under 400 MB); PyPI (Manim) | Setup; the Hugging Face check on each run |
| `course-to-pdf` | The MathJax script from cdn.jsdelivr.net when the pages contain maths and the site has no KaTeX; anything the site's own stylesheet loads from the web | cdn.jsdelivr.net; wherever the site's stylesheet points | Each run |

The licence-check hook and the `license-check` command store their records on your machine in
`~/.local/state/license-check`. These include a 30-day lookup cache of each paper's title,
journal, publisher and licence, never its text. They also store your prompts from the last two
hours, so that only words you typed can lift a refusal, and the papers you have allowed with the
words you quoted to allow them. Refusals and a log of the hook's and command's own errors are
stored there too. Old cache entries and prompts are dropped when new ones are written. The other
records stay until you delete them.

The meeting tool runs pyannote with `HF_HUB_OFFLINE=1` and usage metrics off
(`PYANNOTE_METRICS_ENABLED=false`), whatever your shell has set. pyannote 4 sends those metrics
to `otel.pyannote.ai` by default. Recordings and transcripts stay in `~/Recordings/Meetings/`.
Keep that folder out of iCloud, Dropbox and other synced folders. Audio is moved to the Bin
30 days after its transcript was made, provided the transcript has at least one line and passed
the checks listed in `tools/meeting/README.md`. The tool applies this rule each time a
transcription finishes and when you run `meeting prune`.

## Things to decide for yourself

- Whether to read a transcript or a dataset with Claude at all. Research data under an ethics
  protocol that forbids third-party processing should never be read in a Claude session.
- Whether the model-improvement setting should be on for the account you use for research.
- Whether recordings may be made: tell everyone on a call that you are recording it, and get their
  agreement first.
