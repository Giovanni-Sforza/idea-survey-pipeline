#!/usr/bin/env python3
"""Fetch and verify BibTeX entries for a research-proposal pipeline.

This tool exists because earlier runs of `research-proposal` produced citations
where the cite key was real but the rendered year / author / venue in the prose
was hallucinated. The fix is to *materialize* official BibTeX from a small set
of trusted sources, *validate* it against expected metadata, and *publish* a
ground-truth ``bib_index.json`` that the drafting subagent must consult for
every author / year / venue mention.

Sources (in priority order, matching shared-references/citation-discipline.md):
  1. DBLP search + ``dblp.org/rec/{key}.bib``        (CS/ML conference papers)
  2. arXiv official BibTeX endpoint                  (preprints, fallback)
  3. CrossRef content negotiation on a DOI           (journals)

Validation:
  After fetching, the entry's title / first-author surname / year are compared
  to the *expected* values the caller supplied. A mismatch is logged and the
  entry is marked ``"validated": false``. The caller can then choose to drop
  the entry or write a ``\\needfix{}`` placeholder in the proposal.

Sub-commands
------------
  fetch        Fetch BibTeX for a single paper. Outputs JSON.
  build-index  Read a .bib file and emit a ``bib_index.json``.
  verify-tex   Cross-check ``\\cite{}`` keys and "(YYYY)" patterns in .tex files.

Usage examples
--------------
  python3 tools/bibtex_fetch.py fetch \\
      --arxiv-id 1909.11942 \\
      --expected-year 2019 \\
      --expected-first-author Lan \\
      --expected-title-tokens ALBERT pretraining \\
      --append-to proposal/references.bib

  python3 tools/bibtex_fetch.py build-index \\
      --bib proposal/references.bib \\
      --out proposal/bib_index.json

  python3 tools/bibtex_fetch.py verify-tex \\
      --tex proposal/main.tex proposal/body/*.tex \\
      --bib proposal/references.bib \\
      --bib-index proposal/bib_index.json
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_USER_AGENT = (
    "research-proposal-bibtex-fetch/1.0 "
    "(github.com/wanshuiyin/Auto-claude-code-research-in-sleep)"
)

_ARXIV_BIB_URL = "https://arxiv.org/bibtex/{id}"
_DBLP_SEARCH_URL = "https://dblp.org/search/publ/api?q={q}&format=json&h=5"
_DBLP_BIB_URL = "https://dblp.org/rec/{key}.bib"
_DOI_URL = "https://doi.org/{doi}"

_BIB_ENTRY_RE = re.compile(
    r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)\n\}\s*",
    re.DOTALL,
)
_BIB_FIELD_RE = re.compile(
    r"(?P<field>\w+)\s*=\s*[{\"](?P<value>.*?)[}\"](?=\s*,|\s*$)",
    re.DOTALL,
)
_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_YEAR_INLINE_RE = re.compile(
    r"([A-Z][A-Za-z\-]+(?:\s+et\s+al\.?|\s+and\s+[A-Z][A-Za-z\-]+)?)\s*[(\[]\s*(\d{4})\s*[)\]]"
)


# --------------------------------------------------------------------------- #
# Low-level HTTP                                                              #
# --------------------------------------------------------------------------- #

def _http_get(url: str, accept: str | None = None, timeout: int = 30) -> str:
    headers = {"User-Agent": _USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt == 1:
                time.sleep(3)
                continue
            raise
        except urllib.error.URLError:
            if attempt == 1:
                time.sleep(2)
                continue
            raise
    raise RuntimeError(f"HTTP retries exhausted: {url}")


# --------------------------------------------------------------------------- #
# Source-specific fetchers                                                    #
# --------------------------------------------------------------------------- #

def fetch_arxiv_bibtex(arxiv_id: str) -> str:
    """Return raw BibTeX string from arxiv.org/bibtex/{id}.

    Strips any HTML wrapper that arXiv sometimes returns for bad IDs.
    """
    raw = _http_get(_ARXIV_BIB_URL.format(id=arxiv_id))
    # arXiv occasionally returns an HTML error page with a 200 status. Detect.
    if "<!DOCTYPE" in raw[:100] or "<html" in raw[:100].lower():
        raise RuntimeError(f"arXiv returned HTML for id={arxiv_id} (probably invalid)")
    if "@" not in raw:
        raise RuntimeError(f"arXiv response contains no BibTeX entry for id={arxiv_id}")
    return raw.strip() + "\n"


def fetch_dblp_bibtex(query: str) -> tuple[str, str]:
    """Search DBLP for `query`, fetch BibTeX of the top hit. Returns (bibtex, dblp_key)."""
    search_url = _DBLP_SEARCH_URL.format(q=urllib.parse.quote(query))
    raw = _http_get(search_url)
    data = json.loads(raw)
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if not hits:
        raise RuntimeError(f"DBLP returned no hits for query: {query!r}")
    top = hits[0]["info"]
    dblp_key = top["key"]
    bib = _http_get(_DBLP_BIB_URL.format(key=dblp_key))
    if "@" not in bib:
        raise RuntimeError(f"DBLP returned no BibTeX for key={dblp_key}")
    return bib.strip() + "\n", dblp_key


def fetch_doi_bibtex(doi: str) -> str:
    """Fetch BibTeX via DOI content negotiation."""
    bib = _http_get(_DOI_URL.format(doi=doi), accept="application/x-bibtex")
    if "@" not in bib:
        raise RuntimeError(f"DOI {doi} content negotiation returned no BibTeX")
    return bib.strip() + "\n"


# --------------------------------------------------------------------------- #
# BibTeX parsing & validation                                                 #
# --------------------------------------------------------------------------- #

def parse_bib_entry(bib_text: str) -> dict:
    """Parse a *single* BibTeX entry into a dict. Returns first entry if many.

    Resulting dict has keys: ``entry_type``, ``cite_key``, ``fields`` (str->str).
    """
    m = _BIB_ENTRY_RE.search(bib_text)
    if not m:
        raise ValueError("Could not parse BibTeX entry")
    body = m.group("body")
    fields = {}
    for fm in _BIB_FIELD_RE.finditer(body):
        fields[fm.group("field").lower()] = _clean_field(fm.group("value"))
    return {
        "entry_type": m.group("type").lower(),
        "cite_key": m.group("key").strip(),
        "fields": fields,
    }


def _clean_field(v: str) -> str:
    """Light cleanup for a BibTeX field value."""
    v = re.sub(r"\s+", " ", v).strip()
    # Strip surrounding braces if any remain.
    while v.startswith("{") and v.endswith("}"):
        v = v[1:-1].strip()
    return v


_GROUP_KEYWORDS = (
    "Collaboration", "Group", "Working Group", "Consortium",
    "Team", "Project", "Experiment",
)


def first_author_surname(author_field: str) -> str:
    """Best-effort extraction of the first author's surname for prose citation.

    Special case for collaborations / groups: an entry like
    ``ATLAS Collaboration`` or ``The CMS Collaboration`` is a single corporate
    author. Returning the last whitespace token would yield ``"Collaboration"``,
    causing the drafting subagent to write ``"Collaboration (2025) showed..."``.
    Detect this pattern and return the full group name instead.

    Handles ``Last, First and Last2, First2`` and ``First Last and First2 Last2``.
    """
    first = author_field.split(" and ")[0].strip()
    # Strip a leading definite article ("The ATLAS Collaboration").
    if first.lower().startswith("the "):
        first = first[4:].strip()
    # Group-author rule: a collaboration is its own "surname".
    if any(kw in first for kw in _GROUP_KEYWORDS):
        return first
    if "," in first:
        return first.split(",")[0].strip()
    # "First Middle Last" — assume the last whitespace-separated token is the surname.
    parts = first.split()
    return parts[-1] if parts else ""


def check_arxiv_exists(arxiv_id: str) -> bool | None:
    """HEAD-probe ``arxiv.org/abs/{id}`` to detect fabricated arXiv IDs.

    Returns:
      ``True``  — the abstract page resolves (2xx/3xx status).
      ``False`` — arXiv explicitly returns 404 (the ID does not exist).
      ``None``  — network failure or other HTTP error; cannot determine.

    The ``None`` case must NOT be treated as failure — we don't want a flaky
    connection to invalidate a real citation. Only definite ``False`` (404)
    triggers a validation mismatch in :func:`validate_entry`.
    """
    url = f"https://arxiv.org/abs/{arxiv_id}"
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        return None
    except urllib.error.URLError:
        return None


def _normalize_token(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def validate_entry(
    entry: dict,
    expected_year: int | None = None,
    expected_first_author: str | None = None,
    expected_title_tokens: list[str] | None = None,
) -> dict:
    """Compare a parsed entry to caller-supplied expectations.

    Returns a dict ``{"validated": bool, "mismatches": [str, ...]}``.
    """
    mismatches = []
    fields = entry["fields"]

    if expected_year is not None:
        year_field = fields.get("year", "")
        try:
            year = int(re.sub(r"\D", "", year_field))
        except ValueError:
            year = None
        if year != expected_year:
            mismatches.append(f"year: expected={expected_year} got={year_field!r}")

    if expected_first_author:
        author_field = fields.get("author", "")
        got = first_author_surname(author_field)
        if _normalize_token(got) != _normalize_token(expected_first_author):
            mismatches.append(
                f"first_author: expected={expected_first_author!r} got={got!r}"
            )

    if expected_title_tokens:
        title_norm = _normalize_token(fields.get("title", ""))
        missing = [t for t in expected_title_tokens if _normalize_token(t) not in title_norm]
        if missing:
            mismatches.append(f"title_tokens_missing: {missing}")

    # arXiv existence cross-check — only flag definite False (404), not None.
    # ``arxiv_exists`` is set by ``fetch_for_paper`` after the BibTeX is parsed,
    # regardless of which source (DBLP / DOI / arXiv) produced it. This catches
    # the failure mode where DBLP indexes an arXiv ID that does not actually
    # resolve on arxiv.org.
    if entry.get("arxiv_exists") is False:
        bogus_id = entry.get("source_id") or fields.get("eprint", "?")
        mismatches.append(
            f"arxiv_id_does_not_resolve: {bogus_id} returns 404 on arxiv.org"
        )

    return {"validated": not mismatches, "mismatches": mismatches}


# --------------------------------------------------------------------------- #
# High-level orchestration                                                    #
# --------------------------------------------------------------------------- #

def _probe_and_attach(entry: dict, probe_arxiv: bool) -> dict:
    """If the parsed entry mentions an arXiv ID, attach ``arxiv_exists``.

    The probe runs regardless of which source (DBLP / DOI / arXiv) produced
    the entry — DBLP can index an arXiv ID that doesn't actually resolve, and
    we want to catch that.
    """
    if not probe_arxiv:
        return entry
    aid = (entry.get("fields", {}).get("eprint")
           or (entry.get("source_id") if entry.get("source") == "arxiv" else None))
    if aid:
        entry["arxiv_exists"] = check_arxiv_exists(aid)
    return entry


def fetch_for_paper(
    arxiv_id: str | None = None,
    doi: str | None = None,
    title: str | None = None,
    first_author: str | None = None,
    strategy: str = "auto",
    probe_arxiv: bool = True,
) -> dict:
    """Try sources in priority order and return the first usable entry.

    Strategy ``auto`` means:
      1. If title+author known      → try DBLP first (gives @inproceedings).
      2. If DOI known               → try DOI second.
      3. If arxiv_id known          → arXiv fallback.

    Strategy ``arxiv-only`` skips DBLP/DOI (use when caller knows it's a preprint).

    When ``probe_arxiv=True`` (default), any entry that carries an arXiv ID is
    HEAD-probed against ``arxiv.org/abs/{id}``; the result lands in
    ``entry["arxiv_exists"]`` and is consumed by :func:`validate_entry`.
    """
    errors = []

    if strategy in ("auto", "dblp-first"):
        if title:
            try:
                q = title
                if first_author:
                    q = f"{title} {first_author}"
                bib, key = fetch_dblp_bibtex(q)
                entry = parse_bib_entry(bib)
                entry["source"] = "dblp"
                entry["source_id"] = key
                entry["raw_bibtex"] = bib
                return _probe_and_attach(entry, probe_arxiv)
            except Exception as e:
                errors.append(f"dblp: {e}")

    if strategy in ("auto", "doi-first") and doi:
        try:
            bib = fetch_doi_bibtex(doi)
            entry = parse_bib_entry(bib)
            entry["source"] = "doi"
            entry["source_id"] = doi
            entry["raw_bibtex"] = bib
            return _probe_and_attach(entry, probe_arxiv)
        except Exception as e:
            errors.append(f"doi: {e}")

    if arxiv_id:
        try:
            bib = fetch_arxiv_bibtex(arxiv_id)
            entry = parse_bib_entry(bib)
            entry["source"] = "arxiv"
            entry["source_id"] = arxiv_id
            entry["raw_bibtex"] = bib
            return _probe_and_attach(entry, probe_arxiv)
        except Exception as e:
            errors.append(f"arxiv: {e}")

    raise RuntimeError(
        "All BibTeX sources failed:\n  " + "\n  ".join(errors)
    )


# --------------------------------------------------------------------------- #
# bib_index.json                                                              #
# --------------------------------------------------------------------------- #

def build_bib_index(bib_path: str) -> dict:
    """Read a .bib file and return a dict ``{cite_key: {...metadata...}}``.

    Output schema (per entry):
      year (int | None), first_author_surname (str), all_authors_raw (str),
      title (str), venue (str | None), entry_type (str)

    This is the ground-truth lookup the drafting subagent MUST consult instead
    of writing years / authors from memory.
    """
    bib_text = Path(bib_path).read_text(encoding="utf-8", errors="replace")
    index = {}
    for m in _BIB_ENTRY_RE.finditer(bib_text):
        entry = parse_bib_entry(m.group(0))
        f = entry["fields"]
        year_raw = f.get("year", "")
        try:
            year = int(re.sub(r"\D", "", year_raw)) if year_raw else None
        except ValueError:
            year = None
        venue = (
            f.get("booktitle")
            or f.get("journal")
            or f.get("publisher")
            or f.get("note")
            or None
        )
        index[entry["cite_key"]] = {
            "entry_type": entry["entry_type"],
            "year": year,
            "first_author_surname": first_author_surname(f.get("author", "")),
            "all_authors_raw": f.get("author", ""),
            "title": f.get("title", ""),
            "venue": venue,
        }
    return index


# --------------------------------------------------------------------------- #
# verify-tex                                                                  #
# --------------------------------------------------------------------------- #

def verify_tex(
    tex_paths: list[str],
    bib_index: dict,
) -> dict:
    """Scan .tex files for citation / year integrity violations.

    Detects:
      * undefined: ``\\cite{xyz}`` where ``xyz`` is not in ``bib_index``.
      * year_mismatch: ``Author et al. (YYYY)`` near ``\\cite{key}`` whose
        ``year`` in bib_index does not equal ``YYYY``.
    """
    undefined = []
    year_mismatches = []
    for path in tex_paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue

        # 1. undefined cite keys
        for m in _CITE_RE.finditer(text):
            for key in m.group(1).split(","):
                key = key.strip()
                if not key or key in bib_index:
                    continue
                undefined.append({"file": path, "key": key})

        # 2. year-mention sanity check
        # Heuristic: for every "Author et al. (YYYY)" pattern, find the FIRST
        # \cite{} appearing AFTER it within +120 chars (typical writing pattern:
        # "Brown et al. (2019) \cite{brown_2019}"). If none after, fall back to
        # looking backward within -60 chars. Compare years.
        for m in _YEAR_INLINE_RE.finditer(text):
            inline_year = int(m.group(2))
            end = m.end()
            forward = text[end: end + 120]
            cite_m = _CITE_RE.search(forward)
            if cite_m is None:
                backward = text[max(0, m.start() - 60): m.start()]
                cite_m = _CITE_RE.search(backward)
            if cite_m is None:
                continue
            for key in cite_m.group(1).split(","):
                key = key.strip()
                meta = bib_index.get(key)
                if meta and meta["year"] and meta["year"] != inline_year:
                    year_mismatches.append({
                        "file": path,
                        "prose_year": inline_year,
                        "cite_key": key,
                        "bib_year": meta["year"],
                        "context": m.group(0),
                    })

    return {
        "undefined_cites": undefined,
        "year_mismatches": year_mismatches,
        "ok": not undefined and not year_mismatches,
    }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def _cmd_fetch(args: argparse.Namespace) -> int:
    try:
        entry = fetch_for_paper(
            arxiv_id=args.arxiv_id,
            doi=args.doi,
            title=args.title,
            first_author=args.expected_first_author,
            strategy=args.strategy,
            probe_arxiv=not args.no_arxiv_probe,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

    validation = validate_entry(
        entry,
        expected_year=args.expected_year,
        expected_first_author=args.expected_first_author,
        expected_title_tokens=args.expected_title_tokens,
    )
    entry.update(validation)

    if args.append_to:
        if validation["validated"] or args.force:
            Path(args.append_to).parent.mkdir(parents=True, exist_ok=True)
            with open(args.append_to, "a", encoding="utf-8") as fh:
                fh.write("\n")
                fh.write(entry["raw_bibtex"])
        else:
            entry["appended"] = False
            entry["reason"] = "validation_failed (use --force to override)"
    if "appended" not in entry:
        entry["appended"] = bool(args.append_to)

    # Trim raw_bibtex from CLI output for readability; user can fetch it again.
    short = {k: v for k, v in entry.items() if k != "raw_bibtex"}
    print(json.dumps(short, ensure_ascii=False, indent=2))
    return 0 if validation["validated"] else 1


def _cmd_build_index(args: argparse.Namespace) -> int:
    index = build_bib_index(args.bib)
    Path(args.out).write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(index)} entries to {args.out}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    index = json.loads(Path(args.bib_index).read_text(encoding="utf-8"))
    # Expand globs the shell might not have expanded.
    tex_files: list[str] = []
    for p in args.tex:
        matches = glob.glob(p)
        tex_files.extend(matches if matches else [p])

    result = verify_tex(tex_files, index)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        n_undef = len(result["undefined_cites"])
        n_year = len(result["year_mismatches"])
        print(
            f"\n❌ verify-tex failed: {n_undef} undefined cite key(s), "
            f"{n_year} year mismatch(es).",
            file=sys.stderr,
        )
        return 1
    print("\n✅ verify-tex OK: every \\cite key is defined and inline years match bib.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch and verify BibTeX entries.")
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("fetch", help="Fetch BibTeX for a single paper.")
    pf.add_argument("--arxiv-id")
    pf.add_argument("--doi")
    pf.add_argument("--title")
    pf.add_argument("--strategy", choices=["auto", "dblp-first", "doi-first", "arxiv-only"],
                    default="auto")
    pf.add_argument("--expected-year", type=int)
    pf.add_argument("--expected-first-author")
    pf.add_argument("--expected-title-tokens", nargs="+", default=[])
    pf.add_argument("--append-to", help="Append validated BibTeX to this .bib file.")
    pf.add_argument("--force", action="store_true",
                    help="Append even if validation fails.")
    pf.add_argument("--no-arxiv-probe", action="store_true",
                    help="Skip the HEAD probe to arxiv.org/abs/{id}. "
                         "Use only for offline testing — the probe is the "
                         "guard against fabricated arXiv IDs.")
    pf.set_defaults(func=_cmd_fetch)

    pb = sub.add_parser("build-index", help="Build bib_index.json from a .bib file.")
    pb.add_argument("--bib", required=True)
    pb.add_argument("--out", required=True)
    pb.set_defaults(func=_cmd_build_index)

    pv = sub.add_parser("verify-tex",
                        help="Verify \\cite{} keys and inline years against bib.")
    pv.add_argument("--tex", nargs="+", required=True,
                    help="One or more .tex files (globs allowed).")
    pv.add_argument("--bib", required=True, help="Path to references.bib (unused, kept for symmetry).")
    pv.add_argument("--bib-index", required=True, help="Path to bib_index.json.")
    pv.set_defaults(func=_cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
