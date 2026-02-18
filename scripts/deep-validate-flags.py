#!/usr/bin/env python3
"""
Deep validation of downloaded flag files.

Checks:
1. File integrity (magic bytes, size)
2. Detects state flags mistakenly assigned to municipalities
3. Detects national/foreign flags
4. Detects coat of arms (brasão) files
5. Finds duplicate files (same content, different names)
6. Cross-references with database
"""

import json
import os
import hashlib
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

# Known state flag SVG signatures (title or distinct content)
STATE_FLAG_TITLES = [
    "bandeira do acre", "bandeira de alagoas", "bandeira do amapá",
    "bandeira do amazonas", "bandeira da bahia", "bandeira do ceará",
    "bandeira do distrito federal", "bandeira do espírito santo",
    "bandeira de goiás", "bandeira do maranhão", "bandeira de mato grosso",
    "bandeira de mato grosso do sul", "bandeira de minas gerais",
    "bandeira do pará", "bandeira da paraíba", "bandeira do paraná",
    "bandeira de pernambuco", "bandeira do piauí",
    "bandeira do rio de janeiro", "bandeira do rio grande do norte",
    "bandeira do rio grande do sul", "bandeira de rondônia",
    "bandeira de roraima", "bandeira de santa catarina",
    "bandeira de são paulo", "bandeira de sergipe",
    "bandeira do tocantins",
]

# National/foreign flag indicators
NATIONAL_FLAG_INDICATORS = [
    "bandeira do brasil", "flag of brazil", "bandera de españa",
    "flag of portugal", "flag of france", "flag of the united states",
    "bandeira nacional",
]

# Coat of arms indicators
COAT_OF_ARMS_INDICATORS = [
    "brasão", "brasao", "coat of arms", "escudo", "seal", "selo",
]

MIN_FILE_SIZE = 200
HTML_INDICATORS = [b"<!DOCTYPE html", b"<html", b"404 Not Found", b"403 Forbidden", b"Access Denied"]


def file_hash(filepath: Path) -> str:
    """MD5 hash of file content."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def check_content(filepath: Path) -> dict:
    """Deep-check file content for quality issues."""
    issues = []
    size = filepath.stat().st_size
    ext = filepath.suffix.lower()

    with open(filepath, "rb") as f:
        header = f.read(2048)

    # Size check
    if size < MIN_FILE_SIZE:
        issues.append(f"too_small ({size}b)")

    # HTML error page check (for non-SVG)
    if ext != ".svg":
        header_lower = header.lower()
        for indicator in HTML_INDICATORS:
            if indicator.lower() in header_lower:
                issues.append("html_error_page")
                break

    # SVG/text content analysis
    if ext == ".svg" or size < 1000:
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore").lower()

            # Check for state flag titles
            for title in STATE_FLAG_TITLES:
                if title in text:
                    issues.append(f"state_flag ({title})")
                    break

            # Check for national/foreign flags
            for indicator in NATIONAL_FLAG_INDICATORS:
                if indicator in text:
                    issues.append(f"national_flag ({indicator})")
                    break

            # Note: coat of arms keywords in SVG content are NOT flagged as issues.
            # Many Brazilian municipality flags legitimately contain brasão/escudo elements.
            # Only filename-based coat of arms detection (below) flags actual brasão files.

            # SVG without <svg> tag
            if ext == ".svg" and "<svg" not in text:
                issues.append("invalid_svg (no <svg> tag)")

        except Exception:
            pass

    # Check filename for issues
    fname = filepath.name.lower()
    for indicator in COAT_OF_ARMS_INDICATORS:
        if indicator in fname:
            issues.append(f"filename_coat_of_arms ({indicator})")
            break

    return {
        "path": str(filepath.relative_to(RAW_FLAGS_DIR)),
        "size": size,
        "ext": ext,
        "issues": issues,
        "valid": len(issues) == 0,
    }


def main():
    print("=" * 60)
    print("  🔍 DEEP FLAG VALIDATION")
    print("=" * 60)

    if not RAW_FLAGS_DIR.exists():
        print("  No raw-flags directory!")
        return

    all_files = sorted(f for f in RAW_FLAGS_DIR.rglob("*") if f.is_file())
    print(f"\n  📂 {len(all_files)} files to validate")

    # Validate each file
    results = []
    for f in tqdm(all_files, desc="  Validating", unit="file"):
        results.append(check_content(f))

    # Find duplicates by hash
    print(f"\n  Checking for duplicates...")
    hashes = {}
    for f in tqdm(all_files, desc="  Hashing", unit="file"):
        h = file_hash(f)
        rel = str(f.relative_to(RAW_FLAGS_DIR))
        hashes.setdefault(h, []).append(rel)

    duplicates = {h: files for h, files in hashes.items() if len(files) > 1}

    # Categorize issues
    valid = [r for r in results if r["valid"]]
    invalid = [r for r in results if not r["valid"]]

    issue_types = {}
    for r in invalid:
        for issue in r["issues"]:
            category = issue.split(" (")[0]
            issue_types[category] = issue_types.get(category, 0) + 1

    # Cross-reference with database
    print(f"\n  Cross-referencing with database...")
    with open(DATA_DIR / "municipios.json") as f:
        municipios = json.load(f)

    db_found = {m["ibge_code"] for m in municipios if m["flag_status"] == "found"}
    files_by_code = {}
    for f in all_files:
        try:
            code = int(f.stem.split("-")[0])
            files_by_code.setdefault(code, []).append(str(f.relative_to(RAW_FLAGS_DIR)))
        except (ValueError, IndexError):
            pass

    # Files without DB entry
    orphan_files = []
    for code, files in files_by_code.items():
        if code not in db_found:
            orphan_files.extend(files)

    # DB entries without files
    missing_files = []
    for m in municipios:
        if m["flag_status"] == "found" and m["ibge_code"] not in files_by_code:
            missing_files.append(f"{m['name']} ({m['uf']}) - {m['ibge_code']}")

    # Summary
    print("\n" + "=" * 60)
    print("  📊 DEEP VALIDATION RESULTS")
    print("=" * 60)
    print(f"\n  FILE INTEGRITY:")
    print(f"    Total files:     {len(all_files):>5}")
    print(f"    ✅ Valid:         {len(valid):>5}  ({len(valid)/len(all_files)*100:.1f}%)")
    print(f"    ❌ Invalid:       {len(invalid):>5}  ({len(invalid)/len(all_files)*100:.1f}%)")

    if issue_types:
        print(f"\n  ISSUE BREAKDOWN:")
        for issue, count in sorted(issue_types.items(), key=lambda x: -x[1]):
            print(f"    {issue:30s} {count:>5}")

    print(f"\n  DUPLICATES:")
    print(f"    Duplicate groups: {len(duplicates):>5}")
    dup_files = sum(len(files) - 1 for files in duplicates.values())
    print(f"    Redundant files:  {dup_files:>5}")

    if duplicates:
        print(f"\n    Sample duplicates:")
        for h, files in list(duplicates.items())[:5]:
            print(f"      Hash {h[:8]}:")
            for f in files:
                print(f"        {f}")

    print(f"\n  DATABASE CROSS-REFERENCE:")
    print(f"    DB entries found:         {len(db_found):>5}")
    print(f"    Files with DB match:      {len(files_by_code):>5}")
    print(f"    Orphan files (no DB):     {len(orphan_files):>5}")
    print(f"    DB without file:          {len(missing_files):>5}")

    # File type breakdown
    ext_counts = {}
    ext_sizes = {}
    for r in results:
        ext_counts[r["ext"]] = ext_counts.get(r["ext"], 0) + 1
        ext_sizes[r["ext"]] = ext_sizes.get(r["ext"], 0) + r["size"]

    print(f"\n  FILE TYPES:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        mb = ext_sizes[ext] / (1024 * 1024)
        valid_count = sum(1 for r in valid if r["ext"] == ext)
        print(f"    {ext:8s} {count:>5} files  ({mb:>6.1f} MB)  {valid_count} valid")

    total_size = sum(r["size"] for r in results)
    print(f"\n  Total size: {total_size/(1024*1024):.1f} MB")

    # Save detailed report
    report = {
        "summary": {
            "total": len(all_files),
            "valid": len(valid),
            "invalid": len(invalid),
            "duplicate_groups": len(duplicates),
            "orphan_files": len(orphan_files),
            "db_without_file": len(missing_files),
        },
        "invalid_files": invalid,
        "duplicate_groups": [{"hash": h, "files": files} for h, files in list(duplicates.items())],
        "orphan_files": orphan_files[:50],
    }
    report_path = DATA_DIR / "validation-report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 Full report: {report_path}")

    # Cleanup recommendations
    if invalid:
        print(f"\n  🧹 CLEANUP RECOMMENDATIONS:")
        to_delete = []
        for r in invalid:
            to_delete.append(str(RAW_FLAGS_DIR / r["path"]))

        # Also add duplicate files (keep first, delete rest)
        for h, files in duplicates.items():
            for f in files[1:]:
                path = str(RAW_FLAGS_DIR / f)
                if path not in to_delete:
                    to_delete.append(path)

        print(f"    Files to delete: {len(to_delete)}")
        invalid_size = sum(r["size"] for r in invalid)
        print(f"    Space to free:   {invalid_size/1024:.1f} KB")

        # Save cleanup list
        cleanup_path = DATA_DIR / "cleanup-list.json"
        with open(cleanup_path, "w", encoding="utf-8") as f:
            json.dump(to_delete, f, ensure_ascii=False, indent=2)
        print(f"    Saved to: {cleanup_path}")
        print(f"\n    To execute cleanup, run:")
        print(f"    python3 -c \"import json,os; [os.remove(f) for f in json.load(open('data/cleanup-list.json')) if os.path.exists(f)]\"")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
