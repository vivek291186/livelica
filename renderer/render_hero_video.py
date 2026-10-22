"""Vertical 1080x1920 video from a hero post, for the YouTube Short, Instagram Reel and Facebook Reel.

Usage: python render_hero_video.py story.jpg "narration text" out.mp4 [--voice am_michael]

story.jpg comes from render_hero.py. The shot slowly pushes in while the narration plays,
then holds on a short LiveLica end card. Keep the narration to 2 or 3 sentences (10 to 20 seconds).
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H, FPS, SR = 1080, 1920, 30, 24000
NAVY = (8, 14, 30)
RED = (228, 0, 43)


def end_card(path, url_text):
    img = Image.new("RGB", (W, H), NAVY)
    logo = Image.open(HERE / "assets" / "livelica-logo-white.png").convert("RGBA")
    lw = 760
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    img.paste(logo, ((W - lw) // 2, 760), logo)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(HERE / "fonts" / "Kanit-SemiBoldItalic.ttf"), 56)
    tw = d.textlength(url_text, font=f)
    y = 760 + logo.height + 90
    d.rounded_rectangle([(W - tw) // 2 - 50, y, (W + tw) // 2 + 50, y + 110], radius=55, fill=RED)
    d.text((W // 2, y + 55), url_text, font=f, fill=(255, 255, 255), anchor="mm")
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("narration")
    ap.add_argument("out")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--end-text", default="Shop at livelica.com")
    a = ap.parse_args()

    from kokoro_onnx import Kokoro
    m = HERE / "models"
    kokoro = Kokoro(str(m / "kokoro-v1.0.onnx"), str(m / "voices-v1.0.bin"))
    audio, sr = kokoro.create(a.narration, voice=a.voice, speed=a.speed, lang="en-us")
    lead = np.zeros(int(0.4 * sr), dtype=audio.dtype)
    tail = np.zeros(int(2.2 * sr), dtype=audio.dtype)  # covers the end card
    full = np.concatenate([lead, audio, tail])
    shot = (len(lead) + len(audio)) / sr + 0.6
    total = len(full) / sr

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wav = tmp / "v.wav"
        sf.write(wav, full, sr)
        card = tmp / "end.png"
        end_card(card, a.end_text)
        frames = int(shot * FPS) + 1
        filt = (
            f"[0:v]scale={W * 2}:{H * 2},zoompan=z='min(zoom+0.0007,1.12)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
            f"trim=duration={shot:.3f},fade=t=in:st=0:d=0.4,setpts=PTS-STARTPTS[a];"
            f"[1:v]fps={FPS},trim=duration={total - shot + 0.5:.3f},setpts=PTS-STARTPTS[b];"
            f"[a][b]xfade=transition=fade:duration=0.5:offset={shot - 0.5:.3f},format=yuv420p[v]"
        )
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-loop", "1", "-i", a.story, "-loop", "1", "-i", str(card), "-i", str(wav),
                        "-filter_complex", filt, "-map", "[v]", "-map", "2:a",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
                        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "1",
                        "-t", f"{total:.3f}", "-movflags", "+faststart", a.out], check=True)
    print(f"done: {a.out} {total:.1f}s {Path(a.out).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
