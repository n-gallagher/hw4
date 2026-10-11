"""White product-photo backgrounds (design polish after Problem 10).

74 of the 102 catalogue photos have black backgrounds or black side bars baked into the JPEG.
This makes cleaned copies where the black *connected to the photo's edges* becomes white, so a
navy hoodie or a black logo inside the garment is never touched. Originals in data/products/
are never modified; copies go to data/products_clean/ (inside data/, so never committed).

Copies are made once, in a background thread when the API starts; /images serves the clean
copy when it exists and the original otherwise.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import tools

CLEAN_DIR = tools.DATA_DIR / "products_clean"
MARK = (255, 0, 255)  # temporary fill colour (never appears in the photos' backgrounds)
DARK = 60  # r+g+b below this counts as "black background" (dark navy fabric is ~80-140, so it's safe)
FILL_TOLERANCE = 15  # how far a pixel may differ from the black it spreads from
FRINGE = 60  # near-black JPEG halo pixels right next to the removed background also go white
MAX_REMOVED = 0.85  # safety: if more than 85% of a photo would be removed, keep the original


def clean_photo(src: Path, dst: Path) -> bool:
    """Flood-fill edge-connected black to white. Returns True if anything changed."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    px = im.load()
    border = [(x, 0) for x in range(0, w, 3)] + [(x, h - 1) for x in range(0, w, 3)]
    border += [(0, y) for y in range(0, h, 3)] + [(w - 1, y) for y in range(0, h, 3)]
    changed = False
    for xy in border:
        r, g, b = px[xy]
        if r + g + b < DARK and px[xy] != MARK:
            ImageDraw.floodfill(im, xy, MARK, thresh=FILL_TOLERANCE)
            changed = True
    if not changed:
        return False

    # mask of removed background, grown by 2px to catch the dark JPEG halo around it
    mask = Image.new("L", (w, h))
    mpx = mask.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] == MARK:
                mpx[x, y] = 255
    removed = mask.histogram()[255] / (w * h)
    if removed > MAX_REMOVED:  # the fill leaked into the garment: a black background beats a broken photo
        return False
    halo = mask.filter(ImageFilter.MaxFilter(5)).load()
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p == MARK or (halo[x, y] and sum(p) < FRINGE):
                px[x, y] = (255, 255, 255)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=92)
    return True


def clean_all() -> int:
    """Make any missing clean copies. Safe to call repeatedly."""
    made = 0
    for src in sorted(tools.IMAGES_DIR.glob("*.jpg")):
        dst = CLEAN_DIR / src.name
        if not dst.exists():
            if clean_photo(src, dst):
                made += 1
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())  # already white: keep an identical copy
    return made


def start_background_cleaning() -> None:
    threading.Thread(target=clean_all, name="clean-photos", daemon=True).start()


def photo_path(name: str) -> Path | None:
    """Clean copy if ready, else the original. Only bare file names from data/products are allowed."""
    if "/" in name or "\\" in name or ".." in name or not name.endswith(".jpg"):
        return None
    for folder in (CLEAN_DIR, tools.IMAGES_DIR):
        p = folder / name
        if p.is_file():
            return p
    return None
