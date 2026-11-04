---
name: explainer-video
description: "Make a short narrated explainer video (3Blue1Brown style) on the user's Mac: Manim animates, the tts command (Kokoro, local) narrates, and two checks catch dropped sound and labels sitting on lines before anyone sees it. Use whenever the user wants an idea, derivation, algorithm or result explained as a video or animation: for a course, a talk, a student, or to understand something themselves. Triggers: 'make an explainer video', '3b1b style', 'animate this derivation', 'Manim', 'a video explaining X', 'narrated animation', 'show this as a video', 'explainer on'. No API key needed. Boundaries: a static figure is matplotlib; slides are polished-docs-and-decks; audio alone is text-to-audio; a paper read aloud is paper-to-audio."
---

# Explainer video

A narrated Manim animation, made and checked on the user's Mac. Nothing about the video leaves
the machine, and the Kokoro voice is Apache-2.0, so the video can be shared or posted.

The worked example is `${CLAUDE_SKILL_DIR}/examples/zigzag/`: 46 seconds on why gradient
descent zig-zags in a narrow valley.

## Setup

Check with `command -v manim tts ffmpeg ffprobe latex dvisvgm`. What is missing:

- ffmpeg and uv: `brew install uv ffmpeg`
- Manim Community: `uv tool install --python 3.12 manim`
- `tts`, from pdf2audio (AGPL-3.0; the voice it makes is Apache-2.0):
  `uv tool install --python 3.12 git+https://github.com/jonstraveladventures/pdf2audio`.
  Its first run downloads the Kokoro model from Hugging Face (under 400 MB).
- LaTeX, for equations (`MathTex`): MacTeX includes everything Manim uses. With BasicTeX, Manim's
  installation page lists the extra packages, installed with `sudo tlmgr install`, which asks for
  the Mac's password.

If `~/.local/bin` is not on PATH after a `uv tool install`, `uv tool update-shell` adds it. Ask
before each download and say roughly how large it is. Leave anything that asks for a password to
the user, in the Terminal app.

## Before animating: settle what it says

A polished video persuades whether or not it is right, so it only ever presents results that
were checked elsewhere, and it is never evidence for them.

- Write the claims down first, each with its source (a derivation, a paper's text, a computed
  number). Recompute every number the narration or the screen states from that source.
- A video about someone else's paper works from what the `papers` plugin's licence check allows:
  for a subscription paper, the title, abstract, short quotes and the user's own notes, never its
  full text.
- Ask what it is for if that isn't clear: a course (accuracy and pace for students), a talk, or
  the user working something out. The audience sets the length; one idea per minute is plenty.

## Pipeline

Work in a folder in the user's project, never in this skill's folder. The scripts are in
`${CLAUDE_SKILL_DIR}/scripts/`; call that `$X` below. Copy `$X/narrated_scene.py` into the
project folder first, since each scene imports it from beside itself.

1. **Narration.** Write `narration.json`: a list of `{"id", "text"}` lines in playing order, one
   line per visual beat, usually 1 to 3 sentences. Write for the ear: short sentences, plain
   words, no em-dashes, numbers as they should be said ("zero point one eight"), symbols in words
   ("eta", not "η"). Then run

       python3 $X/narrate.py <folder>

   which makes `audio/<id>.wav` and `audio/durations.json`. Rerun it after any change to the
   text. `--voice` picks another Kokoro voice (`tts --list-voices`).

2. **Scene.** Write `<name>.py` in the folder with a class that subclasses `NarratedScene`; the
   example's first lines show the import. Call `self.segment("<id>", [(animation, share), ...])`
   once per narration line: the line's audio starts there, the animations run one after another,
   each taking `share` of the line, and the rest of the line is a pause. Shares add up to 1 or
   less. Build everything the narration describes inside the segment that says it.

3. **Render** without the cache, always:

       manim -qm --disable_caching --media_dir <folder>/media <folder>/<name>.py <Class>

   `-qm` is 720p30 for drafts; `-qh` is 1080p60 for the version that goes out. The pydub
   `SyntaxWarning` lines at start-up are harmless.

4. **Check** before showing anything:

       python3 $X/check_video.py <folder> <path to the .mp4>

   It fails if the audio track is shorter than the narration, and writes two kinds of sheet.
   `contact-sheet.png` has two frames per line, after the animations have settled.
   `transitions-1.png` and the sheets after it have a frame every quarter second while the
   picture is moving, which is where text usually runs into other text. Read every sheet and look
   at every frame for text touching a curve, an arrow or another label, captions scrambled or
   drawn over each other, labels running off the frame, and anything shown before the narration
   names it. Text that is partly written in is expected mid-animation; two texts drawn into each
   other are not. Fix, re-render, re-check. State in the report which sheets were inspected; the
   sheets sample frames and are not the whole video, and nobody has listened to it unless
   someone did.

5. **Deliver.** Copy the final render next to its script with a plain name and tell the user
   where it is.

## Layout that avoids the usual faults

- Keep zones: title at the top edge, the main diagram in the middle, equations bottom-left,
  derived results bottom-right. Text never goes inside the plot area.
- Use `Axes` with equal x and y scale when geometry matters (contours, angles); set `x_length`
  and `y_length` in proportion to the ranges.
- Fade out a helper (an arrow, a highlight) before drawing what it would sit on.
- Change a caption by fading the old one out and then fading the new one in, as two
  animations. A `Transform` or `ReplacementTransform` between two texts morphs the letters into
  each other, and both are unreadable while it plays.
- Let text finish leaving a place before anything is written there. Fading a caption out while
  a formula is written in the same spot draws one over the other.
- Never put an empty string among caption lines stacked with `arrange`: an empty `Text` has no
  size, so the lines around it crowd together or overlap. Use `buff` on `arrange` for a gap.
- Dark background with theme colours set once at the top of the file; `MathTex` with explicit
  `color`, since its default is white.

## Known failure modes

- **A cached re-render drops sound.** A re-render that reused cached partial movies kept the
  full video but lost about 10 seconds of narration. `--disable_caching` prevents it, and
  `check_video.py` catches it.
- **Overlaps.** The first render of the example drew the gradient arrow on top of the first
  step's line. Code written blind gets positions wrong; only the frames show it. Overlaps that
  last only while an animation plays appear on the transition sheets and not on the contact
  sheet.
- **Timing drift.** If a scene plays animations outside `segment()`, the narration and the
  picture slip apart, and the contact sheet's frame times are off by the same amount. Keep every
  animation inside a segment.
