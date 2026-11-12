"""Checks of the settings package and of the recognition contract (FreeCADCmd src/validation/test_settings_recognition.py).
Needs the generated examples (gen_examples.py). Writes only to a temporary folder."""
import json
import os
import sys
import tempfile

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SRC, os.path.join(_SRC, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ["CLEANCAD_WORKDIR"] = tempfile.mkdtemp(prefix="cleancad_test_")   # presets go here, not into the real workspace
import cleancad_core as core  # noqa: E402
import settings  # noqa: E402
import recognition  # noqa: E402
from recognition import Candidate, Recognizer  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"CHECK {'PASS' if ok else 'FAIL'}  {name}  {detail}")


# ---- settings -----------------------------------------------------------------------------------------
check("built-in presets keep the values the rules always had",
      core.PROFILES["hp_example"] == {**core.PROFILES["hp_example"], "hole_diameter": 6.0, "fillet_radius": 10.0,
                                      "chamfer_size": 5.0, "logo_max_depth": 0.5, "boss_max_diameter": 20.0,
                                      "rib_max_thickness": 4.0}
      and core.PROFILES["keep_fasteners"]["hole_diameter"] == 0.0 and core.PROFILES["keep_fasteners"]["fillet_radius"] == 5.0
      and core.PROFILES["recognition_only"]["hole_diameter"] == 50.0)
v = settings.normalise({"fillet_radius": 999, "chamfer_size": -3, "nonsense": 1})
check("values are clamped into their range and unknown keys dropped",
      v["fillet_radius"] == 50.0 and v["chamfer_size"] == 0.0 and "nonsense" not in v)
check("'preserve fastener holes' forces hole limit 0",
      settings.effective({"hole_diameter": 6.0, "keep_fasteners": True})["hole_diameter"] == 0.0
      and settings.effective({"hole_diameter": 6.0, "keep_fasteners": False})["hole_diameter"] == 6.0)
path = settings.save_preset("my test", {"fillet_radius": 2.5, "keep_fasteners": True})
loaded = settings.load_preset("my test")
check("a user preset is saved as JSON and loaded back",
      os.path.exists(path) and loaded["fillet_radius"] == 2.5 and loaded["keep_fasteners"] is True
      and "my test" in settings.list_presets() and json.load(open(path))["fillet_radius"] == 2.5)
try:
    settings.save_preset("hp_example", {})
    check("a built-in preset cannot be overwritten", False)
except ValueError:
    check("a built-in preset cannot be overwritten", True)
core.apply_settings({"fillet_radius": 1.25, "keep_fasteners": False, "hole_diameter": 3.0})
check("core.apply_settings changes what the rules read", core.PROFILE["fillet_radius"] == 1.25 and core.PROFILE["hole_diameter"] == 3.0)
core.set_profile("my test")
check("core.set_profile accepts a saved user preset", core.PROFILE["fillet_radius"] == 2.5)

# ---- recognition contract -------------------------------------------------------------------------------
manifest = json.load(open(os.path.join(os.environ.get("HOME"), "Documents", "CleanCAD_Workspace", "samples", "examples", "manifest.json")))
plate = next(e for e in manifest if e["name"] == "plate_hole_fillets")
shape = Part.read(plate["file"])
core.set_profile("recognition_only")
cands = recognition.get("rules").recognize(shape)          # default: every real rule
check("rule-based recognizer returns Candidates (a hole and fillets)",
      cands and all(isinstance(c, Candidate) for c in cands) and {"ref_holes", "ref_fillets"} <= {c.feature for c in cands},
      f"{[(c.feature, len(c.faces)) for c in cands]}")
check("registry lists the rule-based recognizer", "rules" in recognition.available())


class FakeCylinders(Recognizer):
    """Stands in for the ML model: every cylinder is a feature, 0.9 sure; one of them only 0.5."""
    name = "fake"

    def recognize(self, shape, settings=None):
        cyl = [f for f in shape.Faces if type(f.Surface).__name__ == "Cylinder"]
        out = [Candidate("cylinder", [core.sig(f)], 0.9, "fake") for f in cyl[:-1]]
        return out + ([Candidate("cylinder", [core.sig(cyl[-1])], 0.5, "fake")] if cyl else [])


recognition.register_as_rule("fake", FakeCylinders())
n_cyl = sum(type(f.Surface).__name__ == "Cylinder" for f in shape.Faces)
core.PROFILE["min_confidence"] = 0.8
picked = core.select(shape, ["fake"])
check("a registered recognizer is a rule: only candidates above min_confidence are selected", len(picked) == n_cyl - 1,
      f"{len(picked)} of {n_cyl}")
core.PROFILE["min_confidence"] = 0.95
check("a higher min_confidence selects nothing", len(core.select(shape, ["fake"])) == 0)
core.PROFILE["min_confidence"] = 0.4
final, removed, failures = core.process(shape, ["fake"])
check("the engine removes what the recognizer found, no engine change needed",
      len(final.Faces) < len(shape.Faces) and final.isValid() and not failures,
      f"faces {len(shape.Faces)} -> {len(final.Faces)}")

print(f"SUMMARY {sum(RESULTS)}/{len(RESULTS)} PASS")
