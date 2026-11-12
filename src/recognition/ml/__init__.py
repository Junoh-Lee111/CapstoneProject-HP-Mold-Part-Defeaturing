"""ML recognizer (graph neural network). Put the model code in this folder only.

Nothing is imported here yet, so the prototype runs without any ML library. When the model is ready:

    # src/recognition/ml/__init__.py
    from .gnn_recognizer import GnnRecognizer          # your class, a subclass of recognition.Recognizer
    from .. import register, register_as_rule
    register("ml", GnnRecognizer)
    register_as_rule("ml", GnnRecognizer())            # now "ml" is a rule name the engine and the screen accept

See README.md in this folder for what recognize() has to return.
"""
