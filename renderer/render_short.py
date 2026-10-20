"""LiveLica vertical product video (1080x1920) for YouTube Shorts, Instagram Reels and Facebook Reels.

Usage: python render_short.py short.json out.mp4 [--voice am_michael]

short.json:
{
  "tag": "BEARINGS",
  "scenes": [
    {"type": "photo",  "image": "img1.jpg", "headline": "Power Bearings Swiss Ceramic", "narration": "..."},
    {"type": "points", "headline": "Why skaters pick it", "bullets": ["...", "..."], "narration": "..."},
    {"type": "photo",  "image": "img2.jpg", "headline": "...", "narration": "..."},
    {"type": "end",    "headline": "Power Bearings Swiss Ceramic", "sub": "Shop at livelica.com", "narration": "..."}
  ]
}
Images are local files (paths relative to short.json). Each scene lasts as long as its narration.
Captions are burned in, one sentence at a time, because most Shorts and Reels are watched muted.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
W, H = 1080, 1920
NAVY = (11, 18, 36)
ICE = (56, 189, 248)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
SR = 24000
PAUSE = 0.35
FPS = 30


def font(kind, size):
    paths = {
        "black": "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf",
        "bold": "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
        "semi": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
        "reg": "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    }
    p = paths.get(kind)
    if p and Path(p).exists():
        return ImageFont.truetype(p, size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def brand(d, tag):
    d.text((70, 90), "LIVELICA", font=font("black", 46), fill=WHITE)
    tf = font("semi", 28)
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle([W - 70 - tw - 44, 84, W - 70, 140], radius=28, outline=ICE, width=3)
    d.text((W - 70 - tw - 22, 96), tag, font=tf, fill=ICE)


def headline_block(d, text, y, size=78, color=WHITE):
    f = font("black", size)
    lines = wrap(d, text, f, W - 140)
    while len(lines) > 3 and size > 52:
        size -= 6
        f = font("black", size)
        lines = wrap(d, text, f, W - 140)
    for line in lines:
        d.text((70, y), line, font=f, fill=color)
        y += int(size * 1.1)
    return y


def photo_base(s, root, tag, path):
    """Product photo: blurred fill behind a sharp, contained photo on a rounded card."""
    src = Image.open(root / s["image"]).convert("RGB")
    bg = src.copy()
    scale = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * scale), int(bg.height * scale)))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), NAVY), 0.62)
    # Text layer (brand + product name) is drawn separately so only the photo moves in the push-in.
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    brand(od, tag)
    y_end = headline_block(od, s.get("headline", ""), 210, 70)
    top = max(y_end + 40, 440)
    box_w, box_h = W - 120, min(860, H - 660 - top)
    sc = min(box_w / src.width, box_h / src.height)
    ph = src.resize((int(src.width * sc), int(src.height * sc)), Image.LANCZOS)
    card = Image.new("RGB", (box_w, box_h), (245, 247, 250))
    card.paste(ph, ((box_w - ph.width) // 2, (box_h - ph.height) // 2))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, box_w, box_h], radius=40, fill=255)
    bg.paste(card, (60, top), mask)
    bg.save(path)
    over.save(Path(path).with_name(Path(path).stem + "_text.png"))


def points_base(s, tag, path):
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for y_rel, th, a in [(0.15, 8, 90), (0.2, 3, 60), (0.86, 6, 70)]:
        y = int(H * y_rel)
        d.line([(-50, y + 300), (W + 50, y - 300)], fill=(30, 94, 130), width=th)
    brand(d, tag)
    y = headline_block(d, s.get("headline", ""), 360, 86)
    d.rectangle([70, y + 24, 210, y + 31], fill=ICE)
    y += 90
    bf = font("semi", 52)
    for b in s.get("bullets", [])[:4]:
        lines = wrap(d, b, bf, W - 220)
        d.ellipse([78, y + 20, 104, y + 46], fill=ICE)
        for line in lines:
            d.text((135, y), line, font=bf, fill=WHITE)
            y += 66
        y += 40
    img.save(path)


def end_base(s, tag, path):
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    brand(d, tag)
    d.text((W // 2, 640), "LIVELICA", font=font("black", 150), fill=ICE, anchor="mm")
    f = font("bold", 70)
    y = 790
    for line in wrap(d, s.get("headline", ""), f, W - 160):
        d.text((W // 2, y), line, font=f, fill=WHITE, anchor="ma")
        y += 82
    label = s.get("sub", "Shop at livelica.com")
    bf = font("semi", 48)
    bw = d.textlength(label, font=bf)
    y += 50
    d.rounded_rectangle([(W - bw) // 2 - 50, y, (W + bw) // 2 + 50, y + 110], radius=55, fill=ICE)
    d.text((W // 2, y + 55), label, font=bf, fill=NAVY, anchor="mm")
    img.save(path)


def caption_png(text, path):
    """Burned-in caption: white bold text on a dark rounded box near the bottom safe area."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("bold", 50)
    lines = wrap(d, text, f, W - 220)[:4]
    lh = 64
    box_h = len(lines) * lh + 50
    top = H - 360 - box_h  # keep clear of the platform UI at the bottom
    widest = max(d.textlength(l, font=f) for l in lines)
    d.rounded_rectangle([(W - widest) // 2 - 36, top, (W + widest) // 2 + 36, top + box_h], radius=26,
                        fill=(0, 0, 0, 175))
    y = top + 25
    for line in lines:
        d.text((W // 2, y), line, font=f, fill=WHITE, anchor="ma")
        y += lh
    img.save(path)


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=1.05)
    a = ap.parse_args()
    spec_path = Path(a.spec)
    root = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    tag = spec.get("tag", "LIVELICA").upper()

    from kokoro_onnx import Kokoro
    mdir = HERE / "models"
    kokoro = Kokoro(str(mdir / "kokoro-v1.0.onnx"), str(mdir / "voices-v1.0.bin"))
    lang = "en-gb" if a.voice.startswith("b") else "en-us"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segs, total = [], 0.0
        for i, s in enumerate(spec["scenes"]):
            # narration, sentence by sentence so each caption can be timed exactly
            parts, cues, t = [], [], 0.0
            for sent in sentences(s["narration"]):
                au, sr = kokoro.create(sent, voice=a.voice, speed=a.speed, lang=lang)
                gap = np.zeros(int(0.12 * sr), dtype=au.dtype)
                parts += [au, gap]
                dur = (len(au) + len(gap)) / sr
                cues.append((t, t + dur, sent))
                t += dur
            audio = np.concatenate(parts + [np.zeros(int(PAUSE * SR), dtype=parts[0].dtype)])
            wav = tmp / f"s{i}.wav"
            sf.write(wav, audio, SR)
            dur = len(audio) / SR

            base = tmp / f"s{i}.png"
            if s["type"] == "photo":
                photo_base(s, root, tag, base)
            elif s["type"] == "points":
                points_base(s, tag, base)
            else:
                end_base(s, tag, base)

            inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(base)]
            filt = []
            frames = int(dur * FPS) + 1
            if s["type"] == "photo":
                # slow push in on product photos
                filt.append(f"[0:v]scale={W * 2}:{H * 2},zoompan=z='min(zoom+0.0006,1.10)':d={frames}:"
                            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[v0]")
            else:
                filt.append(f"[0:v]fps={FPS},format=rgba[v0]")
            last = "v0"
            n_extra = 0
            if s["type"] == "photo":
                inputs += ["-loop", "1", "-i", str(base.with_name(base.stem + "_text.png"))]
                n_extra = 1
                filt.append(f"[v0][1:v]overlay=0:0[vt]")
                last = "vt"
            if s["type"] != "end":
                for k, (c0, c1, text) in enumerate(cues):
                    cp = tmp / f"c{i}_{k}.png"
                    caption_png(text, cp)
                    inputs += ["-loop", "1", "-i", str(cp)]
                    filt.append(f"[{last}][{k + 1 + n_extra}:v]overlay=0:0:enable='between(t,{c0:.2f},{c1:.2f})'[v{k + 1}]")
                    last = f"v{k + 1}"
            filt.append(f"[{last}]format=yuv420p[vout]")
            inputs += ["-i", str(wav)]
            seg = tmp / f"s{i}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                            "-map", "[vout]", "-map", f"{(len(cues) if s['type'] != 'end' else 0) + n_extra + 1}:a",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-r", str(FPS),
                            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "1",
                            "-t", f"{dur:.3f}", str(seg)], check=True)
            segs.append(seg)
            total += dur
            print(f"scene {i + 1}: {s['type']} {dur:.1f}s", flush=True)

        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in segs))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"done: {a.out} {total:.1f}s {Path(a.out).stat().st_size / 1e6:.1f} MB")
    if total > 59:
        print("WARNING: longer than 59 seconds; shorten the narration for Shorts")


if __name__ == "__main__":
    main()
