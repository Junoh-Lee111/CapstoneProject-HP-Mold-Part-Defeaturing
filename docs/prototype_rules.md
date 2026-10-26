# Prototype Rules (provisional)

> **Status: provisional, for testing only.** These are the rules the prototype uses *to exercise the removal
> pipeline end to end*. They are starting points, not validated engineering criteria and not requirements.
> The real decision criteria (what to remove, which limits) are still open and come from HP / the team.
> The formal requirements are in the consolidated FR/NFR/SA/DE document.

Code: `src/` (run headless with FreeCAD: `freecadcmd src/<script>.py`). Test files and results are written to
`~/Documents/CleanCAD_Workspace/`, never into the repository.

## 1. How a rule works

A rule decides which faces of a part are candidates for removal. `process()` in `src/cleancad_core.py` then
groups connected candidate faces into features, removes each feature with FreeCAD `defeaturing()`, and checks
the result (valid solid, shape actually changed). A removal that fails, times out or crashes is recorded as a
failure and the original geometry is kept.

Size limits are **profiles** (configuration), selected with the environment variable `CLEANCAD_PROFILE`:

| Profile | Meaning | Hole diameter | Fillet radius |
|---|---|---|---|
| `hp_example` (default) | parameters of the example HP sent; only for that example | < 6 mm | < 10 mm |
| `keep_fasteners` | fastener holes are kept: only holes of 2 mm or less are removed (HP, 2026-10-13) | <= 2 mm | < 5 mm (earlier starting value, unconfirmed) |
| `recognition_only` | wide limits, to test recognition independent of size | < 50 mm | < 50 mm |

All profiles also carry: logo depth cap 0.5 mm, boss max. diameter 20 mm, rib max. thickness 4 mm,
chamfer max. width 5 mm. These four are our own starting values.

## 2. Rules, grouped by what they recognise

The code is organised the same way: one module per group in `src/rules/` (`holes.py`, `edges.py`,
`protrusions.py`, `markings.py`); `cleancad_core.rules_by_category()` lists them. Shared geometry helpers are in
`src/geom_utils.py`.

| Group | Rule | Selects | Source |
|---|---|---|---|
| **Holes** | `ref_holes` | complete round holes (360 degrees) below the profile diameter, including a blind-hole floor | port of HP's example script |
| **Edge treatments** | `ref_fillets` | blend faces (partial cylinder, torus, sphere) below the profile radius that run tangent into two supporting faces; removed together | port of HP's example script |
| | `chamfer_edge` | a narrow face between two faces it meets at 25-65 degrees, those two being about 90 degrees apart (also countersinks) | ours |
| **Protrusions** | `ref_protrusions` | rounded, elongated patches on a large plane that occur at least twice with the same shape (press-formed ribs) | port of HP's example script |
| | `rib` | thin, long protrusions standing on a flat host (crossing networks, ribs over a gentle bend, ribs at a part's edge) | ours |
| | `boss` | round columns standing on a flat host, up to the max. diameter | ours |
| **Markings** | `logo` | engravings and embosses: faces bundled from the non-circular inner wires of a flat host, shallow only | HP's logo rule description, plus our depth cap |
| *(test scaffolding)* | `cyl`, `prot`, `recess`, `chamfer`, `fail_demo` | the original rules, tied to the shape of the generated test parts | ours (test scaffolding) |

How `logo` works (HP's description): start at the inner wires of a planar face; a wire that is a single circle
is an ordinary hole and is skipped (unless there are several non-circular wires, i.e. several glyphs); follow the
edge adjacency for at most 3 steps through faces smaller than 20 % of the host and not deeper than 0.35 x the
wire size; reject a bundle larger than 25 % of the host; skip a wire that has a matching inner boundary on the
opposite plane (a through cut). Our own addition: a depth cap of 0.5 mm, so that a blind pocket is not taken for a
marking.

## 3. Safety guard

`defeaturing()` can hang on some real free-form geometry. Headless runs therefore execute each removal in a
separate FreeCAD process and kill it after 60 s (`CLEANCAD_DEFEATURE_TIMEOUT`, 0 = off). A timeout counts as an
ordinary failure. The GUI demo runs in-process without a limit.

## 4. How it was tested (and how far to trust it)

- `gen_examples.py` builds 14 simple generated parts (holes, fillets, ribs, chamfer, boss, emboss, engraved and
  embossed text, and negative cases that must stay unchanged) and records, per part, which faces are the ground truth.
- `run_headless.py`: every part must give the expected face count and volume (24/24 with the original and the
  generic rules). `evaluate_rules.py`: face-level precision/recall per rule set -> `logs/evaluation.md`.
- Result on the generated parts: holes, fillets, ribs, chamfers and text logos are found; negative cases are left
  alone. **These parts are simple and made by us - the numbers say nothing about general accuracy.**

## 5. Known limits

- Ribs and bosses are only recognized on a **flat** host (a plane, or a flat free-form face). Ribs that reach the
  host's edge are found from its outer wire (thin, at least twice as long as wide, at least 3 faces); ribs on
  genuinely curved hosts are not found.
- When `defeaturing()` cannot remove a rib or boss, the prism standing on its host plane is cut away instead (boolean
  cut, same guarded worker). On surface models (shells, no solid) a logo is removed by dropping its faces and
  re-making the host face without the logo's holes. Both are fallbacks, tried only after defeaturing failed.
- Marking circles/rings (single circular wire) are treated as holes.
- B-spline chamfers are detected but FreeCAD cannot remove them (reported as a failure).
- Press-part logos given as open shells of flat free-form faces are recognized and mostly removed; a few thin
  stroke fragments of a letter can remain (faces beyond the 3-step limit).
- The text test cases use the macOS font Arial Bold.
- Size limits are not validated; whether a hole or rib must be kept (fasteners, structure) depends on the analysis.

## 6. Open questions for HP

- Criteria for ribs to keep vs. remove; whether stamped (sheet-metal) bosses are in scope.
- Chamfer and fillet limits; whether shallow circular marks may be removed; the logo depth cap.
- How to treat press-part logos (shells).
