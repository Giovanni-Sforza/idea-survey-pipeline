#!/usr/bin/env python3
"""
Orchestrator for per-paper deep analysis.

Prepares a clean analysis workspace for a single paper by:
1. Running latex_source_parser.py (if TeX source available) or pdf_figure_extractor.py
2. Copying relevant images to a clean figures/ subdirectory
3. Generating a context JSON for the subagent

Usage:
    python3 paper_analyzer_orchestrator.py prepare \
        --arxiv-id 2301.07041 \
        --source-dir literature-deep/paper_2301.07041/2301.07041_src/ \
        --output-dir literature-deep/paper_2301.07041/

    python3 paper_analyzer_orchestrator.py prepare \
        --pdf-path papers/1234.56789.pdf \
        --output-dir literature-deep/paper_1234.56789/

Output:
    <output_dir>/
        figure_manifest.json      # Structured figure/table metadata
        figures/                  # Clean copy of relevant images
            fig1.png
            fig2.pdf
            ...
        analysis_context.json     # Combined context for subagent
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_latex_parser(source_dir: Path, output_dir: Path) -> Path:
    """Run latex_source_parser.py and return the path to the generated JSON."""
    manifest_path = output_dir / "figure_manifest.json"

    # Locate the script
    script = Path(__file__).parent / "latex_source_parser.py"
    if not script.exists():
        # Try relative to current working directory
        script = Path("tools") / "latex_source_parser.py"

    if not script.exists():
        raise FileNotFoundError(f"latex_source_parser.py not found at {script}")

    cmd = [
        sys.executable, str(script),
        str(source_dir),
        "--output", str(manifest_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"latex_source_parser failed: {result.stderr}")

    return manifest_path


def _resolve_tool(name: str) -> Path:
    """Locate a sibling tools/ script."""
    script = Path(__file__).parent / name
    if script.exists():
        return script
    script = Path("tools") / name
    if script.exists():
        return script
    raise FileNotFoundError(f"{name} not found")


def run_pdf_full_parser(
    pdf_path: Path,
    output_dir: Path,
    use_pix2tex: bool = True,
    mineru_bin: str = "mineru",
    mineru_raw_dir: Path | None = None,
    lang: str = "en",
) -> Path:
    """Run pdf_full_parser.py (MinerU + pix2tex) — primary PDF path.

    Produces a figure_manifest.json whose schema matches latex_source_parser:
    figures[], tables[], equations[] are all populated and caption-attributed.
    """
    manifest_path = output_dir / "figure_manifest.json"
    script = _resolve_tool("pdf_full_parser.py")

    cmd = [
        sys.executable, str(script), "parse",
        "--pdf", str(pdf_path),
        "--output-dir", str(output_dir),
        "--mineru-bin", mineru_bin,
        "--lang", lang,
    ]
    if not use_pix2tex:
        cmd.append("--no-pix2tex")
    if mineru_raw_dir is not None:
        cmd.extend(["--mineru-raw-dir", str(mineru_raw_dir)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdf_full_parser failed: {result.stderr}")

    return manifest_path


def run_pdf_extractor(pdf_path: Path, output_dir: Path) -> Path:
    """Run pdf_figure_extractor.py — legacy fallback (image-only).

    Used only when MinerU is unavailable.  Produces a degenerate manifest
    where every extracted image becomes a fake 'figure' with no real caption
    and no equations/tables — kept for backward compatibility.
    """
    manifest_path = output_dir / "figure_manifest.json"
    figures_dir = output_dir / "figures"
    script = _resolve_tool("pdf_figure_extractor.py")

    cmd = [
        sys.executable, str(script),
        str(pdf_path),
        "--output", str(figures_dir),
        "--json", str(manifest_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdf_figure_extractor failed: {result.stderr}")

    return manifest_path


def run_pdf_vision_render(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 200,
) -> Path:
    """Run `pdf_vision_parser.py render` — vision-LLM PDF path, stage 1.

    Renders every PDF page to PNG and extracts embedded raster images, then
    writes `vision_stub.json` describing the workspace.  A vision-capable
    subagent must consume the stub, produce `vision_extraction.json`, and call
    `pdf_vision_parser.py finalize` to assemble the final `figure_manifest.json`.

    Returns the path to vision_stub.json (NOT to figure_manifest.json — the
    manifest does not yet exist after this stage).
    """
    stub_path = output_dir / "vision_stub.json"
    script = _resolve_tool("pdf_vision_parser.py")

    cmd = [
        sys.executable, str(script), "render",
        "--pdf", str(pdf_path),
        "--output-dir", str(output_dir),
        "--dpi", str(dpi),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdf_vision_parser render failed: {result.stderr}")

    return stub_path


def copy_images_to_figures_dir(manifest: dict[str, Any], source_dir: Path, figures_dir: Path) -> dict[str, Any]:
    """Copy referenced images to a clean figures/ directory and update paths."""
    figures_dir.mkdir(parents=True, exist_ok=True)

    def copy_and_update(paths: list[str]) -> list[str]:
        updated = []
        for raw_path in paths:
            src = source_dir / raw_path
            if not src.exists():
                # Try resolving as absolute or relative to source_dir parent
                src = Path(raw_path)
                if not src.exists():
                    updated.append(raw_path)
                    continue

            # Sanitize filename for cross-platform safety
            safe_name = src.name.replace("/", "_").replace("\\", "_")
            dst = figures_dir / safe_name

            # Handle name collisions
            counter = 1
            orig_dst = dst
            while dst.exists():
                stem = orig_dst.stem
                suffix = orig_dst.suffix
                dst = figures_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            try:
                shutil.copy2(str(src), str(dst))
                updated.append(str(dst.relative_to(figures_dir.parent)))
            except Exception:
                updated.append(raw_path)
        return updated

    # Update figure image paths
    for fig in manifest.get("figures", []):
        fig["image_paths"] = copy_and_update(fig.get("image_paths", []))
        if fig.get("subfigures"):
            for sf in fig["subfigures"]:
                sf["image_paths"] = copy_and_update(sf.get("image_paths", []))

    # Tables typically don't have images, but if they do (rare), handle them
    for tab in manifest.get("tables", []):
        tab["image_paths"] = copy_and_update(tab.get("image_paths", []))

    # Copy unmatched images too (they might still be useful)
    unmatched_copied = []
    for raw_path in manifest.get("unmatched_images", []):
        src = source_dir / raw_path
        if src.exists():
            safe_name = src.name.replace("/", "_").replace("\\", "_")
            dst = figures_dir / safe_name
            counter = 1
            orig_dst = dst
            while dst.exists():
                stem = orig_dst.stem
                suffix = orig_dst.suffix
                dst = figures_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            try:
                shutil.copy2(str(src), str(dst))
                unmatched_copied.append(str(dst.relative_to(figures_dir.parent)))
            except Exception:
                pass
    manifest["unmatched_images"] = unmatched_copied

    return manifest


def add_image_stats_and_counts(manifest: dict[str, Any], figures_dir: Path) -> dict[str, Any]:
    """Compute image byte stats and element counts, add to manifest."""
    total_bytes = 0
    max_single_bytes = 0
    image_count = 0

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

    # Pre-computed counts so SKILLs don't need to count manually
    manifest["figure_count"] = len(manifest.get("figures", []))
    manifest["table_count"] = len(manifest.get("tables", []))
    manifest["equation_count"] = len(manifest.get("equations", []))

    return manifest


def build_analysis_context(
    paper_info: dict[str, Any],
    manifest: dict[str, Any],
    figures_dir: Path,
    output_dir: Path,
    output_language: str = "en",
) -> Path:
    """Build the combined context JSON for the subagent."""
    context = {
        "paper_info": paper_info,
        "figure_manifest": manifest,
        "figures_directory": str(figures_dir),
        "analysis_output_path": str(output_dir / "deep_analysis.md"),
        "output_language": output_language,
    }

    context_path = output_dir / "analysis_context.json"
    context_path.write_text(
        json.dumps(context, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return context_path


def prepare_from_tex_source(
    arxiv_id: str | None,
    source_dir: Path,
    output_dir: Path,
    paper_info: dict[str, Any],
    output_language: str = "en",
) -> dict[str, Any]:
    """Prepare analysis workspace from a TeX source directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse TeX source
    manifest_path = run_latex_parser(source_dir, output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Step 2: Copy images to clean figures/ dir
    figures_dir = output_dir / "figures"
    manifest = copy_images_to_figures_dir(manifest, source_dir, figures_dir)

    # Step 2b: Compute image stats and counts
    manifest = add_image_stats_and_counts(manifest, figures_dir)

    # Re-write updated manifest
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Step 3: Build context JSON
    context_path = build_analysis_context(paper_info, manifest, figures_dir, output_dir, output_language)

    return {
        "mode": "tex",
        "manifest_path": str(manifest_path),
        "context_path": str(context_path),
        "figures_dir": str(figures_dir),
    }


def _mineru_available(mineru_bin: str = "mineru") -> bool:
    """Quick PATH check for MinerU; mirrors pdf_full_parser.has_mineru."""
    return bool(shutil.which(mineru_bin) or shutil.which("magic-pdf"))


def prepare_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    paper_info: dict[str, Any],
    output_language: str = "en",
    pdf_parser: str = "auto",
    use_pix2tex: bool = True,
    mineru_bin: str = "mineru",
    mineru_raw_dir: Path | None = None,
    mineru_lang: str = "en",
    vision_dpi: int = 200,
) -> dict[str, Any]:
    """Prepare analysis workspace from a PDF file.

    `pdf_parser` selects the backend:
      - "auto" (default): use pdf_full_parser (MinerU) if available, else fall
        back to pdf_figure_extractor.
      - "full": force pdf_full_parser; raise if MinerU is missing.
      - "legacy": force pdf_figure_extractor (image-only, no captions/eqs).
      - "vision": render pages + extract embedded images via PyMuPDF, then
        return mode="pdf-vision-pending".  The caller MUST launch a vision-
        capable subagent to consume vision_stub.json, write
        vision_extraction.json, and then invoke `pdf_vision_parser.py finalize`
        (or call this orchestrator with the same arguments after the
        extraction is in place).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"

    chosen: str
    if pdf_parser == "full":
        chosen = "full"
    elif pdf_parser == "legacy":
        chosen = "legacy"
    elif pdf_parser == "vision":
        chosen = "vision"
    else:  # auto
        chosen = "full" if _mineru_available(mineru_bin) else "legacy"

    if chosen == "vision":
        # Stage 1 of the vision path: render pages + extract embedded images.
        # The figure_manifest.json is NOT written yet — the subagent and the
        # subsequent `finalize` step are responsible for that.
        stub_path = run_pdf_vision_render(pdf_path, output_dir, dpi=vision_dpi)
        return {
            "mode": "pdf-vision-pending",
            "stub_path": str(stub_path),
            "pages_dir": str(output_dir / "vision_pages"),
            "embedded_dir": str(output_dir / "vision_embedded"),
            "manifest_path": str(output_dir / "figure_manifest.json"),  # will exist after finalize
            "figures_dir": str(figures_dir),
            "next_action": (
                "Launch a vision-capable subagent to read vision_stub.json, "
                "produce vision_extraction.json (figures/tables/equations), "
                "then run `python3 tools/pdf_vision_parser.py finalize "
                f"--output-dir {output_dir}` to assemble figure_manifest.json."
            ),
        }

    if chosen == "full":
        # pdf_full_parser writes a complete figure_manifest.json directly.
        manifest_path = run_pdf_full_parser(
            pdf_path,
            output_dir,
            use_pix2tex=use_pix2tex,
            mineru_bin=mineru_bin,
            mineru_raw_dir=mineru_raw_dir,
            lang=mineru_lang,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # pdf_full_parser already populated image_stats + counts; no rewrite needed.
        mode = "pdf-full"

    else:
        # Legacy image-only path — preserves prior behavior so existing fixtures
        # keep working.  This produces a degenerate manifest (no real captions,
        # no equations, no tables) and should be considered a stopgap.
        manifest_path = run_pdf_extractor(pdf_path, output_dir)
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))

        simplified_manifest = {
            "main_tex": None,
            "source_kind": "pdf-legacy",
            "figures": [],
            "tables": [],
            "equations": [],
            "unmatched_images": [img["filename"] for img in raw.get("extracted_images", [])],
        }
        for img in raw.get("extracted_images", []):
            simplified_manifest["figures"].append({
                "type": "figure",
                "environment": "unknown",
                "label": None,
                "caption": f"Extracted image from page {img['page']}",
                "image_paths": [f"figures/{img['filename']}"],
                "subfigures": None,
                "context_paragraphs": [],
                "referenced_in_text": False,
            })
        simplified_manifest = add_image_stats_and_counts(simplified_manifest, figures_dir)
        manifest_path.write_text(
            json.dumps(simplified_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        manifest = simplified_manifest
        mode = "pdf-legacy"

    context_path = build_analysis_context(paper_info, manifest, figures_dir, output_dir, output_language)

    return {
        "mode": mode,
        "manifest_path": str(manifest_path),
        "context_path": str(context_path),
        "figures_dir": str(figures_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate per-paper deep analysis workspace preparation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Prepare analysis workspace for a paper")
    prepare.add_argument("--arxiv-id", default=None, help="arXiv ID (optional)")
    prepare.add_argument("--source-dir", default=None, help="Path to extracted TeX source directory")
    prepare.add_argument("--pdf-path", default=None, help="Path to PDF file (fallback mode)")
    prepare.add_argument("--output-dir", required=True, help="Output directory for analysis workspace")
    prepare.add_argument(
        "--paper-info",
        default="{}",
        help='JSON string with paper metadata: {"title":"...","authors":"...","year":2024,...}',
    )
    prepare.add_argument(
        "--language",
        default="en",
        help='Output language for deep analysis (e.g., en, zh). Default: en',
    )
    prepare.add_argument(
        "--pdf-parser",
        choices=["auto", "full", "legacy", "vision"],
        default="auto",
        help='PDF backend: "auto" picks pdf_full_parser if MinerU is installed, '
             'else falls back to pdf_figure_extractor. "full" forces MinerU. '
             '"legacy" forces the old image-only path. "vision" runs the '
             'PyMuPDF render step and returns mode="pdf-vision-pending" — the '
             'caller must then drive a vision subagent + `pdf_vision_parser.py '
             'finalize`. Default: auto',
    )
    prepare.add_argument(
        "--no-pix2tex",
        action="store_true",
        help="Disable pix2tex equation fallback in pdf_full_parser.",
    )
    prepare.add_argument(
        "--mineru-bin",
        default="mineru",
        help="MinerU binary name on PATH (default: mineru). Tried alongside `magic-pdf`.",
    )
    prepare.add_argument(
        "--mineru-raw-dir",
        default=None,
        help="Reuse a pre-existing MinerU output directory (skip re-run).",
    )
    prepare.add_argument(
        "--mineru-lang",
        default="en",
        help="OCR language passed to MinerU (e.g., en, zh, ja). Default: en",
    )
    prepare.add_argument(
        "--vision-dpi",
        type=int,
        default=200,
        help="DPI for page rendering when --pdf-parser=vision (default: 200).",
    )

    args = parser.parse_args(argv)

    if args.command == "prepare":
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            paper_info = json.loads(args.paper_info)
        except json.JSONDecodeError as exc:
            print(f"Error parsing --paper-info: {exc}", file=sys.stderr)
            return 1

        if args.source_dir:
            result = prepare_from_tex_source(
                args.arxiv_id,
                Path(args.source_dir),
                output_dir,
                paper_info,
                args.language,
            )
        elif args.pdf_path:
            result = prepare_from_pdf(
                Path(args.pdf_path),
                output_dir,
                paper_info,
                args.language,
                pdf_parser=args.pdf_parser,
                use_pix2tex=not args.no_pix2tex,
                mineru_bin=args.mineru_bin,
                mineru_raw_dir=Path(args.mineru_raw_dir) if args.mineru_raw_dir else None,
                mineru_lang=args.mineru_lang,
                vision_dpi=args.vision_dpi,
            )
        else:
            print("Error: either --source-dir or --pdf-path is required", file=sys.stderr)
            return 1

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
