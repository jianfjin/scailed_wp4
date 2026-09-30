#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
proposal_dir="$repo_root/docs/proposal"
output_dir="$proposal_dir/pdf"

mkdir -p "$output_dir"
if command -v pandoc >/dev/null 2>&1; then
  for source in "$proposal_dir"/volume-*.md; do
    target="$output_dir/$(basename "${source%.md}").pdf"
    pandoc "$source" \
      --from=gfm \
      --toc \
      --number-sections \
      --output="$target"
    echo "wrote $target"
  done
  exit 0
fi

command -v soffice >/dev/null 2>&1 || {
  echo "pandoc or LibreOffice (soffice) is required to build proposal PDFs" >&2
  exit 1
}

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

for source in "$proposal_dir"/volume-*.md; do
  base="$(basename "${source%.md}")"
  html="$temp_dir/$base.html"
  python3 - "$source" "$html" <<'PY'
import sys
from pathlib import Path
import markdown

source, target = map(Path, sys.argv[1:])
body = markdown.markdown(
    source.read_text(),
    extensions=["fenced_code", "tables", "toc", "nl2br"],
    output_format="html5",
)
target.write_text(
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<style>@page{size:A4;margin:1.5cm}body{font-family:Arial,sans-serif;margin:0;line-height:1.35}"
    "h1,h2,h3{color:#173f35}table{border-collapse:collapse;width:100%;table-layout:auto}"
    "th,td{border:1px solid #999;padding:3px 4px;vertical-align:top;font-size:9.5pt;"
    "word-break:normal;overflow-wrap:normal;white-space:normal;hyphens:none}"
    "code,pre{font-family:monospace}pre{background:#f3f5f4;padding:8px}"
    "</style></head><body>" + body + "</body></html>",
)
PY
  soffice --headless --convert-to pdf --outdir "$output_dir" "$html" >/dev/null
  echo "wrote $output_dir/$base.pdf"
done
