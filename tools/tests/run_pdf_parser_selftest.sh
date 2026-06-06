#!/usr/bin/env bash
# Quick regression test for tools/pdf_full_parser.py.
# Uses the bundled mineru_minimal fixture so no real PDF / no MinerU install
# is required.  Exits 0 on success, non-zero on any schema regression.
#
# Run from the repository root:
#     bash tools/tests/run_pdf_parser_selftest.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${TMPDIR:-/tmp}/pdf_full_parser_selftest_$$"
trap 'rm -rf "$OUT_DIR"' EXIT

cd "$REPO_ROOT"

echo "[selftest] running pdf_full_parser with mineru_minimal fixture"
python3 tools/pdf_full_parser.py parse \
    --pdf /dev/null \
    --output-dir "$OUT_DIR" \
    --mock-mineru-output tools/tests/fixtures/mineru_minimal/ \
    --no-pix2tex >/dev/null

python3 - "$OUT_DIR" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
manifest = json.loads((out / "figure_manifest.json").read_text())
log = json.loads((out / "parse_log.json").read_text())

def assert_eq(actual, expected, label):
    if actual != expected:
        print(f"FAIL [{label}]: expected {expected!r}, got {actual!r}", file=sys.stderr)
        sys.exit(1)

# schema parity with latex_source_parser
for key in ("main_tex", "figures", "tables", "equations", "unmatched_images",
            "image_stats", "figure_count", "table_count", "equation_count"):
    if key not in manifest:
        print(f"FAIL: manifest missing required key {key!r}", file=sys.stderr)
        sys.exit(1)

assert_eq(manifest["figure_count"], 2, "figure_count")
assert_eq(manifest["table_count"], 1, "table_count")
assert_eq(manifest["equation_count"], 3, "equation_count")

# caption attribution
fig1, fig2 = manifest["figures"]
assert_eq(fig1["caption_provenance"], "mineru_native",      "fig1 provenance")
assert_eq(fig2["caption_provenance"], "heuristic_adjacent", "fig2 provenance")
assert "Drift" in (fig2["caption"] or ""), "fig2 caption text"

# table parity
assert_eq(manifest["tables"][0]["caption_provenance"], "mineru_native", "tab1 provenance")
assert manifest["tables"][0]["table_html"], "tab1 html missing"

# suspect equation flagged but not silently dropped
suspect = [e for e in log["issues"] if e["kind"] == "equation" and e["issue"] == "mineru_low_confidence"]
if not suspect:
    print("FAIL: expected at least one mineru_low_confidence equation in parse_log", file=sys.stderr)
    sys.exit(1)

# unmatched image preserved
if "figures/broken_eq.png" not in manifest["unmatched_images"]:
    print("FAIL: broken_eq.png should land in unmatched_images", file=sys.stderr)
    sys.exit(1)

print(f"OK  figures={manifest['figure_count']} tables={manifest['table_count']} "
      f"equations={manifest['equation_count']} suspect_eqs={len(suspect)}")
PY

echo "[selftest] PASS"
