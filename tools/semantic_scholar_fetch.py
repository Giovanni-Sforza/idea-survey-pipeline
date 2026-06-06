#!/usr/bin/env python3
"""CLI helper for fetching Semantic Scholar papers.

Designed to complement arxiv_fetch.py: arXiv handles preprints, this tool
handles **published venue papers** (IEEE, ACM, Springer, etc.) with rich
metadata (citations, venue, fieldsOfStudy, TLDR).

Commands
--------
search       Relevance search for papers (offset pagination, max 100).
search-bulk  Bulk search with token-based pagination (max 1000).
paper        Fetch one paper by Semantic Scholar paper ID, DOI, CorpusId, ArXiv ID, etc.
references   Fetch the outgoing references of one paper (citation-graph backward edge).
citations    Fetch papers that cite the given paper (citation-graph forward edge).
cross-cited  Given several seed papers, find papers referenced by >= K of them
             (citation-graph hub detection — used by idea-* loop expansion).

Filter flags (shared by search and search-bulk)
-----------------------------------------------
--fields-of-study   e.g. "Computer Science,Engineering"
--publication-types  e.g. "JournalArticle", "Conference", "Review"
--min-citations      e.g. 10
--year               e.g. "2020-", "2020-2024"
--venue              exact venue name, e.g. "IEEE Transactions on Signal Processing"
--open-access        only papers with a public PDF

Examples
--------
# Search for journal articles with >= 10 citations (best combo for quality filtering)
python3 tools/semantic_scholar_fetch.py search "semantic communication" --max 10 \
  --publication-types JournalArticle --min-citations 10

# CS/Engineering papers from 2022 onward
python3 tools/semantic_scholar_fetch.py search "semantic communication" --max 10 \
  --fields-of-study "Computer Science,Engineering" --year "2022-"

# Bulk search sorted by citation count, CS only
python3 tools/semantic_scholar_fetch.py search-bulk "semantic communication" --max 50 \
  --sort citationCount:desc --fields-of-study "Computer Science" --year "2020-"

# Fetch a single paper by DOI or arXiv ID
python3 tools/semantic_scholar_fetch.py paper "10.1109/JSAC.2021.3126077"
python3 tools/semantic_scholar_fetch.py paper "ARXIV:2006.10685"

# Pull the references of one paper (citation-graph backward edge)
python3 tools/semantic_scholar_fetch.py references "ARXIV:2006.10685" --max 50

# Pull papers that cite one paper (citation-graph forward edge)
python3 tools/semantic_scholar_fetch.py citations "ARXIV:2006.10685" --max 50

# Find hub papers referenced by >= 2 of three seeds (citation-graph hub detection)
python3 tools/semantic_scholar_fetch.py cross-cited \
    "ARXIV:2006.10685,ARXIV:2301.07041,10.1109/JSAC.2021.3126077" \
    --direction references --min-overlap 2 --per-seed-max 100 --top 30

# NOTE: --venue requires exact venue name (e.g. "IEEE Transactions on Signal Processing"),
# not partial match like "IEEE". Prefer --publication-types + --fields-of-study instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_API_BASE = "https://api.semanticscholar.org/graph/v1"
_USER_AGENT = "s2-fetch/1.1"
_DEFAULT_TIMEOUT = 30

# Good default for relevance search / single-paper fetch
_DEFAULT_FIELDS = (
    "paperId,title,abstract,year,venue,publicationVenue,publicationTypes,"
    "publicationDate,url,openAccessPdf,authors,externalIds,citationCount,"
    "referenceCount,fieldsOfStudy,s2FieldsOfStudy,tldr"
)

# Bulk search is intended for basic paper data; keep defaults conservative
_DEFAULT_BULK_FIELDS = (
    "paperId,title,abstract,year,venue,publicationDate,url,authors,"
    "externalIds,citationCount,referenceCount,fieldsOfStudy"
)

# Reference / citation endpoints return a *list of edges*, where each edge has a
# nested paper plus per-edge metadata (contextsWithIntent, isInfluential).
# `paper.*` is the dotted-path notation the S2 API uses to project nested fields.
_DEFAULT_REF_CITE_FIELDS = (
    "contextsWithIntent,isInfluential,"
    "paper.paperId,paper.title,paper.abstract,paper.year,paper.venue,"
    "paper.url,paper.openAccessPdf,paper.authors,paper.externalIds,"
    "paper.citationCount,paper.referenceCount,paper.fieldsOfStudy"
)


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _request_json(url: str, *, retries: int = 2, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_headers())
    last_err: Exception | None = None

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                last_err = exc
                continue

            message = f"HTTP {exc.code}"
            if body:
                message += f": {body}"
            raise RuntimeError(message) from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                last_err = exc
                continue
            raise RuntimeError(f"Network error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse JSON response from Semantic Scholar API") from exc

    raise RuntimeError(f"Request failed after retries: {last_err}")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\n", " ")
    return text or None


def _parse_author(author: dict[str, Any]) -> dict[str, Any]:
    return {
        "authorId": author.get("authorId"),
        "name": _clean_text(author.get("name")),
    }


def _parse_publication_venue(pub_venue: dict[str, Any] | None) -> dict[str, Any] | None:
    if not pub_venue:
        return None
    return {
        "id": pub_venue.get("id"),
        "name": _clean_text(pub_venue.get("name")),
        "type": _clean_text(pub_venue.get("type")),
        "issn": _clean_text(pub_venue.get("issn")),
        "url": _clean_text(pub_venue.get("url")),
    }


def _parse_paper(paper: dict[str, Any]) -> dict[str, Any]:
    authors = paper.get("authors") or []
    return {
        "paperId": paper.get("paperId"),
        "title": _clean_text(paper.get("title")),
        "abstract": _clean_text(paper.get("abstract")),
        "year": paper.get("year"),
        "venue": _clean_text(paper.get("venue")),
        "publicationVenue": _parse_publication_venue(paper.get("publicationVenue")),
        "publicationTypes": paper.get("publicationTypes"),
        "publicationDate": _clean_text(paper.get("publicationDate")),
        "url": _clean_text(paper.get("url")),
        "openAccessPdf": paper.get("openAccessPdf"),
        "authors": [_parse_author(a) for a in authors],
        "externalIds": paper.get("externalIds"),
        "citationCount": paper.get("citationCount"),
        "referenceCount": paper.get("referenceCount"),
        "fieldsOfStudy": paper.get("fieldsOfStudy"),
        "s2FieldsOfStudy": paper.get("s2FieldsOfStudy"),
        "tldr": paper.get("tldr"),
    }


def search(
    query: str,
    max_results: int = 10,
    offset: int = 0,
    fields: str = _DEFAULT_FIELDS,
    fields_of_study: str | None = None,
    venue: str | None = None,
    year: str | None = None,
    min_citation_count: int | None = None,
    publication_types: str | None = None,
    open_access_pdf: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "limit": max_results,
        "offset": offset,
        "fields": fields,
    }
    if fields_of_study:
        params["fieldsOfStudy"] = fields_of_study
    if venue:
        params["venue"] = venue
    if year:
        params["year"] = year
    if min_citation_count is not None:
        params["minCitationCount"] = min_citation_count
    if publication_types:
        params["publicationTypes"] = publication_types
    if open_access_pdf:
        params["openAccessPdf"] = ""
    url = f"{_API_BASE}/paper/search?{urllib.parse.urlencode(params)}"
    payload = _request_json(url)

    data = payload.get("data") or []
    return {
        "mode": "search",
        "total": payload.get("total"),
        "offset": offset,
        "next_offset": offset + len(data),
        "data": [_parse_paper(item) for item in data],
    }


def search_bulk(
    query: str,
    max_results: int = 100,
    token: str | None = None,
    fields: str = _DEFAULT_BULK_FIELDS,
    sort: str | None = None,
    fields_of_study: str | None = None,
    venue: str | None = None,
    year: str | None = None,
    min_citation_count: int | None = None,
    publication_types: str | None = None,
    open_access_pdf: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "limit": max_results,
        "fields": fields,
    }
    if token:
        params["token"] = token
    if sort:
        params["sort"] = sort
    if fields_of_study:
        params["fieldsOfStudy"] = fields_of_study
    if venue:
        params["venue"] = venue
    if year:
        params["year"] = year
    if min_citation_count is not None:
        params["minCitationCount"] = min_citation_count
    if publication_types:
        params["publicationTypes"] = publication_types
    if open_access_pdf:
        params["openAccessPdf"] = ""

    url = f"{_API_BASE}/paper/search/bulk?{urllib.parse.urlencode(params)}"
    payload = _request_json(url)

    data = payload.get("data") or []
    return {
        "mode": "search-bulk",
        "token": payload.get("token"),
        "returned": len(data),
        "sort": sort,
        "data": [_parse_paper(item) for item in data],
    }


def get_paper(paper_id: str, fields: str = _DEFAULT_FIELDS) -> dict[str, Any]:
    encoded_id = urllib.parse.quote(paper_id, safe="")
    params = {"fields": fields}
    url = f"{_API_BASE}/paper/{encoded_id}?{urllib.parse.urlencode(params)}"
    payload = _request_json(url)
    return _parse_paper(payload)


def _fetch_edges(
    paper_id: str,
    *,
    endpoint: str,
    nested_key: str,
    max_results: int,
    fields: str,
    min_year: int | None = None,
) -> list[dict[str, Any]]:
    """Page through the references or citations endpoint, returning a flat list
    where each entry is the nested paper enriched with `_contexts` and
    `_is_influential` per-edge fields.

    `endpoint`   -- "references" or "citations".
    `nested_key` -- "citedPaper" or "citingPaper" (the field S2 nests the paper under).
    """
    # The fields parameter uses `paper.X` projection for the nested paper; rewrite
    # to the endpoint-specific nested key.
    api_fields = fields.replace("paper.", f"{nested_key}.")

    encoded_id = urllib.parse.quote(paper_id, safe="")
    edges: list[dict[str, Any]] = []
    offset = 0
    PAGE = 100  # S2 hard cap

    while len(edges) < max_results:
        page_limit = min(PAGE, max_results - len(edges))
        params = {
            "limit": page_limit,
            "offset": offset,
            "fields": api_fields,
        }
        url = f"{_API_BASE}/paper/{encoded_id}/{endpoint}?{urllib.parse.urlencode(params)}"
        payload = _request_json(url)

        data = payload.get("data") or []
        if not data:
            break

        for edge in data:
            nested = edge.get(nested_key) or {}
            if not nested.get("paperId"):
                continue
            if min_year is not None:
                y = nested.get("year")
                if y is None or y < min_year:
                    continue
            parsed = _parse_paper(nested)
            parsed["_contexts"] = edge.get("contextsWithIntent")
            parsed["_is_influential"] = edge.get("isInfluential")
            edges.append(parsed)

        # If this page was short, we've drained the source — stop.
        if len(data) < page_limit:
            break
        offset += len(data)

    return edges[:max_results]


def references(
    paper_id: str,
    *,
    max_results: int = 100,
    fields: str = _DEFAULT_REF_CITE_FIELDS,
    min_year: int | None = None,
) -> dict[str, Any]:
    data = _fetch_edges(
        paper_id,
        endpoint="references",
        nested_key="citedPaper",
        max_results=max_results,
        fields=fields,
        min_year=min_year,
    )
    return {
        "mode": "references",
        "source_paper_id": paper_id,
        "returned": len(data),
        "data": data,
    }


def citations(
    paper_id: str,
    *,
    max_results: int = 100,
    fields: str = _DEFAULT_REF_CITE_FIELDS,
    min_year: int | None = None,
) -> dict[str, Any]:
    data = _fetch_edges(
        paper_id,
        endpoint="citations",
        nested_key="citingPaper",
        max_results=max_results,
        fields=fields,
        min_year=min_year,
    )
    return {
        "mode": "citations",
        "source_paper_id": paper_id,
        "returned": len(data),
        "data": data,
    }


def cross_cited(
    seed_ids: list[str],
    *,
    direction: str = "references",
    per_seed_max: int = 100,
    min_overlap: int = 2,
    top: int = 50,
    min_year: int | None = None,
    fields: str = _DEFAULT_REF_CITE_FIELDS,
) -> dict[str, Any]:
    """Hub-detection: for each seed paper, fetch its references (default) or
    citations, then aggregate to find candidates referenced/cited by >=
    `min_overlap` seeds. Returns the top `top` candidates sorted by
    (overlap_count desc, citationCount desc).
    """
    if direction not in ("references", "citations"):
        raise ValueError("direction must be 'references' or 'citations'")

    fetcher = references if direction == "references" else citations

    # paperId -> aggregated record
    agg: dict[str, dict[str, Any]] = {}
    # Track which seeds contributed; we drop self-hits at the end.
    seed_set: set[str] = set()
    per_seed_meta: list[dict[str, Any]] = []

    for seed in seed_ids:
        seed_set.add(seed)
        try:
            result = fetcher(
                seed,
                max_results=per_seed_max,
                fields=fields,
                min_year=min_year,
            )
        except Exception as exc:
            per_seed_meta.append({"seed": seed, "status": "error", "error": str(exc), "returned": 0})
            continue

        per_seed_meta.append({"seed": seed, "status": "ok", "returned": result.get("returned", 0)})

        for paper in result.get("data", []):
            pid = paper.get("paperId")
            if not pid:
                continue
            # Skip if the candidate IS one of the seeds (a seed citing another seed
            # doesn't make it a hub for the *set*).
            external = paper.get("externalIds") or {}
            external_aliases = {
                pid,
                external.get("DOI"),
                f"ARXIV:{external.get('ArXiv')}" if external.get("ArXiv") else None,
                f"CorpusId:{external.get('CorpusId')}" if external.get("CorpusId") else None,
            }
            external_aliases.discard(None)
            if external_aliases & seed_set:
                continue

            entry = agg.setdefault(
                pid,
                {
                    **paper,
                    "_overlapping_seeds": [],
                    "_influential_for_seeds": [],
                    "_contexts_by_seed": {},
                },
            )
            entry["_overlapping_seeds"].append(seed)
            if paper.get("_is_influential"):
                entry["_influential_for_seeds"].append(seed)
            ctx = paper.get("_contexts")
            if ctx:
                entry["_contexts_by_seed"][seed] = ctx

    # Filter by min_overlap and rank.
    filtered = [v for v in agg.values() if len(v["_overlapping_seeds"]) >= min_overlap]

    def _rank_key(v: dict[str, Any]) -> tuple[int, int, int]:
        return (
            -len(v["_overlapping_seeds"]),
            -len(v["_influential_for_seeds"]),
            -(v.get("citationCount") or 0),
        )

    filtered.sort(key=_rank_key)

    # Strip per-edge fields that were aggregator-internal — the caller wants the
    # overlap counts, not the raw per-edge contexts (those are still in
    # _contexts_by_seed).
    for entry in filtered:
        entry["overlap_count"] = len(entry["_overlapping_seeds"])
        entry["influential_overlap_count"] = len(entry["_influential_for_seeds"])
        entry["overlapping_seeds"] = entry.pop("_overlapping_seeds")
        entry["influential_for_seeds"] = entry.pop("_influential_for_seeds")
        entry["contexts_by_seed"] = entry.pop("_contexts_by_seed")
        entry.pop("_contexts", None)
        entry.pop("_is_influential", None)

    return {
        "mode": "cross-cited",
        "direction": direction,
        "seeds": list(seed_ids),
        "min_overlap": min_overlap,
        "per_seed_max": per_seed_max,
        "per_seed_meta": per_seed_meta,
        "candidates_before_overlap_filter": len(agg),
        "returned": min(top, len(filtered)),
        "data": filtered[:top],
    }


def _add_filter_args(parser: argparse.ArgumentParser) -> None:
    """Add shared filtering arguments to a search sub-parser."""
    parser.add_argument(
        "--fields-of-study",
        default=None,
        help="Comma-separated fields of study filter, e.g. 'Computer Science,Engineering'.",
    )
    parser.add_argument(
        "--venue",
        default=None,
        help="Comma-separated venue filter, e.g. 'IEEE,ACM' or 'Nature'.",
    )
    parser.add_argument(
        "--year",
        default=None,
        help="Year or range, e.g. '2023', '2020-2024', '2020-', '-2023'.",
    )
    parser.add_argument(
        "--min-citations",
        type=int,
        default=None,
        metavar="N",
        help="Minimum citation count filter.",
    )
    parser.add_argument(
        "--publication-types",
        default=None,
        help="Comma-separated types: JournalArticle,Conference,Review,etc.",
    )
    parser.add_argument(
        "--open-access",
        action="store_true",
        default=False,
        help="Only return papers with a public PDF.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search and fetch papers from Semantic Scholar.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Relevance search for papers")
    search_parser.add_argument("query", help="Keyword query")
    search_parser.add_argument(
        "--max",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of results to return (default: 10).",
    )
    search_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset for pagination (default: 0).",
    )
    search_parser.add_argument(
        "--fields",
        default=_DEFAULT_FIELDS,
        help="Comma-separated response fields to request.",
    )
    _add_filter_args(search_parser)

    bulk_parser = subparsers.add_parser(
        "search-bulk",
        help="Bulk search for papers with token-based pagination",
    )
    bulk_parser.add_argument("query", help="Keyword query")
    bulk_parser.add_argument(
        "--max",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of results to return in this page (default: 100).",
    )
    bulk_parser.add_argument(
        "--token",
        default=None,
        help="Continuation token returned by a previous bulk search page.",
    )
    bulk_parser.add_argument(
        "--sort",
        default=None,
        help="Optional sort for bulk search, e.g. publicationDate:desc or citationCount:desc",
    )
    bulk_parser.add_argument(
        "--fields",
        default=_DEFAULT_BULK_FIELDS,
        help="Comma-separated response fields to request.",
    )
    _add_filter_args(bulk_parser)

    paper_parser = subparsers.add_parser("paper", help="Fetch one paper by ID")
    paper_parser.add_argument(
        "id",
        help=(
            "Semantic Scholar paper ID, DOI, CorpusId:..., ARXIV:..., PMID:..., MAG:..., ACL:..., etc."
        ),
    )
    paper_parser.add_argument(
        "--fields",
        default=_DEFAULT_FIELDS,
        help="Comma-separated response fields to request.",
    )

    # references — outgoing citation-graph edges
    ref_parser = subparsers.add_parser(
        "references",
        help="Fetch the outgoing references of one paper (citation-graph backward edge).",
    )
    ref_parser.add_argument(
        "id",
        help="Semantic Scholar paper ID, DOI, ARXIV:..., etc.",
    )
    ref_parser.add_argument(
        "--max",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of references to return (paginates internally; default 100).",
    )
    ref_parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        metavar="Y",
        help="Drop references with year < Y or unknown year.",
    )
    ref_parser.add_argument(
        "--fields",
        default=_DEFAULT_REF_CITE_FIELDS,
        help=(
            "Comma-separated fields. Use 'paper.X' to project fields of the "
            "nested cited paper; per-edge fields are 'contextsWithIntent' and 'isInfluential'."
        ),
    )

    # citations — incoming citation-graph edges
    cite_parser = subparsers.add_parser(
        "citations",
        help="Fetch papers that cite one paper (citation-graph forward edge).",
    )
    cite_parser.add_argument(
        "id",
        help="Semantic Scholar paper ID, DOI, ARXIV:..., etc.",
    )
    cite_parser.add_argument(
        "--max",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of citations to return (paginates internally; default 100).",
    )
    cite_parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        metavar="Y",
        help="Drop citing papers with year < Y or unknown year (useful to keep only recent followers).",
    )
    cite_parser.add_argument(
        "--fields",
        default=_DEFAULT_REF_CITE_FIELDS,
        help=(
            "Comma-separated fields. Use 'paper.X' to project fields of the "
            "nested citing paper; per-edge fields are 'contextsWithIntent' and 'isInfluential'."
        ),
    )

    # cross-cited — hub detection across multiple seeds
    hub_parser = subparsers.add_parser(
        "cross-cited",
        help="Find papers referenced (or citing) >= K seeds — citation-graph hub detection.",
    )
    hub_parser.add_argument(
        "ids",
        help="Comma-separated seed paper IDs (any S2-resolvable form).",
    )
    hub_parser.add_argument(
        "--direction",
        choices=["references", "citations"],
        default="references",
        help=(
            "'references' (default): find papers cited by >= K seeds (best for surfacing "
            "seminal predecessors). 'citations': find papers that cite >= K seeds "
            "(best for surfacing recent followers / competitors)."
        ),
    )
    hub_parser.add_argument(
        "--per-seed-max",
        type=int,
        default=100,
        metavar="N",
        help="Per-seed reference/citation cap (default 100).",
    )
    hub_parser.add_argument(
        "--min-overlap",
        type=int,
        default=2,
        metavar="K",
        help="Only return candidates referenced/cited by >= K seeds (default 2).",
    )
    hub_parser.add_argument(
        "--top",
        type=int,
        default=50,
        metavar="N",
        help="Cap the output at N candidates after ranking (default 50).",
    )
    hub_parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        metavar="Y",
        help="Drop candidates with year < Y.",
    )
    hub_parser.add_argument(
        "--fields",
        default=_DEFAULT_REF_CITE_FIELDS,
        help="Comma-separated fields. See references/citations subcommand for the convention.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "search":
            result = search(
                query=args.query,
                max_results=args.max,
                offset=args.offset,
                fields=args.fields,
                fields_of_study=args.fields_of_study,
                venue=args.venue,
                year=args.year,
                min_citation_count=args.min_citations,
                publication_types=args.publication_types,
                open_access_pdf=args.open_access,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "search-bulk":
            result = search_bulk(
                query=args.query,
                max_results=args.max,
                token=args.token,
                fields=args.fields,
                sort=args.sort,
                fields_of_study=args.fields_of_study,
                venue=args.venue,
                year=args.year,
                min_citation_count=args.min_citations,
                publication_types=args.publication_types,
                open_access_pdf=args.open_access,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "paper":
            result = get_paper(
                paper_id=args.id,
                fields=args.fields,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "references":
            result = references(
                args.id,
                max_results=args.max,
                fields=args.fields,
                min_year=args.min_year,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "citations":
            result = citations(
                args.id,
                max_results=args.max,
                fields=args.fields,
                min_year=args.min_year,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "cross-cited":
            seed_ids = [s.strip() for s in args.ids.split(",") if s.strip()]
            if not seed_ids:
                raise ValueError("cross-cited: no seed IDs provided")
            result = cross_cited(
                seed_ids,
                direction=args.direction,
                per_seed_max=args.per_seed_max,
                min_overlap=args.min_overlap,
                top=args.top,
                min_year=args.min_year,
                fields=args.fields,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        raise ValueError(f"Unsupported command: {args.command}")

    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())