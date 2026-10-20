"""LiveLica blog-to-YouTube video renderer.

Usage: python make_video.py scenes.json out.mp4 [--voice bm_george] [--speed 1.0]

scenes.json:
{
  "title": "Video title",
  "url": "https://www.livelica.com/blogs/...",
  "scenes": [
    {"type": "title",   "heading": "...", "sub": "...", "narration": "..."},
    {"type": "points",  "heading": "...", "bullets": ["...", "..."], "narration": "..."},
    {"type": "diagram", "heading": "...", "svg": "<svg ...>...</svg>", "narration": "..."},
    {"type": "end",     "heading": "...", "sub": "...", "narration": "..."}
  ]
}
Each scene is shown for exactly as long as its narration lasts, plus a short pause.
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("KOKORO_DIR", HERE / "models"))
W, H = 1920, 1080
BG = (15, 23, 42)          # #0f172a
PANEL = (17, 28, 51)
ICE = (56, 189, 248)       # #38bdf8
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
GREEN = (34, 197, 94)
PAUSE = 0.7                # seconds of silence after each scene
SR = 24000


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def base(brand=True):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ICE)
    if brand:
        d.text((90, H - 80), "LIVELICA", font=font(30, True), fill=ICE)
        d.text((W - 90, H - 80), "livelica.com", font=font(28), fill=MUTED, anchor="ra")
    return img, d


def render_title(s, path):
    img, d = base()
    y = 330
    for line in wrap(d, s["heading"], font(84, True), 1600):
        d.text((W // 2, y), line, font=font(84, True), fill=WHITE, anchor="mm")
        y += 104
    if s.get("sub"):
        d.text((W // 2, y + 40), s["sub"], font=font(40), fill=ICE, anchor="mm")
    img.save(path)


def render_points(s, path, visible=None):
    """Heading plus bullets; `visible` limits how many bullets are drawn (for one-by-one reveals)."""
    img, d = base()
    hf, bf = font(66, True), font(48)
    head = wrap(d, s["heading"], hf, 1700)
    bullets = s.get("bullets", [])
    blines = [wrap(d, b, bf, 1540) for b in bullets]
    block_h = len(head) * 82 + 80 + sum(len(l) * 62 + 36 for l in blines)
    y = max(110, (H - 110 - block_h) // 2)
    for line in head:
        d.text((130, y), line, font=hf, fill=WHITE)
        y += 82
    d.rectangle([130, y + 18, 310, y + 24], fill=ICE)
    y += 80
    n = len(bullets) if visible is None else visible
    for idx, lines in enumerate(blines):
        if idx < n:
            d.ellipse([138, y + 18, 160, y + 40], fill=ICE)
            for line in lines:
                d.text((195, y), line, font=bf, fill=WHITE)
                y += 62
        else:
            y += 62 * len(lines)
        y += 36
    img.save(path)


def points_states(s, tmp, i, dur):
    """Images and durations that reveal bullets one at a time across the narration."""
    n = len(s.get("bullets", []))
    if n == 0:
        p = Path(tmp) / f"s{i:02d}_0.png"
        render_points(s, p)
        return [(p, dur)]
    lead = min(3.0, dur * 0.12)               # heading alone for a moment
    step = (dur - lead) / n
    out = []
    for k in range(n + 1):
        p = Path(tmp) / f"s{i:02d}_{k}.png"
        render_points(s, p, visible=k)
        out.append((p, lead if k == 0 else step))
    return out


def render_diagram(s, path, tmp):
    import cairosvg
    svg = s["svg"]
    # Shopify lowercases attribute names; restore the ones cairo needs.
    svg = svg.replace("viewbox=", "viewBox=").replace("markerwidth=", "markerWidth=").replace(
        "markerheight=", "markerHeight=").replace("refx=", "refX=").replace("refy=", "refY=")
    svg = re.sub(r'style="[^"]*"', "", svg, count=1)
    if "xmlns=" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    png = Path(tmp) / (Path(path).stem + "_svg.png")
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(png), output_width=1640)
    img, d = base()
    top = 60
    if s.get("heading"):
        d.text((W // 2, 90), s["heading"], font=font(52, True), fill=WHITE, anchor="mm")
        top = 150
    dia = Image.open(png).convert("RGB")
    max_w, max_h = 1720, H - top - 130
    scale = min(max_w / dia.width, max_h / dia.height)
    dia = dia.resize((int(dia.width * scale), int(dia.height * scale)), Image.LANCZOS)
    img.paste(dia, ((W - dia.width) // 2, top + (max_h - dia.height) // 2))
    img.save(path)


def render_end(s, path):
    img, d = base(brand=False)
    d.text((W // 2, 380), "LIVELICA", font=font(110, True), fill=ICE, anchor="mm")
    y = 520
    for line in wrap(d, s["heading"], font(56, True), 1600):
        d.text((W // 2, y), line, font=font(56, True), fill=WHITE, anchor="mm")
        y += 72
    if s.get("sub"):
        for line in wrap(d, s["sub"], font(38), 1700):
            d.text((W // 2, y + 30), line, font=font(38), fill=MUTED, anchor="mm")
            y += 50
    img.save(path)


def render_thumbnail(spec, path):
    """1280x720 YouTube thumbnail: short punchy text, brand bar."""
    tw, th = 1280, 720
    img = Image.new("RGB", (tw, th), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 24, th], fill=ICE)
    text = spec.get("thumbnail_text") or spec["title"]
    size = 104
    while size > 56:
        lines = wrap(d, text, font(size, True), 1100)
        if len(lines) <= 3:
            break
        size -= 8
    y = (th - len(lines) * (size + 16)) // 2 - 30
    for k, line in enumerate(lines):
        d.text((80, y), line, font=font(size, True), fill=ICE if k == len(lines) - 1 else WHITE)
        y += size + 16
    d.text((80, th - 90), "LIVELICA", font=font(44, True), fill=ICE)
    d.text((tw - 70, th - 84), "speed skating guides", font=font(34), fill=MUTED, anchor="ra")
    img.save(path)


def mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def tts(kokoro, text, voice, speed):
    """Synthesize sentence by sentence (keeps each chunk inside the model's limit)."""
    lang = "en-gb" if voice.startswith("b") else "en-us"
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    parts = []
    for sent in sentences:
        audio, sr = kokoro.create(sent, voice=voice, speed=speed, lang=lang)
        parts.append(audio)
        parts.append(np.zeros(int(0.18 * sr), dtype=audio.dtype))
    return np.concatenate(parts) if parts else np.zeros(SR, dtype=np.float32)


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()

    from kokoro_onnx import Kokoro
    kokoro = Kokoro(str(MODEL_DIR / "kokoro-v1.0.onnx"), str(MODEL_DIR / "voices-v1.0.bin"))
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    # Diagrams can be pulled straight from the article HTML: {"type":"diagram","svg_index":0}
    if spec.get("article_html"):
        html = (Path(a.spec).parent / spec["article_html"]).read_text(encoding="utf-8")
        svgs = re.findall(r"<svg.*?</svg>", html, flags=re.S | re.I)
        for s in spec["scenes"]:
            if s["type"] == "diagram" and "svg_index" in s:
                s["svg"] = svgs[s["svg_index"]]

    with tempfile.TemporaryDirectory() as tmp:
        segs, srt, chapters, clock = [], [], [], 0.0
        for i, s in enumerate(spec["scenes"]):
            audio = tts(kokoro, s["narration"], a.voice, a.speed)
            audio = np.concatenate([audio, np.zeros(int(PAUSE * SR), dtype=audio.dtype)])
            wav = Path(tmp) / f"s{i:02d}.wav"
            sf.write(wav, audio, SR)
            dur = len(audio) / SR

            if s["type"] == "points":
                states = points_states(s, tmp, i, dur)
            else:
                img = Path(tmp) / f"s{i:02d}.png"
                {"title": render_title, "end": render_end}.get(
                    s["type"], lambda s, p: render_diagram(s, p, tmp))(s, img)
                states = [(img, dur)]
            ilist = Path(tmp) / f"s{i:02d}_imgs.txt"
            ilist.write_text("".join(f"file '{p}'\nduration {d:.3f}\n" for p, d in states)
                             + f"file '{states[-1][0]}'\n")
            seg = Path(tmp) / f"s{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(ilist),
                            "-i", str(wav), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage",
                            "-preset", "medium", "-crf", "28", "-c:a", "aac", "-b:a", "128k",
                            "-ar", "48000", "-t", f"{dur:.3f}", str(seg)], check=True)
            segs.append(seg)
            # Captions: one cue per sentence, timed in proportion to its length
            sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", s["narration"]) if x.strip()]
            total_chars = sum(len(x) for x in sents) or 1
            t = clock
            for sent in sents:
                span = (dur - PAUSE) * len(sent) / total_chars
                srt.append(f"{len(srt) + 1}\n{srt_time(t)} --> {srt_time(t + span)}\n{sent}\n")
                t += span
            chapters.append(f"{mmss(clock)} {s.get('chapter') or s['heading']}")
            clock += dur
            print(f"scene {i + 1}/{len(spec['scenes'])}: {s['type']} {dur:.1f}s", flush=True)

        # Optional real human intro (e.g. 5 to 10 seconds of the owner on camera), prepended to every video.
        intro = HERE / "assets" / "intro.mp4"
        if intro.exists():
            norm = Path(tmp) / "intro.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(intro), "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
                            "-ar", "48000", "-ac", "1", str(norm)], check=True)
            idur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "default=nw=1:nk=1", str(norm)], capture_output=True, text=True).stdout)
            segs.insert(0, norm)
            chapters = ["0:00 Intro"] + [f"{mmss(float(c.split()[0].split(':')[0]) * 60 + float(c.split()[0].split(':')[1]) + idur)} {c.split(' ', 1)[1]}" for c in chapters]
            new_srt = []
            for cue in srt:
                parts = cue.split("\n")
                a_, b_ = parts[1].split(" --> ")
                def to_s(x):
                    h, m_, rest = x.split(":"); s_, ms = rest.split(",")
                    return int(h) * 3600 + int(m_) * 60 + int(s_) + int(ms) / 1000
                parts[1] = f"{srt_time(to_s(a_) + idur)} --> {srt_time(to_s(b_) + idur)}"
                new_srt.append("\n".join(parts))
            srt = new_srt
            clock += idur

        lst = Path(tmp) / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in segs))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", "-movflags", "+faststart", a.out], check=True)
        out = Path(a.out)
        out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
        if not chapters[0].startswith("0:00 Intro"):
            chapters[0] = "0:00 " + chapters[0].split(" ", 1)[1]
        out.with_name(out.stem + "_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
        render_thumbnail(spec, out.with_name(out.stem + "_thumbnail.png"))
    mb = os.path.getsize(a.out) / 1e6
    print(f"done: {a.out} {clock / 60:.1f} min {mb:.1f} MB")


if __name__ == "__main__":
    main()
