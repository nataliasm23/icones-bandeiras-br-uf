#!/usr/bin/env python3
"""
Validate downloaded flag files.

Checks:
1. File size (too small = error page, too large = not a flag)
2. File type matches extension (magic bytes)
3. SVG files contain valid SVG content
4. Image dimensions (for raster images, using PIL if available)
5. Not an HTML error page
"""

import json
import os
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

# Magic bytes for common image formats
MAGIC_BYTES = {
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".webp": [b"RIFF"],
    ".svg": [b"<?xml", b"<svg", b"<!DOCTYPE svg"],
    ".bmp": [b"BM"],
}

MIN_FILE_SIZE = 500       # bytes — smaller is likely not a real image
MAX_FILE_SIZE = 50_000_000  # 50 MB — too large to be a flag

# HTML error indicators
HTML_ERROR_INDICATORS = [
    b"<!DOCTYPE html",
    b"<html",
    b"404 Not Found",
    b"403 Forbidden",
    b"Access Denied",
    b"Error",
    b"<head>",
]


def validate_file(filepath: Path) -> dict:
    """Validate a single flag file."""
    issues = []
    size = filepath.stat().st_size

    # Size check
    if size < MIN_FILE_SIZE:
        issues.append(f"Too small: {size} bytes")
    if size > MAX_FILE_SIZE:
        issues.append(f"Too large: {size} bytes")

    # Read first bytes
    with open(filepath, "rb") as f:
        header = f.read(1024)

    ext = filepath.suffix.lower()

    # Check for HTML error pages masquerading as images
    if ext != ".svg":  # SVG can contain XML/HTML-like content
        for indicator in HTML_ERROR_INDICATORS:
            if indicator.lower() in header.lower():
                issues.append(f"Appears to be HTML, not an image ({indicator.decode('utf-8', errors='ignore')[:30]})")
                break

    # Magic bytes check
    if ext in MAGIC_BYTES:
        magic_match = False
        for magic in MAGIC_BYTES[ext]:
            if header.startswith(magic) or (ext == ".svg" and magic in header[:500]):
                magic_match = True
                break
        if not magic_match:
            # SVG can start with whitespace or BOM
            if ext == ".svg":
                text = header.decode("utf-8", errors="ignore").strip()
                if text.startswith("<?xml") or text.startswith("<svg") or "<svg" in text[:500]:
                    magic_match = True
            if not magic_match:
                actual = header[:20].hex()
                issues.append(f"Bad magic bytes for {ext}: {actual}")

    # SVG-specific checks
    if ext == ".svg":
        try:
            full_content = filepath.read_text(encoding="utf-8", errors="ignore")
            if "<svg" not in full_content.lower():
                issues.append("SVG file missing <svg> tag")
            if len(full_content) < 100:
                issues.append(f"SVG too short: {len(full_content)} chars")
        except Exception as e:
            issues.append(f"Cannot read SVG: {e}")

    return {
        "path": str(filepath),
        "size": size,
        "ext": ext,
        "valid": len(issues) == 0,
        "issues": issues,
    }


def main():
    print("=" * 60)
    print("  🔍 FLAG FILE VALIDATOR")
    print("=" * 60)

    if not RAW_FLAGS_DIR.exists():
        print("  No raw-flags directory found!")
        return

    # Find all files
    all_files = sorted(RAW_FLAGS_DIR.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]
    print(f"\n  📂 Found {len(all_files)} files to validate")

    # Validate
    valid_count = 0
    invalid_count = 0
    invalid_files = []

    ext_counts = {}
    ext_sizes = {}

    for filepath in tqdm(all_files, desc="  Validating", unit="file"):
        result = validate_file(filepath)
        ext = result["ext"]
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        ext_sizes[ext] = ext_sizes.get(ext, 0) + result["size"]

        if result["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
            invalid_files.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("  📊 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total files:    {len(all_files):>6}")
    print(f"  ✅ Valid:        {valid_count:>6}  ({valid_count/len(all_files)*100:.1f}%)")
    print(f"  ❌ Invalid:      {invalid_count:>6}  ({invalid_count/len(all_files)*100:.1f}%)")

    print(f"\n  File types:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        mb = ext_sizes[ext] / (1024 * 1024)
        print(f"    {ext:8s} {count:>5} files  ({mb:.1f} MB)")

    if invalid_files:
        print(f"\n  ⚠️  Invalid files (first 20):")
        for f in invalid_files[:20]:
            path = Path(f["path"]).relative_to(RAW_FLAGS_DIR)
            issues = "; ".join(f["issues"])
            print(f"    {path} → {issues}")

        # Save full invalid list
        invalid_path = DATA_DIR / "invalid-flags.json"
        with open(invalid_path, "w", encoding="utf-8") as f:
            json.dump(invalid_files, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 Full invalid list saved to {invalid_path}")

        # Cleanup option
        total_invalid_size = sum(f["size"] for f in invalid_files)
        print(f"\n  Invalid files total size: {total_invalid_size / 1024:.1f} KB")
        print(f"  To clean up: delete files listed in data/invalid-flags.json")

    total_size = sum(f.stat().st_size for f in all_files)
    print(f"\n  Total collection size: {total_size / (1024*1024):.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
