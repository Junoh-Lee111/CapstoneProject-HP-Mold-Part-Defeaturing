# input/ (planned)

Reserved for the input side of the pipeline (architecture C1-C3):

- STEP ingestion and B-rep face extraction beyond `Part.read()`
- conversion of the B-rep to a face-adjacency graph (nodes = faces, edges = shared edges, with surface type /
  area / normal attributes) as the input of the pretrained recognition model
- a mapping between the model's face numbering and FreeCAD's faces (the biggest open risk)

Nothing is implemented here yet; the current prototype reads STEP files directly in the scripts.
