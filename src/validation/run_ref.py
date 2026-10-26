"""Run the reference rules (holes / fillets / repeated protrusions) on one STEP file through the
CleanCAD pipeline and compare with a reference result.

Run: REF_IN=a.stp REF_OUT=out.step [REF_REF=ref.stp] [CLEANCAD_PROFILE=hp_example|keep_fasteners] \
     freecadcmd src/validation/run_ref.py
"""
import os
import sys
import time
from collections import Counter

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core

RULES = ["ref_holes", "ref_fillets", "ref_protrusions"]


def summary(shape):
    return {"faces": len(shape.Faces), "volume": round(shape.Volume, 1),
            "types": dict(Counter(type(f.Surface).__name__ for f in shape.Faces)),
            "valid": shape.isValid(), "solids": len(shape.Solids)}


def main():
    inp, out, ref = os.environ["REF_IN"], os.environ["REF_OUT"], os.environ.get("REF_REF")
    lines = []

    def log(s):
        print("RESULT " + s)
        lines.append(s)

    shape = Part.read(inp)
    t0 = time.time()
    final, removed, failures = core.process(shape, RULES)
    log(f"profile {core.PROFILE}; {time.time() - t0:.0f}s; removed groups {len(removed)}, failures {len(failures)}")
    log(f"before {summary(shape)}")
    log(f"after  {summary(final)}")
    final.exportStep(out)
    if ref:
        r = Part.read(ref)
        log(f"ref    {summary(r)}")
        a, b = Counter(core.sig(f) for f in final.Faces), Counter(core.sig(f) for f in r.Faces)
        log(f"face signatures: ours {sum(a.values())}, ref {sum(b.values())}, common {sum((a & b).values())}, "
            f"only ours {sum((a - b).values())}, only ref {sum((b - a).values())}")
    for fl in failures:
        log(f"failure: {fl['types']} {fl['faces']} faces: {fl['reason']}")
    with open(os.path.splitext(out)[0] + "_report.txt", "w") as fh:
        fh.write("\n".join(lines) + "\n")


main()
