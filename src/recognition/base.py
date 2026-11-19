"""The data every recognizer returns."""
from dataclasses import dataclass, field


@dataclass
class Candidate:
    """One recognised feature: a group of faces of the model.

    feature     feature type, e.g. "fillet", "hole", "chamfer", "rib", "boss", "logo", "deboss"
    faces       the faces as face signatures (cleancad_core.sig(face): type, area, centre) - the identity the engine
                uses, which survives edits of other faces. Graph nodes of the ML model must be mapped to these.
    confidence  0..1; the rule-based recognizer reports 1.0
    source      who found it: "rules", "ml", ...
    reason      one line for the report / the screen table
    size_mm     the measured size the decision uses (radius, width, depth ...), if there is one
    """
    feature: str
    faces: list
    confidence: float = 1.0
    source: str = "rules"
    reason: str = ""
    size_mm: float = None
    extra: dict = field(default_factory=dict)


class Recognizer:
    """Base class: implement recognize(shape) and return a list of Candidate."""
    name = "base"

    def recognize(self, shape, settings=None):
        raise NotImplementedError
