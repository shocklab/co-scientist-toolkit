#!/usr/bin/env python3
"""Check a rendered explainer before anyone sees it.

    check_video.py <project folder> <video.mp4> [--out sheet.png]

Prints the video and audio stream lengths against the narration, fails if the audio track is
shorter than the narration (a cached Manim re-render can drop sound), and writes two kinds of
sheet for the overlap check: a contact sheet with two frames per narration line (middle and just
before the end), when everything has settled, and transition sheets with a frame every quarter
second while the picture is moving, which is when captions and formulas run into each other.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

GAP = 0.4

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("video")
ap.add_argument("--out")
ap.add_argument("--step", type=float, default=0.25, help="seconds between transition frames")
args = ap.parse_args()

folder = os.path.abspath(args.folder)
lines = json.load(open(os.path.join(folder, "narration.json")))
dur = json.load(open(os.path.join(folder, "audio", "durations.json")))

probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                        "-of", "json", args.video], capture_output=True, text=True, check=True)
streams = {s["codec_type"]: float(s.get("duration", 0)) for s in json.loads(probe.stdout)["streams"]}
narr = sum(dur[ln["id"]] for ln in lines)
print(f"video {streams.get('video', 0):.2f} s, audio {streams.get('audio', 0):.2f} s, "
      f"narration {narr:.2f} s")
ok = True
if "audio" not in streams:
    print("FAIL: no audio track"); ok = False
elif streams["audio"] < narr - 0.5:
    print("FAIL: audio track shorter than the narration; re-render with --disable_caching"); ok = False

# Segment start times follow NarratedScene: each line plays for its length plus GAP. Any
# animation outside segments (an intro before the first line) shifts these; pass the sheet
# through a look rather than trusting the times exactly.
times, t = [], 0.0
for ln in lines:
    d = dur[ln["id"]] + GAP
    times += [t + d * 0.5, t + d - 0.15]
    t += d
cols = 2
rows = math.ceil(len(times) / cols)
out = args.out or os.path.join(folder, "contact-sheet.png")
sel = "+".join(f"lt(prev_pts*TB\\,{x:.3f})*gte(pts*TB\\,{x:.3f})" for x in times)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", args.video, "-vf",
                f"select='{sel}',scale=640:-1,tile={cols}x{rows}", "-frames:v", "1", out], check=True)
print(f"contact sheet: {out} ({len(times)} frames, middle and end of each line)")


def tile(at, path, cols=4, rows=6):
    sel = "+".join(f"lt(prev_pts*TB\\,{x:.3f})*gte(pts*TB\\,{x:.3f})" for x in at)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", args.video, "-vf",
                    f"select='{sel}',scale=480:-1,tile={cols}x{rows}", "-frames:v", "1", path], check=True)


# Stretches where the picture is moving: everything outside the still stretches freezedetect finds.
end = streams.get("video", 0)
info = subprocess.run(["ffmpeg", "-v", "info", "-i", args.video, "-vf", "freezedetect=n=0.0001:d=0.2",
                       "-f", "null", "-"], capture_output=True, text=True).stderr
starts = [float(x) for x in re.findall(r"freeze_start: ([0-9.]+)", info)]
ends = [float(x) for x in re.findall(r"freeze_end: ([0-9.]+)", info)]
ends += [end] * (len(starts) - len(ends))                  # a still stretch running to the end
moving, t0 = [], 0.0
for a, b in list(zip(starts, ends)) + [(end, end)]:
    x = t0 + args.step / 2
    while x < a:
        moving.append(x)
        x += args.step
    t0 = b
per = 24
base = os.path.splitext(out)[0].replace("contact-sheet", "transitions")
for old in [f for f in os.listdir(os.path.dirname(out)) if re.match(re.escape(os.path.basename(base)) + r"-\d+\.png$", f)]:
    os.remove(os.path.join(os.path.dirname(out), old))
for i in range(0, len(moving), per):
    chunk = moving[i:i + per]
    path = f"{base}-{i // per + 1}.png"
    tile(chunk, path)
    print(f"transition sheet: {path} (frames at {', '.join(f'{x:.2f}' for x in chunk)} s, left to right, top to bottom)")
if not moving:
    print("no moving frames found; nothing for the transition sheets")
sys.exit(0 if ok else 1)
