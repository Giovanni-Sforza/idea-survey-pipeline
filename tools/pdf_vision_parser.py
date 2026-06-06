#!/usr/bin/env python3
"""
Vision-LLM PDF parser — third PDF backend alongside MinerU (`pdf_full_parser.py`)
and the image-only legacy (`pdf_figure_extractor.py`).

Design intent
-------------
MinerU is the highest-fidelity option but unusable on low-spec laptops: it
downloads ~5 GB of model weights and pegs every CPU core for ~30 s/page.  The
legacy extractor is cheap but degenerate (no captions, no tables, no equations).

The vision path splits the work in two:

  1. This script does the cheap mechanical part: render every PDF page to PNG
     with PyMuPDF, extract embedded raster images, and emit a `vision_stub.json`
     describing what is on disk.  No LLM calls happen here.

  2. A vision-capable subagent (Kimi K2.5, Claude with vision, etc.) consumes
     `vision_stub.json`, reads each page PNG via `ReadMediaFile`, and writes
     `vision_extraction.json` containing the structured figures / tables /
     equations identified across the document.

  3. This script's `finalize` subcommand stitches the subagent's extraction
     into a `figure_manifest.json` whose schema is byte-for-byte compatible
     with `pdf_full_parser.py`, so the downstream `paper-analyzer` subagent
     and the `research-proposal` skill see no difference between backends.

Caption provenance ladder (kept compatible with `pdf_full_parser`):

    mineru_native       — only emitted by pdf_full_parser
    vision_llm          — NEW: caption identified by the vision subagent
    heuristic_adjacent  — only emitted by pdf_full_parser
    heuristic_local     — only emitted by pdf_full_parser
    missing             — caption was not recoverable

Usage
-----
    # Stage 1 — render + extract embedded images (fast, local, no LLM)
    python3 pdf_vision_parser.py render \\
        --pdf path/to/paper.pdf \\
        --output-dir literature-deep/paper_xxx/ \\
        --dpi 200

    # Subagent now reads vision_stub.json and writes vision_extraction.json …

    # Stage 2 — assemble the final manifest from the extraction
    python3 pdf_vision_parser.py finalize \\
        --output-dir literature-deep/paper_xxx/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

DEFAULT_RENDER_DPI = 200          # 200 DPI is the sweet spot for vision OCR
MIN_EMBED_IMG_BYTES = 4096        # below ~4 KB it's almost always a logo / glyph
PAGE_PNG_PREFIX = "page_"         # page_001.png, page_002.png, …
EMBED_PNG_PREFIX = "embed_"       # embed_p01_001.png, …
VISION_STUB_FILENAME = "vision_stub.json"
VISION_EXTRACTION_FILENAME = "vision_extraction.json"
MANIFEST_FILENAME = "figure_manifest.json"
PARSE_LOG_FILENAME = "parse_log.json"
PAGES_SUBDIR = "vision_pages"     # rendered page images (kept separate from figures/)
EMBED_SUBDIR = "vision_embedded"  # all embedded raster images extracted from the PDF


# ---------------------------------------------------------------------------
# Stage 1: render
# ---------------------------------------------------------------------------

def render_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = DEFAULT_RENDER_DPI,
) -> dict[str, Any]:
    """Render every page of the PDF to PNG and extract embedded raster images.

    Returns the stub dict (also written to output_dir/vision_stub.json).
    """
    try:
        import fitz  # type: ignore  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF (`fitz`) is required for pdf_vision_parser. "
            "Install with `pip install PyMuPDF`."
        ) from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / PAGES_SUBDIR
    embed_dir = output_dir / EMBED_SUBDIR
    pages_dir.mkdir(parents=True, exist_ok=True)
    embed_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    pages_meta: list[dict[str, Any]] = []
    embed_meta: list[dict[str, Any]] = []

    for page_idx, page in enumerate(doc, start=1):
        # 1) Page image (always rendered, even if blank — keeps numbering stable)
        page_filename = f"{PAGE_PNG_PREFIX}{page_idx:03d}.png"
        page_out = pages_dir / page_filename
        try:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(str(page_out))
            page_bytes = page_out.stat().st_size
        except Exception as exc:
            print(f"  [render] page {page_idx} failed: {exc}", file=sys.stderr)
            page_bytes = 0

        pages_meta.append({
            "page": page_idx,
            "path": f"{PAGES_SUBDIR}/{page_filename}",
            "bytes": page_bytes,
            "dpi": dpi,
        })

        # 2) Embedded raster images (high-resolution originals — preferred for figures)
        embed_idx_on_page = 0
        try:
            image_list = page.get_images(full=True)
        except Exception as exc:
            print(f"  [render] page {page_idx} get_images failed: {exc}", file=sys.stderr)
            image_list = []

        for img_info in image_list:
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                img_bytes = base.get("image")
                ext = base.get("ext", "png").lower()
            except Exception as exc:
                print(
                    f"  [render] extract_image xref={xref} on page {page_idx} failed: {exc}",
                    file=sys.stderr,
                )
                continue
            if not img_bytes or len(img_bytes) < MIN_EMBED_IMG_BYTES:
                continue
            # Normalize to .png filename even if the underlying bytes are jpg/jpeg —
            # downstream image_preprocessor.py handles the conversion at the figures/
            # stage.  Here we keep the original bytes verbatim.
            embed_idx_on_page += 1
            embed_filename = f"{EMBED_PNG_PREFIX}p{page_idx:02d}_{embed_idx_on_page:03d}.{ext}"
            embed_out = embed_dir / embed_filename
            try:
                embed_out.write_bytes(img_bytes)
            except Exception as exc:
                print(f"  [render] write {embed_out} failed: {exc}", file=sys.stderr)
                continue

            embed_meta.append({
                "embed_id": f"p{page_idx:02d}_{embed_idx_on_page:03d}",
                "page": page_idx,
                "path": f"{EMBED_SUBDIR}/{embed_filename}",
                "bytes": embed_out.stat().st_size,
                "ext": ext,
            })

    doc.close()

    stub = {
        "schema_version": 1,
        "source_kind": "pdf-vision",
        "pdf_path": str(pdf_path),
        "render_dpi": dpi,
        "pages_dir": PAGES_SUBDIR,
        "embedded_dir": EMBED_SUBDIR,
        "page_count": len(pages_meta),
        "pages": pages_meta,
        "embedded_images": embed_meta,
        # Empty placeholders for the subagent to fill in:
        "extraction_status": "pending",
    }

    stub_path = output_dir / VISION_STUB_FILENAME
    stub_path.write_text(
        json.dumps(stub, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return stub


# ---------------------------------------------------------------------------
# Stage 2: finalize
# ---------------------------------------------------------------------------

VALID_PROVENANCE = {"vision_llm", "heuristic_local", "missing"}


def _validate_extraction(extraction: dict[str, Any]) -> list[str]:
    """Return a list of human-readable schema errors (empty list = OK)."""
    errors: list[str] = []
    for key in ("figures", "tables", "equations"):
        if key not in extraction:
            errors.append(f"missing top-level key: {key!r}")
        elif not isinstance(extraction[key], list):
            errors.append(f"{key} must be a list, got {type(extraction[key]).__name__}")
    return errors


def _safe_get(obj: dict[str, Any], key: str, default: Any = None) -> Any:
    val = obj.get(key, default)
    return default if val is None else val


def finalize(
    output_dir: Path,
    extraction_path: Path | None = None,
    stub_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble figure_manifest.json + parse_log.json from a vision extraction.

    Inputs (all under output_dir unless overridden):
      - vision_stub.json     (produced by `render`)
      - vision_extraction.json (produced by the vision subagent)

    Outputs:
      - figure_manifest.json (schema-compatible with pdf_full_parser)
      - parse_log.json       (audit trail of caption_provenance != mineru_native)
      - figures/             (chosen embedded images copied in with deterministic names)
    """
    output_dir = Path(output_dir)
    stub_path = stub_path or (output_dir / VISION_STUB_FILENAME)
    extraction_path = extraction_path or (output_dir / VISION_EXTRACTION_FILENAME)

    if not stub_path.exists():
        raise FileNotFoundError(f"Missing {stub_path}; run `render` first.")
    if not extraction_path.exists():
        raise FileNotFoundError(
            f"Missing {extraction_path}; the vision subagent must produce it "
            f"before calling `finalize`."
        )

    stub = json.loads(stub_path.read_text(encoding="utf-8"))
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))

    errors = _validate_extraction(extraction)
    if errors:
        raise ValueError("vision_extraction.json schema errors: " + "; ".join(errors))

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Index embedded images by embed_id for fast lookup
    embed_by_id: dict[str, dict[str, Any]] = {
        e["embed_id"]: e for e in stub.get("embedded_images", [])
    }

    parse_log: list[dict[str, Any]] = []

    # -------- figures --------
    figures: list[dict[str, Any]] = []
    used_embed_ids: set[str] = set()
    for i, fig in enumerate(extraction.get("figures", []), start=1):
        label = _safe_get(fig, "label", f"fig{i}")
        caption = _safe_get(fig, "caption", None)
        page = fig.get("page")
        embed_id = fig.get("embed_id")
        provenance = _safe_get(fig, "caption_provenance", "vision_llm")
        if provenance not in VALID_PROVENANCE:
            provenance = "vision_llm"

        image_paths: list[str] = []
        if embed_id and embed_id in embed_by_id:
            src = output_dir / embed_by_id[embed_id]["path"]
            ext = src.suffix.lower() or ".png"
            dst = figures_dir / f"fig{i}{ext}"
            counter = 1
            while dst.exists():
                dst = figures_dir / f"fig{i}_{counter}{ext}"
                counter += 1
            try:
                shutil.copy2(str(src), str(dst))
                image_paths.append(f"figures/{dst.name}")
                used_embed_ids.add(embed_id)
            except Exception as exc:
                print(f"  [finalize] copy {src} -> {dst} failed: {exc}", file=sys.stderr)
                parse_log.append({
                    "kind": "figure",
                    "index": i,
                    "issue": "embed_copy_failed",
                    "embed_id": embed_id,
                })

        if not image_paths:
            parse_log.append({
                "kind": "figure",
                "index": i,
                "issue": "no_embed_image",
                "embed_id": embed_id,
                "page": page,
            })

        if caption is None or provenance != "vision_llm":
            parse_log.append({
                "kind": "figure",
                "index": i,
                "issue": "caption_provenance",
                "provenance": provenance if caption is not None else "missing",
                "page": page,
            })

        figures.append({
            "type": "figure",
            "environment": "pdf",
            "label": label,
            "caption": caption,
            "image_paths": image_paths,
            "subfigures": None,
            "context_paragraphs": _safe_get(fig, "context_paragraphs", []),
            "referenced_in_text": bool(fig.get("referenced_in_text", False)),
            "page": page,
            "caption_provenance": provenance if caption is not None else "missing",
        })

    # -------- tables --------
    tables: list[dict[str, Any]] = []
    for i, tab in enumerate(extraction.get("tables", []), start=1):
        label = _safe_get(tab, "label", f"tab{i}")
        caption = _safe_get(tab, "caption", None)
        page = tab.get("page")
        table_html = _safe_get(tab, "table_html", None)
        if table_html is None:
            # accept markdown as a fallback — the schema field is table_html
            # but consumers downstream only need *some* structured text.
            md = tab.get("table_markdown")
            if isinstance(md, str) and md.strip():
                table_html = "<!-- markdown -->\n" + md
        provenance = _safe_get(tab, "caption_provenance", "vision_llm")
        if provenance not in VALID_PROVENANCE:
            provenance = "vision_llm"

        # Tables don't get an image_path in the vision path by default.
        # If the subagent supplied an embed_id we'll copy that image in too.
        image_paths: list[str] = []
        embed_id = tab.get("embed_id")
        if embed_id and embed_id in embed_by_id:
            src = output_dir / embed_by_id[embed_id]["path"]
            ext = src.suffix.lower() or ".png"
            dst = figures_dir / f"tab{i}{ext}"
            counter = 1
            while dst.exists():
                dst = figures_dir / f"tab{i}_{counter}{ext}"
                counter += 1
            try:
                shutil.copy2(str(src), str(dst))
                image_paths.append(f"figures/{dst.name}")
                used_embed_ids.add(embed_id)
            except Exception as exc:
                print(f"  [finalize] copy {src} -> {dst} failed: {exc}", file=sys.stderr)

        if caption is None or provenance != "vision_llm":
            parse_log.append({
                "kind": "table",
                "index": i,
                "issue": "caption_provenance",
                "provenance": provenance if caption is not None else "missing",
                "page": page,
            })

        tables.append({
            "type": "table",
            "environment": "pdf",
            "label": label,
            "caption": caption,
            "image_paths": image_paths,
            "subfigures": None,
            "context_paragraphs": _safe_get(tab, "context_paragraphs", []),
            "referenced_in_text": bool(tab.get("referenced_in_text", False)),
            "page": page,
            "caption_provenance": provenance if caption is not None else "missing",
            "table_html": table_html,
        })

    # -------- equations --------
    equations: list[dict[str, Any]] = []
    for i, eq in enumerate(extraction.get("equations", []), start=1):
        latex = _safe_get(eq, "latex", "")
        raw_tex = _safe_get(eq, "raw_tex", latex)
        # Strip surrounding $$ if present, matching pdf_full_parser convention.
        latex_clean = latex.strip()
        if latex_clean.startswith("$$") and latex_clean.endswith("$$"):
            latex_clean = latex_clean[2:-2].strip()
        page = eq.get("page")
        if not latex_clean:
            parse_log.append({
                "kind": "equation",
                "index": i,
                "issue": "empty_latex",
                "page": page,
            })
        equations.append({
            "id": f"eq{i}",
            "type": "equation",
            "environment": "pdf",
            "label": _safe_get(eq, "label", None),
            "latex": latex_clean,
            "numbered": bool(eq.get("numbered", True)),
            "raw_tex": raw_tex,
            "context_paragraphs": _safe_get(eq, "context_paragraphs", []),
            "referenced_in_text": bool(eq.get("referenced_in_text", False)),
            "page": page,
            "pix2tex_fallback_used": False,   # vision path doesn't use pix2tex
        })

    # -------- unmatched images --------
    # Embedded images the subagent did NOT match to any figure/table still get
    # copied into figures/ so the downstream paper-analyzer can see them.
    unmatched: list[str] = []
    for embed_id, info in embed_by_id.items():
        if embed_id in used_embed_ids:
            continue
        src = output_dir / info["path"]
        if not src.exists():
            continue
        ext = src.suffix.lower() or ".png"
        dst = figures_dir / f"unmatched_{embed_id}{ext}"
        counter = 1
        while dst.exists():
            dst = figures_dir / f"unmatched_{embed_id}_{counter}{ext}"
            counter += 1
        try:
            shutil.copy2(str(src), str(dst))
            unmatched.append(f"figures/{dst.name}")
        except Exception:
            pass

    manifest: dict[str, Any] = {
        "main_tex": None,
        "source_kind": "pdf-vision",
        "pdf_path": stub.get("pdf_path"),
        "figures": figures,
        "tables": tables,
        "equations": equations,
        "unmatched_images": unmatched,
    }

    # Match pdf_full_parser post-processing: image_stats + counts.
    _add_image_stats_and_counts(manifest, figures_dir)

    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # parse_log: only write if there are entries (mirrors pdf_full_parser behavior)
    if parse_log:
        log_path = output_dir / PARSE_LOG_FILENAME
        log_payload = {
            "source_kind": "pdf-vision",
            "pdf_path": stub.get("pdf_path"),
            "issues": parse_log,
        }
        log_path.write_text(
            json.dumps(log_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # mark the stub as consumed (helps debugging)
    stub["extraction_status"] = "completed"
    stub_path.write_text(
        json.dumps(stub, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return manifest


def _add_image_stats_and_counts(manifest: dict[str, Any], figures_dir: Path) -> None:
    total_bytes = 0
    max_single_bytes = 0
    count = 0
    if figures_dir.exists():
        for p in figures_dir.iterdir():
            if p.is_file():
                sz = p.stat().st_size
                total_bytes += sz
                if sz > max_single_bytes:
                    max_single_bytes = sz
                count += 1
    manifest["image_stats"] = {
        "total_bytes": total_bytes,
        "max_single_bytes": max_single_bytes,
        "count": count,
    }
    manifest["figure_count"] = len(manifest.get("figures", []))
    manifest["table_count"] = len(manifest.get("tables", []))
    manifest["equation_count"] = len(manifest.get("equations", []))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vision-LLM PDF parser (PyMuPDF render + subagent-driven extraction).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # render
    render = subparsers.add_parser("render", help="Render PDF pages + extract embedded images")
    render.add_argument("--pdf", required=True, help="Path to PDF file")
    render.add_argument("--output-dir", required=True, help="Workspace directory")
    render.add_argument("--dpi", type=int, default=DEFAULT_RENDER_DPI,
                        help=f"Page render DPI (default: {DEFAULT_RENDER_DPI})")

    # finalize
    finalize_cmd = subparsers.add_parser(
        "finalize",
        help="Assemble figure_manifest.json from the vision subagent's extraction",
    )
    finalize_cmd.add_argument("--output-dir", required=True, help="Workspace directory")
    finalize_cmd.add_argument("--extraction", default=None,
                              help=f"Path to {VISION_EXTRACTION_FILENAME} (default: <output-dir>/{VISION_EXTRACTION_FILENAME})")
    finalize_cmd.add_argument("--stub", default=None,
                              help=f"Path to {VISION_STUB_FILENAME} (default: <output-dir>/{VISION_STUB_FILENAME})")

    # check-deps
    subparsers.add_parser("check-deps", help="Verify PyMuPDF is importable")

    args = parser.parse_args(argv)

    if args.command == "render":
        stub = render_pdf(Path(args.pdf), Path(args.output_dir), dpi=args.dpi)
        print(json.dumps({
            "status": "ok",
            "page_count": stub["page_count"],
            "embedded_image_count": len(stub["embedded_images"]),
            "stub_path": str(Path(args.output_dir) / VISION_STUB_FILENAME),
            "pages_dir": str(Path(args.output_dir) / PAGES_SUBDIR),
        }, indent=2, ensure_ascii=False))
        return 0

    if args.command == "finalize":
        manifest = finalize(
            Path(args.output_dir),
            extraction_path=Path(args.extraction) if args.extraction else None,
            stub_path=Path(args.stub) if args.stub else None,
        )
        print(json.dumps({
            "status": "ok",
            "manifest_path": str(Path(args.output_dir) / MANIFEST_FILENAME),
            "figure_count": manifest["figure_count"],
            "table_count": manifest["table_count"],
            "equation_count": manifest["equation_count"],
            "unmatched_image_count": len(manifest.get("unmatched_images", [])),
        }, indent=2, ensure_ascii=False))
        return 0

    if args.command == "check-deps":
        try:
            import fitz  # type: ignore
            print(json.dumps({"status": "ok", "pymupdf_version": fitz.__doc__.split()[0] if fitz.__doc__ else "unknown"}, ensure_ascii=False))
            return 0
        except ImportError:
            print(json.dumps({"status": "missing", "missing": ["PyMuPDF"]}, ensure_ascii=False))
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
