# ML recognizer - where the model goes

Everything that belongs to the ML recognition lives in **this folder** (model code, weights loader, graph
conversion, its own requirements). The rest of the prototype does not change when it arrives.

## The contract

```python
from recognition import Recognizer, Candidate

class GnnRecognizer(Recognizer):
    name = "ml"
    def recognize(self, shape, settings=None):
        # shape: FreeCAD Part.Shape (the original B-rep, never rebuilt from the model output)
        # return [Candidate(feature="fillet", faces=[sig, ...], confidence=0.93, source="ml", reason="...")]
```

* `faces` are **face signatures**: `cleancad_core.sig(face)`. The graph nodes must be mapped back to the faces of
  `shape.Faces`, so keep a node-index to face table when you build the graph.
* `confidence` is 0..1. The settings (`min_confidence`) decide which candidates are used.
* The model output is only a recognition: which faces, which feature type. The engine removes them from the
  original B-rep; whether a feature is removed (size limits, keep fasteners) stays a decision of the rules/settings.
* The engine selects again after every removal, so `recognize()` is called many times: cache the model.

## Register it

`recognition.register("ml", GnnRecognizer)` and `recognition.register_as_rule("ml", GnnRecognizer())`, in
`ml/__init__.py`. Then `ml` can be put in the rule list of the demo and of `core.process()`.

## Keep out of other folders

Do not edit `src/engine/`, `src/rules/` or `src/demo/` for the model. If the contract is not enough, change it
here in `recognition/base.py` together with the lead.
