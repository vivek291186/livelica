"""Fallback scene when Canva is unavailable: the real product photo cut out and lit on a dark studio floor.

Usage: python make_studio_scene.py product.jpg scene.png [--w 1080 --h 1350]
The product sits in the lower part so the headline fits above it, like the Canva scenes.
"""
import argparse

from PIL import Image, ImageDraw, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("out")
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=1350)
    a = ap.parse_args()
    W, H = a.w, a.h

    from rembg import new_session, remove
    cut = remove(Image.open(a.photo).convert("RGB"), session=new_session("isnet-general-use"))
    # drop faint alpha residue (photographed shadows) so the crop hugs the real product
    alpha = cut.getchannel("A").point(lambda v: 0 if v < 40 else v)
    cut.putalpha(alpha)
    cut = cut.crop(alpha.point(lambda v: 255 if v >= 128 else 0).getbbox())

    # background: deep navy with a soft blue glow behind the product and a floor line
    bg = Image.new("RGB", (W, H), (6, 12, 28))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([W * 0.05, H * 0.38, W * 0.95, H * 0.98], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(W // 6))
    bg.paste(Image.new("RGB", (W, H), (30, 80, 140)), (0, 0), glow.point(lambda v: v * 0.75))
    floor_y = int(H * 0.86)

    s = min(W * 0.86 / cut.width, H * 0.40 / cut.height)
    cut = cut.resize((int(cut.width * s), int(cut.height * s)), Image.LANCZOS)
    x, y = (W - cut.width) // 2, floor_y - cut.height

    # reflection
    ref = cut.transpose(Image.FLIP_TOP_BOTTOM)
    fade = Image.linear_gradient("L").resize(ref.size).point(lambda v: max(0, 90 - v))
    ref.putalpha(Image.composite(ref.getchannel("A"), Image.new("L", ref.size, 0), fade).point(lambda v: v // 3))
    bg.paste(ref, (x, floor_y), ref)
    # contact shadow
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).ellipse([x + cut.width * 0.08, floor_y - 14, x + cut.width * 0.92, floor_y + 18], fill=200)
    bg.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(cut, (x, y), cut)
    bg.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
