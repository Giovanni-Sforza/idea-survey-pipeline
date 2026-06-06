#!/usr/bin/env python3
"""
Unified image preprocessor for idea-survey pipeline.
Converts various image formats to PNG and downsamples oversized images.

Workflow: Type conversion -> Size detection -> Compression

Supported input formats: eps, pdf, png, jpg, jpeg, tiff, bmp, gif
Output format: png (uniform)

Usage:
    python3 tools/image_preprocessor.py literature-deep/paper_xxx/figures/ --max-dimension 1536 --max-filesize-mb 2
    python3 tools/image_preprocessor.py literature-deep/paper_xxx/ --recursive --max-dimension 2048 --delete-originals

Dependencies:
    - Python Pillow (pip install Pillow)
    - Ghostscript (gs) or ImageMagick (convert) for EPS/PDF conversion
    - Optional: pdftoppm (poppler) or pdf2image for PDF conversion
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


SUPPORTED_INPUTS = {".eps", ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}


def has_ghostscript() -> bool:
    return shutil.which("gs") is not None


def has_imagemagick() -> bool:
    return shutil.which("convert") is not None


def has_pdftoppm() -> bool:
    return shutil.which("pdftoppm") is not None


def convert_eps_to_png(eps_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Convert EPS to PNG using Ghostscript or ImageMagick."""
    if has_ghostscript():
        cmd = [
            "gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop",
            f"-r{dpi}", "-sDEVICE=png16m", f"-sOutputFile={png_path}",
            str(eps_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True

    if has_imagemagick():
        cmd = ["convert", "-density", str(dpi), str(eps_path), "-flatten", str(png_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True

    if HAS_PILLOW:
        try:
            with Image.open(str(eps_path)) as img:
                img.load(scale=max(1, dpi // 72))
                img.save(str(png_path), "PNG")
            return True
        except Exception:
            pass

    return False


def convert_pdf_to_png(pdf_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Convert PDF to PNG (first page only for figures)."""
    if has_pdftoppm():
        stem = png_path.stem
        out_dir = png_path.parent
        cmd = [
            "pdftoppm", "-png", "-r", str(dpi), "-f", "1", "-l", "1",
            str(pdf_path), str(out_dir / stem)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            expected = out_dir / f"{stem}-1.png"
            if expected.exists():
                expected.rename(png_path)
                return True

    if has_imagemagick():
        cmd = ["convert", "-density", str(dpi), f"{pdf_path}[0]", "-flatten", str(png_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True

    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=dpi)
        if images:
            images[0].save(str(png_path), "PNG")
            return True
    except Exception:
        pass

    return False


def convert_other_to_png(src_path: Path, png_path: Path) -> bool:
    """Convert TIFF/BMP/GIF/JPG to PNG using Pillow."""
    if not HAS_PILLOW:
        return False
    try:
        with Image.open(str(src_path)) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(str(png_path), "PNG")
        return True
    except Exception as exc:
        print(f"  Pillow conversion failed: {exc}", file=sys.stderr)
        return False


def downsample_image(img_path: Path, max_dimension: int, max_filesize_mb: float) -> bool:
    """
    Downsample an image if it exceeds dimension or filesize thresholds.
    Returns True if the image is acceptable (either already okay or successfully resized).
    """
    if not HAS_PILLOW:
        return True

    try:
        filesize_mb = img_path.stat().st_size / (1024 * 1024)

        with Image.open(str(img_path)) as img:
            width, height = img.size

            needs_resize = max(width, height) > max_dimension
            needs_compress = filesize_mb > max_filesize_mb

            if not needs_resize and not needs_compress:
                return True

            if needs_resize:
                ratio = min(max_dimension / width, max_dimension / height, 1.0)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
            else:
                new_width, new_height = width, height

            resized = img.resize((new_width, new_height), Image.LANCZOS)

            if resized.mode in ("RGBA", "P"):
                resized = resized.convert("RGBA")
            elif resized.mode != "RGB":
                resized = resized.convert("RGB")

            resized.save(str(img_path), "PNG", optimize=True)

            new_size = img_path.stat().st_size / (1024 * 1024)
            action = []
            if needs_resize:
                action.append(f"{width}x{height} -> {new_width}x{new_height}")
            if needs_compress:
                action.append(f"{filesize_mb:.1f}MB -> {new_size:.1f}MB")
            print(f"    Downsampled: {img_path.name} ({', '.join(action)})")
            return True

    except Exception as exc:
        print(f"  Downsample failed for {img_path.name}: {exc}", file=sys.stderr)
        return False


def process_image(src_path: Path, output_dir: Path, max_dimension: int, max_filesize_mb: float, dpi: int = 300) -> bool:
    """Full pipeline: convert (if needed) -> downsample -> validate."""
    suffix = src_path.suffix.lower()

    if suffix not in SUPPORTED_INPUTS:
        return True

    if suffix == ".png":
        png_path = output_dir / src_path.name
    else:
        png_path = output_dir / (src_path.stem + ".png")

    if png_path.exists() and png_path.stat().st_mtime >= src_path.stat().st_mtime:
        return downsample_image(png_path, max_dimension, max_filesize_mb)

    needs_conversion = suffix in {".eps", ".pdf", ".tiff", ".tif", ".bmp", ".gif", ".jpg", ".jpeg"}

    if needs_conversion:
        print(f"  Converting: {src_path.name} -> {png_path.name} ...", end=" ")

        if suffix == ".eps":
            success = convert_eps_to_png(src_path, png_path, dpi)
        elif suffix == ".pdf":
            success = convert_pdf_to_png(src_path, png_path, dpi)
        else:
            success = convert_other_to_png(src_path, png_path)

        if not success:
            print("FAILED")
            return False
        print("OK")
    elif suffix == ".png":
        if src_path.parent != output_dir:
            shutil.copy2(str(src_path), str(png_path))

    if png_path.exists():
        downsample_image(png_path, max_dimension, max_filesize_mb)

    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preprocess images for agent consumption: convert formats + downsample oversized images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("directory", help="Directory to scan for images")
    parser.add_argument(
        "--max-dimension", type=int, default=1536,
        help="Max pixel dimension (width or height). Images larger than this will be downsampled. Default: 1536"
    )
    parser.add_argument(
        "--max-filesize-mb", type=float, default=2.0,
        help="Max file size in MB. Images larger than this will be compressed. Default: 2.0"
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="DPI for vector format conversion (EPS/PDF). Default: 300"
    )
    parser.add_argument(
        "--recursive", action="store_true", default=True,
        help="Scan recursively. Default: True"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would be done without modifying files"
    )
    parser.add_argument(
        "--delete-originals", action="store_true",
        help="Delete original non-PNG files after conversion"
    )

    args = parser.parse_args(argv)

    root = Path(args.directory)
    if not root.exists():
        print(f"ERROR: Directory not found: {root}", file=sys.stderr)
        return 1

    pattern = "**/*" if args.recursive else "*"
    image_files = []
    for ext in SUPPORTED_INPUTS:
        image_files.extend(root.glob(pattern + ext))
        image_files.extend(root.glob(pattern + ext.upper()))

    image_files = sorted(set(image_files))

    if not image_files:
        print(f"No supported image files found in {root}")
        return 0

    print(f"Found {len(image_files)} image file(s) in {root}")
    print(f"Settings: max_dimension={args.max_dimension}px, max_filesize={args.max_filesize_mb}MB, dpi={args.dpi}")

    if args.dry_run:
        for img_path in image_files:
            rel = img_path.relative_to(root)
            suffix = img_path.suffix.lower()
            if suffix == ".png":
                print(f"  Would check/downsample: {rel}")
            else:
                print(f"  Would convert: {rel} -> {img_path.stem}.png")
        return 0

    success_count = 0
    fail_count = 0
    converted_count = 0

    for img_path in image_files:
        suffix = img_path.suffix.lower()
        output_dir = img_path.parent

        if process_image(img_path, output_dir, args.max_dimension, args.max_filesize_mb, args.dpi):
            success_count += 1
            if suffix != ".png":
                converted_count += 1
            if args.delete_originals and suffix != ".png" and img_path.exists():
                try:
                    img_path.unlink()
                except Exception as exc:
                    print(f"  Warn: could not delete {img_path.name}: {exc}")
        else:
            fail_count += 1

    # Update figure_manifest.json image_stats if present (reflects post-processed sizes)
    manifest_path = root / "figure_manifest.json"
    if manifest_path.exists():
        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            total_bytes = 0
            max_single_bytes = 0
            image_count = 0
            figures_dir = root / "figures"
            if figures_dir.exists():
                for p in figures_dir.iterdir():
                    if p.is_file():
                        sz = p.stat().st_size
                        total_bytes += sz
                        if sz > max_single_bytes:
                            max_single_bytes = sz
                        image_count += 1
            manifest["image_stats"] = {
                "total_bytes": total_bytes,
                "max_single_bytes": max_single_bytes,
                "count": image_count,
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Updated image_stats in {manifest_path}")
        except Exception as exc:
            print(f"  Warn: could not update figure_manifest.json: {exc}", file=sys.stderr)

    print(f"\nDone: {success_count} succeeded, {fail_count} failed.")
    print(f"Converted: {converted_count} files. Oversized images were downsampled to max {args.max_dimension}px.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
