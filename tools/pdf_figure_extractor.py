#!/usr/bin/env python3
"""
Extract images from a PDF file, with optional figure/table page detection.

Used as a fallback when TeX source is unavailable (non-arXiv papers, etc.).

Usage:
    python3 pdf_figure_extractor.py <pdf_path> --output <output_dir>
    python3 pdf_figure_extractor.py <pdf_path> --output <output_dir> --pages-with-figures-only

Output JSON structure:
{
  "pdf_path": "papers/1234.56789.pdf",
  "total_pages": 12,
  "extracted_images": [
    {
      "filename": "1234.56789_p3_img1.png",
      "page": 3,
      "index": 1,
      "ext": "png",
      "width": 800,
      "height": 600,
      "size_bytes": 45000
    }
  ],
  "pages_with_figures": [3, 7, 9]
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def detect_figure_pages(pdf_path: str) -> list[int]:
    """Use PyMuPDF to detect pages likely containing figures/tables."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    figure_pages = set()
    keywords = [r"Figure\s+\d", r"Fig\.\s*\d", r"Table\s+\d", r"TABLE\s+\d"]
    pattern = re.compile("|".join(keywords))

    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            text = doc[page_num].get_text()
            if pattern.search(text):
                figure_pages.add(page_num + 1)  # 1-indexed
        doc.close()
    except Exception:
        pass

    return sorted(figure_pages)


def extract_images(pdf_path: str, output_dir: Path, pages_with_figures_only: bool = False) -> dict[str, Any]:
    """Extract embedded images from a PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF (fitz) is required. Install with: pip install pymupdf"
        )

    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = pdf_path_obj.stem

    figure_pages = detect_figure_pages(pdf_path)

    doc = fitz.open(pdf_path)
    extracted = []
    total_images = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_idx = page_num + 1

        if pages_with_figures_only and page_idx not in figure_pages:
            continue

        images = page.get_images(full=True)
        for img_idx, img in enumerate(images):
            xref = img[0]
            total_images += 1
            try:
                pix = fitz.Pixmap(doc, xref)
                # CMYK -> RGB conversion if needed
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                ext = "png"
                if pix.n == 1:  # grayscale
                    ext = "png"

                filename = f"{prefix}_p{page_idx}_img{img_idx + 1}.{ext}"
                out_path = output_dir / filename
                pix.save(str(out_path))
                pix = None  # free memory

                extracted.append({
                    "filename": filename,
                    "page": page_idx,
                    "index": img_idx + 1,
                    "ext": ext,
                    "width": pix.width if pix else 0,
                    "height": pix.height if pix else 0,
                    "size_bytes": out_path.stat().st_size,
                })
            except Exception as exc:
                print(f"Warning: failed to extract image on page {page_idx}, idx {img_idx}: {exc}", file=sys.stderr)

    doc.close()

    return {
        "pdf_path": str(pdf_path_obj.resolve()),
        "total_pages": len(doc) if 'doc' in dir() else 0,
        "extracted_images": extracted,
        "pages_with_figures": figure_pages,
        "total_embedded_images": total_images,
    }


def fallback_extract_with_pdftoppm(pdf_path: str, output_dir: Path, pages: list[int] | None = None) -> dict[str, Any]:
    """Fallback extraction using pdftoppm (poppler-utils) for specific pages."""
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = Path(pdf_path).stem
    extracted = []

    page_args = []
    if pages:
        page_args = ["-f", str(pages[0]), "-l", str(pages[-1])]

    cmd = [
        "pdftoppm", "-png", "-r", "200",
        *page_args,
        pdf_path,
        str(output_dir / f"{prefix}_page"),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            for f in sorted(output_dir.glob(f"{prefix}_page-*.png")):
                # Parse page number from filename: prefix_page-XXX.png
                match = re.search(rf"{re.escape(prefix)}_page-(\d+)\.png", f.name)
                page_num = int(match.group(1)) if match else 0
                extracted.append({
                    "filename": f.name,
                    "page": page_num,
                    "index": 1,
                    "ext": "png",
                    "width": 0,
                    "height": 0,
                    "size_bytes": f.stat().st_size,
                })
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"pdftoppm fallback failed: {exc}", file=sys.stderr)

    return {
        "pdf_path": pdf_path,
        "total_pages": 0,
        "extracted_images": extracted,
        "pages_with_figures": pages or [],
        "total_embedded_images": len(extracted),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract images from PDF files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for extracted images",
    )
    parser.add_argument(
        "--pages-with-figures-only",
        action="store_true",
        default=False,
        help="Only extract from pages containing 'Figure', 'Fig.', or 'Table' text",
    )
    parser.add_argument(
        "--fallback-only",
        action="store_true",
        default=False,
        help="Use pdftoppm fallback instead of PyMuPDF",
    )
    parser.add_argument(
        "--json", "-j",
        default=None,
        help="Write JSON metadata to this file (default: print to stdout)",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output)

    try:
        if args.fallback_only:
            pages = detect_figure_pages(args.pdf_path) if args.pages_with_figures_only else None
            result = fallback_extract_with_pdftoppm(args.pdf_path, output_dir, pages)
        else:
            try:
                result = extract_images(
                    args.pdf_path, output_dir,
                    pages_with_figures_only=args.pages_with_figures_only
                )
            except RuntimeError as exc:
                print(f"{exc}, trying fallback...", file=sys.stderr)
                pages = detect_figure_pages(args.pdf_path) if args.pages_with_figures_only else None
                result = fallback_extract_with_pdftoppm(args.pdf_path, output_dir, pages)

        if args.json:
            json_path = Path(args.json)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote {args.json}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
