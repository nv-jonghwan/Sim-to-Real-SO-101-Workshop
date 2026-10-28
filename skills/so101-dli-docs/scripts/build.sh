#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
mode=${1:-both}
language=${2:-all}
case "$mode" in learner|event|instructor|both|all) ;; *) echo 'Usage: build.sh [learner|event|instructor|both|all] [en|ko|all]' >&2; exit 2 ;; esac
case "$language" in en|ko|all) ;; *) echo 'Usage: build.sh [learner|event|instructor|both|all] [en|ko|all]' >&2; exit 2 ;; esac
if [[ ! -x "$repo/.venv/bin/sphinx-build" ]]; then
  echo 'Missing documentation environment: run uv sync --frozen in the repo first.' >&2
  exit 2
fi
"$repo/.venv/bin/python" - "$repo" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
pointers = []
for name in ('docs', 'images'):
    for path in (root / name).rglob('*'):
        if '_build' in path.parts or not path.is_file() or path.stat().st_size >= 512:
            continue
        if path.read_bytes().startswith(b'version https://git-lfs.github.com/spec/v1'):
            pointers.append(str(path.relative_to(root)))
if pointers:
    sys.exit('Hydrate document LFS files before building: ' + ', '.join(pointers))
PY
cd "$repo"
for locale in en ko; do
  [[ "$language" == all || "$language" == "$locale" ]] || continue
  if [[ "$locale" == ko ]]; then
    .venv/bin/python skills/so101-dli-docs/scripts/localization.py check
  fi
  for audience in learner event instructor; do
    if [[ "$mode" != all && "$mode" != "$audience" ]]; then
      [[ "$mode" == both && "$audience" != instructor ]] || continue
    fi
    output="docs/_build/$audience"
    [[ "$locale" == en ]] || output="docs/_build/ko/$audience"
    args=()
    [[ "$audience" == learner ]] || args=(-t event)
    [[ "$audience" != instructor ]] || args+=(-t instructor)
    # Regenerate search terms alongside the full page rewrite.
    rm -f -- "$output/html/searchindex.js"
    # Rewrite every page so cached sidebars pick up renamed page titles.
    .venv/bin/sphinx-build -M html docs "$output" "${args[@]}" -D "language=$locale" -a -W --keep-going
  done
done
