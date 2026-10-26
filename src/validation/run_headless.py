"""Headless end-to-end check of every example in manifest.json against its expected result.

Run: FreeCADCmd src/validation/gen_examples.py && FreeCADCmd src/validation/run_headless.py
Reads/writes only under $CLEANCAD_WORKDIR (default ~/Documents/CleanCAD_Workspace) - nothing in the repo.
"""
import os
import sys
import json
import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
EXAMPLES = os.path.join(WORKDIR, "samples", "examples")
OUT_DIR = os.path.join(EXAMPLES, "out")
FAIL_DIR = os.path.join(EXAMPLES, "failures")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(FAIL_DIR, exist_ok=True)


def main():
    manifest = json.load(open(os.path.join(EXAMPLES, "manifest.json")))
    rows = []
    jobs = [(e, e["rules"], "scaffolding") for e in manifest]
    jobs += [(e, e["generic_rules"], "generic") for e in manifest if "generic_rules" in e]
    for entry, rules, variant in jobs:
        core.set_profile("recognition_only" if variant == "generic" else "hp_example")
        source = Part.read(entry["file"])
        final_shape, removed, failures = core.process(source, rules)
        label = entry["name"] + ("" if variant == "scaffolding" else " [generic]")
        out_path = os.path.join(OUT_DIR, f"{entry['name']}{'' if variant == 'scaffolding' else '_generic'}_defeatured.step")
        final_shape.exportStep(out_path)

        if failures:  # FR-DEF-04 / NFR-REL-02: keep geometry + failed face IDs for manual fix + retraining
            source.exportStep(os.path.join(FAIL_DIR, f"{entry['name']}_failed.step"))
            json.dump(failures, open(os.path.join(FAIL_DIR, f"{entry['name']}_failed.json"), "w"), indent=1)

        round_trip = Part.read(out_path)
        ok = (
            len(final_shape.Faces) == entry["expected_faces"]
            and abs(final_shape.Volume - entry["expected_volume"]) <= 0.05
            and (len(failures) > 0) == entry["expect_failure"]
            and final_shape.isValid()
            and round_trip.isValid()
        )
        rows.append((label, len(source.Faces), len(final_shape.Faces), entry["expected_faces"],
                     round(final_shape.Volume, 2), entry["expected_volume"], len(removed), len(failures),
                     "PASS" if ok else "CHECK"))
        print(f"RESULT {label:28s} faces {len(source.Faces):3d}->{len(final_shape.Faces):3d} "
              f"(expected {entry['expected_faces']:3d})  volume {final_shape.Volume:10.2f} "
              f"(expected {entry['expected_volume']:10.2f})  removed={len(removed)} failed={len(failures)}  "
              f"{'PASS' if ok else 'CHECK'}")

    report_path = os.path.join(WORKDIR, "logs", "report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("| example | faces before | after | expected | volume | expected | features removed | failures | verdict |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write("| " + " | ".join(map(str, r)) + " |\n")
    passed = sum(r[-1] == "PASS" for r in rows)
    print(f"SUMMARY {passed}/{len(rows)} PASS -> {report_path}")


# Note: FreeCADCmd runs this file with __name__ set to the module name, not "__main__",
# so call main() unconditionally rather than gating on the usual `if __name__ == "__main__"`.
main()
