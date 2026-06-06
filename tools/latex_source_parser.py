#!/usr/bin/env python3
"""
Parse an extracted arXiv TeX source directory and extract structured
information about figures, tables, their captions, labels, and in-text references.

Usage:
    python3 latex_source_parser.py <source_dir> [--output figure_manifest.json]

Output JSON structure:
{
  "main_tex": "main.tex",
  "figures": [...],
  "tables": [...],
  "equations": [
    {
      "id": "eq:loss",
      "type": "equation",
      "environment": "equation",
      "label": "eq:loss",
      "latex": "L = \\sum_{i=1}^n (y_i - \\hat{y}_i)^2",
      "numbered": true,
      "raw_tex": "\\begin{equation}...\\end{equation}",
      "context_paragraphs": ["As defined in Equation \\eqref{eq:loss}, ..."],
      "referenced_in_text": true
    }
  ],
  "unmatched_images": ["logo.png"]
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


# ============================================================
# Constants
# ============================================================

# Image extensions commonly used in LaTeX
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".ps", ".gif", ".tiff", ".tif", ".bmp"}

# Max recursion depth for \input / \include
MAX_INCLUDE_DEPTH = 10

# Environment names we care about
FIGURE_ENVS = {"figure", "figure*", "wrapfigure", "wrapfigure*"}
TABLE_ENVS = {"table", "table*", "wraptable", "wraptable*", "tabular", "tabular*"}
SUBFIGURE_ENVS = {"subfigure", "subfloat"}


# ============================================================
# Utility functions
# ============================================================

def find_main_tex(source_dir: Path) -> Path | None:
    """Find the main .tex file by looking for \\documentclass."""
    tex_files = list(source_dir.rglob("*.tex"))
    if not tex_files:
        return None

    # Prefer root-level .tex files first
    root_tex = [f for f in tex_files if f.parent == source_dir]
    candidates = root_tex if root_tex else tex_files

    for tex_file in candidates:
        try:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            if r"\documentclass" in content:
                return tex_file
        except Exception:
            continue

    # Fallback: return the first root-level tex, or first anywhere
    return candidates[0] if candidates else None


def resolve_input_path(base_dir: Path, input_path: str) -> Path | None:
    """Resolve a path from \\input or \\include to an actual file."""
    # Strip .tex extension if present (LaTeX adds it automatically)
    clean = input_path.strip()
    if clean.endswith(".tex"):
        candidates = [clean]
    else:
        candidates = [clean + ".tex", clean]

    for cand in candidates:
        p = base_dir / cand
        if p.exists():
            return p
    return None


def read_tex_with_includes(tex_path: Path, depth: int = 0, visited: set[str] | None = None) -> str:
    """Read a .tex file, recursively inlining \\input and \\include."""
    if depth > MAX_INCLUDE_DEPTH:
        return ""
    if visited is None:
        visited = set()

    abs_path = str(tex_path.resolve())
    if abs_path in visited:
        return ""
    visited.add(abs_path)

    try:
        content = tex_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    base_dir = tex_path.parent

    # Pattern for \input{...} and \include{...}
    input_pattern = re.compile(r"\\(input|include)\{([^}]+)\}")

    def replace_input(m: re.Match) -> str:
        cmd = m.group(1)
        path_str = m.group(2)
        included = resolve_input_path(base_dir, path_str)
        if included is None:
            return m.group(0)  # keep original if not found
        return read_tex_with_includes(included, depth + 1, visited)

    return input_pattern.sub(replace_input, content)


def strip_comments(tex: str) -> str:
    """Remove TeX comments (lines starting with %, or inline %)."""
    lines = []
    for line in tex.splitlines():
        # Handle escaped % (\%) — simple heuristic
        idx = line.find("%")
        while idx != -1:
            if idx > 0 and line[idx - 1] == "\\":
                idx = line.find("%", idx + 1)
            else:
                break
        if idx != -1:
            line = line[:idx]
        lines.append(line)
    return "\n".join(lines)


def find_matching_end(tex: str, start_pos: int, env_name: str) -> int:
    """Find the matching \\end{env_name} for a \\begin{env_name} at start_pos."""
    # Simple brace-level counting for \begin and \end
    pattern_begin = re.compile(r"\\begin\{([^}]+)\}")
    pattern_end = re.compile(r"\\end\{([^}]+)\}")

    depth = 1
    pos = start_pos + len(f"\\begin{{{env_name}}}")
    while depth > 0 and pos < len(tex):
        b = pattern_begin.search(tex, pos)
        e = pattern_end.search(tex, pos)

        if b and e:
            if b.start() < e.start():
                if b.group(1) == env_name:
                    depth += 1
                pos = b.end()
            else:
                if e.group(1) == env_name:
                    depth -= 1
                if depth == 0:
                    return e.start()
                pos = e.end()
        elif e:
            if e.group(1) == env_name:
                depth -= 1
            if depth == 0:
                return e.start()
            pos = e.end()
        else:
            break

    return -1


def extract_brace_content(tex: str, start: int) -> tuple[str, int] | None:
    """Extract the content inside matching braces starting at start. Returns (content, end_pos)."""
    if start >= len(tex) or tex[start] != "{":
        return None
    depth = 1
    i = start + 1
    while i < len(tex) and depth > 0:
        if tex[i] == "{":
            depth += 1
        elif tex[i] == "}":
            depth -= 1
        i += 1
    if depth == 0:
        return tex[start + 1 : i - 1], i
    return None


def extract_caption(tex: str) -> str | None:
    """Extract \\caption{...} content, handling optional short caption."""
    # \\caption[short]{long}  or  \\caption{long}
    # Use a simpler approach: find \\caption, then extract braces
    idx = tex.find(r"\caption")
    if idx == -1:
        return None

    pos = idx + len(r"\caption")
    # Skip optional [...]
    if pos < len(tex) and tex[pos] == "[":
        close = tex.find("]", pos + 1)
        if close != -1:
            pos = close + 1

    result = extract_brace_content(tex, pos)
    if result:
        return result[0].strip()
    return None


def extract_label(tex: str) -> str | None:
    """Extract \\label{...} content."""
    pattern = re.compile(r"\\label\{([^}]+)\}")
    m = pattern.search(tex)
    return m.group(1).strip() if m else None


def extract_includegraphics(tex: str) -> list[str]:
    """Extract all \\includegraphics[...]{filename} paths."""
    paths = []
    # Pattern: \\includegraphics[optional]{filename}
    pattern = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
    for m in pattern.finditer(tex):
        paths.append(m.group(1).strip())
    return paths


def resolve_image_paths(raw_paths: list[str], source_dir: Path, tex_dir: Path) -> list[str]:
    """Resolve raw image paths to actual files relative to source_dir."""
    resolved = []
    for raw in raw_paths:
        # Some papers use paths like {fig1,fig2} for subfigures — skip those
        if "," in raw and not any(ext in raw.lower() for ext in IMAGE_EXTENSIONS):
            continue

        # Try with and without extension
        candidates = [raw]
        if not any(raw.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
            for ext in IMAGE_EXTENSIONS:
                candidates.append(raw + ext)

        found = False
        for cand in candidates:
            # Try relative to tex directory first, then source root
            for base in [tex_dir, source_dir]:
                p = base / cand
                if p.exists():
                    try:
                        rel = p.relative_to(source_dir)
                        resolved.append(str(rel))
                    except ValueError:
                        resolved.append(str(p))
                    found = True
                    break
            if found:
                break

        if not found:
            # Fallback: search entire source tree by basename + extension
            # Handles messy arXiv sources where images are dumped in root
            # but referenced as figs/model.pdf or similar
            stem = Path(raw).stem
            for ext in IMAGE_EXTENSIONS:
                matches = list(source_dir.rglob(f"{stem}{ext}")) + list(source_dir.rglob(f"{stem}{ext.upper()}"))
                if matches:
                    try:
                        rel = matches[0].relative_to(source_dir)
                        resolved.append(str(rel))
                    except ValueError:
                        resolved.append(str(matches[0]))
                    found = True
                    break

        if not found:
            # Keep the raw path even if not found — subagent can try to locate it
            resolved.append(raw)

    return resolved


def find_references_in_text(full_tex: str, label: str, context_chars: int = 300) -> list[str]:
    """Find \\ref{label} and \\cref{label} in the full text and extract surrounding context."""
    contexts = []
    # Match \ref{label}, \cref{label}, \Cref{label}, \eqref{label}
    pattern = re.compile(r"\\(?:c|C|eq)?ref\{" + re.escape(label) + r"\}")
    for m in pattern.finditer(full_tex):
        start = max(0, m.start() - context_chars)
        end = min(len(full_tex), m.end() + context_chars)
        snippet = full_tex[start:end]
        # Clean up: collapse whitespace
        snippet = " ".join(snippet.split())
        contexts.append(snippet)
    return contexts


def extract_floats(full_tex: str, env_names: set[str]) -> list[dict[str, Any]]:
    """Extract all floating environments (figure/table) from the full TeX text."""
    floats = []
    # Match any \begin{figure...} or \begin{table...}
    env_pattern = re.compile(r"\\begin\{((?:" + "|".join(re.escape(e) for e in env_names) + r")\*?)\}")

    pos = 0
    while True:
        m = env_pattern.search(full_tex, pos)
        if not m:
            break

        env_name = m.group(1)
        start_pos = m.start()
        end_pos = find_matching_end(full_tex, start_pos, env_name)
        if end_pos == -1:
            pos = m.end()
            continue

        body = full_tex[m.end():end_pos]

        # Extract components
        label = extract_label(body)
        caption = extract_caption(body)
        image_paths = extract_includegraphics(body)

        # Check for subfigures
        subfigures = []
        for sub_env in SUBFIGURE_ENVS:
            sub_pattern = re.compile(rf"\\begin\{{{re.escape(sub_env)}\*?\}}")
            for sm in sub_pattern.finditer(body):
                sub_end = find_matching_end(body, sm.start(), sub_env)
                if sub_end == -1:
                    continue
                sub_body = body[sm.end():sub_end]
                sub_label = extract_label(sub_body)
                sub_caption = extract_caption(sub_body)
                sub_images = extract_includegraphics(sub_body)
                subfigures.append({
                    "label": sub_label,
                    "caption": sub_caption,
                    "image_paths": sub_images,
                })

        float_type = "figure" if any(e.startswith("figure") or e.startswith("wrapfigure") for e in [env_name]) else "table"

        floats.append({
            "type": float_type,
            "environment": env_name,
            "label": label,
            "caption": caption,
            "image_paths": image_paths,
            "subfigures": subfigures if subfigures else None,
            "raw_tex": full_tex[start_pos:end_pos + len(f"\\end{{{env_name}}}")],
        })

        pos = end_pos + len(f"\\end{{{env_name}}}")

    return floats


# Equation environments we care about
EQUATION_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "eqnarray", "eqnarray*"}


def extract_equations(full_tex: str) -> list[dict[str, Any]]:
    """Extract display math environments from the full TeX text."""
    equations: list[dict[str, Any]] = []
    eq_counter = 1

    # 1. \begin{equation}, \begin{align}, etc.
    env_pattern = re.compile(
        r"\\begin\{(" + "|".join(re.escape(e) for e in EQUATION_ENVS) + r")\}"
    )
    pos = 0
    while True:
        m = env_pattern.search(full_tex, pos)
        if not m:
            break
        env_name = m.group(1)
        start_pos = m.start()
        end_pos = find_matching_end(full_tex, start_pos, env_name)
        if end_pos == -1:
            pos = m.end()
            continue
        end_full = end_pos + len(f"\\end{{{env_name}}}")
        body = full_tex[m.end():end_pos]
        label = extract_label(body)
        eq_id = label if label else f"eq_{eq_counter}"
        eq_counter += 1
        equations.append({
            "id": eq_id,
            "type": "equation",
            "environment": env_name,
            "label": label,
            "latex": body.strip(),
            "numbered": not env_name.endswith("*"),
            "raw_tex": full_tex[start_pos:end_full],
            "start_pos": start_pos,
            "end_pos": end_full,
        })
        pos = end_full

    # 2. \[ ... \]
    display_pattern = re.compile(r"\\\[((?:[^\\]|\\(?!\]))*?)\\\]")
    for m in display_pattern.finditer(full_tex):
        start_pos = m.start()
        end_pos = m.end()
        # Skip if inside an already-extracted environment
        if any(e["start_pos"] <= start_pos < e["end_pos"] for e in equations):
            continue
        body = m.group(1)
        label = extract_label(body)
        eq_id = label if label else f"eq_{eq_counter}"
        eq_counter += 1
        equations.append({
            "id": eq_id,
            "type": "equation",
            "environment": "displaymath",
            "label": label,
            "latex": body.strip(),
            "numbered": False,
            "raw_tex": m.group(0),
            "start_pos": start_pos,
            "end_pos": end_pos,
        })

    # 3. $$ ... $$
    display_dollar_pattern = re.compile(r"\$\$((?:[^\$]|\\\$)*?)\$\$")
    for m in display_dollar_pattern.finditer(full_tex):
        start_pos = m.start()
        end_pos = m.end()
        if any(e["start_pos"] <= start_pos < e["end_pos"] for e in equations):
            continue
        body = m.group(1)
        label = extract_label(body)
        eq_id = label if label else f"eq_{eq_counter}"
        eq_counter += 1
        equations.append({
            "id": eq_id,
            "type": "equation",
            "environment": "displaymath",
            "label": label,
            "latex": body.strip(),
            "numbered": False,
            "raw_tex": m.group(0),
            "start_pos": start_pos,
            "end_pos": end_pos,
        })

    # Sort by position and remove internal position fields
    equations.sort(key=lambda e: e["start_pos"])
    for e in equations:
        del e["start_pos"]
        del e["end_pos"]

    return equations


def find_all_images(source_dir: Path) -> list[str]:
    """Find all image files in the source directory."""
    images = []
    for ext in IMAGE_EXTENSIONS:
        images.extend(source_dir.rglob(f"*{ext}"))
        images.extend(source_dir.rglob(f"*{ext.upper()}"))
    # Return paths relative to source_dir
    return sorted(set(str(p.relative_to(source_dir)) for p in images))


def parse_tex_source(source_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    """Main entry point: parse a TeX source directory and return structured data."""
    source_dir = Path(source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    main_tex = find_main_tex(source_dir)
    if main_tex is None:
        return {
            "main_tex": None,
            "figures": [],
            "tables": [],
            "unmatched_images": find_all_images(source_dir),
            "error": "No .tex files found",
        }

    # Read full document with includes inlined
    full_tex = read_tex_with_includes(main_tex)
    full_tex_nocomment = strip_comments(full_tex)

    tex_dir = main_tex.parent

    # Extract figures and tables
    figure_envs = FIGURE_ENVS | SUBFIGURE_ENVS
    table_envs = TABLE_ENVS

    all_floats = extract_floats(full_tex_nocomment, figure_envs | table_envs)

    figures = []
    tables = []

    for f in all_floats:
        if f["type"] == "figure":
            figures.append(f)
        else:
            tables.append(f)

    # Resolve image paths
    for f in figures:
        f["image_paths"] = resolve_image_paths(f["image_paths"], source_dir, tex_dir)
        if f.get("subfigures"):
            for sf in f["subfigures"]:
                sf["image_paths"] = resolve_image_paths(sf["image_paths"], source_dir, tex_dir)

    # Extract equations
    equations = extract_equations(full_tex_nocomment)
    for eq in equations:
        if eq.get("label"):
            eq["context_paragraphs"] = find_references_in_text(full_tex_nocomment, eq["label"])
            eq["referenced_in_text"] = len(eq["context_paragraphs"]) > 0
        else:
            eq["context_paragraphs"] = []
            eq["referenced_in_text"] = False

    # Find in-text references for figures and tables
    for f in figures + tables:
        if f.get("label"):
            f["context_paragraphs"] = find_references_in_text(full_tex_nocomment, f["label"])
            f["referenced_in_text"] = len(f["context_paragraphs"]) > 0
        else:
            f["context_paragraphs"] = []
            f["referenced_in_text"] = False

    # Find unmatched images (images not referenced by any figure)
    all_images = set(find_all_images(source_dir))
    referenced = set()
    for f in figures:
        for p in f.get("image_paths", []):
            referenced.add(p)
        if f.get("subfigures"):
            for sf in f["subfigures"]:
                for p in sf.get("image_paths", []):
                    referenced.add(p)

    unmatched = sorted(all_images - referenced)

    result = {
        "main_tex": str(main_tex.relative_to(source_dir)),
        "figures": figures,
        "tables": tables,
        "equations": equations,
        "unmatched_images": unmatched,
    }

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


# ============================================================
# CLI
# ============================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse arXiv TeX source and extract figure/table metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source_dir", help="Path to extracted TeX source directory")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: print to stdout)",
    )
    args = parser.parse_args(argv)

    try:
        result = parse_tex_source(args.source_dir, args.output)
        if args.output is None:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Wrote {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
