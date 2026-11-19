"""The removal rules, grouped by what they recognise. Importing this package registers all of them in
cleancad_core (see cleancad_core.rules_by_category()).

  holes         ref_holes
  edges         ref_fillets, chamfer_edge
  protrusions   ref_protrusions, rib, boss
  markings      logo
  pockets       flatten (shallow recesses filled flat; holes in the floor stay)
  bumps         bump (small raised dots cut away)
"""
from . import holes, edges, protrusions, markings, pockets, bumps  # noqa: F401
