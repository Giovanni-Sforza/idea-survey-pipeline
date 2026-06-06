#!/usr/bin/env python3
"""
papers_pool.py — Multi-project paper pool manager for the idea-survey pipeline.

A "paper pool" is a globally shared directory (default location:
~/aris/papers-pool/) that holds every paper that has ever been deep-analyzed
across any project. Each project's idea-survey/literature-deep/ becomes a
collection of symlinks into the pool, so:

  * Two projects that search for the same paper share the analysis (no
    redundant work, no redundant token spend).
  * The Step 4.5 paper_card.json and Step 4 deep_analysis.md live exactly
    once on disk.
  * Cross-project provenance (which project/topic first analyzed the paper,
    which projects subsequently used it) is preserved in the pool itself.

The tool is OFF by default. It activates when the environment variable
ARIS_PAPERS_POOL is set to an existing directory. With ARIS_PAPERS_POOL
unset or pointing nowhere, the resolve subcommand falls back to project-local
literature-deep/ behavior — completely backward compatible.

Subcommands:
  init                 Create an empty pool at $ARIS_PAPERS_POOL.
  resolve              Decide reuse/analyze for each selected paper and set
                       up project symlinks. Main entry point for skills.
  status               Print pool stats (count, recent additions, etc).
  selftest             Run an end-to-end correctness test in a temp dir.

Invariants the tool enforces:
  * One paper_key per logical paper (computed from arxiv_id, then DOI,
    then title hash — first non-null wins).
  * index.json is the single source of truth for paper_key lookups.
  * Concurrent skill runs are serialized via an fcntl lock on
    {pool}/.lock — safe for multiple terminals.
  * Every project that touches a pool paper appends to that paper's
    analyzed_by.json (first_analyzed + subsequent_uses).
"""

from __future__ import annotations

import argparse
import datetime
import errno
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INDEX_SCHEMA_VERSION = "1"
ANALYZED_BY_SCHEMA_VERSION = "1"
ENV_VAR = "ARIS_PAPERS_POOL"


# ---------------------------------------------------------------------------
# Helpers: pool location
# ---------------------------------------------------------------------------


def pool_root() -> Path | None:
    """Return the configured pool root (Path) or None if not set."""
    p = os.environ.get(ENV_VAR, "").strip()
    if not p:
        return None
    return Path(p).expanduser().resolve()


def pool_enabled() -> bool:
    p = pool_root()
    return p is not None and p.exists()


# ---------------------------------------------------------------------------
# Helpers: paper-key derivation
# ---------------------------------------------------------------------------


def normalize_arxiv_id(arxiv_id) -> str | None:
    if not arxiv_id:
        return None
    s = str(arxiv_id).strip().lower()
    # strip URL prefix if user passed a URL
    s = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", s)
    s = re.sub(r"\.pdf$", "", s)
    # strip version suffix (e.g. v2)
    s = re.sub(r"v\d+$", "", s)
    return s or None


def normalize_doi(doi) -> str | None:
    if not doi:
        return None
    s = str(doi).strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s or None


def title_hash(title) -> str | None:
    """Lowercased, punctuation-stripped, whitespace-normalized SHA-256 prefix."""
    if not title:
        return None
    s = re.sub(r"\s+", " ", str(title).strip().lower())
    s = re.sub(r"[^\w\s]", "", s)
    if not s:
        return None
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def make_paper_key(paper: dict) -> str:
    """Compute a stable paper_key from candidate metadata.

    Priority: arxiv_id → doi → title hash. Raises ValueError if none available.
    """
    arxiv = normalize_arxiv_id(paper.get("arxiv_id"))
    if arxiv:
        safe = arxiv.replace(".", "_").replace("/", "_")
        return "paper_arxiv_" + safe
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return "paper_doi_" + hashlib.sha256(doi.encode("utf-8")).hexdigest()[:16]
    t = title_hash(paper.get("title"))
    if t:
        return "paper_title_" + t
    raise ValueError(
        "Cannot compute paper_key for paper without arxiv_id, doi, or title: "
        + json.dumps(paper)[:200]
    )


def index_lookup(idx: dict, paper: dict) -> tuple[str | None, str | None]:
    """Return (paper_key, hit_via) if found in any sub-index, else (None, None)."""
    arxiv = normalize_arxiv_id(paper.get("arxiv_id"))
    if arxiv and arxiv in idx.get("by_arxiv_id", {}):
        return idx["by_arxiv_id"][arxiv], "arxiv_id"
    doi = normalize_doi(paper.get("doi"))
    if doi and doi in idx.get("by_doi", {}):
        return idx["by_doi"][doi], "doi"
    t = title_hash(paper.get("title"))
    if t and t in idx.get("by_title_hash", {}):
        return idx["by_title_hash"][t], "title_hash"
    return None, None


# ---------------------------------------------------------------------------
# Helpers: locking, JSON IO
# ---------------------------------------------------------------------------


class PoolLock:
    """Context manager: exclusive lock on {pool}/.lock via fcntl."""

    def __init__(self, pool_dir: Path):
        self.pool_dir = pool_dir
        self.fd = None

    def __enter__(self):
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.pool_dir / ".lock"
        lock_path.touch(exist_ok=True)
        self.fd = os.open(str(lock_path), os.O_RDWR)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


def read_json(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    # atomic-ish write via tempfile + rename
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(p.parent), delete=False
    ) as tf:
        json.dump(obj, tf, indent=2, ensure_ascii=False, sort_keys=False)
        tf.write("\n")
        tmp = tf.name
    os.replace(tmp, str(p))


def utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ---------------------------------------------------------------------------
# Helpers: index + analyzed_by maintenance
# ---------------------------------------------------------------------------


def ensure_index(pool_dir: Path) -> dict:
    """Load index.json, creating a fresh one if missing."""
    idx_path = pool_dir / "index.json"
    idx = read_json(idx_path)
    if idx is None:
        idx = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "by_arxiv_id": {},
            "by_doi": {},
            "by_title_hash": {},
        }
        write_json(idx_path, idx)
    else:
        # backfill any missing keys
        idx.setdefault("schema_version", INDEX_SCHEMA_VERSION)
        idx.setdefault("by_arxiv_id", {})
        idx.setdefault("by_doi", {})
        idx.setdefault("by_title_hash", {})
    return idx


def index_register(idx: dict, paper: dict, paper_key: str) -> None:
    """Add (arxiv_id, doi, title_hash) → paper_key mappings in place."""
    arxiv = normalize_arxiv_id(paper.get("arxiv_id"))
    doi = normalize_doi(paper.get("doi"))
    t = title_hash(paper.get("title"))
    if arxiv:
        idx["by_arxiv_id"][arxiv] = paper_key
    if doi:
        idx["by_doi"][doi] = paper_key
    if t:
        idx["by_title_hash"][t] = paper_key


def update_analyzed_by(
    pool_paper_dir: Path,
    project_dir: Path,
    topic: str,
    action: str,
) -> None:
    """Append project provenance to {pool_paper_dir}/analyzed_by.json."""
    ab_path = pool_paper_dir / "analyzed_by.json"
    ab = read_json(ab_path) or {
        "schema_version": ANALYZED_BY_SCHEMA_VERSION,
        "first_analyzed": None,
        "subsequent_uses": [],
    }
    ab.setdefault("schema_version", ANALYZED_BY_SCHEMA_VERSION)
    ab.setdefault("subsequent_uses", [])
    entry = {
        "project_dir": str(project_dir),
        "topic": topic,
        "date_utc": utc_now(),
    }
    if ab.get("first_analyzed") is None and action == "analyze":
        ab["first_analyzed"] = entry
    else:
        # only append if this project hasn't been recorded already
        proj_dirs = {u.get("project_dir") for u in ab["subsequent_uses"]}
        first_proj = (ab["first_analyzed"] or {}).get("project_dir")
        if entry["project_dir"] != first_proj and entry["project_dir"] not in proj_dirs:
            ab["subsequent_uses"].append(entry)
    write_json(ab_path, ab)


# ---------------------------------------------------------------------------
# Symlink management
# ---------------------------------------------------------------------------


def ensure_project_link(project_link: Path, target: Path) -> str:
    """Ensure {project_link} is a symlink to {target}.

    Returns a string status: "created" | "exists_ok" | "conflict_real_dir" |
    "conflict_wrong_target".
    """
    target = target.resolve()
    if project_link.is_symlink():
        try:
            current = (project_link.parent / os.readlink(project_link)).resolve()
        except OSError:
            current = None
        if current == target:
            return "exists_ok"
        # wrong symlink — replace it
        project_link.unlink()
        project_link.parent.mkdir(parents=True, exist_ok=True)
        project_link.symlink_to(target)
        return "conflict_wrong_target"
    if project_link.exists():
        # real directory/file is in the way; do NOT clobber, just warn
        return "conflict_real_dir"
    project_link.parent.mkdir(parents=True, exist_ok=True)
    project_link.symlink_to(target)
    return "created"


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    p = pool_root()
    if p is None:
        print(
            f"{ENV_VAR} is not set. Example:\n"
            "  export ARIS_PAPERS_POOL=$HOME/aris/papers-pool",
            file=sys.stderr,
        )
        return 2
    p.mkdir(parents=True, exist_ok=True)
    with PoolLock(p):
        ensure_index(p)
    print(f"Pool initialized at {p}")
    print(f"Index: {p / 'index.json'}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: resolve  (the workhorse)
# ---------------------------------------------------------------------------


def cmd_resolve(args: argparse.Namespace) -> int:
    selected = read_json(Path(args.selected_papers))
    if selected is None:
        print(f"ERROR: {args.selected_papers} not found", file=sys.stderr)
        return 1
    if not isinstance(selected, list):
        print(
            f"ERROR: {args.selected_papers} must contain a JSON array of paper dicts",
            file=sys.stderr,
        )
        return 1

    project_dir = Path(args.project_dir).resolve()
    project_topic = args.topic or ""
    literature_deep_dir = project_dir / "idea-survey" / "literature-deep"
    literature_deep_dir.mkdir(parents=True, exist_ok=True)

    pool_p = pool_root()
    pool_mode = pool_p is not None and pool_p.exists()
    if pool_p is not None and not pool_p.exists():
        # User set the env var but never ran `init`. Be friendly:
        print(
            f"WARN: {ENV_VAR}={pool_p} does not exist. Falling back to project-local mode. "
            f"Run `papers_pool.py init` to enable the shared pool.",
            file=sys.stderr,
        )

    results: list[dict] = []
    warnings: list[str] = []

    def resolve_paper_no_pool(paper: dict) -> dict | None:
        try:
            key = make_paper_key(paper)
        except ValueError as e:
            warnings.append(str(e))
            return None
        project_paper_dir = literature_deep_dir / key
        project_paper_dir.mkdir(parents=True, exist_ok=True)
        already = bool(paper.get("already_analyzed"))
        action = "reuse" if already else "analyze"
        return {
            **paper,
            "pool_status": {
                "paper_key": key,
                "action": action,
                "hit_via": "already_analyzed_flag" if already else None,
                "pool_paper_dir": str(project_paper_dir),
                "project_link": str(project_paper_dir),
                "pool_mode": False,
            },
        }

    def resolve_paper_pool(paper: dict, idx: dict) -> dict | None:
        try:
            new_key = make_paper_key(paper)
        except ValueError as e:
            warnings.append(str(e))
            return None
        hit_key, hit_via = index_lookup(idx, paper)
        if hit_key:
            paper_key = hit_key
            action = "reuse"
            pool_paper_dir = pool_p / hit_key  # type: ignore[operator]
            # backfill the index with any new identifiers we learned
            index_register(idx, paper, hit_key)
        else:
            paper_key = new_key
            action = "analyze"
            pool_paper_dir = pool_p / new_key  # type: ignore[operator]
            pool_paper_dir.mkdir(parents=True, exist_ok=True)
            index_register(idx, paper, new_key)
        project_link = literature_deep_dir / paper_key
        link_status = ensure_project_link(project_link, pool_paper_dir)
        if link_status == "conflict_real_dir":
            warnings.append(
                f"{project_link} is a real directory, not a symlink. Pool dir is "
                f"{pool_paper_dir}. Migrate it manually or delete the project copy."
            )
        update_analyzed_by(pool_paper_dir, project_dir, project_topic, action)
        return {
            **paper,
            "pool_status": {
                "paper_key": paper_key,
                "action": action,
                "hit_via": hit_via,
                "pool_paper_dir": str(pool_paper_dir),
                "project_link": str(project_link),
                "project_link_status": link_status,
                "pool_mode": True,
            },
        }

    if pool_mode:
        with PoolLock(pool_p):  # type: ignore[arg-type]
            idx = ensure_index(pool_p)  # type: ignore[arg-type]
            for paper in selected:
                r = resolve_paper_pool(paper, idx)
                if r is not None:
                    results.append(r)
            write_json(pool_p / "index.json", idx)  # type: ignore[operator]
    else:
        for paper in selected:
            r = resolve_paper_no_pool(paper)
            if r is not None:
                results.append(r)

    write_json(Path(args.output), results)

    summary = {
        "total": len(results),
        "reuse": sum(1 for r in results if r["pool_status"]["action"] == "reuse"),
        "analyze": sum(1 for r in results if r["pool_status"]["action"] == "analyze"),
        "pool_mode": pool_mode,
        "pool_root": str(pool_p) if pool_p else None,
        "warnings": warnings,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not warnings else 0  # warnings don't fail the run


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    p = pool_root()
    if p is None or not p.exists():
        print(f"{ENV_VAR} not configured or pool dir does not exist.")
        return 0
    with PoolLock(p):
        idx = ensure_index(p)
        papers = sorted(d for d in os.listdir(p) if (p / d).is_dir() and d.startswith("paper_"))
        print(f"Pool root: {p}")
        print(f"Papers in pool: {len(papers)}")
        print(f"Index entries: arxiv={len(idx['by_arxiv_id'])}, "
              f"doi={len(idx['by_doi'])}, title_hash={len(idx['by_title_hash'])}")
        # show 10 most recent by mtime of deep_analysis.md
        recents = []
        for name in papers:
            da = p / name / "deep_analysis.md"
            if da.exists():
                recents.append((da.stat().st_mtime, name))
        recents.sort(reverse=True)
        for mtime, name in recents[:10]:
            iso = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"  {iso}  {name}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: migrate
# ---------------------------------------------------------------------------


def _extract_metadata_for_migration(paper_dir: Path) -> dict:
    """Best-effort: reconstruct paper metadata for index registration.

    Inspects the directory basename and any auxiliary files (figure_manifest,
    deep_analysis.md first lines). Returns a dict suitable for index_register
    and ensure_index lookups. The returned dict always has `paper_key`.
    """
    name = paper_dir.name
    meta: dict = {"paper_key": name}

    # 1. Reverse-engineer identifiers from the directory name.
    if name.startswith("paper_arxiv_"):
        rest = name[len("paper_arxiv_"):]
        # Common new-style arxiv id: YYMM_NNNNN -> "YYMM.NNNNN"
        m = re.match(r"^(\d{4})_(\d{4,5})$", rest)
        if m:
            meta["arxiv_id"] = f"{m.group(1)}.{m.group(2)}"
        else:
            # Old-style with subject prefix: subject_YYMMNNN -> "subject/YYMMNNN"
            m2 = re.match(r"^([a-z\-]+)_([\d]+)$", rest)
            if m2:
                meta["arxiv_id"] = f"{m2.group(1)}/{m2.group(2)}"
            else:
                # Fallback: store the rest verbatim, normalized
                meta["arxiv_id"] = rest.replace("_", ".")
    elif name.startswith("paper_doi_"):
        # DOI was hashed, cannot reverse. The paper_key itself acts as the
        # only identifier; future lookups must use the same DOI hash to find it.
        pass
    elif name.startswith("paper_title_"):
        # Same: title was hashed, cannot reverse.
        pass

    # 2. Try to extract title/year from deep_analysis.md (first ~30 lines).
    da_path = paper_dir / "deep_analysis.md"
    if da_path.exists():
        try:
            head = da_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:30]
            for line in head:
                line = line.strip()
                # First-line title: "# Deep Analysis: <Title>"
                if line.startswith("# Deep Analysis:") and "title" not in meta:
                    meta["title"] = line.split(":", 1)[1].strip()
                # Markdown table row like "| **Title** | ... |"
                if "| **Title**" in line and "title" not in meta:
                    parts = [c.strip() for c in line.split("|")]
                    if len(parts) >= 3:
                        meta["title"] = parts[2]
                if "| **Year**" in line and "year" not in meta:
                    parts = [c.strip() for c in line.split("|")]
                    if len(parts) >= 3:
                        try:
                            meta["year"] = int(parts[2])
                        except ValueError:
                            pass
        except OSError:
            pass

    return meta


def cmd_migrate(args: argparse.Namespace) -> int:
    """Migrate an existing project's literature-deep/ into the shared pool.

    Walks {project_dir}/idea-survey/literature-deep/paper_*/, and for each
    REAL (non-symlink) directory:
      1. Moves it into $ARIS_PAPERS_POOL/{basename}/
      2. Replaces the original location with a symlink to the pool dir
      3. Registers the paper in index.json (arxiv_id when derivable)
      4. Records project provenance in analyzed_by.json (as first_analyzed
         unless a record already exists, in which case as subsequent_uses)

    If a pool entry with the same basename already exists, the project's
    real directory is left in place and a warning is logged (manual merge
    required).
    """
    pool_p = pool_root()
    if pool_p is None:
        print(
            f"ERROR: {ENV_VAR} is not set. Run `export ARIS_PAPERS_POOL=...` "
            "and `papers_pool.py init` first.",
            file=sys.stderr,
        )
        return 2
    if not pool_p.exists():
        print(
            f"ERROR: pool directory {pool_p} does not exist. "
            "Run `papers_pool.py init` first.",
            file=sys.stderr,
        )
        return 2

    project_dir = Path(args.project_dir).resolve()
    literature_deep_dir = project_dir / "idea-survey" / "literature-deep"
    if not literature_deep_dir.exists():
        print(
            f"ERROR: {literature_deep_dir} does not exist. Nothing to migrate.",
            file=sys.stderr,
        )
        return 1

    project_topic = args.topic or ""
    dry_run = bool(args.dry_run)
    on_conflict = args.on_conflict  # "skip" | "error"

    # Enumerate paper directories
    candidates = []
    for p in sorted(literature_deep_dir.glob("paper_*")):
        if not p.is_dir():
            continue
        if p.is_symlink():
            continue  # already migrated
        candidates.append(p)

    if not candidates:
        print(f"No real paper directories to migrate in {literature_deep_dir}.")
        print("(Either nothing exists, or everything is already a symlink.)")
        return 0

    moved: list[dict] = []
    skipped: list[dict] = []
    conflicts: list[dict] = []

    with PoolLock(pool_p):
        idx = ensure_index(pool_p)
        for paper_dir in candidates:
            paper_key = paper_dir.name
            target = pool_p / paper_key
            meta = _extract_metadata_for_migration(paper_dir)
            entry = {
                "paper_dir": str(paper_dir),
                "paper_key": paper_key,
                "target": str(target),
                "metadata": meta,
            }

            if target.exists():
                # conflict: pool already has this paper_key
                if on_conflict == "error":
                    print(
                        f"ERROR: {target} already exists in pool. "
                        f"Cannot migrate {paper_dir} without conflict resolution. "
                        f"Re-run with --on-conflict skip to skip these, "
                        f"or manually merge.",
                        file=sys.stderr,
                    )
                    return 3
                # on_conflict == "skip"
                entry["reason"] = "pool entry already exists"
                conflicts.append(entry)
                continue

            if dry_run:
                entry["action"] = "would migrate"
                moved.append(entry)
                continue

            # Actually move and re-link
            try:
                paper_dir.rename(target)  # mv works across same FS; falls back below if not
            except OSError as e:
                if e.errno == errno.EXDEV:
                    # cross-device move: copytree + rmtree fallback
                    import shutil
                    shutil.copytree(paper_dir, target)
                    shutil.rmtree(paper_dir)
                else:
                    print(
                        f"ERROR: could not move {paper_dir} -> {target}: {e}",
                        file=sys.stderr,
                    )
                    entry["reason"] = f"move failed: {e}"
                    skipped.append(entry)
                    continue

            # Create the symlink back into the project
            paper_dir.symlink_to(target.resolve())

            # Register in index.json
            index_register(idx, meta, paper_key)

            # Record provenance — this project was the FIRST to analyze the paper
            # (unless analyzed_by.json already exists from a prior pool run)
            update_analyzed_by(target, project_dir, project_topic, action="analyze")

            entry["action"] = "migrated"
            moved.append(entry)

        # Persist the updated index (unless dry-run)
        if not dry_run:
            write_json(pool_p / "index.json", idx)

    summary = {
        "project_dir": str(project_dir),
        "pool_root": str(pool_p),
        "candidates_scanned": len(candidates),
        "moved": len(moved),
        "skipped": len(skipped),
        "conflicts": len(conflicts),
        "dry_run": dry_run,
    }
    print(json.dumps(summary, indent=2))
    if conflicts:
        print("\nConflicts (existing pool entries with same paper_key):", file=sys.stderr)
        for c in conflicts:
            print(f"  {c['paper_dir']} -> {c['target']} ({c['reason']})", file=sys.stderr)
    if skipped:
        print("\nSkipped (move failures):", file=sys.stderr)
        for s in skipped:
            print(f"  {s['paper_dir']}: {s['reason']}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: selftest
# ---------------------------------------------------------------------------


def cmd_selftest(args: argparse.Namespace) -> int:
    """End-to-end test in a temp dir. Saves your real pool from any side effects."""
    saved = os.environ.get(ENV_VAR)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pool = tmp / "pool"
            os.environ[ENV_VAR] = str(pool)

            # init
            assert cmd_init(argparse.Namespace()) == 0
            assert (pool / "index.json").exists()

            # project A: two new papers
            projA = tmp / "projA"
            (projA / "idea-survey").mkdir(parents=True)
            selA = projA / "idea-survey" / "selected.json"
            write_json(selA, [
                {"arxiv_id": "2301.07041", "title": "Paper A", "year": 2023},
                {"arxiv_id": "2302.13971", "title": "Paper B", "year": 2023},
            ])
            outA = projA / "idea-survey" / "resolved.json"
            argsA = argparse.Namespace(
                selected_papers=str(selA),
                project_dir=str(projA),
                topic="topic A",
                output=str(outA),
            )
            assert cmd_resolve(argsA) == 0
            rA = read_json(outA)
            assert all(r["pool_status"]["action"] == "analyze" for r in rA), \
                f"first run should mark all as analyze, got {rA}"
            assert all(r["pool_status"]["pool_mode"] for r in rA)

            # simulate Step 4: write deep_analysis.md into the pool
            for r in rA:
                pd = Path(r["pool_status"]["pool_paper_dir"])
                (pd / "deep_analysis.md").write_text(f"# {r['title']}\n")

            # project B: one overlapping paper + one new
            projB = tmp / "projB"
            (projB / "idea-survey").mkdir(parents=True)
            selB = projB / "idea-survey" / "selected.json"
            write_json(selB, [
                {"arxiv_id": "2301.07041", "title": "Paper A", "year": 2023},
                {"arxiv_id": "2309.99999", "title": "Paper C", "year": 2024},
            ])
            outB = projB / "idea-survey" / "resolved.json"
            argsB = argparse.Namespace(
                selected_papers=str(selB),
                project_dir=str(projB),
                topic="topic B",
                output=str(outB),
            )
            assert cmd_resolve(argsB) == 0
            rB = read_json(outB)
            actionsB = {r["title"]: r["pool_status"]["action"] for r in rB}
            assert actionsB.get("Paper A") == "reuse", f"Paper A should be reuse, got {actionsB}"
            assert actionsB.get("Paper C") == "analyze", f"Paper C should be analyze, got {actionsB}"

            # Project B should have a symlink to the same pool dir as Project A
            link_b = Path([r for r in rB if r["title"] == "Paper A"][0]["pool_status"]["project_link"])
            assert link_b.is_symlink(), f"{link_b} should be a symlink"
            assert (link_b / "deep_analysis.md").exists(), "symlinked deep_analysis.md should be reachable"

            # analyzed_by.json should record both projects on Paper A
            ab = read_json(pool / "paper_arxiv_2301_07041" / "analyzed_by.json")
            assert ab["first_analyzed"]["topic"] == "topic A"
            assert any(u["topic"] == "topic B" for u in ab["subsequent_uses"]), \
                f"Project B should be in subsequent_uses, got {ab}"

            # title-only fallback
            projC = tmp / "projC"
            (projC / "idea-survey").mkdir(parents=True)
            selC = projC / "idea-survey" / "selected.json"
            write_json(selC, [
                {"title": "Title-only paper", "year": 2020},
            ])
            outC = projC / "idea-survey" / "resolved.json"
            argsC = argparse.Namespace(
                selected_papers=str(selC),
                project_dir=str(projC),
                topic="topic C",
                output=str(outC),
            )
            assert cmd_resolve(argsC) == 0
            rC = read_json(outC)
            assert rC[0]["pool_status"]["paper_key"].startswith("paper_title_")

            # Re-running resolve on project A must be idempotent (no changes, no new entries)
            ab_before = read_json(pool / "paper_arxiv_2301_07041" / "analyzed_by.json")
            assert cmd_resolve(argsA) == 0
            ab_after = read_json(pool / "paper_arxiv_2301_07041" / "analyzed_by.json")
            assert ab_before == ab_after, "second resolve in same project must be a no-op for analyzed_by"

            # No-pool mode test: unset env var and ensure fallback works
            del os.environ[ENV_VAR]
            projD = tmp / "projD"
            (projD / "idea-survey").mkdir(parents=True)
            selD = projD / "idea-survey" / "selected.json"
            write_json(selD, [
                {"arxiv_id": "2401.00001", "title": "Paper D", "year": 2024, "already_analyzed": False},
                {"arxiv_id": "2401.00002", "title": "Paper E", "year": 2024, "already_analyzed": True},
            ])
            outD = projD / "idea-survey" / "resolved.json"
            argsD = argparse.Namespace(
                selected_papers=str(selD),
                project_dir=str(projD),
                topic="topic D",
                output=str(outD),
            )
            assert cmd_resolve(argsD) == 0
            rD = read_json(outD)
            assert all(not r["pool_status"]["pool_mode"] for r in rD)
            d_actions = {r["title"]: r["pool_status"]["action"] for r in rD}
            assert d_actions["Paper D"] == "analyze"
            assert d_actions["Paper E"] == "reuse"
            # In no-pool mode, project_link == pool_paper_dir (no symlinks)
            for r in rD:
                assert r["pool_status"]["project_link"] == r["pool_status"]["pool_paper_dir"]
                assert not Path(r["pool_status"]["project_link"]).is_symlink()

            # Migrate test: re-enable pool, set up a "legacy" project with
            # real (non-symlink) paper directories, and migrate them.
            os.environ[ENV_VAR] = str(pool)  # restore pool
            projE = tmp / "projE"
            legacy_lit = projE / "idea-survey" / "literature-deep"
            legacy_lit.mkdir(parents=True)
            (legacy_lit / "paper_arxiv_2501_12345").mkdir()
            (legacy_lit / "paper_arxiv_2501_12345" / "deep_analysis.md").write_text(
                "# Deep Analysis: Migration Test Paper\n"
                "\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| **Title** | Migration Test Paper |\n"
                "| **Year** | 2025 |\n"
            )
            (legacy_lit / "paper_arxiv_2501_67890").mkdir()
            (legacy_lit / "paper_arxiv_2501_67890" / "deep_analysis.md").write_text("# Some paper\n")

            # Dry-run first
            args_mig_dry = argparse.Namespace(
                project_dir=str(projE),
                topic="legacy topic",
                dry_run=True,
                on_conflict="error",
            )
            assert cmd_migrate(args_mig_dry) == 0
            # Dry-run must not touch anything
            assert (legacy_lit / "paper_arxiv_2501_12345").is_dir() and \
                not (legacy_lit / "paper_arxiv_2501_12345").is_symlink(), \
                "dry-run must not modify project state"
            assert not (pool / "paper_arxiv_2501_12345").exists(), \
                "dry-run must not create pool entries"

            # Real migrate
            args_mig = argparse.Namespace(
                project_dir=str(projE),
                topic="legacy topic",
                dry_run=False,
                on_conflict="error",
            )
            assert cmd_migrate(args_mig) == 0
            # After migration: project entries should be symlinks
            assert (legacy_lit / "paper_arxiv_2501_12345").is_symlink(), \
                f"after migrate, {legacy_lit / 'paper_arxiv_2501_12345'} should be a symlink"
            assert (legacy_lit / "paper_arxiv_2501_12345" / "deep_analysis.md").exists(), \
                "symlinked deep_analysis.md should be reachable"
            # Pool should have the entries with indexes
            assert (pool / "paper_arxiv_2501_12345" / "deep_analysis.md").exists()
            ab_mig = read_json(pool / "paper_arxiv_2501_12345" / "analyzed_by.json")
            assert ab_mig["first_analyzed"]["topic"] == "legacy topic"
            # Index should know about the arxiv_id
            idx = read_json(pool / "index.json")
            assert idx["by_arxiv_id"].get("2501.12345") == "paper_arxiv_2501_12345", \
                f"index should map 2501.12345 -> paper_arxiv_2501_12345; got {idx['by_arxiv_id']}"

            # Re-run migrate: should find 0 candidates (all are symlinks now)
            assert cmd_migrate(args_mig) == 0

            # Now a NEW project that needs the same paper should reuse the pool entry
            projF = tmp / "projF"
            (projF / "idea-survey").mkdir(parents=True)
            selF = projF / "idea-survey" / "selected.json"
            write_json(selF, [{"arxiv_id": "2501.12345", "title": "Migration Test Paper", "year": 2025}])
            outF = projF / "idea-survey" / "resolved.json"
            argsF = argparse.Namespace(
                selected_papers=str(selF),
                project_dir=str(projF),
                topic="downstream user",
                output=str(outF),
            )
            assert cmd_resolve(argsF) == 0
            rF = read_json(outF)
            assert rF[0]["pool_status"]["action"] == "reuse", \
                f"migrated paper should be reusable by a new project, got {rF[0]['pool_status']}"

            print("OK: papers_pool.py selftest passed")
            return 0
    finally:
        if saved is None:
            os.environ.pop(ENV_VAR, None)
        else:
            os.environ[ENV_VAR] = saved


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="papers_pool.py",
        description="Multi-project paper pool manager (see module docstring).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub_init = sub.add_parser("init", help="Initialize the pool at $ARIS_PAPERS_POOL")
    sub_init.set_defaults(func=cmd_init)

    sub_resolve = sub.add_parser(
        "resolve",
        help="Decide reuse/analyze for each selected paper; set up project symlinks",
    )
    sub_resolve.add_argument(
        "--selected-papers",
        required=True,
        help="Path to .synthesis_selected.json (a JSON array of paper dicts)",
    )
    sub_resolve.add_argument(
        "--project-dir",
        required=True,
        help="Path to the project root (must contain idea-survey/)",
    )
    sub_resolve.add_argument(
        "--topic",
        default="",
        help="Project topic (recorded in analyzed_by.json provenance)",
    )
    sub_resolve.add_argument(
        "--output",
        required=True,
        help="Output path for the resolved JSON (consumed by Step 3+)",
    )
    sub_resolve.set_defaults(func=cmd_resolve)

    sub_status = sub.add_parser("status", help="Print pool stats")
    sub_status.set_defaults(func=cmd_status)

    sub_migrate = sub.add_parser(
        "migrate",
        help="Move an existing project's literature-deep/ into the pool and "
             "replace each real paper_*/ directory with a symlink to its "
             "new pool location.",
    )
    sub_migrate.add_argument(
        "--project-dir",
        required=True,
        help="Project root (must contain idea-survey/literature-deep/)",
    )
    sub_migrate.add_argument(
        "--topic",
        default="",
        help="Topic to record as first_analyzed in each paper's analyzed_by.json "
             "(if the paper has no prior provenance). Recommended.",
    )
    sub_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be moved without modifying anything.",
    )
    sub_migrate.add_argument(
        "--on-conflict",
        choices=["skip", "error"],
        default="error",
        help="When a pool entry with the same paper_key already exists: "
             "`error` (default; abort and let the user investigate) or "
             "`skip` (leave the project's copy in place, don't migrate it).",
    )
    sub_migrate.set_defaults(func=cmd_migrate)

    sub_st = sub.add_parser("selftest", help="Run end-to-end self test in a temp dir")
    sub_st.set_defaults(func=cmd_selftest)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
