"""The rule-based recognizer: the rules of src/rules wrapped in the common Candidate form."""
import os
import sys

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
import rules  # noqa: E402,F401    registers the rules in cleancad_core
from .base import Candidate, Recognizer  # noqa: E402


class RuleRecognizer(Recognizer):
    name = "rules"

    def __init__(self, rule_names=None):
        self.rule_names = list(rule_names) if rule_names else core.all_rules()

    def recognize(self, shape, settings=None):
        """One Candidate per connected group of faces a rule selects. The profile (size limits) in force is the
        one in core.PROFILE - set it with core.apply_settings()."""
        out = []
        for name in self.rule_names:
            faces = core.select(shape, [name])
            for group in core.groups(shape, faces):
                out.append(Candidate(feature=name, faces=[core.sig(f) for f in group], confidence=1.0,
                                     source="rules", reason=f"rule '{name}' ({core.CATEGORY.get(name, 'other')})"))
        return out
