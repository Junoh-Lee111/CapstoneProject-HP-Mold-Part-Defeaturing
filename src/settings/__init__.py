"""SETTINGS: the size limits and switches that decide WHAT may be removed, in one place.

Pure Python (no FreeCAD), so the rules, the screen, the ML code and the tests can all import it.

  FIELDS           the numeric limits with unit, range and a one-line explanation (the screen builds itself from it)
  BUILTIN_PRESETS  the preset values that ship with the code
  effective(values)  what the rules actually read (core.PROFILE): e.g. 'keep fastener holes' forces hole limit 0
  list_presets / load_preset / save_preset   user presets, stored as JSON under $CLEANCAD_WORKDIR/presets
"""
from .presets import (FIELDS, SWITCHES, CONFIDENCE, BUILTIN_PRESETS, DEFAULT_PRESET, effective, normalise,  # noqa: F401
                      presets_dir, list_presets, load_preset, save_preset)
