#!/usr/bin/env python3
"""
pdf_full_parser.py
==================

Full-spectrum PDF parser for non-arXiv papers.  Replaces the figure-only
`pdf_figure_extractor.py` path: produces a figure_manifest.json whose schema is
byte-for-byte compatible with `latex_source_parser.py`, so downstream
paper-analyzer subagents and `research-proposal` need NO code changes.

Pipeline
--------
1. (Optional) Run MinerU on the input PDF -> mineru_raw/
2. Locate MinerU's *_content_list.json (v2) or content_list.json (v1).
3. Walk the content list:
     - 'image' / 'figure'  -> figures[]
     - 'table'             -> tables[]
     - 'equation' / 'interline_equation' / 'inline_equation' (display only)
                           -> equations[]
     - 'text' / 'title'    -> kept as context blocks for caption fallback and
                              for `context_paragraphs` reference scanning.
4. Caption attribution:
     a. trust MinerU's `img_caption` / `table_caption` when present
     b. otherwise scan adjacent text blocks for "Figure N"/"Fig. N"/"图 N"
        and verify the running figure index
     c. write `caption_missing` to parse_log.json when (a) and (b) both fail
5. Equation confidence check + pix2tex fallback:
     - flag MinerU equations that look broken (unbalanced braces, < 3 chars,
       unbalanced \\begin/\\end, etc.)
     - if MinerU stored a rendered crop alongside the equation, rerun pix2tex
       on the crop (lazy import, silent skip if not installed)
6. Copy / convert images into <output>/figures/ with deterministic names
   (fig1.png, fig2.png, tab1.png, ...).  Defers the heavy lifting to
   image_preprocessor.py so PDF/EPS/etc. all become PNG.
7. Build context_paragraphs by scanning the joined text body for "Figure N",
   "Fig. N", "Table N", "图 N", "Eq. N", "Equation (N)" patterns.

The main agent never reads the manifest; only subagents do.  This script's job
is to keep the schema identical to the TeX path so that the boundary protocol
stays clean.

Usage
-----
    python3 pdf_full_parser.py parse \\
        --pdf paper.pdf \\
        --output-dir literature-deep/paper_xxxx/

    python3 pdf_full_parser.py parse \\
        --pdf paper.pdf \\
        --output-dir literature-deep/paper_xxxx/ \\
        --mineru-raw-dir cached/mineru_output_of_paper/   # skip rerun
        --no-pix2tex

    python3 pdf_full_parser.py check-deps

Self-test (no real PDF needed)
------------------------------
    python3 pdf_full_parser.py parse \\
        --pdf dummy.pdf \\
        --output-dir /tmp/test_out/ \\
        --mock-mineru-output tests/fixtures/mineru_minimal/
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


# ============================================================
# Constants
# ============================================================

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".gif", ".tiff", ".tif", ".bmp", ".webp"}

# Heuristics for caption validation.  Anything beyond these defaults a missing
# caption rather than a hallucinated one — the bias is conservative.
CAPTION_MIN_LEN = 10            # too short -> likely junk
CAPTION_MAX_LEN = 2000          # too long -> likely two captions glued
CAPTION_TRIGGERS = re.compile(
    r"^\s*(?:figure|fig\.?|table|tab\.?|图|表|scheme|chart)\s*[\.:]?\s*\d",
    re.IGNORECASE,
)

# Equation sanity checks.
EQ_MIN_LEN = 3                  # "L=0" is fine; one-char equations almost never are
EQ_MAX_BAD_RATIO = 0.4          # >40% non-LaTeX chars -> suspicious

# MinerU content_list types we recognize.  MinerU v1 and v2 use slightly
# different vocabularies so we accept the union.
IMAGE_TYPES = {"image", "figure"}
TABLE_TYPES = {"table"}
EQUATION_TYPES = {"equation", "interline_equation"}        # display only
INLINE_EQ_TYPES = {"inline_equation"}                       # ignored for our equations[]
TEXT_TYPES = {"text", "title", "list", "caption"}


# ============================================================
# Dependency checks
# ============================================================

def has_mineru(binary: str = "mineru") -> bool:
    return shutil.which(binary) is not None or shutil.which("magic-pdf") is not None


def has_pix2tex() -> bool:
    try:
        import pix2tex  # noqa: F401
        return True
    except ImportError:
        return False


def check_deps_cli() -> int:
    print(f"MinerU  available: {has_mineru()}  (looked for `mineru` and `magic-pdf` on PATH)")
    print(f"pix2tex available: {has_pix2tex()}  (Python `pix2tex` package)")
    if not has_mineru():
        print(
            "\nMinerU install:  https://github.com/opendatalab/MinerU\n"
            "  uv tool install -U \"mineru[core]\"\n"
            "  # or:  pip install -U \"mineru[core]\""
        )
    if not has_pix2tex():
        print(
            "\npix2tex install (optional, equation fallback):\n"
            "  pip install \"pix2tex[gui]\"  # or just `pix2tex` without GUI deps\n"
            "  Model weights download on first run."
        )
    return 0


# ============================================================
# Run MinerU
# ============================================================

def run_mineru(
    pdf_path: Path,
    work_dir: Path,
    mineru_bin: str = "mineru",
    lang: str = "en",
) -> Path:
    """
    Invoke MinerU CLI on pdf_path; return the directory that will contain
    *_content_list.json.  Tries the new `mineru` binary first, then falls
    back to the legacy `magic-pdf` CLI.

    MinerU v2 default layout:
        work_dir/<pdf_stem>/auto/<pdf_stem>_content_list.json
                                <pdf_stem>.md
                                images/
    MinerU v1 (magic-pdf) layout:
        work_dir/<pdf_stem>/auto/content_list.json
                                <pdf_stem>.md
                                images/

    We just return work_dir; locate_mineru_outputs() finds the rest.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which(mineru_bin):
        # MinerU v2 CLI:  mineru -p <pdf> -o <out> -l <lang> -m auto
        cmd = [
            mineru_bin,
            "-p", str(pdf_path),
            "-o", str(work_dir),
            "-l", lang,
            "-m", "auto",
        ]
    elif shutil.which("magic-pdf"):
        # MinerU v1 CLI
        cmd = [
            "magic-pdf",
            "-p", str(pdf_path),
            "-o", str(work_dir),
            "-m", "auto",
        ]
    else:
        raise RuntimeError(
            "Neither `mineru` nor `magic-pdf` found on PATH. "
            "Install with:  uv tool install -U 'mineru[core]'  "
            "or  pip install -U 'mineru[core]'"
        )

    print(f"  [mineru] running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # MinerU is chatty; print last few lines of stderr so the user knows
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"MinerU failed (exit {result.returncode}):\n{tail}")
    return work_dir


def locate_mineru_outputs(work_dir: Path) -> tuple[Path, Path, Path]:
    """
    Return (content_list_json, markdown_file, images_dir).  Searches
    recursively under work_dir to handle both v1 and v2 layouts.
    """
    candidates = list(work_dir.rglob("*_content_list.json")) + list(work_dir.rglob("content_list.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No content_list.json under {work_dir} — MinerU may have failed silently. "
            f"Check {work_dir} contents."
        )
    # Prefer the deepest path (auto/ subdir) and the v2 named variant
    candidates.sort(key=lambda p: (0 if p.name.endswith("_content_list.json") else 1, -len(p.parts)))
    content_list = candidates[0]
    base = content_list.parent

    md_files = list(base.glob("*.md"))
    md_file = md_files[0] if md_files else base / "out.md"

    images_dir = base / "images"
    if not images_dir.exists():
        # MinerU sometimes puts images in a sibling 'figures' dir
        alt = base / "figures"
        if alt.exists():
            images_dir = alt
        else:
            images_dir = base  # last resort; we'll filter by extension

    return content_list, md_file, images_dir


# ============================================================
# Caption attribution
# ============================================================

def _looks_like_caption(text: str) -> bool:
    if not text:
        return False
    text_strip = text.strip()
    if len(text_strip) < CAPTION_MIN_LEN or len(text_strip) > CAPTION_MAX_LEN:
        return False
    return CAPTION_TRIGGERS.match(text_strip) is not None


def _extract_caption_index(text: str) -> int | None:
    """Pull the figure/table number out of a caption-like line."""
    m = re.match(
        r"^\s*(?:figure|fig\.?|table|tab\.?|图|表|scheme|chart)\s*[\.:]?\s*(\d+)",
        text.strip(),
        re.IGNORECASE,
    )
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def attach_caption(
    item: dict[str, Any],
    item_idx: int,
    content_list: list[dict[str, Any]],
    expected_num: int,
    is_table: bool = False,
) -> tuple[str | None, str]:
    """
    Resolve the caption for a MinerU image/table entry.  Returns
    (caption_string_or_None, provenance), where provenance is one of:
       'mineru_native'         caption came directly from MinerU
       'heuristic_adjacent'    captured from a neighboring text block by index match
       'heuristic_local'       captured from a neighbor without index match (weaker)
       'missing'               no caption could be attributed
    """
    # 1. Trust MinerU's own attribution first
    native_field = "table_caption" if is_table else "img_caption"
    native = item.get(native_field)
    if isinstance(native, list) and native:
        joined = " ".join(s for s in native if isinstance(s, str)).strip()
        if joined:
            return joined, "mineru_native"
    if isinstance(native, str) and native.strip():
        return native.strip(), "mineru_native"

    # MinerU v2 also sometimes uses 'caption'
    alt = item.get("caption")
    if isinstance(alt, str) and alt.strip():
        return alt.strip(), "mineru_native"

    # 2. Heuristic: scan neighbors (±3 blocks) for a caption-shaped text
    window = range(max(0, item_idx - 3), min(len(content_list), item_idx + 4))
    indexed_match: str | None = None
    nearby_match: str | None = None
    for j in window:
        if j == item_idx:
            continue
        neighbor = content_list[j]
        text_val = neighbor.get("text") if isinstance(neighbor, dict) else None
        if not isinstance(text_val, str):
            continue
        if not _looks_like_caption(text_val):
            continue
        cap_idx = _extract_caption_index(text_val)
        if cap_idx == expected_num:
            indexed_match = text_val.strip()
            break
        if nearby_match is None:
            nearby_match = text_val.strip()

    if indexed_match:
        return indexed_match, "heuristic_adjacent"
    if nearby_match:
        return nearby_match, "heuristic_local"

    return None, "missing"


# ============================================================
# Equation sanity + pix2tex fallback
# ============================================================

def equation_is_suspect(latex: str) -> bool:
    if not latex or len(latex.strip()) < EQ_MIN_LEN:
        return True
    # Brace balance
    if latex.count("{") != latex.count("}"):
        return True
    # \begin / \end balance
    if latex.count(r"\begin") != latex.count(r"\end"):
        return True
    # Garbage-char heuristic (cheap: count chars outside ASCII printable/whitespace)
    bad = sum(1 for c in latex if not (32 <= ord(c) < 127 or c in "\t\n"))
    if bad / max(1, len(latex)) > EQ_MAX_BAD_RATIO:
        return True
    return False


_pix2tex_model = None


def pix2tex_redo(image_path: Path) -> str | None:
    """Lazy-load pix2tex and rerun on an image crop.  None on any failure."""
    global _pix2tex_model
    try:
        if _pix2tex_model is None:
            from pix2tex.cli import LatexOCR
            _pix2tex_model = LatexOCR()
        from PIL import Image as PILImage
        img = PILImage.open(str(image_path))
        return _pix2tex_model(img)
    except Exception as exc:
        print(f"  [pix2tex] skipped on {image_path.name}: {exc}", file=sys.stderr)
        return None


# ============================================================
# Cross-reference scanning (for context_paragraphs)
# ============================================================

def build_text_body(content_list: list[dict[str, Any]]) -> str:
    """Concatenate all text-type blocks for grep-style reference search."""
    out: list[str] = []
    for item in content_list:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t in TEXT_TYPES:
            v = item.get("text")
            if isinstance(v, str):
                out.append(v)
    return "\n\n".join(out)


def find_context_paragraphs(body: str, kind: str, num: int) -> list[str]:
    """
    Find paragraphs that reference 'Figure N' / 'Table N' / 'Eq. (N)' / '图 N'.
    Returns up to 4 short snippets (300 chars window each).
    """
    if kind == "figure":
        pattern = re.compile(rf"\b(?:figure|fig\.?|图)\s*\.?\s*0*{num}\b", re.IGNORECASE)
    elif kind == "table":
        pattern = re.compile(rf"\b(?:table|tab\.?|表)\s*\.?\s*0*{num}\b", re.IGNORECASE)
    elif kind == "equation":
        # equations: Eq. N, Eqn N, Equation (N), Equation~N
        pattern = re.compile(
            rf"\b(?:equation|eq\.?|eqn\.?)\s*[~\.]?\s*\(?0*{num}\)?",
            re.IGNORECASE,
        )
    else:
        return []

    contexts: list[str] = []
    for m in pattern.finditer(body):
        start = max(0, m.start() - 300)
        end = min(len(body), m.end() + 300)
        snippet = " ".join(body[start:end].split())
        contexts.append(snippet)
        if len(contexts) >= 4:
            break
    return contexts


# ============================================================
# Main conversion: MinerU content_list -> figure_manifest.json
# ============================================================

def convert_content_list(
    content_list: list[dict[str, Any]],
    images_dir: Path,
    figures_dir: Path,
    pdf_path: Path,
    use_pix2tex: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Return (manifest_dict, parse_log_entries).
    Copies the relevant images into figures_dir with stable names.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    body = build_text_body(content_list)

    figures: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    equations: list[dict[str, Any]] = []
    parse_log: list[dict[str, Any]] = []

    fig_seq = 0
    tab_seq = 0
    eq_seq = 0

    seen_images: set[str] = set()  # mineru image paths we've already copied

    def copy_image(rel_path: str, target_name: str) -> str | None:
        """Copy MinerU-side image into figures_dir under a deterministic name.
        Returns the relative path inside the parent of figures_dir, or None."""
        if not rel_path:
            return None
        # MinerU stores image paths relative to its own output dir
        candidates = [
            images_dir / rel_path,
            images_dir / Path(rel_path).name,
            images_dir.parent / rel_path,
        ]
        # Also try absolute / cwd
        if Path(rel_path).is_absolute():
            candidates.insert(0, Path(rel_path))
        src: Path | None = None
        for c in candidates:
            if c.exists() and c.is_file():
                src = c
                break
        if src is None:
            return None

        suffix = src.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            suffix = ".png"  # MinerU should always emit png/jpg; be conservative
        dst = figures_dir / f"{target_name}{suffix}"
        counter = 1
        # If dst already exists from a prior pass, bump the counter until free.
        while dst.exists():
            dst = figures_dir / f"{target_name}_{counter}{suffix}"
            counter += 1
        try:
            shutil.copy2(str(src), str(dst))
        except Exception as exc:
            print(f"  [copy] {src} -> {dst} failed: {exc}", file=sys.stderr)
            return None
        seen_images.add(str(src.resolve()))
        return f"figures/{dst.name}"

    for idx, item in enumerate(content_list):
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")

        # ---------------- figures ----------------
        if item_type in IMAGE_TYPES:
            fig_seq += 1
            img_rel = item.get("img_path") or item.get("image_path") or item.get("path")
            copied_rel = copy_image(img_rel, f"fig{fig_seq}") if img_rel else None

            caption, provenance = attach_caption(item, idx, content_list, fig_seq, is_table=False)
            if provenance != "mineru_native":
                parse_log.append({
                    "kind": "figure",
                    "index": fig_seq,
                    "issue": "caption_provenance",
                    "provenance": provenance,
                    "page": item.get("page_idx"),
                })

            figures.append({
                "type": "figure",
                "environment": "pdf",
                "label": f"fig{fig_seq}",
                "caption": caption,
                "image_paths": [copied_rel] if copied_rel else [],
                "subfigures": None,
                "context_paragraphs": find_context_paragraphs(body, "figure", fig_seq),
                "referenced_in_text": False,  # set after the loop
                "page": item.get("page_idx"),
                "caption_provenance": provenance,
            })

        # ---------------- tables ----------------
        elif item_type in TABLE_TYPES:
            tab_seq += 1
            img_rel = item.get("img_path") or item.get("image_path")
            table_body = item.get("table_body") or item.get("html") or item.get("table_caption_html")

            copied_rel = copy_image(img_rel, f"tab{tab_seq}") if img_rel else None
            caption, provenance = attach_caption(item, idx, content_list, tab_seq, is_table=True)
            if provenance != "mineru_native":
                parse_log.append({
                    "kind": "table",
                    "index": tab_seq,
                    "issue": "caption_provenance",
                    "provenance": provenance,
                    "page": item.get("page_idx"),
                })

            tables.append({
                "type": "table",
                "environment": "pdf",
                "label": f"tab{tab_seq}",
                "caption": caption,
                "image_paths": [copied_rel] if copied_rel else [],
                "subfigures": None,
                "context_paragraphs": find_context_paragraphs(body, "table", tab_seq),
                "referenced_in_text": False,
                "page": item.get("page_idx"),
                "caption_provenance": provenance,
                "table_html": table_body if isinstance(table_body, str) else None,
            })

        # ---------------- equations ----------------
        elif item_type in EQUATION_TYPES:
            eq_seq += 1
            latex = (
                item.get("text")
                or item.get("latex")
                or item.get("equation")
                or ""
            )
            # MinerU often wraps display math in $$...$$ already; strip for our latex field
            latex_clean = latex.strip()
            if latex_clean.startswith("$$") and latex_clean.endswith("$$"):
                latex_clean = latex_clean[2:-2].strip()

            redo_used = False
            if equation_is_suspect(latex_clean):
                parse_log.append({
                    "kind": "equation",
                    "index": eq_seq,
                    "issue": "mineru_low_confidence",
                    "page": item.get("page_idx"),
                    "raw_excerpt": latex_clean[:120],
                })
                # Try pix2tex if the equation has a rendered crop and the feature is enabled
                if use_pix2tex and has_pix2tex():
                    img_rel = item.get("img_path") or item.get("image_path")
                    if img_rel:
                        # locate the crop, copy into figures_dir for archival, redo
                        crop_path = None
                        for c in [images_dir / img_rel, images_dir / Path(img_rel).name]:
                            if c.exists():
                                crop_path = c
                                break
                        if crop_path is not None:
                            redo = pix2tex_redo(crop_path)
                            if redo and not equation_is_suspect(redo):
                                latex_clean = redo.strip()
                                redo_used = True
                                parse_log.append({
                                    "kind": "equation",
                                    "index": eq_seq,
                                    "issue": "pix2tex_fallback_applied",
                                    "page": item.get("page_idx"),
                                })

            equations.append({
                "id": f"eq{eq_seq}",
                "type": "equation",
                "environment": "pdf",
                "label": None,
                "latex": latex_clean,
                "numbered": True,                  # PDF display eqs are usually numbered
                "raw_tex": latex.strip(),
                "context_paragraphs": find_context_paragraphs(body, "equation", eq_seq),
                "referenced_in_text": False,
                "page": item.get("page_idx"),
                "pix2tex_fallback_used": redo_used,
            })

    # Mark referenced_in_text
    for f in figures + tables + equations:
        f["referenced_in_text"] = bool(f.get("context_paragraphs"))

    # Collect unmatched images: anything in images_dir we didn't copy
    unmatched: list[str] = []
    if images_dir.exists():
        for p in images_dir.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if str(p.resolve()) in seen_images:
                continue
            # Copy unmatched into figures/ too so subagent can still see them
            dst = figures_dir / p.name
            counter = 1
            while dst.exists():
                dst = figures_dir / f"{p.stem}_{counter}{p.suffix}"
                counter += 1
            try:
                shutil.copy2(str(p), str(dst))
                unmatched.append(f"figures/{dst.name}")
            except Exception:
                pass

    manifest = {
        "main_tex": None,
        "source_kind": "pdf",
        "pdf_path": str(pdf_path),
        "figures": figures,
        "tables": tables,
        "equations": equations,
        "unmatched_images": unmatched,
    }
    return manifest, parse_log


# ============================================================
# Post-process: normalize images to PNG via image_preprocessor.py
# ============================================================

def normalize_figures(figures_dir: Path) -> None:
    """Hand the figures/ dir to image_preprocessor.py for unified PNG output."""
    script = Path(__file__).parent / "image_preprocessor.py"
    if not script.exists():
        return
    cmd = [
        sys.executable, str(script),
        str(figures_dir),
        "--max-dimension", "1536",
        "--max-filesize-mb", "2",
        "--delete-originals",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"  [image_preprocessor] non-zero exit ({result.returncode}); "
            f"continuing.  stderr tail:",
            file=sys.stderr,
        )
        print("\n".join(result.stderr.splitlines()[-10:]), file=sys.stderr)


def add_image_stats_and_counts(manifest: dict[str, Any], figures_dir: Path) -> None:
    """Match the post-processing done by paper_analyzer_orchestrator."""
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


# ============================================================
# Top-level entry
# ============================================================

def parse_pdf(
    pdf_path: Path,
    output_dir: Path,
    mineru_bin: str = "mineru",
    use_pix2tex: bool = True,
    mineru_raw_dir: Path | None = None,
    mock_mineru_output: Path | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """
    Full parse pipeline.  Returns the final manifest dict (also written to
    output_dir/figure_manifest.json).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"

    if mock_mineru_output is not None:
        # Self-test path: skip MinerU, use a pre-baked directory
        raw_root = Path(mock_mineru_output)
    elif mineru_raw_dir is not None:
        raw_root = Path(mineru_raw_dir)
    else:
        raw_root = output_dir / "mineru_raw"
        if not has_mineru(mineru_bin):
            raise RuntimeError(
                "MinerU is not installed and no --mineru-raw-dir / --mock-mineru-output "
                "was provided.  Run `python3 pdf_full_parser.py check-deps` for install hints."
            )
        run_mineru(pdf_path, raw_root, mineru_bin=mineru_bin, lang=lang)

    content_list_path, _md_path, images_dir = locate_mineru_outputs(raw_root)

    raw_text = content_list_path.read_text(encoding="utf-8")
    content_list = json.loads(raw_text)
    if not isinstance(content_list, list):
        raise ValueError(
            f"{content_list_path}: expected a JSON list at the root, "
            f"got {type(content_list).__name__}"
        )

    manifest, parse_log = convert_content_list(
        content_list,
        images_dir=images_dir,
        figures_dir=figures_dir,
        pdf_path=pdf_path,
        use_pix2tex=use_pix2tex,
    )

    # Normalize images to PNG + downsample, then re-tally stats
    normalize_figures(figures_dir)
    # image_preprocessor renamed files (suffix -> .png) and may have deleted
    # originals.  Update the manifest paths accordingly: if a referenced file
    # no longer exists but the same-stem .png does, switch the reference.
    _rewire_image_paths_after_normalize(manifest, output_dir)
    add_image_stats_and_counts(manifest, figures_dir)

    manifest_path = output_dir / "figure_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log_path = output_dir / "parse_log.json"
    log_path.write_text(
        json.dumps(
            {
                "pdf_path": str(pdf_path),
                "mineru_raw_dir": str(raw_root),
                "content_list_source": str(content_list_path),
                "pix2tex_enabled": use_pix2tex and has_pix2tex(),
                "issues": parse_log,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return manifest


def _rewire_image_paths_after_normalize(manifest: dict[str, Any], output_dir: Path) -> None:
    """If image_preprocessor renamed foo.pdf -> foo.png, update manifest refs."""
    figures_dir = output_dir / "figures"

    def fix(paths: list[str]) -> list[str]:
        out: list[str] = []
        for raw in paths:
            target = output_dir / raw if not raw.startswith("/") else Path(raw)
            if target.exists():
                out.append(raw)
                continue
            # Try same stem with .png
            stem = Path(raw).stem
            alt = figures_dir / f"{stem}.png"
            if alt.exists():
                out.append(f"figures/{alt.name}")
            else:
                out.append(raw)
        return out

    for f in manifest.get("figures", []):
        f["image_paths"] = fix(f.get("image_paths", []))
        if f.get("subfigures"):
            for sf in f["subfigures"]:
                sf["image_paths"] = fix(sf.get("image_paths", []))
    for t in manifest.get("tables", []):
        t["image_paths"] = fix(t.get("image_paths", []))
    manifest["unmatched_images"] = fix(manifest.get("unmatched_images", []))


# ============================================================
# CLI
# ============================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full-spectrum PDF parser: figures + tables + equations -> figure_manifest.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sub_parse = subparsers.add_parser("parse", help="Parse a single PDF into a manifest")
    sub_parse.add_argument("--pdf", required=True, help="Path to the input PDF")
    sub_parse.add_argument("--output-dir", required=True, help="Destination directory")
    sub_parse.add_argument("--mineru-bin", default="mineru", help="MinerU binary name on PATH (default: mineru)")
    sub_parse.add_argument(
        "--mineru-raw-dir",
        default=None,
        help="Reuse a pre-existing MinerU output directory (skip rerun).",
    )
    sub_parse.add_argument(
        "--mock-mineru-output",
        default=None,
        help="Self-test mode: pretend this directory is MinerU's output. Skips MinerU.",
    )
    sub_parse.add_argument(
        "--no-pix2tex",
        action="store_true",
        help="Disable pix2tex equation fallback.",
    )
    sub_parse.add_argument("--lang", default="en", help="OCR language for MinerU (default: en)")

    subparsers.add_parser("check-deps", help="Print availability of MinerU / pix2tex.")

    args = parser.parse_args(argv)

    if args.command == "check-deps":
        return check_deps_cli()

    if args.command == "parse":
        pdf_path = Path(args.pdf)
        # PDF only needs to exist when we're actually going to invoke MinerU.
        # Reuse modes (mock or pre-existing mineru_raw) treat --pdf as metadata.
        will_invoke_mineru = (args.mock_mineru_output is None and args.mineru_raw_dir is None)
        if will_invoke_mineru and not pdf_path.exists():
            print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
            return 1

        try:
            manifest = parse_pdf(
                pdf_path=pdf_path,
                output_dir=Path(args.output_dir),
                mineru_bin=args.mineru_bin,
                use_pix2tex=not args.no_pix2tex,
                mineru_raw_dir=Path(args.mineru_raw_dir) if args.mineru_raw_dir else None,
                mock_mineru_output=Path(args.mock_mineru_output) if args.mock_mineru_output else None,
                lang=args.lang,
            )
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        # Brief summary to stdout (matches latex_source_parser CLI feedback)
        print(
            json.dumps(
                {
                    "figure_count": manifest.get("figure_count", 0),
                    "table_count": manifest.get("table_count", 0),
                    "equation_count": manifest.get("equation_count", 0),
                    "image_stats": manifest.get("image_stats", {}),
                    "manifest_path": str(Path(args.output_dir) / "figure_manifest.json"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
