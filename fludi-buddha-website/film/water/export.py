"""The water film's frames for the site: PNG frames from render.mjs -> WebP, in two sizes, and a poster.

Run from fludi-buddha-website/ after `node film/water/render.mjs frames --n 540`:
  .venv/Scripts/python film/water/export.py [--q 50] [--qm 55]
Writes web/public/film/water/960/fNNNNN.webp (960 x 768), web/public/film/water/512/ (512 x 410)
and web/public/film/water/poster.jpg (the first frame), and prints the total sizes.

The picture shows at about 715 x 572 CSS px on a 1440 px screen, so 960 is enough; the knife texture
compresses poorly, and quality 50 keeps it while holding the film near 30 MB (the old film was 38 MB).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

SITE = Path(__file__).resolve().parents[2]
SRC = SITE / "film" / "out" / "water" / "frames"
DST = SITE / "web" / "public" / "film" / "water"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=int, default=50, help="WebP quality, desktop")
    ap.add_argument("--qm", type=int, default=55, help="WebP quality, phones")
    a = ap.parse_args()
    frames = sorted(SRC.glob("f*.png"))
    if not frames:
        raise SystemExit(f"no frames in {SRC}: run node film/water/render.mjs frames first")
    big, small = DST / "960", DST / "512"
    for old in (DST / "1024",):
        if old.exists():
            for f in old.glob("*.webp"):
                f.unlink()
            old.rmdir()
    for d in (big, small):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.webp"):
            f.unlink()

    def one(p):
        im = Image.open(p).convert("RGB")
        im.resize((960, 768), Image.LANCZOS).save(big / (p.stem + ".webp"), "WEBP", quality=a.q, method=6)
        im.resize((512, 410), Image.LANCZOS).save(small / (p.stem + ".webp"), "WEBP", quality=a.qm, method=6)

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, frames))
    Image.open(frames[0]).convert("RGB").resize((960, 768), Image.LANCZOS).save(DST / "poster.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    size = lambda d: sum(f.stat().st_size for f in d.glob("*.webp")) / 1e6
    print(f"{len(frames)} frames  desktop {size(big):.1f} MB  phones {size(small):.1f} MB")


if __name__ == "__main__":
    main()
