#!/bin/bash
# Start the interactive demo for one of the HP sample parts, with the rules and profile that suit it.
# The HP files are confidential and are NOT in this repository: point HP_SAMPLES at the folder that holds them.
#
# Usage:
#   hp_demo.sh list            what each sample shows and how well it works
#   hp_demo.sh <name>          start one, e.g. hp_demo.sh pin     (a part of the file name is enough)
#
# Env:
#   HP_SAMPLES   folder with the HP .step / .stp files (default: ~/Downloads/Features_Cut)
#
# Keys in the demo: -> next step, <- back, click a face to add / remove it, R reset, H hide messages.
# Only one FreeCAD may run at a time: the script closes a demo that is still open.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HP_SAMPLES="${HP_SAMPLES:-$HOME/Downloads/Features_Cut}"

# name | file | rules | what it shows
ALL="ref_protrusions,rib_simplify,pin_tip,boss,ref_holes,ref_fillets,chamfer_edge,logo"
SAMPLES=(
  "pin|Boss_dol_to_keep_and_remove.step|$ALL|a locating pin is kept, its tapered tip becomes a plain cylinder (the bore inside stays closed)"
  "boss|Boss_to_remove.step|$ALL|two rounded edges at a stamped boss are made square"
  "fillet1|Fillet1.stp|$ALL|rounded edges"
  "fillet2|Fillet2.stp|$ALL|rounded edge"
  "hole1|Hole1.stp|$ALL|nothing is removed: round holes are always kept"
  "hole2|Hole2.stp|$ALL|one small face goes, the hole stays"
  "hole3|Hole3.stp|$ALL|rounded corner; the camera turns to features on the back"
  "hole4|Hole4.stp|$ALL|ring around a fastener hole and the hole stay, the stepped round goes"
  "rib|PH_rib_to_remove.step|$ALL|rounded ribs become rectangular ribs (no gap at the bend)"
  "logo1|Logoes_Press_01.step|$ALL|press-part logos on an open shell (two sheets); a small stub at the sheet edge remains"
  "logo2|Logoes_Press_02_X01.step|$ALL|press-part logos on an open shell"
  "chamfer|chamfer_001_Remove.step|$ALL|LIMIT: free-form chamfer, only part of it can be removed (failure is reported)"
)
# Not suited for a live demo: Ph_rib_to_keep (slow, only part of the rounds go), Many_ribs_to_remove (1566 faces, minutes),
# Logoes_Mold_01 (991 faces, slow).

if [ "${1:-list}" = "list" ]; then
  printf '%-9s %-34s %s\n' NAME FILE "WHAT IT SHOWS"
  for row in "${SAMPLES[@]}"; do
    IFS='|' read -r name file rules text <<<"$row"
    printf '%-9s %-34s %s\n' "$name" "$file" "$text"
  done
  exit 0
fi

for row in "${SAMPLES[@]}"; do
  IFS='|' read -r name file rules text <<<"$row"
  if [ "$name" = "$1" ] || [[ "$file" == *"$1"* ]]; then
    if [ ! -f "$HP_SAMPLES/$file" ]; then
      echo "Not found: $HP_SAMPLES/$file  (set HP_SAMPLES to the folder with the HP files)" >&2
      exit 1
    fi
    pkill -f "Resources/bin/freecad" 2>/dev/null || true
    sleep 2
    echo "$name: $text"
    CLEANCAD_PROFILE=keep_fasteners bash "$SCRIPT_DIR/fcdemo.sh" "$HP_SAMPLES/$file" "$rules"
    exit 0
  fi
done
echo "Unknown sample '$1'. Try: hp_demo.sh list" >&2
exit 1
