"""Setting definitions, built-in presets and user presets (JSON files)."""
import json
import os
import re
from collections import namedtuple

Field = namedtuple("Field", "key label unit minimum maximum step hint")

# The numeric limits. All sizes are millimetres. Provisional values, NOT validated general criteria
# (the mentor: "should not be treated as a universal rule"): the user is meant to change them.
FIELDS = (
    Field("hole_diameter", "Hole diameter", "mm", 0.0, 50.0, 0.1, "round holes smaller than this may be removed"),
    Field("fillet_radius", "Fillet radius", "mm", 0.0, 50.0, 0.1, "rounded edges up to this radius are removed"),
    Field("chamfer_size", "Chamfer width", "mm", 0.0, 20.0, 0.1, "bevelled edges up to this width are removed"),
    Field("logo_max_depth", "Logo max depth", "mm", 0.0, 5.0, 0.1, "engraved / raised marks up to this depth are logos"),
    Field("boss_max_diameter", "Boss max diameter", "mm", 0.0, 100.0, 0.5, "round columns up to this diameter are bosses"),
    Field("rib_max_thickness", "Rib max thickness", "mm", 0.0, 20.0, 0.5, "thin walls up to this thickness are ribs"),
)

# On / off switches and the confidence limit (the confidence is used by recognizers that report one, i.e. ML).
SWITCHES = (
    ("keep_fasteners", "Preserve fastener holes", "round holes are never removed, whatever the hole limit"),
)
CONFIDENCE = ("min_confidence", "Minimum confidence", 0.0, 1.0, 0.05)

_BASE = {"hole_diameter": 6.0, "fillet_radius": 10.0, "chamfer_size": 5.0, "logo_max_depth": 0.5,
         "boss_max_diameter": 20.0, "rib_max_thickness": 4.0, "keep_fasteners": False, "min_confidence": 0.0}

BUILTIN_PRESETS = {
    # example parameters of the HP-supplied script (hard_7); NOT general criteria
    "hp_example": dict(_BASE),
    # recognition-only evaluation: size limits so wide that no real feature is filtered out by size
    "recognition_only": dict(_BASE, hole_diameter=50.0, fillet_radius=50.0),
    # HP: fastener holes are kept (the 2 mm is the mentor's size below which a hole is optional);
    # the fillet value is the earlier mentor starting value, still to be confirmed
    "keep_fasteners": dict(_BASE, hole_diameter=2.0, fillet_radius=5.0, keep_fasteners=True),
}
DEFAULT_PRESET = "hp_example"


def normalise(values):
    """Complete a values dict with the defaults and clamp every number into its range."""
    out = dict(_BASE)
    out.update({k: v for k, v in (values or {}).items() if k in _BASE})
    for f in FIELDS:
        out[f.key] = min(max(float(out[f.key]), f.minimum), f.maximum)
    out["min_confidence"] = min(max(float(out["min_confidence"]), CONFIDENCE[2]), CONFIDENCE[3])
    out["keep_fasteners"] = bool(out["keep_fasteners"])
    return out


def effective(values):
    """The dict the rules read (core.PROFILE). 'Preserve fastener holes' means: no round hole is removed."""
    v = normalise(values)
    return {"hole_diameter": 0.0 if v["keep_fasteners"] else v["hole_diameter"],
            "fillet_radius": v["fillet_radius"], "chamfer_size": v["chamfer_size"],
            "logo_max_depth": v["logo_max_depth"], "boss_max_diameter": v["boss_max_diameter"],
            "rib_max_thickness": v["rib_max_thickness"], "min_confidence": v["min_confidence"]}


def presets_dir():
    workdir = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
    return os.path.join(workdir, "presets")


def _file(name):
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not safe:
        raise ValueError("empty preset name")
    return os.path.join(presets_dir(), safe + ".json")


def list_presets():
    """Names of the built-in presets followed by the user's saved ones."""
    saved = []
    if os.path.isdir(presets_dir()):
        saved = sorted(os.path.splitext(n)[0] for n in os.listdir(presets_dir()) if n.endswith(".json"))
    return list(BUILTIN_PRESETS) + [n for n in saved if n not in BUILTIN_PRESETS]


def load_preset(name):
    if name in BUILTIN_PRESETS:
        return normalise(BUILTIN_PRESETS[name])
    with open(_file(name)) as fh:
        return normalise(json.load(fh))


def save_preset(name, values):
    """Store a user preset; a built-in name cannot be overwritten. Returns the file path."""
    if name in BUILTIN_PRESETS:
        raise ValueError(f"'{name}' is a built-in preset; choose another name")
    os.makedirs(presets_dir(), exist_ok=True)
    path = _file(name)
    with open(path, "w") as fh:
        json.dump(normalise(values), fh, indent=1)
    return path
