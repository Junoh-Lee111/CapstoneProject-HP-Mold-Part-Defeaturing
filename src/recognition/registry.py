"""Name -> recognizer. The rule-based one is always there; an ML recognizer registers itself from src/recognition/ml."""
from .base import Recognizer

_FACTORIES = {}


def register(name, factory):
    """factory: a Recognizer instance or a callable returning one."""
    _FACTORIES[name] = factory


def get(name):
    factory = _FACTORIES[name]
    return factory if isinstance(factory, Recognizer) else factory()


def available():
    return sorted(_FACTORIES)


def load_builtin():
    from .rule_based import RuleRecognizer
    register("rules", RuleRecognizer)
    try:                                    # optional: the ML recognizer (needs its own libraries)
        from . import ml  # noqa: F401
    except ImportError:
        pass

