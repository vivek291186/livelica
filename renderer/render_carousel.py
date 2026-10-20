"""LiveLica carousel renderer for Instagram and Facebook (1080x1350, 4:5).

Usage: python render_carousel.py carousel.json out_dir/

carousel.json:
{
  "tag": "INLINE TRAINING",                    # small label on every slide
  "article_html": "article.html",              # optional, for diagram slides
  "slides": [
    {"type": "cover",   "title": "Exam season? Keep your speed", "sub": "90 minutes a week is enough"},
    {"type": "point",   "title": "Keep the frequency, cut the volume", "body": "Two 30 minute sessions beat one 90 minute session."},
    {"type": "diagram", "title": "What holds and what fades", "svg_index": 0},
    {"type": "quote",   "text": "Cut the session, never the sleep."},
    {"type": "photo",   "image": "img1.jpg", "title": "Product name", "sub": "One short line"},   # local file
    {"type": "cta",     "title": "Full guide with the weekly plan", "body": "Link in bio"}
  ]
}
Writes slide_01.jpg, slide_02.jpg ... into out_dir.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
NAVY = (11, 18, 36)
NAVY2 = (17, 28, 54)
CARD = (22, 35, 66)
ICE = (56, 189, 248)
ICE_DIM = (30, 94, 130)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
M = 88  # outer margin

FONTS = {
    "display": "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
    "display_black": "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf",
    "regular": "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "medium": "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "semibold": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
}
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(kind, size):
    for p in (FONTS.get(kind), FALLBACK):
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wrap(d, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, kind, start, min_size, max_w, max_lines):
    size = start
    while size > min_size:
        f = font(kind, size)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
        size -= 4
    f = font(kind, min_size)
    return f, wrap(d, text, f, max_w), min_size


def background(variant=0):
    """Deep navy gradient with soft speed streaks: the brand motif on every slide."""
    img = Image.new("RGB", (W, H), NAVY)
    grad = Image.linear_gradient("L").resize((W, H)).rotate(35, expand=False)
    img = Image.composite(Image.new("RGB", (W, H), NAVY2), img, grad)
    streaks = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streaks)
    rows = [(0.18, 7, 70), (0.24, 3, 45), (0.82, 5, 55), (0.88, 2, 35)] if variant == 0 else \
           [(0.10, 4, 40), (0.90, 6, 60), (0.95, 2, 30)]
    for y_rel, thick, alpha in rows:
        y = int(H * y_rel)
        sd.line([(-100, y + 260), (W + 100, y - 260)], fill=ICE + (alpha,), width=thick)
    streaks = streaks.filter(ImageFilter.GaussianBlur(1.2))
    img.paste(streaks, (0, 0), streaks)
    return img


def chrome(d, tag, idx, total, dark_footer=False):
    """Brand wordmark, category tag and slide counter."""
    d.text((M, 78), "LIVELICA", font=font("display_black", 34), fill=WHITE)
    tf = font("semibold", 22)
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle([W - M - tw - 40, 70, W - M, 116], radius=23, outline=ICE, width=2)
    d.text((W - M - tw - 20, 81), tag, font=tf, fill=ICE)
    # progress dots
    dot_y = H - 92
    x = M
    for i in range(total):
        wdt = 46 if i == idx else 14
        d.rounded_rectangle([x, dot_y, x + wdt, dot_y + 14], radius=7, fill=ICE if i == idx else ICE_DIM)
        x += wdt + 10
    d.text((W - M, dot_y - 6), "@livelicax", font=font("medium", 24), fill=MUTED, anchor="ra")


def slide_cover(s, tag, idx, total):
    img = background(0)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    f, lines, size = fit(d, s["title"], "display_black", 112, 72, W - 2 * M, 5)
    lh = int(size * 1.08)
    block = len(lines) * lh
    y = (H - block) // 2 - 60
    for k, line in enumerate(lines):
        d.text((M, y), line, font=f, fill=ICE if k == len(lines) - 1 else WHITE)
        y += lh
    if s.get("sub"):
        y += 30
        sf = font("medium", 40)
        for line in wrap(d, s["sub"], sf, W - 2 * M):
            d.text((M, y), line, font=sf, fill=MUTED)
            y += 54
    d.text((W - M, H - 170), "Swipe", font=font("semibold", 30), fill=WHITE, anchor="ra")
    ax = W - M - d.textlength("Swipe", font=font("semibold", 30)) - 70
    d.line([(ax, H - 152), (ax + 50, H - 152)], fill=ICE, width=4)
    d.polygon([(ax + 50, H - 162), (ax + 64, H - 152), (ax + 50, H - 142)], fill=ICE)
    return img


def slide_point(s, tag, idx, total, number):
    img = background(1)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    tf, tlines, tsize = fit(d, s["title"], "display", 80, 54, W - 2 * M, 4)
    bf, blines, bsize = (None, [], 0)
    if s.get("body"):
        bf, blines, bsize = fit(d, s["body"], "regular", 48, 36, W - 2 * M, 8)
    num_h, gap = 170, 40
    block = num_h + gap + len(tlines) * int(tsize * 1.14) + 80 + len(blines) * int(bsize * 1.42)
    y = max(180, (H - block) // 2)
    d.text((M, y - 20), f"{number:02d}", font=font("display_black", 170), fill=ICE_DIM)
    y += num_h + gap
    for line in tlines:
        d.text((M, y), line, font=tf, fill=WHITE)
        y += int(tsize * 1.14)
    d.rectangle([M, y + 26, M + 120, y + 32], fill=ICE)
    y += 80
    for line in blines:
        d.text((M, y), line, font=bf, fill=(203, 213, 225))
        y += int(bsize * 1.42)
    return img


def slide_quote(s, tag, idx, total):
    img = background(0)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    d.text((M - 8, 300), "“", font=font("display_black", 260), fill=ICE)
    f, lines, size = fit(d, s["text"], "display", 84, 56, W - 2 * M, 6)
    y = 560
    for line in lines:
        d.text((M, y), line, font=f, fill=WHITE)
        y += int(size * 1.16)
    return img


def slide_diagram(s, tag, idx, total, svgs, tmp):
    import cairosvg
    img = background(1)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    tf, tlines, tsize = fit(d, s["title"], "display", 64, 46, W - 2 * M, 3)
    y = 200
    for line in tlines:
        d.text((M, y), line, font=tf, fill=WHITE)
        y += int(tsize * 1.14)
    svg = svgs[s["svg_index"]]
    for a, b in [("viewbox=", "viewBox="), ("markerwidth=", "markerWidth="), ("markerheight=", "markerHeight="),
                 ("refx=", "refX="), ("refy=", "refY=")]:
        svg = svg.replace(a, b)
    svg = re.sub(r'style="[^"]*"', "", svg, count=1)
    if "xmlns=" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    png = Path(tmp) / f"dia_{idx}.png"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(png), output_width=1800)
    dia = Image.open(png).convert("RGB")
    # Use nearly the full slide width so labels stay readable on a phone, centred in the space left.
    side = 36
    avail_top, avail_bot = y + 40, H - 150
    max_w, max_h = W - 2 * side, avail_bot - avail_top
    scale = min(max_w / dia.width, max_h / dia.height)
    dia = dia.resize((int(dia.width * scale), int(dia.height * scale)), Image.LANCZOS)
    top = avail_top + (max_h - dia.height) // 2
    mask = Image.new("L", dia.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, dia.width, dia.height], radius=22, fill=255)
    img.paste(dia, ((W - dia.width) // 2, top), mask)
    if s.get("caption"):
        cf = font("regular", 32)
        cy = top + dia.height + 30
        for line in wrap(d, s["caption"], cf, W - 2 * M):
            d.text((M, cy), line, font=cf, fill=MUTED)
            cy += 44
    return img


def slide_photo(s, tag, idx, total, root):
    """Real product photo on a light card, product name above, short line below."""
    img = background(0)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    tf, tlines, tsize = fit(d, s.get("title", ""), "display_black", 72, 48, W - 2 * M, 3)
    y = 190
    for line in tlines:
        d.text((M, y), line, font=tf, fill=WHITE)
        y += int(tsize * 1.1)
    src = Image.open(root / s["image"]).convert("RGB")
    top = y + 40
    bottom = H - (230 if s.get("sub") else 150)
    box_w, box_h = W - 2 * 60, bottom - top
    card = Image.new("RGB", (box_w, box_h), (255, 255, 255))
    sc = min((box_w - 40) / src.width, (box_h - 40) / src.height)
    ph = src.resize((int(src.width * sc), int(src.height * sc)), Image.LANCZOS)
    card.paste(ph, ((box_w - ph.width) // 2, (box_h - ph.height) // 2))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, box_w, box_h], radius=32, fill=255)
    img.paste(card, (60, top), mask)
    if s.get("sub"):
        d.text((M, bottom + 30), s["sub"], font=font("medium", 36), fill=ICE)
    return img


def slide_cta(s, tag, idx, total):
    img = background(0)
    d = ImageDraw.Draw(img)
    chrome(d, tag, idx, total)
    d.text((W // 2, 420), "LIVELICA", font=font("display_black", 120), fill=ICE, anchor="mm")
    f, lines, size = fit(d, s.get("title", "Full guide on our blog"), "display", 64, 46, W - 2 * M, 3)
    y = 560
    for line in lines:
        d.text((W // 2, y), line, font=f, fill=WHITE, anchor="ma")
        y += int(size * 1.15)
    y += 50
    label = s.get("body", "Link in bio")
    bf = font("semibold", 40)
    bw = d.textlength(label, font=bf)
    d.rounded_rectangle([(W - bw) // 2 - 44, y, (W + bw) // 2 + 44, y + 92], radius=46, fill=ICE)
    d.text((W // 2, y + 46), label, font=bf, fill=NAVY, anchor="mm")
    d.text((W // 2, y + 170), "Save this for your next session", font=font("medium", 32), fill=MUTED, anchor="mm")
    return img


def main():
    import tempfile
    spec_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    svgs = []
    if spec.get("article_html"):
        html = (spec_path.parent / spec["article_html"]).read_text(encoding="utf-8")
        svgs = re.findall(r"<svg.*?</svg>", html, flags=re.S | re.I)
    tag = spec.get("tag", "SPEED SKATING").upper()
    slides = spec["slides"]
    total, number = len(slides), 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(slides):
            t = s["type"]
            if t == "cover":
                img = slide_cover(s, tag, i, total)
            elif t == "point":
                number += 1
                img = slide_point(s, tag, i, total, number)
            elif t == "quote":
                img = slide_quote(s, tag, i, total)
            elif t == "diagram":
                img = slide_diagram(s, tag, i, total, svgs, tmp)
            elif t == "photo":
                img = slide_photo(s, tag, i, total, spec_path.parent)
            else:
                img = slide_cta(s, tag, i, total)
            p = out_dir / f"slide_{i + 1:02d}.jpg"
            img.save(p, quality=93, subsampling=0)
            print(p)


if __name__ == "__main__":
    main()
