"""LiveLica hero product post: AI scene with the real product, plus headline and the real logo on top.

Usage: python render_hero.py hero.json out_dir/

hero.json:
{
  "background": "scene.png",              # text-free 4:5 scene (product already in it)
  "background_story": "scene_9x16.png",   # optional text-free 9:16 scene for story.jpg and the video
  "lines": [                              # headline, top to bottom, 2 or 3 lines
    {"text": "READY TO", "style": "white"},
    {"text": "RACE", "style": "accent"},  # the big word, LiveLica red
    {"text": "THIS SEASON?", "style": "white"}
  ],
  "product": "EHS Short Track Boots"      # optional small label bottom right
}
Writes post.jpg (1080x1350, Instagram and Facebook) and story.jpg (1080x1920, used by render_hero_video.py).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
RED = (228, 0, 43)
WHITE = (255, 255, 255)
LOGO = HERE / "assets" / "livelica-logo-white.png"
F_BLACK = HERE / "fonts" / "Kanit-BlackItalic.ttf"
F_SEMI = HERE / "fonts" / "Kanit-SemiBoldItalic.ttf"


def cover(img, w, h, focus_y=0.5):
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = int((img.height - h) * focus_y)
    return img.crop((x, y, x + w, y + h))


def fit_font(path, text, max_w, size, d):
    while size > 30:
        f = ImageFont.truetype(str(path), size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(str(path), size)


def shadowed(canvas, draw_fn, blur=14, opacity=150, offset=(0, 6)):
    """Draw text with a soft dark shadow so it reads on bright sky or snow."""
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sh), (0, 0, 0, opacity), offset)
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    top = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(top), None, (0, 0))
    canvas.alpha_composite(top)


def compose(bg, lines, product, W, H, top_y):
    img = cover(bg, W, H, 0.55).convert("RGBA")
    # gentle darkening at the top and bottom for legibility, keeps the photo natural
    grad = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        a = 110 * max(0.0, 1 - t / 0.42) ** 1.6 + 120 * max(0.0, (t - 0.80) / 0.20) ** 1.5
        grad.putpixel((0, y), int(a))
    shade = Image.new("RGBA", (W, H), (5, 12, 30, 0))
    shade.putalpha(grad.resize((W, H)))
    img.alpha_composite(shade)

    d = ImageDraw.Draw(img)
    y = top_y
    for ln in lines:
        accent = ln.get("style") == "accent"
        size = int(W * (0.235 if accent else 0.105))
        f = fit_font(F_BLACK, ln["text"], W - 120, size, d)
        color = RED + (255,) if accent else WHITE + (255,)
        bb = d.textbbox((0, 0), ln["text"], font=f, anchor="ma")
        y -= bb[1]  # place by the visible top of the letters, not the font's tall ascender
        ink_h = bb[3] - bb[1]

        def draw(dd, c, off, f=f, y=y, color=color, text=ln["text"]):
            dd.text((W // 2 + off[0], y + off[1]), text, font=f, fill=c or color, anchor="ma")
        if accent:
            # thin white keyline keeps red readable on blue sky and dark mountains
            def draw(dd, c, off, f=f, y=y, color=color, text=ln["text"]):
                dd.text((W // 2 + off[0], y + off[1]), text, font=f, fill=c or color, anchor="ma",
                        stroke_width=0 if c else 3, stroke_fill=(255, 255, 255, 255))
        shadowed(img, draw)
        y += bb[1] + ink_h + int(W * 0.028)

    # real logo bottom left
    logo = Image.open(LOGO).convert("RGBA")
    lw = int(W * 0.34)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    lx, ly = 56, H - logo.height - 60
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    blk = Image.new("RGBA", logo.size, (0, 0, 0, 170))
    blk.putalpha(logo.getchannel("A").point(lambda a: a * 170 // 255))
    sh.paste(blk, (lx, ly + 4), blk)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    img.alpha_composite(logo, (lx, ly))

    if product:
        f = ImageFont.truetype(str(F_SEMI), int(W * 0.03))
        def draw(dd, c, off):
            dd.text((W - 56 + off[0], ly + logo.height // 2 + off[1]), product.upper(), font=f,
                    fill=c or (255, 255, 255, 235), anchor="rm")
        shadowed(img, draw, blur=6, opacity=170, offset=(0, 2))
    return img.convert("RGB")


def main():
    spec_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    bg = Image.open(spec_path.parent / spec["background"]).convert("RGB")
    out.mkdir(parents=True, exist_ok=True)
    compose(bg, spec["lines"], spec.get("product"), 1080, 1350, 70).save(out / "post.jpg", quality=93)
    bg_story = bg
    if spec.get("background_story"):  # optional separate 9:16 scene so the product is not cropped in the video
        bg_story = Image.open(spec_path.parent / spec["background_story"]).convert("RGB")
    compose(bg_story, spec["lines"], spec.get("product"), 1080, 1920, 230).save(out / "story.jpg", quality=93)
    print("wrote", out / "post.jpg", out / "story.jpg")


if __name__ == "__main__":
    main()
