#!/usr/bin/env python3
"""
spec_parser.py
==============

Parses the v2 `derivation-target.md` causal-graph endpoint blocks
(sections §1A, §1B, §1C, §1D) into a structured dict that the
`axiom-explorer` subagent consumes as part of its input payload.

This tool is OPTIONAL — the calling skill (`derivation-refine-loop`
Step 3.5) already has a `try/except ImportError` fallback that
passes the raw markdown to the axiom-explorer if this module is not
importable. The structured dict is preferred because:

  1. It guarantees the four endpoint blocks are present and at least
     filled enough to be machine-readable, before any compute is
     spent.
  2. It separates the user's filled-in values from template
     placeholders (`{e.g. ...}` patterns), so the explorer doesn't
     waste search-budget hallucinating off placeholder text.
  3. It produces an explicit `unfilled[]` list that the skill can
     surface to the user as "you need to fill in these fields
     before the loop can axiom-explore here."

Usage (Python):

    from tools.spec_parser import parse_endpoint_blocks
    with open("derivation-target.md") as f:
        spec = f.read()
    endpoints = parse_endpoint_blocks(spec)
    # endpoints["source_endpoint"]["allowed_parametrizations"] → list[str]

Usage (CLI, for smoke-testing):

    python3 tools/spec_parser.py parse \
        --input  analytic-derivation/<run>/derivation-target.md \
        --output /tmp/endpoints.json
    python3 tools/spec_parser.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_endpoint_blocks(text: str) -> dict[str, Any]:
    """Parse a derivation-target.md spec into structured endpoint dict.

    Returns a dict with keys:
      - source_endpoint:        dict | None  (§1A)
      - sink_endpoint:          dict | None  (§1B)
      - required_intermediates: list[str]    (§1C)
      - forbidden_detours:      list[str]    (§1D)
      - unfilled:               list[str]    paths of fields still at
                                              template default
      - warning:                str | None   high-level diagnostic; None on
                                              full success
      - schema_version:         "v2"
    """
    sections = _slice_sections(text)

    source = _parse_endpoint_section(
        sections.get("1A"),
        functional_key="allowed_parametrizations",
        disallowed_key="disallowed_parametrizations",
    )
    sink = _parse_endpoint_section(
        sections.get("1B"),
        functional_key="allowed_statistical_functionals",
        disallowed_key="disallowed_instantiations",
    )
    required = _parse_list_only_section(sections.get("1C"))
    forbidden = _parse_list_only_section(sections.get("1D"))

    unfilled: list[str] = []
    if source is None:
        unfilled.append("§1A source_endpoint (missing block)")
    else:
        unfilled.extend(_collect_unfilled(source, "source_endpoint"))
    if sink is None:
        unfilled.append("§1B sink_endpoint (missing block)")
    else:
        unfilled.extend(_collect_unfilled(sink, "sink_endpoint"))

    # §1C / §1D are OPTIONAL — empty is fine, not "unfilled".

    warning = None
    if source is None or sink is None:
        warning = (
            "spec is missing one or more SACRED endpoint blocks; "
            "axiom-explorer cannot proceed. Fix §1A and §1B in the spec."
        )
    elif unfilled:
        warning = (
            f"spec has {len(unfilled)} field(s) still at template default; "
            "axiom-explorer's isomorphism guard may flag endpoint_underspecified. "
            "See `unfilled` for the full list."
        )

    return {
        "schema_version": "v2",
        "source_endpoint": source,
        "sink_endpoint": sink,
        "required_intermediates": required,
        "forbidden_detours": forbidden,
        "unfilled": unfilled,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Section slicer
# ---------------------------------------------------------------------------


# Matches a §-style heading line starting with "### 1A.", "### 1B.", etc.
# Permissive: tolerates extra whitespace, missing punctuation, or
# "— MUST FILL" / "— OPTIONAL" annotations.
_SECTION_HEADER_RE = re.compile(
    r"^###\s*1([ABCD])\b[^\n]*$",
    re.MULTILINE,
)


def _slice_sections(text: str) -> dict[str, str]:
    """Return {section_letter: section_body_text}, e.g. {'1A': '- **Node ...'}."""
    matches = list(_SECTION_HEADER_RE.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        letter = "1" + m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        # Stop at the next ## or ### outside our section (defensive)
        next_section = re.search(r"^##\s", body, re.MULTILINE)
        if next_section:
            body = body[: next_section.start()]
        out[letter] = body.strip()
    return out


# ---------------------------------------------------------------------------
# Bullet-block parsing
# ---------------------------------------------------------------------------


# Matches a top-level bullet of the form `- **Key**: rest`.
# Bold key is required (the template always bolds them).
_TOP_BULLET_RE = re.compile(
    r"^-\s+\*\*([^*]+?)\*\*\s*(?:\([^)]*\))?\s*:?\s*(.*)$",
    re.MULTILINE,
)

# Matches a nested sub-bullet (2+ spaces of indent, then `- ` or `* `).
_SUB_BULLET_RE = re.compile(
    r"^[ \t]{2,}[-*]\s+(.+)$",
    re.MULTILINE,
)


def _parse_endpoint_section(
    body: str | None,
    *,
    functional_key: str,
    disallowed_key: str,
) -> dict[str, Any] | None:
    """Parse §1A or §1B into a dict.

    `functional_key` is the JSON key for the list of allowed instantiations
    (different vocabulary for source vs sink). `disallowed_key` is the
    matching forbidden-list key.
    """
    if not body:
        return None

    parsed = _parse_bullets_with_subbullets(body)

    # Canonicalize keys. The template uses prose labels like
    # "Node name", "Physical class", etc.; map them onto JSON keys.
    key_map = {
        "node name": "node_name",
        "physical class": "physical_class",
        "allowed parametrizations": functional_key,
        "allowed statistical functionals": functional_key,
        "disallowed parametrizations": disallowed_key,
        "disallowed instantiations": disallowed_key,
        "ontology tag": "ontology_tag",
    }

    out: dict[str, Any] = {
        "node_name": None,
        "physical_class": None,
        functional_key: [],
        disallowed_key: [],
        "ontology_tag": None,
    }

    for label, payload in parsed.items():
        canon = key_map.get(label.strip().lower())
        if canon is None:
            # Unknown bullet — preserve verbatim under "extra_<label>"
            out[f"extra_{_slugify(label)}"] = payload
            continue
        if canon in (functional_key, disallowed_key):
            # Always a list; payload may be a list of sub-bullets OR a
            # single inline string (treat the latter as a 1-item list).
            if isinstance(payload, list):
                out[canon] = [_strip_placeholder(x) for x in payload
                              if _strip_placeholder(x)]
            elif _strip_placeholder(payload):
                out[canon] = [_strip_placeholder(payload)]
        else:
            # Scalar fields: strip placeholders to None if value is e.g.-text
            if isinstance(payload, list):
                # The template sometimes puts the value on the next line as
                # the only sub-bullet. Take the first nonempty item.
                first = next((p for p in payload if _strip_placeholder(p)),
                             None)
                out[canon] = first
            else:
                out[canon] = _strip_placeholder(payload)

    return out


def _parse_list_only_section(body: str | None) -> list[str]:
    """Parse §1C / §1D as a flat list of bullet items."""
    if not body:
        return []
    items: list[str] = []
    for line in body.splitlines():
        line = line.rstrip()
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if not m:
            continue
        item = _strip_placeholder(m.group(1).strip())
        if item:
            items.append(item)
    return items


def _parse_bullets_with_subbullets(body: str) -> dict[str, Any]:
    """Walk body line-by-line; group top bullets with their sub-bullets.

    Returns {top_label: payload}, where payload is either:
      - str  — if the top bullet had inline content and no sub-bullets
      - list[str] — if there were sub-bullets (in source order)
    """
    out: dict[str, Any] = {}
    current_label: str | None = None
    current_inline: str = ""
    current_subs: list[str] = []

    def _flush() -> None:
        nonlocal current_label, current_inline, current_subs
        if current_label is None:
            return
        if current_subs:
            # Sub-bullets take precedence; if inline text was also
            # present (rare), include it as the first item.
            payload: Any = ([current_inline] if current_inline.strip()
                            else []) + current_subs
            out[current_label] = payload
        else:
            out[current_label] = current_inline.strip()
        current_label = None
        current_inline = ""
        current_subs = []

    for raw_line in body.splitlines():
        # Top-level bullet?
        m_top = _TOP_BULLET_RE.match(raw_line)
        if m_top:
            _flush()
            current_label = m_top.group(1).strip()
            current_inline = m_top.group(2).strip()
            continue
        # Sub-bullet?
        m_sub = _SUB_BULLET_RE.match(raw_line)
        if m_sub and current_label is not None:
            current_subs.append(m_sub.group(1).strip())
            continue
        # Continuation line of inline value (e.g. wrapped prose)?
        if current_label is not None and raw_line.strip() and not raw_line.lstrip().startswith(("-", "*")):
            if current_inline:
                current_inline += " " + raw_line.strip()
            else:
                current_inline = raw_line.strip()

    _flush()
    return out


# ---------------------------------------------------------------------------
# Placeholder / unfilled detection
# ---------------------------------------------------------------------------


# Matches template placeholders like `{e.g. "..."}` or `{...}`.
# We treat any value entirely wrapped in {...} as a placeholder, AND
# any value that *starts* with `{e.g.` (the template's e.g.-marker often
# wraps across lines, so the closing brace may live on a later line).
_PLACEHOLDER_RE = re.compile(r"^\s*\{[^{}]*\}\s*$")
_PLACEHOLDER_PREFIX_RE = re.compile(r"^\s*\{?\s*e\.g\.\s", re.IGNORECASE)
# Matches a residual parenthetical-label fragment that leaked from a
# multi-line bullet header like `- **Key** (long\n explanation):`. The
# leaked fragment looks like "(long explanation):" or "long explanation):"
# at the start of `current_inline`. We strip those.
# Catch a leaked "(...): " prefix that bled in from a multi-line
# bullet-header parenthetical. We allow any chars between `(` and `):`
# (including em-dashes, quotes, nested punctuation other than `)`).
_LEAKED_LABEL_PAREN_RE = re.compile(r"^\([^)]*\):\s*")
# Catch a placeholder-tail fragment like `...long e.g. text"}` left over
# when a multi-line `{e.g. "..."}` wraps across lines and our regex only
# captured the head.
_PLACEHOLDER_TAIL_RE = re.compile(r'.*?["\']?\}\s*$')


def _strip_placeholder(text: str | None) -> str | None:
    """Return None if the text is a template placeholder; otherwise stripped text.

    Recognises three placeholder shapes:
      1. Self-contained {...} on one line.
      2. Multi-line {e.g. ...} where the opening brace may have been
         consumed by the bullet-label regex and only the e.g. tail
         survives.
      3. Residual ")"-tail from a multi-line bullet parenthetical
         label that bled into the value.
    Also strips leading/trailing backticks (markdown inline code).
    """
    if text is None:
        return None
    s = text.strip()
    if not s:
        return None
    # Case 3: drop any leaked "...): " residue at the start of the value.
    s2 = _LEAKED_LABEL_PAREN_RE.sub("", s)
    if s2 != s:
        s = s2.strip()
        if not s:
            return None
    # Case 1: self-contained placeholder.
    if _PLACEHOLDER_RE.match(s):
        return None
    # Case 2: starts with `{e.g.` or `e.g.` — template default.
    if _PLACEHOLDER_PREFIX_RE.match(s):
        return None
    # Case 4: leftover tail of a wrapped {e.g. ...} placeholder —
    # text that ends with `"}` (or `'}`) and contains no meaningful
    # content. Treat conservatively: only strip if the body is
    # plausibly a wrap-fragment (short, ends with the placeholder
    # closing delimiter).
    if s.endswith(('"}', "'}", "}")) and not s.startswith(("{", "(")):
        # Could still be a user-supplied value that happens to end in
        # `}`; only drop if the value looks like prose ending in `"}`
        # (i.e. contains no JSON-like structure).
        if "{" not in s and len(s) < 250:
            return None
    # Strip leading/trailing backticks (markdown inline code).
    s = s.strip("`").strip()
    if not s:
        return None
    return s


def _collect_unfilled(d: dict[str, Any], prefix: str) -> list[str]:
    """Walk dict and return dotted paths of None / empty values."""
    out: list[str] = []
    for k, v in d.items():
        if k.startswith("extra_"):
            continue
        path = f"{prefix}.{k}"
        if v is None:
            out.append(path)
        elif isinstance(v, list) and not v:
            out.append(path)
    return out


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_SELFTEST_FIXTURE = """# Derivation Target Spec (v2)

## 1. Research-question definition — MUST FILL

### 1A. Source endpoint (control-parameter CLASS) — MUST FILL

- **Node name**: `nuclear_quadrupole_deformation`
- **Physical class** (one sentence):
  Ground-state axisymmetric quadrupole deformation of the colliding nucleus.
- **Allowed parametrizations** (what counts as the same class):
  - scalar β_2
  - β_2 with Euler-angle orientation DOF (vector form)
  - β_2 + β_2,γ triaxial parameters
- **Disallowed parametrizations** (would change the research question):
  - β_3 (octupole) — a different deformation order
  - nuclear charge radius — different physical quantity
- **Ontology tag** (machine-readable): `physics/nuclear-structure/deformation/quadrupole`

### 1B. Sink endpoint (observable CLASS) — MUST FILL

- **Node name**: `event_variance_of_longitudinal_Lambda_polarization`
- **Physical class** (one sentence):
  Event-by-event fluctuation of the longitudinal Λ polarization in HIC.
- **Allowed statistical functionals**:
  - Var(P_z) = <P_z²> - <P_z>²
  - <P_z²> (second moment)
- **Disallowed instantiations**:
  - <P_z> alone
  - P_y
- **Ontology tag** (machine-readable): `physics/heavy-ion/polarization/longitudinal/fluctuation`

### 1C. Required intermediate nodes — OPTIONAL

- hydrodynamic response v_2 = k_2 · ε_2

### 1D. Forbidden detours — OPTIONAL

- no QED / EM-field contributions to the polarization
- no contributions beyond Standard Model

### 1E. Target observable — MATH FORM — MUST FILL

(this block is ignored by the parser)
"""


def _cmd_selftest() -> int:
    result = parse_endpoint_blocks(_SELFTEST_FIXTURE)

    assertions = []
    assertions.append(
        ("schema_version is v2", result["schema_version"] == "v2"),
    )
    assertions.append(
        ("source_endpoint present",
         result["source_endpoint"] is not None),
    )
    assertions.append(
        ("sink_endpoint present",
         result["sink_endpoint"] is not None),
    )
    assertions.append(
        ("source node_name correct",
         result["source_endpoint"]["node_name"]
         == "nuclear_quadrupole_deformation"),
    )
    assertions.append(
        ("source allowed_parametrizations has 3 entries",
         len(result["source_endpoint"]["allowed_parametrizations"]) == 3),
    )
    assertions.append(
        ("sink allowed_statistical_functionals has 2 entries",
         len(result["sink_endpoint"]["allowed_statistical_functionals"]) == 2),
    )
    assertions.append(
        ("source disallowed_parametrizations has 2 entries",
         len(result["source_endpoint"]["disallowed_parametrizations"]) == 2),
    )
    assertions.append(
        ("required_intermediates has 1 entry",
         len(result["required_intermediates"]) == 1),
    )
    assertions.append(
        ("forbidden_detours has 2 entries",
         len(result["forbidden_detours"]) == 2),
    )
    assertions.append(
        ("unfilled is empty (fixture is fully filled)",
         result["unfilled"] == []),
    )
    assertions.append(
        ("warning is None (fully filled)",
         result["warning"] is None),
    )

    failures = [(name, ok) for name, ok in assertions if not ok]
    for name, ok in assertions:
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {name}")

    if failures:
        print()
        print(f"FAIL: {len(failures)}/{len(assertions)} assertions failed.")
        print("Parsed result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    print()
    print(f"OK: all {len(assertions)} assertions passed.")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    text = Path(args.input).read_text()
    result = parse_endpoint_blocks(text)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(payload + "\n")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(payload)
    return 0 if result["source_endpoint"] and result["sink_endpoint"] else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="spec_parser",
        description=__doc__.splitlines()[1] if __doc__ else "",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="parse a derivation-target.md")
    p_parse.add_argument("--input", required=True,
                         help="path to derivation-target.md")
    p_parse.add_argument("--output", default=None,
                         help="path for JSON output; stdout if omitted")

    sub.add_parser("selftest", help="run built-in fixture test")

    args = p.parse_args(argv)

    if args.cmd == "parse":
        return _cmd_parse(args)
    if args.cmd == "selftest":
        return _cmd_selftest()
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
