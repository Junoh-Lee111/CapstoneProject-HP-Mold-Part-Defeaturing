# STEP Processing Library Comparison

> Purpose: research to select libraries for (1) the CAD kernel layer that reads/writes/manipulates STEP files, and
> (2) the layer that converts shape features into a representation (e.g. a graph) AI can recognize, for the Mold-Part Defeaturing project.
> Researched: 2026-09 (subject to change with newer releases; re-check versions before actual adoption)

## 1. Big Picture

```
STEP file (.step)
   │  ① Read/parse (CAD kernel)
   ▼
B-rep model (Face/Edge/Vertex topology)
   │  ② Graph representation conversion (ML wrapper)
   ▼
Face adjacency graph + UV sampling, etc.
   │  ③ Feature recognition model (GNN, etc.)
   ▼
Label: "this face/edge is a hole/fillet/chamfer/rib/boss"
   │  ④ Removal logic (back to the CAD kernel)
   ▼
Simplified STEP file output
```

Steps ①④ are the **CAD kernel library**, ② is the **ML-connecting wrapper**, and ③ is the **feature recognition model** (which we train/implement ourselves).

## 2. CAD Kernel Library Comparison (handles ①④)

All of these are internally based on **Open CASCADE Technology (OCCT)** — an open-source 3D CAD kernel written in C++. So the real question isn't "which kernel" but "how raw vs. how wrapped do we want our access to OCCT to be."

| Library | Nature | STEP Support | Pros | Cons | Recommended Use |
|---|---|---|---|---|---|
| **pythonocc-core** | Near 1:1 Python binding of almost the entire OCCT C++ API (thousands of classes) | Broad data exchange support: IGES/STEP/STL/PLY/OBJ/GLTF, etc. | Most low-level; direct control down to face/edge/vertex level → the fine-grained access required to implement feature recognition/removal logic | API mirrors the C++ style, so there's a learning curve; documentation is sparse | **Core STEP I/O and feature manipulation layer** |
| **build123d** | Latest independent Python CAD framework, derived from CadQuery. Built on OCP (another Python binding of OCCT) | Export/import of major formats including STEP | Pythonic, clean syntax; well-organized shape manipulation API; can also access OCP's low-level types | Optimized for parametric "modeling" (designing new shapes) → may be heavier than needed for our "analyze/decompose an existing model" use case | Auxiliary use for result verification/visualization if needed |
| **CadQuery** | Predecessor of build123d, specialized in parametric CAD scripting | Export to STEP, STL, AMF, 3MF, etc. | Intuitive API, beginner-friendly | More limited low-level (raw OCP type) access compared to build123d | Lower priority (can be replaced by build123d) |
| **FreeCAD Python API** | Python API built into FreeCAD (an open-source CAD program), also OCCT-based | Good STEP read/write, can run alongside the GUI | Results can be checked visually via the GUI (useful for debugging) | Requires the whole heavyweight application; not suited for server/batch automation | Visual verification of results during the prototyping phase |
| **Gmsh** | Dedicated mesh generation library (can interoperate with OCCT geometry) | Mesh generation after STEP import | Needed for evaluating actual CAE mesh quality (validating our project's "success criteria") | Does not support CAD shape editing itself; mesh generation only | Use in the **evaluation stage** (comparing mesh quality/analysis before and after simplification) |

**Conclusion: our own research recommendation is pythonocc-core** for the core layer, with FreeCAD for visual verification. **This specific binding is not yet confirmed by the mentor** — see §8 for what's actually confirmed (the OCCT-based approach, not a specific library) and the naming discrepancy that still needs to be resolved. This also means **NX is not required** for the project. Reasons for the pythonocc-core recommendation:
- We need direct access to almost all of OCCT's functionality (face/edge traversal, curvature computation, boolean operations, fillet/chamfer removal APIs, etc.) to implement the core logic of "recognize and remove features"
- build123d/CadQuery are optimized for "designing a new model," so pythonocc-core fits our workflow of "analyzing an existing model and removing only part of it" better
- FreeCAD can be used as an aid for result visualization/verification

## 3. ML-Connecting Wrapper (②)

| Library | Description | Notes |
|---|---|---|
| **occwl** | A lightweight wrapper on top of pythonocc, released by Autodesk AI Lab. Supports B-rep → face adjacency graph conversion and UV parameter domain sampling for faces/edges | Used by the official implementations of several CAD deep learning papers, including UV-Net. **Removes the need to hand-write the repetitive B-rep-to-graph conversion logic** → a strong candidate for adoption in our project |

## 4. Feature Recognition Models (③) — Existing Research/Implementations to Reference

Rather than building from scratch, it's recommended to reference/transfer-learn from the following public implementations:

| Name | Approach | Notes |
|---|---|---|
| **UV-Net** (Autodesk) | Processes each face's UV grid with a CNN and the face adjacency graph with a GNN, then combines them | Pairs well with occwl |
| **BRepNet** (Autodesk) | Defines convolution kernels directly on B-rep coedges (directed edges) → learns directly from B-rep without an intermediate representation | Topology-aware; paper and implementation are public |
| **AAGNet** | Uses an Attributed Adjacency Graph (gAAG) that encodes geometry, topology, and extra attributes together for machining feature recognition | Relatively recent; GitHub includes both training code and a data-generation tool → **top candidate baseline for us** |
| **BrepMFR** | Transformer + graph attention-based machining feature recognition with domain adaptation support | Generalizes well across different CAD sources (useful if HP's real data differs from the training data) |

## 5. Public Datasets for Training/Validation

**HP's real CAD data is confidential and will not be shared with the team** (confirmed by HP mentor). Training/validation data will instead come from: (a) simple CAD shapes the team authors itself, and (b) the public datasets below:

| Dataset | Size | Labels | Notes |
|---|---|---|---|
| **MFCAD** | 15,488 models | 16 machining feature types (chamfer, hole, etc.), planar faces only | Relatively simple, good starting point |
| **MFCAD++** | 59,655 models | 24 feature types, includes curved surfaces, 3–10 features per model | More realistic/challenging than MFCAD |
| **Fusion 360 Gallery – Segmentation Dataset** | 35,858 models (STEP format provided) | 8 categories per face (ExtrudeSide/End, CutSide/End, Fillet, Chamfer, RevolveSide/End) | Officially released by Autodesk; includes original STEP files, so it can be used immediately to validate the pythonocc/occwl pipeline |

## 6. Overall Conclusion (tech stack)

```
STEP I/O + geometry manipulation   →  FreeCAD (Python API, headless/standalone) — CONFIRMED 2026-09-18, see §9
                                       cadquery — optional, STEP-generation only
Before/after validation            →  Gmsh (mesh quality) + FreeCAD (visual check)   [CONFIRMED]
B-rep → graph conversion           →  occwl or a FreeCAD-API-based equivalent      [needs re-check, see §7]
Feature recognition model          →  AAGNet or a custom model based on UV-Net (pretrain on MFCAD/MFCAD++/Fusion 360 Gallery + self-authored shapes; no HP data) — team's own choice, no mentor preference   [open, must run on CPU at inference time — see §9]
```

## 7. Open Questions
- [x] ~~Confirm the exact CAD toolchain with the mentor~~ — **RESOLVED 2026-09-18, see §9**
- [ ] Check occwl's compatibility with the confirmed toolchain (occwl is built on pythonocc-core specifically — since the mentor's answer is FreeCAD-python API, occwl may need to be swapped for a hand-written B-rep traversal via FreeCAD's own API, or run pythonocc-core in parallel just for the graph-conversion step)
- [ ] Prototype a loading pipeline using Fusion 360 Gallery STEP data with the confirmed FreeCAD-python API toolchain

## 8. HP Validation (2026-09)

HP mentor Byoungho Yoo reviewed the CAD license constraint (the team has no access to NX, HP's in-house CAD software) and confirmed the project can proceed without it:

- **OCCT** (the open-source CAD kernel underlying all the Python binding candidates) can replace NX for geometry creation and defeaturing — he ran a preliminary test on a simple geometry and it worked. His meeting slide named the specific access path as **"FreeCAD-python API"**.
- **FreeCAD** can be used for visualizing/verifying the resulting geometry — matches what this document had already proposed.
- Caveat: only tested on simple geometry so far; behavior on more complex real parts still needs validation.
- He flagged the same next challenge this document identifies in §4: deciding **which features to select for defeaturing**, which he also expects will need AI-based training to identify automatically.
- HP's real CAD data is confidential and **will not be provided**. Instead, HP suggested the team create simple shapes itself for the defeaturing pipeline (see §5).

**Naming discrepancy — RESOLVED.** The school's AI Lab server guide had described our approach as "OCCT (via cadquery)", differing from the mentor's own "FreeCAD-python API", and our own §2 research had recommended a third option (pythonocc-core). We asked directly; see §9 for the mentor's answer.

## 9. Toolchain & Process Confirmation (2026-09-18 meeting)

Follow-up mentor meeting resolved the remaining open items:

**Toolchain (resolved):**
- **FreeCAD is the preferred final platform** — specifically its Python API, run headless as **standalone batch/automated code**, not as manual scripting inside the FreeCAD GUI app.
- **cadquery may optionally be used, but only for generating STEP files** — not as the main geometry-processing engine.
- This settles the pythonocc-core vs. cadquery vs. FreeCAD-python API question from §8: **FreeCAD Python API wins**; pythonocc-core (our own earlier recommendation) is not the confirmed path.
- Follow-up: occwl is built specifically on pythonocc-core, so it needs to be re-evaluated — either replace it with a hand-written B-rep-to-graph conversion using FreeCAD's own API, or call pythonocc-core in parallel just for that one step (see §7).

**Deployment environment (resolved):**
- Geometry processing (inference/runtime) **must run on a normal office laptop without a GPU**.
- Model **training** may use a GPU-equipped server (e.g., our AI Lab RTX 5090 server).
- This directly constrains the feature recognition model choice: it must be light enough for CPU inference.

**Success criteria (resolved):**
- **Defeaturing accuracy is the top priority.**
- **Analysis accuracy (stress/deformation error) is explicitly NOT measured — out of scope for this project.**

**Decision Logic — staged approach (resolved):**
1. Stage 1: rule-based selection (by size)
2. Stage 2: ML-based selection
3. Stage 3: cases the pipeline fails on are corrected manually and fed back into the training set for Stage 2 (a retraining loop, not a one-time dataset)

**Geometry-healing failure handling (resolved):**
- Failure rate cannot be specified in advance.
- On failure, store the geometry and the ID of the failed face for later use — it gets manually corrected and treated as a special training input (ties into the Stage 3 retraining loop above).

**Self-authored test shape guidance (resolved):**
- Typical mold part: **2-3mm thick**, **~100-200 (mm) in width**.
- Representative shape types to include: (1) slightly curved shapes with a cut-out (press-formed), (2) ribbed parts, (3) parts with features near an edge.

**Feature recognition model (resolved — no mentor preference):**
- The mentor has no preference among UV-Net/BRepNet/AAGNet/BrepMFR — **the team decides on its own**.
- Feature type recognition quality needs to be evaluated (ties into NFR-ACC-01).
- Must be able to run on a CPU laptop (see deployment environment above).

## References
- [Top Open Source CAD APIs and Libraries for Developers in 2026](https://blog.fileformat.com/cad/top-open-source-cad-api-and-libraries-for-developers-in-2026)
- [build123d GitHub](https://github.com/gumyr/build123d)
- [CadQuery Documentation](https://cadquery.readthedocs.io/en/latest/)
- [pythonocc-core GitHub](https://github.com/tpaviot/pythonocc-core)
- [AAGNet GitHub](https://github.com/whjdark/AAGNet)
- [Fusion 360 Gallery Dataset GitHub](https://github.com/AutodeskAILab/Fusion360GalleryDataset)
- [BRepGAT (JCDE)](https://academic.oup.com/jcde/article/10/6/2384/7453688)
- [FilletRec (arXiv)](https://arxiv.org/pdf/2511.05561)
