# VascuQuest Build Plan

**Status:** Executable implementation plan  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`, `SCIENTIFIC_MODEL.md`, `API_PLUGIN_CONTRACT.md`, `CLI_CONTRACT.md`, `TEST_VALIDATION_CONTRACT.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Convert the frozen design contracts into a practical, file-by-file implementation sequence that can be built, audited, and tested incrementally without premature technology commitments or scientific drift.

---

## 1. Build objective

The implementation goal is a research-grade Python package that:

- opens and identifies PWDB `3275625` without requiring a full dataset download;
- exposes virtual subjects, cohorts, canonical quantities, vascular locations, geometry, and waveforms through one Python API;
- preserves units, evidence class, validity, and provenance in every material scientific result;
- acquires/verifies only required source artifacts;
- supports registered derivations, research operators, discovery methods, and exporters through the frozen plugin protocols;
- exposes the same scientific implementation through the `vascuquest` CLI;
- remains testable without the full 44.3 GB dataset in ordinary development;
- keeps large-path storage/access decisions empirical until the ingestion spike passes.

The plan optimizes for **correct implementation with low rework**, not maximum feature count per commit.

---

## 2. Execution rule: one file at a time

Implementation proceeds **one repository file at a time**.

For each file:

1. implement only the responsibility assigned to that file;
2. inspect the resulting file for contract violations;
3. run the smallest relevant test/check set;
4. correct any failure before creating the next file;
5. commit only after the file is internally coherent with already-created dependencies.

A later file may reveal a defect in an earlier file. In that case the earlier file is amended and re-tested before implementation continues.

No batch is considered complete merely because all planned files exist.

---

## 3. Build gate rule

Each implementation batch has an explicit exit gate.

A batch may advance only when:

- its targeted tests pass;
- no governing contract violation is known;
- no unresolved scientific ambiguity has been hidden behind implementation defaults;
- public semantics created in that batch are internally consistent;
- any remaining uncertainty is explicitly deferred to an already-approved later gate.

The mandatory ingestion spike remains a **hard gate** before the production large-path backend/storage strategy is frozen.

---

## 4. Supported Python baseline

V1 targets:

```text
Python >=3.11,<3.15
```

Supported minor versions are therefore:

```text
3.11
3.12
3.13
3.14
```

Rationale as of 2026-08-24:

- Python 3.11 through 3.14 are active supported releases;
- Python 3.10 is near end of security support and is not needed for the research target;
- Python 3.15 is still pre-release and is not a v1 target;
- current NumPy 2.4 supports Python 3.11-3.14;
- current SciPy 1.17 supports Python 3.11-3.14;
- current h5py 3.15 provides Python 3.14 wheels;
- current Typer and WFDB releases support this Python range.

This is deliberately conservative: the package uses modern typing/runtime capabilities without tying v1 to a pre-release interpreter.

---

## 5. Dependency policy for implementation

### 5.1 Build system

Use one `pyproject.toml` as the authoritative package/build configuration.

Use `setuptools` as the initial build backend because the project does not require a specialized build system.

Do not add Poetry, Hatch, PDM, Conda metadata, or a second dependency authority during initial implementation.

### 5.2 Initial mandatory runtime dependencies

Only dependencies needed by broad v1 behavior should be mandatory.

The initial baseline may include:

```text
numpy >=2.0,<3
Typer >=0.27,<1
platformdirs >=4,<5
```

The lower NumPy bound avoids requiring a specific recent patch/minor when VascuQuest does not use a 2.4-only feature; the supported CI environments use compatible contemporary NumPy builds.

`platformdirs` is justified only for cross-platform user cache/data/state locations.

### 5.3 Source-reader dependencies

The following are expected for the built-in PWDB backend but remain isolated from the scientific domain:

```text
scipy >=1.17,<2      # conventional MATLAB files/numerical utilities where required
h5py >=3.15,<4       # MATLAB v7.3/HDF5 access where validated
wfdb >=4.3,<5        # WFDB source representation where selected
```

Whether all three become unconditional runtime requirements or a documented `pwdb` extra is decided after the small-source adapters and ingestion spike demonstrate the practical user path.

The built-in backend must not be architecturally rewritten merely to avoid a reasonable scientific-reader dependency.

### 5.4 Development dependencies

Keep the developer stack minimal:

```text
pytest
pytest-cov
ruff
mypy
build
```

Additional test/development packages require a demonstrated need.

### 5.5 Versioning rule

Use compatible version ranges rather than pinning one patch release in package metadata.

Exact tested versions are captured by CI/environment provenance when needed.

Do not add a lockfile as the authoritative distribution requirement for a library package.

---

## 6. Initial repository target

The implementation starts from the approved architecture and converges toward this practical structure:

```text
pyproject.toml
LICENSE
README.md

src/vascuquest/
    __init__.py
    __main__.py
    _version.py
    errors.py
    bootstrap.py

    domain/
        __init__.py
        identity.py
        evidence.py
        location.py
        quantity.py
        subject.py
        cohort.py
        result.py

    provenance/
        __init__.py
        model.py
        builder.py
        serialization.py

    ports/
        __init__.py
        backend.py
        methods.py
        exporter.py

    schema/
        __init__.py
        loader.py
        resources/
            pwdb3275625_manifest.json
            canonical_schema.json

    plugins/
        __init__.py
        descriptor.py
        registry.py

    data/
        __init__.py
        paths.py
        state.py
        integrity.py
        sources.py
        acquisition.py
        archive.py

    backends/
        __init__.py
        pwdb3275625/
            __init__.py
            capabilities.py
            csv_reader.py
            geometry_reader.py
            waveform_reader.py
            matlab_reader.py
            path_reader.py
            backend.py

    methods/
        __init__.py
        reconstructions.py

    services/
        __init__.py
        datasets.py
        selection.py
        retrieval.py
        execution.py
        exporting.py
        reproduction.py

    api/
        __init__.py
        session.py

    exporters/
        __init__.py
        json_exporter.py
        csv_exporter.py

    cli/
        __init__.py
        app.py
        commands.py
        rendering.py

tests/
    unit/
    contracts/
    adapters/
    scientific/
    cli/
    integration/
    fixtures/
    full_data/
```

This tree is a build target, not permission to create empty placeholder modules. A file is created only when its batch begins.

`methods/` is the single justified addition to the architecture sketch: it houses built-in scientific components so scientific algorithms do not leak into `services`, `plugins`, or `cli`. It does not become a dumping ground for arbitrary analyses.

---

## 7. Batch 0 — Packaging and import skeleton

### Files, in order

1. `pyproject.toml`
2. `LICENSE`
3. `src/vascuquest/_version.py`
4. `src/vascuquest/errors.py`
5. `src/vascuquest/__init__.py`
6. minimal packaging smoke tests

### Responsibilities

- package metadata;
- Apache-2.0 project licence;
- Python `>=3.11,<3.15` declaration;
- build backend/configuration;
- stable top-level exception root;
- importable package with no dataset/network/CLI side effects.

The console-script entry point and `__main__.py` are deliberately **not** created yet. They belong to Batch 13 when the real CLI exists; creating an executable stub now would add disposable code and rework.

### Gate 0

Must demonstrate:

```text
python -c "import vascuquest"
python -m build
```

A built wheel must install into a clean environment and remain importable.

No CLI, scientific model, or data reader is implemented in this batch.

---

## 8. Batch 1 — Core scientific value model

### Files, in order

1. `domain/identity.py`
2. `domain/evidence.py`
3. `domain/location.py`
4. `domain/quantity.py`
5. `domain/subject.py`
6. `domain/cohort.py`
7. `domain/result.py`
8. `domain/__init__.py`
9. corresponding unit tests file-by-file

### Responsibilities

Implement only the semantics frozen in `SCIENTIFIC_MODEL.md`:

- dataset/subject identity;
- five evidence classes;
- distinct site/segment/path/path-position location identities;
- quantity definitions;
- lightweight virtual-subject references;
- deterministic cohorts;
- scientific results/waveforms;
- explicit missing/validity semantics where represented.

### Forbidden in Batch 1

- Zenodo URLs;
- MAT/WFDB/HDF5 knowledge;
- CLI types;
- plugin loading;
- research equations;
- dataframe assumptions.

### Gate 1

Pure tests pass with no filesystem/network access.

---

## 9. Batch 2 — Canonical manifest and scientific schema

### Files, in order

1. `schema/resources/pwdb3275625_manifest.json`
2. `schema/resources/canonical_schema.json`
3. `schema/loader.py`
4. `schema/__init__.py`
5. manifest/schema contract tests

### Responsibilities

- encode the exact 16-artifact canonical manifest;
- encode only scientifically verified v1 canonical definitions/mappings;
- preserve upstream aliases/unit labels and defect annotations;
- validate uniqueness, dimensions, categories, aliases, and schema version;
- expose schema metadata without data acquisition.

### Critical restraint

The first schema does **not** need to contain every possible future PWDB quantity before code can proceed.

It must contain every quantity needed by implemented v1 capabilities, and expansion occurs only from verified source semantics.

### Gate 2

Manifest exactness and schema mechanical-validation tests pass.

---

## 10. Batch 3 — Provenance and result serialization

### Files, in order

1. `provenance/model.py`
2. `provenance/builder.py`
3. `provenance/serialization.py`
4. `provenance/__init__.py`
5. provenance/result round-trip tests

### Responsibilities

- serializable provenance nodes/records;
- source artifact/checksum references;
- method/plugin/version/parameter facts;
- evidence and validity retention;
- acyclic completed lineage;
- deterministic semantic serialization where promised.

Large arrays are referenced or represented through result serialization, not duplicated in provenance.

### Gate 3

Provenance round trips preserve scientific identity and cannot silently discard evidence/method/source identity.

---

## 11. Batch 4 — Public ports and plugin registry

### Files, in order

1. `ports/backend.py`
2. `ports/methods.py`
3. `ports/exporter.py`
4. `ports/__init__.py`
5. `plugins/descriptor.py`
6. `plugins/registry.py`
7. `plugins/__init__.py`
8. protocol/registry conformance tests

### Responsibilities

Implement exactly the five approved plugin categories:

- dataset backend;
- derivation;
- research operator;
- discovery method;
- result exporter.

External entry points resolve to zero-argument factories and use integer protocol major `1`.

### Gate 4

Tests demonstrate:

- compatible registration;
- duplicate-ID rejection;
- incompatible-major rejection;
- broken optional-plugin isolation;
- no arbitrary file-path plugin loading.

---

## 12. Batch 5 — Local data state and integrity

### Files, in order

1. `data/paths.py`
2. `data/state.py`
3. `data/integrity.py`
4. `data/sources.py`
5. `data/acquisition.py`
6. `data/archive.py`
7. `data/__init__.py`
8. data-layer tests using local/fake HTTP and generated archives

### Responsibilities

- cross-platform cache/data/state paths;
- source registration;
- canonical manifest resolution;
- checksum verification;
- streamed acquisition;
- temporary/incomplete state;
- atomic verified promotion;
- offline enforcement;
- mirror/source precedence;
- safe ZIP extraction;
- basic local-process concurrency safety.

### Deferred

Reliable resume/range behavior for real Zenodo large files remains unclaimed until Tier 3 evidence exists.

### Gate 5

All failure paths in the data contract pass using controlled fixtures without live Zenodo dependence.

---

## 13. Batch 6 — PWDB lightweight backend

### Files, in order

1. `backends/__init__.py`
2. `backends/pwdb3275625/__init__.py`
3. `backends/pwdb3275625/capabilities.py`
4. `backends/pwdb3275625/csv_reader.py`
5. `backends/pwdb3275625/backend.py` — metadata/CSV capabilities only at first
6. canonical excerpt/adapter tests

### Responsibilities

Make useful research possible before waveform/path implementation:

- open canonical dataset identity;
- list source capabilities;
- enumerate subjects;
- expose validated model/configuration/haemodynamic/index/timing quantities available from CSV;
- construct lightweight cohorts;
- preserve source/canonical fields, units, evidence, and provenance.

### Gate 6

A researcher can open PWDB, inspect subject metadata and retrieve canonical scalar quantities using only required small artifacts.

No path or waveform promise is made by code that has not yet been implemented.

---

## 14. Batch 7 — Geometry and common-site waveform adapters

### Files, in order

1. `backends/pwdb3275625/geometry_reader.py`
2. `backends/pwdb3275625/waveform_reader.py`
3. `backends/pwdb3275625/matlab_reader.py` for non-path MAT needs where validated
4. extend `backend.py`
5. adapter/canonical-fixture tests
6. cross-representation tests where retained excerpts permit them

### Reader-selection rule

Do not build three equally featured waveform readers merely because three upstream representations exist.

Select one production common-site representation after measured readability/fidelity testing; retain other representations only where they add validation or a meaningful fallback.

If WFDB is reliable and light, use the maintained WFDB package rather than reimplementing its binary format.

### Gate 7

At least one validated common-site waveform path and geometry path are available through canonical `Waveform`/geometry results with source provenance.

---

## 15. Batch 8 — Mandatory empirical ingestion spike

This batch is **evidence gathering plus the smallest necessary spike code**, not production-path implementation by guesswork.

### Required real-source checks

Use verified artifacts from record `3275625` to inspect at least:

- one metadata CSV;
- one common-site WFDB record;
- representative geometry;
- `pwdb_data.mat`;
- one bounded subject/path/signal read from a large path MAT file.

### Required decisions

For each source class choose:

```text
DIRECT
INDEXED
CONVERTED
```

Record:

- actual format/hierarchy;
- indexing semantics;
- memory behavior;
- first/repeated access behavior;
- subject/path alignment;
- reader dependency;
- range/resume behavior if claimed;
- cross-representation differences and justified tolerances.

### Hard stop

`path_reader.py` cannot be declared production-ready until this gate passes.

If the environment available during implementation cannot access a required multi-gigabyte canonical artifact, code may progress on all non-path components, but the package must remain explicitly **not fully validated for path-resolved v1 support** until the spike is executed elsewhere against the real artifact.

This is a release-validation limitation, not permission to fake the result.

---

## 16. Batch 9 — Production path reader

### Files

1. `backends/pwdb3275625/path_reader.py`
2. amend `backend.py`
3. path-reader unit/fixture tests
4. real-source Tier 3 regression tests/markers

### Implementation rule

Implement only the strategy selected by Batch 8.

Do not simultaneously maintain direct, indexed, and converted production implementations unless empirical results demonstrate that more than one is necessary.

### Gate 9

A bounded path request returns a canonical result without scientifically incorrect remapping and without whole-file materialization when the selected source strategy supports slicing.

---

## 17. Batch 10 — Application services and Python facade

### Files, in order

1. `services/datasets.py`
2. `services/selection.py`
3. `services/retrieval.py`
4. `services/execution.py`
5. `services/exporting.py`
6. `services/reproduction.py`
7. `services/__init__.py`
8. `api/session.py`
9. `api/__init__.py`
10. `bootstrap.py`
11. update top-level `__init__.py`
12. API integration tests

### Responsibilities

- compose the backend/data/schema/plugin/provenance layers;
- expose `open_dataset()` and `DatasetSession`;
- resolve canonical inputs for methods;
- keep scientific retrieval separate from presentation;
- enforce evidence/unit/admissibility/provenance contracts;
- reproduce only compatible workflows.

### Gate 10

Documented Python examples for open/status/subjects/select/get/waveform/derive/model/discover/export/reproduce route through one coherent facade.

Methods not installed/implemented fail clearly rather than being simulated.

---

## 18. Batch 11 — Built-in scientific components

### Initial files

1. `methods/reconstructions.py`
2. `methods/__init__.py`
3. method-specific tests

The first built-in reconstruction may implement the already-audited flow-rate reconstruction only after source units/contexts are validated.

No other equation enters merely to make the package appear scientifically rich.

### Discovery-method rule

V1.0 must include at least one genuinely useful built-in discovery method **only after** its definition, evidence semantics, missing-data behavior, outputs, and validation oracle are scientifically explicit.

The algorithm is not guessed in this build plan.

A candidate discovery method receives its own implementation file and method-specific tests when selected. Protocol infrastructure may be tested with fixture methods before that point.

### Research-operator rule

Project-specific Womersley, anisotropy, fractional, susceptibility, CGL, or other paper-derived formulations are not rushed into core v1 merely to populate the operator registry.

They may be implemented later as separately validated built-in or external operators while preserving the source mathematics exactly.

### Gate 11

Every shipped built-in scientific component has an authoritative definition, dimensions/units validation, evidence classification, provenance, and independent/reference tests appropriate to the method.

---

## 19. Batch 12 — Exporters

### Files, in order

1. `exporters/json_exporter.py`
2. `exporters/csv_exporter.py`
3. `exporters/__init__.py`
4. exporter tests

### Rules

- JSON is the canonical portable metadata/result representation for bounded structured outputs;
- CSV is only used for naturally tabular outputs;
- sidecar metadata is produced when CSV cannot carry required scientific context;
- exporters do not perform scientific calculations.

### Gate 12

Export round trips preserve required scientific identity, evidence, units, coordinates, and provenance metadata.

---

## 20. Batch 13 — CLI

### Files/changes, in order

1. `cli/rendering.py`
2. `cli/commands.py`
3. `cli/app.py`
4. `cli/__init__.py`
5. `src/vascuquest/__main__.py`
6. amend `pyproject.toml` to add the `vascuquest` console-script entry point
7. CLI tests

### Responsibilities

Implement exactly the command tree frozen in `CLI_CONTRACT.md`.

The CLI performs only:

- argument parsing;
- request construction;
- service/API dispatch;
- progress/diagnostic rendering;
- stdout/stderr formatting;
- exit-code mapping.

### Gate 13

Must demonstrate both executable forms:

```text
python -m vascuquest --help
vascuquest --help
```

and establish that:

- JSON/JSONL/CSV stdout is never polluted by diagnostics;
- noninteractive confirmation behavior is deterministic;
- large-download safeguards work;
- exit codes match contract;
- Python/CLI parity tests pass;
- no CLI-only scientific calculation exists.

---

## 21. Batch 14 — CI, package checks, and public README

### Files/changes, in order

1. CI workflow file(s), kept minimal
2. update `README.md`
3. finalize required package metadata/classifiers/entry points in `pyproject.toml`
4. final install/build smoke tests

### CI matrix

Use:

- Linux: Python 3.11, 3.12, 3.13, 3.14;
- Windows: Python 3.11 and 3.14;
- macOS: Python 3.11 and 3.14.

Do not multiply every optional/full-data test across every OS/Python combination.

### README scope

Only after the implementation exists, document:

- what VascuQuest is;
- installation;
- canonical dataset acquisition/registration;
- minimal Python example;
- minimal CLI example;
- evidence/provenance model;
- plugin model;
- validation status/limitations;
- citations/licences.

README claims must reflect passing implementation, not planned functionality.

### Gate 14

The wheel/sdist build, clean-environment installation, import, CLI smoke tests, and fast CI pass on the declared matrix.

---

## 22. Batch 15 — Release validation

Before claiming a fully validated PWDB v1 release:

1. run Tier 3 ingestion validation for the selected real-source strategies;
2. run Tier 4 against the claimed full canonical data scope;
3. record exact code revision, package version, schema version, source checksums, platform/library context, and validation results;
4. resolve every release-critical failure rather than marking it xfail;
5. confirm Apache-2.0 code licence boundary and upstream dataset/third-party attribution.

A code-complete package may exist before full-source Tier 4 completes, but it must not be presented as fully validated against all 44.3 GB until that validation actually passes.

---

## 23. Vertical-slice order for session efficiency

Although the batches define dependency order, implementation should produce useful vertical slices early.

The preferred progression is:

```text
install/import
    -> dataset identity + manifest
    -> subjects + CSV quantities
    -> cohorts
    -> provenance
    -> geometry/common waveforms
    -> plugins/method execution
    -> path data after spike
    -> exporters
    -> full CLI surface
    -> release validation
```

This ensures that failures are discovered against working end-to-end paths rather than after constructing a large unused framework.

---

## 24. Definition of code-complete v1

The implementation is code-complete only when all of the following exist and pass their applicable non-full-data tests:

- installable package;
- public Python facade;
- canonical manifest/schema;
- evidence/validity/provenance model;
- local registration/acquisition/integrity layer;
- PWDB subject/scalar metadata backend;
- geometry access;
- validated common-site waveform access;
- path-reader implementation selected by spike evidence;
- five plugin protocols/registry;
- at least the validated built-in scientific component(s) actually claimed by v1;
- JSON/CSV exporters;
- frozen CLI command tree;
- API/CLI parity;
- fast CI/platform checks;
- package build/install tests.

No TODO placeholder counts as an implemented capability.

---

## 25. Definition of scientifically validated v1

Code-complete is not the same as scientifically validated.

The release is fully validated for PWDB `3275625` only when:

- canonical artifact identity/integrity checks pass;
- schema/source mappings pass;
- subject alignment is validated;
- waveform/geometry/path mappings pass their real-source tests;
- cross-representation checks pass justified tolerances;
- every shipped scientific method passes method-specific validation;
- provenance/evidence tests pass;
- Tier 3 and applicable Tier 4 validation pass on the exact release candidate.

---

## 26. What must not be built during initial implementation

Unless a failing acceptance requirement proves one is necessary, do not add:

- database server;
- web server/UI;
- workflow engine;
- cloud SDK requirement;
- graph database;
- dependency-injection framework;
- custom query language;
- plugin marketplace;
- arbitrary Python plugin execution;
- GPU/HPC runtime;
- distributed compute framework;
- plotting subsystem;
- universal storage conversion;
- second canonical PWDB release;
- clinical-data subsystem;
- project-paper equations inside the source backend, CLI, or scientific ontology.

---

## 27. Anti-overengineering rule

Before creating a new abstraction, class, module, dependency, cache representation, or plugin category, ask:

> Does an already-frozen contract require this now, or does a failing measured use case demonstrate the need?

If neither is true, do not add it.

Repeated code alone does not justify an abstraction until the shared responsibility is scientifically/architecturally the same.

---

## 28. Anti-oversimplification rule

Do not remove a distinction merely because two current values look similar.

The implementation must preserve, at minimum:

- dataset identity versus local path;
- source versus canonical semantics;
- source/reconstructed/derived/inferred/modelled evidence;
- evidence versus validity;
- site versus segment versus path position;
- missing versus unavailable versus invalid;
- canonical source versus derived cache;
- method protocol compatibility versus scientific validation;
- Python scientific result versus CLI rendering.

---

## 29. Mathematical-fidelity rule

No implementation batch is allowed to invent, simplify, rearrange, approximate, or generalize a scientific equation simply to make coding easier.

For any mathematical method that enters VascuQuest:

1. identify the authoritative definition;
2. preserve its symbols/semantics internally even if public canonical names differ;
3. establish input/output units and applicable domain;
4. implement the method in the scientific component that owns it;
5. create independent/reference tests;
6. document any numerical approximation explicitly;
7. assign evidence class according to the operation rather than convenience.

If the authoritative material is insufficient to implement a method unambiguously, implementation stops for that method rather than guessing.

---

## 30. Build audit after every batch

At each batch boundary, audit five questions:

1. **Contract fidelity:** Does the implementation still satisfy all governing Markdown contracts?
2. **Simplicity:** Did we add machinery not required by a current acceptance scenario?
3. **Completeness:** Did we omit a required semantic distinction or failure path?
4. **Feasibility:** Does the implementation work with realistic local resources and supported platforms?
5. **Scientific fidelity:** Did any parser/service/API choice alter scientific meaning, units, evidence, provenance, or mathematics?

A "no" answer blocks progression.

---

## 31. Commit discipline

Use small commits aligned with completed responsibilities.

Recommended commit scale:

- one coherent implementation file plus its direct tests; or
- one tightly coupled resource/test update when splitting would leave the repository invalid.

Do not combine unrelated architectural layers in one commit merely to reduce commit count.

Do not rewrite the governing contracts during implementation unless a genuine contradiction is discovered. Such a change requires an explicit reviewed contract amendment before code proceeds under the new rule.

---

## 32. Session completion strategy

To maximize the amount that can be completed correctly in one working session:

1. prioritize deterministic local code and small-source functionality first;
2. run targeted tests immediately after each file rather than accumulating failures;
3. avoid optional feature work before the core vertical slice passes;
4. perform real-data acquisition only when the next implementation decision actually depends on it;
5. do not download the complete 44.3 GB merely for development convenience;
6. separate code completion from full-dataset release validation when data-transfer/runtime constraints make Tier 4 impractical in the same environment.

The package must never claim a validation state that was not actually executed.

---

## 33. Final pre-build gate

Implementation may begin only if this build plan passes the following audit.

### Traceability

- Every batch maps to responsibilities already frozen in the governing contracts.
- No new scientific ontology or equation has been introduced.
- The ingestion spike remains a hard gate for large-path strategy.

### Simplicity

- The project uses one Python package, one build configuration, one CLI framework, one plugin registry, and one test runner.
- No speculative infrastructure is required.
- Files are created only when their responsibility is implemented.

### Completeness

- Packaging, domain, schema, provenance, plugins, data engineering, PWDB backend, API, methods, exporters, CLI, tests, CI, and release validation all have an implementation stage.
- Failure handling and provenance are built alongside features rather than added at the end.

### Feasibility

- Python 3.11-3.14 has a compatible contemporary scientific stack.
- Ordinary development does not require the full canonical dataset.
- Large-file decisions depend on measured source behavior.
- The plan can produce useful end-to-end functionality before path-data work.

### Scientific fidelity

- Source semantics remain separate from mathematical research operators.
- No unverified equation or tolerance is scheduled for implementation.
- Built-in scientific methods require authoritative definitions and independent validation.

If every answer is yes, implementation begins with **Batch 0, file 1: `pyproject.toml`**.

---

## 34. Planning closure

With this file accepted, the pre-implementation Markdown contract set is complete:

```text
DESIGN_CONTRACT.md
ARCHITECTURE.md
DATA_ENGINEERING.md
SCIENTIFIC_MODEL.md
API_PLUGIN_CONTRACT.md
CLI_CONTRACT.md
TEST_VALIDATION_CONTRACT.md
BUILD_PLAN.md
```

No additional planning Markdown file is required before coding.

The next action after approval is not more architecture documentation. It is implementation of `pyproject.toml`, followed by its audit and tests before the next repository file is created.