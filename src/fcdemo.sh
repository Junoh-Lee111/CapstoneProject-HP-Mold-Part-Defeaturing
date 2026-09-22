#!/bin/bash
# Live FreeCAD demo of the CleanCAD prototype (see demo_freecad.py).
#
# Usage:
#   fcdemo.sh [--quit]                     all examples from manifest.json, one after another
#   fcdemo.sh [--quit] name1,name2         only those examples
#   fcdemo.sh [--quit] file.step [rules]   a single file, rules comma-separated (default: cyl)
#
# Env:
#   CLEANCAD_WORKDIR    where results/logs/snapshots go (default: ~/Documents/CleanCAD_Workspace)
#   CLEANCAD_DELAY_MS   delay between animation steps in ms (default: 1200)
#   FREECAD_APP         path to the FreeCAD.app bundle (default: /Applications/FreeCAD.app)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FREECAD_APP="${FREECAD_APP:-/Applications/FreeCAD.app}"

if [ "${1:-}" = "--quit" ]; then
  export CLEANCAD_AUTOQUIT=1
  shift
fi

if [[ "${1:-}" == *.step ]]; then
  export CLEANCAD_INPUT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
  export CLEANCAD_RULE="${2:-cyl}"
elif [ -n "${1:-}" ]; then
  export CLEANCAD_ONLY="$1"
fi

nohup "$FREECAD_APP/Contents/MacOS/FreeCAD" "$SCRIPT_DIR/demo_freecad.py" >/dev/null 2>&1 &
echo "FreeCAD launched. Results under: ${CLEANCAD_WORKDIR:-$HOME/Documents/CleanCAD_Workspace}"
