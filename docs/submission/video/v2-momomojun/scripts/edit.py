# Cuts the takes, lays the voice-over, labels and captions, and exports pivot-demo.mp4.
import pathlib, re, subprocess

HERE = pathlib.Path(__file__).parent

# (take, start, end) pieces in order; None = end card
PIECES = [
    ("live", 0.0, 27.0),
    ("explain", 0.0, 20.2),
    ("personal", 0.0, 7.2), ("personal", 12.6, 14.4), ("follow", None, None),
    ("whatif", 0.0, 10.0), ("whatif", 12.6, 20.8),
    ("report", 0.0, 10.4),
    ("end", 0.0, 11.8),
]
FOLLOW_PAD = 1.4  # hold the first frame of the follow take
VOICE = {"s1": 0.3, "s2": 15.0, "s3": 27.3, "s4": 47.5, "s5": 60.5, "s6": 78.7, "s7": 89.2}

def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))

inputs, filters, vlabels = [], [], []
def add_input(args):
    inputs.extend(args); return sum(1 for a in inputs if a == "-i") - 1

seg_start, t = [], 0.0
for n, (take, a, b) in enumerate(PIECES):
    seg_start.append(t)
    if take == "end":
        i = add_input(["-loop", "1", "-framerate", "30", "-t", str(b), "-i", "cards/end.png"])
        filters.append(f"[{i}:v]format=yuv420p,setsar=1,fps=30,fade=t=in:st=0:d=0.4,fade=t=out:st={b - 0.6}:d=0.6[p{n}]")
        t += b
    elif take == "follow":
        i = add_input(["-i", f"takes/{take}.mp4"])
        d = dur(HERE / "takes" / f"{take}.mp4")
        filters.append(f"[{i}:v]tpad=start_mode=clone:start_duration={FOLLOW_PAD},setpts=PTS-STARTPTS,setsar=1[p{n}]")
        t += d + FOLLOW_PAD
    else:
        i = add_input(["-i", f"takes/{take}.mp4"])
        filters.append(f"[{i}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,setsar=1[p{n}]")
        t += b - a
    vlabels.append(f"[p{n}]")
TOTAL = t
filters.append("".join(vlabels) + f"concat=n={len(PIECES)}:v=1:a=0[cat]")

S = seg_start
OVER = [  # image, from, to
    ("title", 0.15, 3.4),
    ("l_livefan", 3.4, VOICE["s2"]), ("l_liveana", VOICE["s2"], S[1]),
    ("l_explain", S[1], S[2]), ("l_personal", S[2], S[5]),
    ("l_wifan", S[5], S[6]), ("l_wiana", S[6], S[7]), ("l_report", S[7], S[8]),
]
cur = "cat"
for k, (img, a, b) in enumerate(OVER):
    i = add_input(["-loop", "1", "-framerate", "30", "-t", f"{TOTAL:.2f}", "-i", f"cards/{img}.png"])
    fade = f",fade=t=in:st={a}:d=0.3:alpha=1,fade=t=out:st={b - 0.3}:d=0.3:alpha=1"
    filters.append(f"[{i}:v]format=rgba{fade}[o{k}]")
    filters.append(f"[{cur}][o{k}]overlay=0:0:enable='between(t,{a},{b})'[v{k}]")
    cur = f"v{k}"

# captions: shift each voice line's cues to its place
def ts(x):
    h, m, s = x.split(":"); return int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))
def fmt(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
cues = []
for name, off in VOICE.items():
    for block in (HERE / "tts" / f"{name}.srt").read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.strip().splitlines()
        a, b = [ts(x.strip()) for x in lines[1].split("-->")]
        cues.append((a + off, b + off, " ".join(lines[2:])))
cues.sort()
for j in range(len(cues) - 1):  # no overlaps
    if cues[j][1] > cues[j + 1][0]:
        cues[j] = (cues[j][0], cues[j + 1][0] - 0.02, cues[j][2])
(HERE / "captions.srt").write_text("\n\n".join(f"{n + 1}\n{fmt(a)} --> {fmt(b)}\n{txt}" for n, (a, b, txt) in enumerate(cues)) + "\n", encoding="utf-8")
style = ("Fontname=Segoe UI,Fontsize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H70000000,BackColour=&H70000000,"
         "BorderStyle=3,Outline=1.6,Shadow=0,MarginV=26,MarginL=70,MarginR=70,Bold=0")
filters.append(f"[{cur}]subtitles=filename=captions.srt:force_style='{style}',format=yuv420p[vout]")

# voice
alabels = []
for k, (name, off) in enumerate(VOICE.items()):
    i = add_input(["-i", f"tts/{name}.mp3"])
    filters.append(f"[{i}:a]aresample=48000,adelay=delays={int(off * 1000)}:all=1[a{k}]")
    alabels.append(f"[a{k}]")
filters.append("".join(alabels) + f"amix=inputs={len(alabels)}:duration=longest:normalize=0,apad,atrim=end={TOTAL:.2f},"
               f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={TOTAL - 0.6:.2f}:d=0.6[aout]")

(HERE / "filter.txt").write_text(";\n".join(filters), encoding="utf-8")
cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-/filter_complex", "filter.txt", "-map", "[vout]", "-map", "[aout]",
       "-t", f"{TOTAL:.2f}", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "pivot-demo.mp4"]
subprocess.run(cmd, cwd=HERE, check=True)
print(f"total {TOTAL:.2f}s; segments start at", ", ".join(f"{x:.2f}" for x in seg_start))
