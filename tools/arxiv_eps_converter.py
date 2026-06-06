#!/usr/bin/env python3
"""
Convert EPS figures in arXiv source directories to PNG for agent consumption.

Many arXiv papers include figures as .eps files, which vision-enabled agents
cannot read directly. This script finds all EPS files and converts them to
high-resolution PNGs in the same directory.

Usage:
    python3 tools/arxiv_eps_converter.py literature-deep/paper_2301.07041/2301.07041_src/
    python3 tools/arxiv_eps_converter.py literature-deep/paper_2301.07041/2301.07041_src/ --dpi 300 --dry-run

Dependencies (one of the following):
    - Ghostscript (gs)  [preferred]
    - ImageMagick (convert)
    - Python Pillow (with ghostscript backend)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def has_ghostscript() -> bool:
    return shutil.which("gs") is not None


def has_imagemagick() -> bool:
    return shutil.which("convert") is not None


def has_pillow() -> bool:
    try:
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def convert_with_ghostscript(eps_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Convert EPS to PNG using Ghostscript."""
    cmd = [
        "gs",
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dEPSCrop",
        f"-r{dpi}",
        "-sDEVICE=png16m",
        f"-sOutputFile={png_path}",
        str(eps_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Ghostscript failed for {eps_path.name}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def convert_with_imagemagick(eps_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Convert EPS to PNG using ImageMagick."""
    cmd = [
        "convert",
        "-density", str(dpi),
        str(eps_path),
        "-flatten",
        str(png_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ImageMagick failed for {eps_path.name}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def convert_with_pillow(eps_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Convert EPS to PNG using Python Pillow."""
    try:
        from PIL import Image
        with Image.open(str(eps_path)) as img:
            # Pillow reads EPS via ghostscript internally; set resolution
            img.load(scale=dpi // 72)  # EPS default is 72 DPI
            img.save(str(png_path), "PNG")
        return True
    except Exception as exc:
        print(f"  Pillow failed for {eps_path.name}: {exc}", file=sys.stderr)
        return False


def convert_eps(eps_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Try multiple methods to convert a single EPS file to PNG."""
    if png_path.exists():
        # Skip if already converted and newer than source
        if png_path.stat().st_mtime >= eps_path.stat().st_mtime:
            return True

    methods = []
    if has_ghostscript():
        methods.append(("Ghostscript", convert_with_ghostscript))
    if has_imagemagick():
        methods.append(("ImageMagick", convert_with_imagemagick))
    if has_pillow():
        methods.append(("Pillow", convert_with_pillow))

    if not methods:
        print(
            "ERROR: No EPS conversion backend found. "
            "Install Ghostscript (gs), ImageMagick (convert), or Python Pillow.",
            file=sys.stderr,
        )
        return False

    for name, func in methods:
        if func(eps_path, png_path, dpi):
            return True

    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert EPS figures to PNG for agent consumption.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("directory", help="Directory to scan for EPS files")
    parser.add_argument("--dpi", type=int, default=300, help="Output resolution in DPI (default: 300)")
    parser.add_argument("--recursive", action="store_true", default=True, help="Scan recursively")
    parser.add_argument("--dry-run", action="store_true", help="List files without converting")
    parser.add_argument("--delete-eps", action="store_true", help="Delete original EPS after conversion")

    args = parser.parse_args(argv)

    root = Path(args.directory)
    if not root.exists():
        print(f"ERROR: Directory not found: {root}", file=sys.stderr)
        return 1

    # Find all EPS files
    pattern = "**/*.eps" if args.recursive else "*.eps"
    eps_files = sorted(root.glob(pattern))

    if not eps_files:
        print(f"No EPS files found in {root}")
        return 0

    print(f"Found {len(eps_files)} EPS file(s) in {root}")

    if args.dry_run:
        for eps_path in eps_files:
            png_path = eps_path.with_suffix(".png")
            print(f"  Would convert: {eps_path.relative_to(root)} -> {png_path.relative_to(root)}")
        return 0

    success_count = 0
    fail_count = 0

    for eps_path in eps_files:
        png_path = eps_path.with_suffix(".png")
        rel_eps = eps_path.relative_to(root)
        rel_png = png_path.relative_to(root)

        print(f"  Converting: {rel_eps} -> {rel_png} ...", end=" ")

        if convert_eps(eps_path, png_path, args.dpi):
            print("OK")
            success_count += 1
            if args.delete_eps:
                try:
                    eps_path.unlink()
                except Exception as exc:
                    print(f"    (warn: could not delete {rel_eps}: {exc})")
        else:
            print("FAILED")
            fail_count += 1

    print(f"\nDone: {success_count} succeeded, {fail_count} failed.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
