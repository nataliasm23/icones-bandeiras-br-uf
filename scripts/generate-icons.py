#!/usr/bin/env python3
"""
Generate municipality flag icon set in 4 SVG styles + 8 PNG variants.

Output structure:
  dist/
    full/svg/{UF}/          300x200 viewBox
    rounded/svg/{UF}/       300x200, r=20 corners
    circle/svg/{UF}/        200x200, circular clip
    square-rounded/svg/{UF}/ 200x200, r=20 square clip
    full/png-200/{UF}/      300x200 PNG
    full/png-800/{UF}/      1200x800 PNG
    rounded/png-200/{UF}/   300x200 PNG (rounded)
    rounded/png-800/{UF}/   1200x800 PNG (rounded)
    circle/png-200/{UF}/    200x200 PNG
    circle/png-800/{UF}/    800x800 PNG
    square-rounded/png-200/{UF}/ 200x200 PNG
    square-rounded/png-800/{UF}/ 800x800 PNG

Usage:
  python3 scripts/generate-icons.py [--workers N] [--uf SP] [--skip-png] [--skip-svg]
"""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw
from tqdm import tqdm

# Allow very large images (some municipality flags are huge)
Image.MAX_IMAGE_PIXELS = None


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"
DIST_DIR = ROOT / "dist"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"

# ---------------------------------------------------------------------------
# SVG Templates
# ---------------------------------------------------------------------------
SVG_FULL = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 300 200" width="300" height="200">
  <image width="300" height="200" href="{data_uri}" preserveAspectRatio="xMidYMid slice"/>
</svg>"""

SVG_ROUNDED = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 300 200" width="300" height="200">
  <defs><clipPath id="r"><rect width="300" height="200" rx="20"/></clipPath></defs>
  <image width="300" height="200" href="{data_uri}" clip-path="url(#r)" preserveAspectRatio="xMidYMid slice"/>
</svg>"""

SVG_CIRCLE = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 200 200" width="200" height="200">
  <defs><clipPath id="c"><circle cx="100" cy="100" r="100"/></clipPath></defs>
  <image width="200" height="200" href="{data_uri}" clip-path="url(#c)" preserveAspectRatio="xMidYMid slice"/>
</svg>"""

SVG_SQUARE_ROUNDED = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 200 200" width="200" height="200">
  <defs><clipPath id="sr"><rect width="200" height="200" rx="20"/></clipPath></defs>
  <image width="200" height="200" href="{data_uri}" clip-path="url(#sr)" preserveAspectRatio="xMidYMid slice"/>
</svg>"""


# ---------------------------------------------------------------------------
# Style definitions: (template, width, height, suffix)
# ---------------------------------------------------------------------------
SVG_STYLES = {
    "full":            (SVG_FULL,            300, 200, "full"),
    "rounded":         (SVG_ROUNDED,         300, 200, "rounded"),
    "circle":          (SVG_CIRCLE,          200, 200, "circle"),
    "square-rounded":  (SVG_SQUARE_ROUNDED,  200, 200, "sq"),
}

# PNG sizes: (size_label, scale_factor_from_base)
# For 3:2 styles (full/rounded): base 300x200, large 1200x800
# For 1:1 styles (circle/square-rounded): base 200x200, large 800x800
PNG_SIZES = {
    "png-200": 1,    # base resolution
    "png-800": 4,    # 4x scale
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_municipios(filter_uf=None):
    """Load municipality data, optionally filtered by UF."""
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Only include entries with a local flag file
    result = [m for m in data if m.get("flag_local")]

    if filter_uf:
        result = [m for m in result if m["uf"] == filter_uf.upper()]

    return result


def svg_to_png(svg_path, output_path, width, height):
    """Convert SVG to PNG using rsvg-convert."""
    try:
        subprocess.run(
            [
                "rsvg-convert",
                "-w", str(width),
                "-h", str(height),
                "--keep-aspect-ratio",
                "-o", str(output_path),
                str(svg_path),
            ],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def raster_to_png_bytes(source_path, width, height):
    """Open any raster image and return resized PNG bytes."""
    with Image.open(source_path) as img:
        img = img.convert("RGBA")
        img = img.resize((width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def svg_source_to_png_bytes(source_path, width, height):
    """Convert SVG source to PNG bytes using rsvg-convert."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        success = svg_to_png(source_path, tmp_path, width, height)
        if success and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as f:
                return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return None


def to_base64_data_uri(png_bytes):
    """Convert PNG bytes to a base64 data URI."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def make_rounded_mask(size, radius):
    """Create a rounded rectangle alpha mask."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    return mask


def make_circle_mask(size):
    """Create a circular alpha mask."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, w, h], fill=255)
    return mask


def apply_mask(png_bytes, mask):
    """Apply an alpha mask to PNG image bytes, return new PNG bytes."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    # Resize mask to match image
    if mask.size != img.size:
        mask = mask.resize(img.size, Image.LANCZOS)
    # Apply mask to alpha channel
    r, g, b, a = img.split()
    img.putalpha(mask)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main processing for a single municipality
# ---------------------------------------------------------------------------
def process_municipality(mun, skip_svg=False, skip_png=False):
    """Process a single municipality flag into all output formats.

    Returns (ibge_code, success, error_msg)
    """
    ibge_code = mun["ibge_code"]
    slug = mun["slug"]
    uf = mun["uf"]
    flag_local = mun["flag_local"]

    source_path = DATA_DIR / flag_local
    if not source_path.exists():
        return (ibge_code, False, f"Source file not found: {source_path}")

    ext = source_path.suffix.lower()
    is_svg_source = ext == ".svg"

    # Step 1: Normalize source to two PNG buffers (3:2 and 1:1)
    try:
        if is_svg_source:
            png_full_bytes = svg_source_to_png_bytes(source_path, 300, 200)
            png_square_bytes = svg_source_to_png_bytes(source_path, 200, 200)
            if not png_full_bytes or not png_square_bytes:
                # Fallback: try opening as raster (some .svg are actually raster)
                png_full_bytes = raster_to_png_bytes(source_path, 300, 200)
                png_square_bytes = raster_to_png_bytes(source_path, 200, 200)
        else:
            png_full_bytes = raster_to_png_bytes(source_path, 300, 200)
            png_square_bytes = raster_to_png_bytes(source_path, 200, 200)
    except Exception as e:
        return (ibge_code, False, f"Failed to normalize: {e}")

    # Step 2: Generate base64 data URIs
    data_uri_full = to_base64_data_uri(png_full_bytes)
    data_uri_square = to_base64_data_uri(png_square_bytes)

    # Step 3: Generate SVG files
    if not skip_svg:
        for style_name, (template, w, h, suffix) in SVG_STYLES.items():
            out_dir = DIST_DIR / style_name / "svg" / uf
            out_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{ibge_code}-{slug}-{suffix}.svg"
            out_path = out_dir / filename

            data_uri = data_uri_full if w == 300 else data_uri_square
            svg_content = template.format(data_uri=data_uri)

            out_path.write_text(svg_content, encoding="utf-8")

    # Step 4: Generate PNG files
    if not skip_png:
        # Pre-compute high-res PNG buffers for each style
        # full: 300x200 base, 1200x800 large
        # rounded: 300x200 base, 1200x800 large (with mask)
        # circle: 200x200 base, 800x800 large (with mask)
        # square-rounded: 200x200 base, 800x800 large (with mask)

        png_configs = {
            "full": {
                "png-200": (300, 200, None),
                "png-800": (1200, 800, None),
            },
            "rounded": {
                "png-200": (300, 200, "rounded"),
                "png-800": (1200, 800, "rounded"),
            },
            "circle": {
                "png-200": (200, 200, "circle"),
                "png-800": (800, 800, "circle"),
            },
            "square-rounded": {
                "png-200": (200, 200, "rounded"),
                "png-800": (800, 800, "rounded"),
            },
        }

        suffix_map = {
            "full": "full",
            "rounded": "rounded",
            "circle": "circle",
            "square-rounded": "sq",
        }

        for style_name, sizes in png_configs.items():
            suffix = suffix_map[style_name]

            for size_label, (w, h, mask_type) in sizes.items():
                out_dir = DIST_DIR / style_name / size_label / uf
                out_dir.mkdir(parents=True, exist_ok=True)

                filename = f"{ibge_code}-{slug}-{suffix}.png"
                out_path = out_dir / filename

                # Generate the sized PNG
                try:
                    if is_svg_source:
                        sized_bytes = svg_source_to_png_bytes(source_path, w, h)
                        if not sized_bytes:
                            sized_bytes = raster_to_png_bytes(source_path, w, h)
                    else:
                        sized_bytes = raster_to_png_bytes(source_path, w, h)

                    # Apply mask if needed
                    if mask_type == "rounded":
                        # Scale radius proportionally
                        base_size = 200 if w == h else 300
                        radius = int(20 * w / base_size)
                        mask = make_rounded_mask((w, h), radius)
                        sized_bytes = apply_mask(sized_bytes, mask)
                    elif mask_type == "circle":
                        mask = make_circle_mask((w, h))
                        sized_bytes = apply_mask(sized_bytes, mask)

                    out_path.write_bytes(sized_bytes)
                except Exception as e:
                    return (ibge_code, False, f"PNG generation failed ({style_name}/{size_label}): {e}")

    return (ibge_code, True, None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate municipality flag icon set"
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--uf", type=str, default=None,
        help="Process only a specific UF (e.g., SP)"
    )
    parser.add_argument(
        "--skip-png", action="store_true",
        help="Skip PNG generation (SVG only)"
    )
    parser.add_argument(
        "--skip-svg", action="store_true",
        help="Skip SVG generation (PNG only)"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Process only first N municipalities (for testing)"
    )
    args = parser.parse_args()

    print(f"Loading municipality data from {MUNICIPIOS_JSON}...")
    municipios = load_municipios(filter_uf=args.uf)

    if args.limit > 0:
        municipios = municipios[:args.limit]

    total = len(municipios)
    print(f"Processing {total} municipalities with flags...")

    if args.skip_svg:
        print("  SVG generation: SKIPPED")
    else:
        print("  SVG generation: 4 styles (full, rounded, circle, square-rounded)")

    if args.skip_png:
        print("  PNG generation: SKIPPED")
    else:
        print("  PNG generation: 4 styles x 2 sizes = 8 variants")

    print(f"  Workers: {args.workers}")
    print(f"  Output: {DIST_DIR}")
    print()

    successes = 0
    failures = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_municipality, mun,
                skip_svg=args.skip_svg,
                skip_png=args.skip_png,
            ): mun
            for mun in municipios
        }

        with tqdm(total=total, desc="Generating icons", unit="flag") as pbar:
            for future in as_completed(futures):
                ibge_code, success, error_msg = future.result()
                if success:
                    successes += 1
                else:
                    failures.append((ibge_code, error_msg))
                pbar.update(1)

    # Summary
    print()
    print(f"Done! {successes}/{total} flags processed successfully.")

    if failures:
        print(f"\n{len(failures)} failures:")
        for code, msg in failures[:20]:
            print(f"  {code}: {msg}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")

    # Count output files
    if not args.skip_svg:
        svg_count = sum(1 for _ in DIST_DIR.rglob("*.svg")
                       if any(p.name in [str(m["uf"]) for m in municipios]
                              for p in _.parents))
        print(f"\nSVG files generated: ~{svg_count}")

    if not args.skip_png:
        png_count = sum(1 for _ in DIST_DIR.rglob("*.png"))
        print(f"PNG files generated: ~{png_count}")


if __name__ == "__main__":
    main()
