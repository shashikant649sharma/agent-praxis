#!/usr/bin/env python3
"""
Prepare supplied artwork for the Agent Praxis site.

Takes the generated crest and plate images and converts them into what the
design system actually needs: single-colour ultramarine line art with an alpha
channel driven by ink density.

Why do it this way, rather than with CSS filters:

  * The source art is near-black line work on white. A CSS `screen` blend over
    ultramarine reproduces the toile look perfectly — but ONLY if the paper is
    an opaque white. If the PNG carries real alpha (lines only, no paper), the
    same blend renders the art invisible against the ultramarine ground. The
    correct CSS therefore depends on a property of the file we cannot rely on.

  * Baking the tint removes that dependency entirely. The output is ultramarine
    ink at alpha = ink density, so it composites correctly onto any ground,
    light or dark, with no blend mode at all.

It also auto-crops the plates. They are wide friezes sitting in the top ~60% of
a mostly-empty canvas; left alone, `object-fit: cover` would centre on the dead
white space and push the actual artwork out of frame.

Usage:
    python tools/prepare_assets.py --src website/assets --out website/assets/prepared
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required:  pip install Pillow")

# The single ink of the whole design system: Royal Ultramarine #1b2be6
ULTRAMARINE = (27, 43, 230)


def flatten_to_white(im: Image.Image) -> Image.Image:
    """Composite any alpha onto white so downstream maths sees one tone plane."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    return im.convert("RGB")


def content_bbox(gray: Image.Image, threshold: int = 244, pad_ratio: float = 0.015):
    """Bounding box of everything darker than `threshold`, plus a little air."""
    probe = gray.copy()
    probe.thumbnail((900, 900))
    mask = probe.point(lambda v: 255 if v < threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    sx = gray.width / probe.width
    sy = gray.height / probe.height
    left, top, right, bottom = (
        int(bbox[0] * sx), int(bbox[1] * sy), int(bbox[2] * sx), int(bbox[3] * sy)
    )
    pad_x = int(gray.width * pad_ratio)
    pad_y = int(gray.height * pad_ratio)
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(gray.width, right + pad_x),
        min(gray.height, bottom + pad_y),
    )


def to_ultramarine_ink(gray: Image.Image, contrast: float = 1.0, floor: int = 6) -> Image.Image:
    """
    Map a grey tone plane to ultramarine ink.

    alpha = how much ink is on the paper, i.e. darkness. White paper becomes
    fully transparent; a black line becomes fully opaque ultramarine; a
    half-tone engraving hatch becomes half-opaque ultramarine.
    """
    if contrast != 1.0:
        gray = gray.point(lambda v: max(0, min(255, int(128 + (v - 128) * contrast))))

    alpha = ImageOps.invert(gray)  # black ink -> 255, white paper -> 0
    if floor > 0:
        alpha = alpha.point(lambda v: 0 if v < floor else min(255, int((v - floor) * 255 / (255 - floor))))

    out = Image.new("RGBA", gray.size, ULTRAMARINE + (0,))
    out.putalpha(alpha)
    return out


def process(path: str, out_path: str, *, max_width: int, crop: bool,
            contrast: float, pad_ratio: float, floor: int) -> dict:
    src = Image.open(path)
    original = (src.width, src.height, src.mode)

    rgb = flatten_to_white(src)
    gray = ImageOps.autocontrast(rgb.convert("L"), cutoff=1)

    if crop:
        box = content_bbox(gray, pad_ratio=pad_ratio)
        if box:
            gray = gray.crop(box)

    if max_width and gray.width > max_width:
        h = round(gray.height * max_width / gray.width)
        gray = gray.resize((max_width, h), Image.LANCZOS)

    rgba = to_ultramarine_ink(gray, contrast=contrast, floor=floor)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rgba.save(out_path, "PNG", optimize=True)

    return {
        "src": path,
        "out": out_path,
        "was": original,
        "now": (rgba.width, rgba.height),
        "in_kb": os.path.getsize(path) / 1024,
        "out_kb": os.path.getsize(out_path) / 1024,
    }


JOBS = [
    # Crest: Temple seal
    dict(key="crest", match="Minimalist Classical Temple Icon.png",
         out="crest.png", max_width=512, crop=False, contrast=1.12, pad_ratio=0.0, floor=8),

    # The labyrinth mark
    dict(key="mark", match="logo2.png",
         out="mark-labyrinth.png", max_width=768, crop=False, contrast=1.06, pad_ratio=0.0, floor=6),

    # Large backdrop friezes
    dict(key="plate-hero", match="Scholarly Clockwork and Celestial Still Life.png",
         out="plate-hero.png", max_width=2400, crop=True, contrast=1.18, pad_ratio=0.02, floor=10),

    dict(key="plate-arenas", match="Renaissance Library Terrace and Labyrinth Garden.png",
         out="plate-arenas.png", max_width=2400, crop=True, contrast=1.18, pad_ratio=0.02, floor=10),

    # Bespoke Environment Engravings
    dict(key="arena-1984", match="All-Seeing Eye Over Censored Ledger.png",
         out="arena-1984.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),

    dict(key="arena-trial", match="The Paperwork Labyrinth Courthouse.png",
         out="arena-trial.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),

    dict(key="arena-dorian", match="Ornate Portrait and Rococo Mirror.png",
         out="arena-dorian.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),

    dict(key="arena-frankenstein", match="Victorian Automaton Laboratory Engraving.png",
         out="arena-frankenstein.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),

    dict(key="arena-catch22", match="Locked Spiral Bureaucracy.png",
         out="arena-catch22.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),

    dict(key="arena-metamorphosis", match="Insect Man at the Writing Desk.png",
         out="arena-metamorphosis.png", max_width=1200, crop=True, contrast=1.22, pad_ratio=0.015, floor=8),
]


def find_file(src_dirs: list[str], filename: str) -> str | None:
    for d in src_dirs:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="website/assets")
    ap.add_argument("--out", default="website/assets/prepared")
    args = ap.parse_args()

    search_dirs = [
        args.src,
        os.path.join(args.src, "arenas"),
        "new assests",
    ]

    rows = []
    for job in JOBS:
        path = find_file(search_dirs, job["match"])
        if not path:
            print(f"  skip  {job['match']}  (not found in {search_dirs})")
            continue
        out_path = os.path.join(args.out, job["out"])
        info = process(
            path, out_path,
            max_width=job["max_width"], crop=job["crop"],
            contrast=job["contrast"], pad_ratio=job["pad_ratio"], floor=job["floor"],
        )
        rows.append((job["key"], info))

    print()
    print(f"{'asset':10} {'source':>18} {'prepared':>14} {'ratio':>7} {'weight':>16}")
    print("-" * 72)
    for key, i in rows:
        w0, h0, m0 = i["was"]
        w1, h1 = i["now"]
        print(f"{key:10} {f'{w0}x{h0}':>18} {f'{w1}x{h1}':>14} "
              f"{w1 / h1:>6.2f}:1 {i['in_kb']:>7.0f} -> {i['out_kb']:.0f} KB")

    total_in = sum(i["in_kb"] for _, i in rows)
    total_out = sum(i["out_kb"] for _, i in rows)
    print("-" * 72)
    print(f"{'total':10} {'':>18} {'':>14} {'':>7} {total_in:>7.0f} -> {total_out:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
