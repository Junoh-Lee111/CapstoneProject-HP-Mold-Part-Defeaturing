# CleanCAD prototype - code layout

The code is split into layers (folders). Architecture modules C1-C9 are in brackets.

| Folder | Layer | What is in it |
|---|---|---|
| `input/` | Input [C1-C3] | *(planned)* STEP reading, B-rep face extraction, face-adjacency graph for the ML step. See its README. |
| `recognition/` | Recognition contract [C4] | What every recognizer returns (`Candidate`: feature, face signatures, confidence, source, reason), the registry, `register_as_rule()` (lets a recognizer act as one more rule for the engine). `rule_based.py` wraps the rules; **the ML recognizer goes into `recognition/ml/` only** (see its README). |
| `settings/` | Limits [C5] | The size limits and switches (hole diameter, fillet radius, chamfer width, logo depth, boss diameter, rib thickness, preserve fastener holes, minimum confidence), built-in presets, user presets as JSON under `$CLEANCAD_WORKDIR/presets`. Pure Python, no FreeCAD. The screen's left panel edits exactly these. |
| `rules/` | Rules [C4, C5] | What to remove, grouped by what it recognises: `holes.py`, `edges.py` (fillets, chamfers), `protrusions.py` (ribs, bosses, repeated bumps), `markings.py` (logos, shallow recesses / debosses). Today rule-based; the ML recognition will plug in here. |
| `engine/` | Engine [C5-C7] | `cleancad_core.py` (select, group, remove, verify, failure handling, profiles), `defeature_worker.py` (guarded removal process with a time limit), `geom_utils.py` (shared geometry helpers), `live.py` (remove a chosen set of faces in one go, for the live preview). |
| `output/` | Output [C7, C9] | *(planned)* result STEP, failure records, report. Today the scripts write these straight into `~/Documents/CleanCAD_Workspace/`. See its README. |
| `demo/` | Screen [C8] | `demo_freecad.py` (interactive FreeCAD demo), `fcdemo.sh` (launcher for any file), `hp_demo.sh` (launcher for the HP sample parts with the rules that suit each). |
| `validation/` | Checks | `gen_examples.py` (test parts + face-level ground truth), `run_headless.py` (28 checks), `evaluate_rules.py` (precision / recall), `test_timeout.py`, `test_settings_recognition.py` (settings and recognition contract, 12 checks). |

## Run (FreeCAD 1.1.3, macOS)
```bash
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
$FC src/validation/gen_examples.py     # test parts (once, or after a change)
$FC src/validation/run_headless.py     # all checks -> "28/28 PASS"
$FC src/validation/evaluate_rules.py   # rule accuracy -> ~/Documents/CleanCAD_Workspace/logs/evaluation.md
bash src/demo/fcdemo.sh <file.step> <rule[,rule]>    # interactive demo, e.g. rib, logo, chamfer_edge
```
### Demo with the HP sample parts
The HP files are confidential and are not in the repository; `HP_SAMPLES` is the folder that holds them
(required: `export HP_SAMPLES=...`, there is no default because the files are confidential).
```bash
bash src/demo/hp_demo.sh list       # which samples, what each one shows, which have a known limit
bash src/demo/hp_demo.sh pin        # start one (closes a demo that is still open)
```
In the demo: `->` next step, `<-` back, click a face to add / remove it, `R` reset, `H` hide messages.
Not suited for a live demo: Ph_rib_to_keep, Many_ribs_to_remove, Logoes_Mold_01 (many faces, minutes of waiting).
Known limits are listed in `docs/prototype_rules.md`, section 5.

Results never go into the repository; they are written to `~/Documents/CleanCAD_Workspace/`.
Rules and thresholds are provisional - see `docs/prototype_rules.md`.
