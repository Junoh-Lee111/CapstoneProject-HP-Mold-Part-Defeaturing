"""RECOGNITION: the common contract for everything that finds "this group of faces is a fillet / hole / rib ...".

Two kinds of recognizer follow it:
  rules   the rule-based recognizer (the rules in src/rules, wrapped)                      -> recognition.rule_based
  ml      the ML recognizer (graph neural network on the face-adjacency graph)             -> src/recognition/ml/

Both return a list of Candidate (feature type, face signatures, confidence, source, reason). What is removed is
decided afterwards from the candidates and the settings (src/settings); the engine (src/engine) does the removing.
To make a recognizer available to the engine and the screen as one more rule, register it once:

    from recognition import register_as_rule
    register_as_rule("ml", MyRecognizer())

so the ML code never has to touch the engine, the rules or the screen. See ml/README.md.
"""
from .base import Candidate, Recognizer  # noqa: F401
from .registry import register, get, available  # noqa: F401
from .bridge import register_as_rule  # noqa: F401

from .registry import load_builtin  # noqa: E402
load_builtin()      # last: the ML folder may import the names above
