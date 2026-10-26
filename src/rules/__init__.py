"""The removal rules, grouped by what they recognise. Importing this package registers all of them in
cleancad_core (see cleancad_core.rules_by_category()).

  holes         ref_holes
  edges         ref_fillets, chamfer_edge
  protrusions   ref_protrusions, rib, boss
  markings      logo
"""
from . import holes, edges, protrusions, markings  # noqa: F401
