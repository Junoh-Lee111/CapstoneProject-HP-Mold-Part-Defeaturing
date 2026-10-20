"""Face-level evaluation of rule sets against generated ground truth.

Run: FreeCADCmd src/gen_examples.py && FreeCADCmd src/evaluate_rules.py
Reads manifest.json + <case>.truth.json (written by gen_examples.py) and, for each rule set,
compares the faces the rules SELECT on the generated shape with the faces that must be removed.
Writes $CLEANCAD_WORKDIR/logs/evaluation.md (nothing is written into the repo).
Precision = selected faces that are truth / selected faces; recall = truth faces selected / truth faces.
"""
import json
import os
import sys
from collections import defaultdict

import Part

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
EXAMPLES = os.path.join(WORKDIR, "samples", "examples")
REF = ["ref_holes", "ref_fillets", "ref_protrusions"]


def predict(shape, rules, profile):
    core.set_profile(profile)
    return {core.sig(f) for f in core.select(shape, rules)}


def ratio(a, b):
    return f"{a / b:.2f}" if b else "n/a"


def main():
    manifest = [e for e in json.load(open(os.path.join(EXAMPLES, "manifest.json"))) if "truth" in e]
    sets = [  # (label, rules or None=use the case's own scaffolding rules, profile)
        ("scaffolding rules (cyl/prot/recess/chamfer)", None, "hp_example"),
        ("ref rules, recognition only (size limits 50 mm)", REF, "recognition_only"),
        ("ref rules, hp_example (holes < 6 mm, fillets < 10 mm)", REF, "hp_example"),
        ("logo rule (engraving / emboss), hp_example", ["logo"], "hp_example"),
    ]
    out = ["# Face-level rule evaluation", "",
           "Truth = faces of the generated shape that are not part of the clean base shape. "
           "Generated cases only (9); logos are out of scope.", ""]
    for label, rules, profile in sets:
        out += [f"## {label}", "",
                "| case | truth | selected | TP | FP | FN | precision | recall | missed types |",
                "|---|---|---|---|---|---|---|---|---|"]
        tt = tp = tfp = tfn = 0
        by_type = defaultdict(lambda: [0, 0])
        for e in manifest:
            shape = Part.read(e["file"])
            truth_rows = json.load(open(e["truth"]))["remove"]
            truth = {tuple(r["sig"]): r["type"] for r in truth_rows}
            pred = predict(shape, rules or e["rules"], profile)
            hit = {s for s in truth if s in pred}
            fp, fn = pred - set(truth), set(truth) - pred
            missed = sorted({truth[s] for s in fn})
            for s, t in truth.items():
                by_type[t][1] += 1
                by_type[t][0] += s in pred
            out.append(f"| {e['name']} | {len(truth)} | {len(pred)} | {len(hit)} | {len(fp)} | {len(fn)} | "
                       f"{ratio(len(hit), len(pred))} | {ratio(len(hit), len(truth))} | {', '.join(missed) or '-'} |")
            tt, tp, tfp, tfn = tt + len(truth), tp + len(hit), tfp + len(fp), tfn + len(fn)
        out += ["", f"Overall: precision {ratio(tp, tp + tfp)}, recall {ratio(tp, tt)} "
                    f"(TP {tp}, FP {tfp}, FN {tfn}).", "",
                "| feature type | truth faces | found | recall |", "|---|---|---|---|"]
        for t, (found, n) in sorted(by_type.items()):
            out.append(f"| {t} | {n} | {found} | {ratio(found, n)} |")
        out.append("")
        print(f"RESULT {label}: precision {ratio(tp, tp + tfp)} recall {ratio(tp, tt)} TP={tp} FP={tfp} FN={tfn}")
    path = os.path.join(WORKDIR, "logs", "evaluation.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(out) + "\n")
    print(f"RESULT report -> {path}")


main()
