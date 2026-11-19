"""Lets a recognizer take part in the engine as one more rule, without changing the engine or the rules."""
import os
import sys

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402


def register_as_rule(name, recognizer, category="recognition", batch="try"):
    """Register `recognizer` as the engine rule `name`: the faces of its candidates whose confidence is at least
    the profile's 'min_confidence' are the faces to remove. The engine selects again after every removal, so
    recognize() is called repeatedly: keep the expensive part (the model) cached inside the recognizer."""

    def select(shape):
        limit = core.PROFILE.get("min_confidence", 0.0)
        wanted = {s for c in recognizer.recognize(shape) if c.confidence >= limit for s in map(tuple, c.faces)}
        return [f for f in shape.Faces if core.sig(f) in wanted]

    core.set_rule(name, batch=batch, category=category)(select)
    return select
