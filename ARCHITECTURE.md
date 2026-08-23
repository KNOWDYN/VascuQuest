# VascuQuest Architecture

**Status:** Architecture contract for implementation  
**Governing document:** `DESIGN_CONTRACT.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Scope of this document:** Define the software structure, dependency rules, runtime responsibilities, extension seams, and architectural acceptance criteria for VascuQuest.  

---

## 1. Architectural objective

VascuQuest is a **research explorer and discovery engine for virtual vascular populations**. The architecture must make PWDB data scientifically usable without making the rest of the system depend on PWDB file names, MATLAB structures, Zenodo URLs, or one storage technology.

The architecture therefore has four goals:

1. keep scientific meaning independent from storage and user interface;
2. expose the same scientific capabilities through Python and the CLI;
3. make provenance and evidence classification intrinsic to every scientific result;
4. permit future datasets, derivations, operators, and discovery methods to be added without modifying unrelated core code.

The architecture must stay small enough to implement and reason about. It must not introduce distributed systems, service meshes, databases, workflow engines, dependency-injection frameworks, or mandatory cloud components unless later evidence demonstrates a real need.

---

## 2. Governing constraints

This architecture inherits the following binding rules from `DESIGN_CONTRACT.md`.

- VascuQuest v1 supports Zenodo record `3275625` as the sole canonical source dataset.
- Source artifacts are immutable and are not re-hosted by VascuQuest.
- Data acquisition is selective, verified, cached locally, and compatible with pre-existing local copies and institutional mirrors.
- Every scientific quantity is classified as `SOURCE`, `RECONSTRUCTED`, `DERIVED`, `INFERRED`, or `MODELLED`.
- VascuQuest maintains a separately versioned canonical scientific schema.
- The core licence is Apache-2.0 and incompatible source implementations do not enter the permissive core.
- Production storage and chunking choices remain provisional until the empirical ingestion spike is complete.
- The Python API and CLI must use the same scientific implementation path.
- Specialized research theories and advanced execution stacks belong outside the irreducible core unless they later prove universal.

If this document conflicts with `DESIGN_CONTRACT.md`, the design contract wins.

---

## 3. Architectural style

VascuQuest uses a **layered ports-and-adapters architecture** implemented with ordinary Python modules, typed interfaces, and an explicit composition root.

The term is used narrowly. It means:

- the scientific domain defines meanings and invariants;
- application services coordinate scientific use cases;
- ports define contracts for capabilities supplied by backends or extensions;
- adapters implement those contracts for PWDB, Zenodo/local files, the CLI, and third-party plugins;
- one composition root wires concrete implementations together at runtime.

VascuQuest will **not** use a dependency-injection framework. Constructor/function injection and explicit object creation are sufficient.

### Dependency direction

```text
                 User interfaces
              Python API      CLI
                   \          /
                    \        /
                 Application layer
                        |
                        v
                 Scientific domain
                        ^
                        |
                  Public ports
                        ^
                        |
       +----------------+----------------+
       |                |                |
  PWDB backend      Plugin adapters   I/O adapters
  acquisition       third-party       local/remote
  schema maps       extensions        persistence
```

The important rule is not the drawing; it is the dependency direction:

> **Scientific domain code must not import concrete data backends, Zenodo clients, CLI frameworks, plotting libraries, or plugin implementations.**

Concrete adapters depend on core contracts, not the reverse.

---

## 4. Layer responsibilities

### 4.1 Domain layer

The domain layer holds scientific meaning and storage-independent objects.

It is responsible for concepts such as:

- dataset identity;
- virtual subject identity;
- physiological plausibility state;
- arterial segment, topology, geometry, site, and path;
- waveform and sampling metadata;
- scientific quantity and physical unit metadata;
- cohort definition;
- evidence class;
- provenance references;
- derivation request/result semantics;
- research-operator request/result semantics;
- discovery result semantics.

The domain layer may use NumPy-compatible array concepts where necessary, but it must not require a particular persistent storage representation.

The domain layer must not know that PWDB data originate in CSV, WFDB, MAT, HDF5, ZIP archives, or Zenodo.

### 4.2 Ports layer

Ports are stable public contracts implemented by backends and extensions.

The initial architecture requires the following port categories:

- `DatasetBackend` — exposes a validated virtual-population dataset through canonical domain concepts;
- `ArtifactSource` — locates/acquires/verifies immutable source artifacts;
- `SchemaProvider` — maps source fields into the canonical scientific schema;
- `Derivation` — deterministically computes a scientific quantity from declared inputs;
- `ResearchOperator` — applies an explicit scientific model or algorithm with declared assumptions and admissibility information;
- `DiscoveryMethod` — performs an auditable exploratory or inferential search on a defined cohort/input space;
- `ResultExporter` — serializes results without changing their scientific meaning or provenance.

These names describe responsibilities, not final class signatures. Exact Python protocols are frozen later in `API_PLUGIN_CONTRACT.md`.

### 4.3 Application layer

The application layer coordinates use cases. It does not redefine scientific equations or parse source formats.

Its responsibilities include:

- opening a dataset through a backend;
- selecting subjects/cohorts;
- requesting quantities and waveforms;
- resolving prerequisites for derivations/operators;
- running discovery methods;
- collecting provenance;
- validating compatibility between requested inputs and available data;
- exporting/reproducing results;
- translating predictable failures into stable application errors.

Examples of application services may include concepts such as dataset cataloguing, querying, deriving, modelling, discovering, comparing, and reproducing. Exact command names are deferred to `CLI_CONTRACT.md`.

### 4.4 Infrastructure/adapters layer

Infrastructure implements concrete external concerns.

For v1 this includes, at minimum:

- Zenodo `3275625` manifest and acquisition adapter;
- local registered-source adapter;
- institutional mirror support where configured;
- checksum verification;
- PWDB source readers;
- local cache/research-store implementation;
- plugin discovery through standard Python packaging entry points;
- concrete exporters selected for v1.

Specific storage technologies for large path data remain **provisional until the ingestion spike**. The architecture may hide them behind ports but must not prematurely require a permanent Zarr/Parquet/DuckDB/xarray solution.

### 4.5 Interface layer

The interface layer contains:

- the public Python facade;
- the CLI;
- optional presentation helpers.

The interface layer may format results but must not contain unique scientific algorithms.

The CLI must call application services or the public facade rather than independently accessing PWDB files.

---

## 5. Proposed package topology

The following top-level package structure is approved as the implementation starting point:

```text
src/vascuquest/
    __init__.py
    api/                 # stable user-facing Python facade
    domain/              # scientific meanings and immutable/value objects
    ports/               # backend/derivation/operator/discovery/export contracts
    services/            # application use cases and orchestration
    backends/            # concrete dataset backends
        pwdb3275625/      # canonical v1 PWDB backend
    data/                 # acquisition, manifests, cache/source registration
    schema/               # canonical schema loading/validation
    provenance/           # provenance construction/serialization
    plugins/              # entry-point discovery and compatibility checks
    exporters/            # built-in result serializers
    cli/                  # command-line adapter only
    errors.py             # stable public error hierarchy
    _version.py           # package version access
```

This is a **module-boundary contract**, not a requirement to create empty files for every hypothetical future feature.

Rules:

1. No `utils.py` dumping ground is permitted. Shared code must belong to a named responsibility.
2. `backends/pwdb3275625` may know the historical source layout; `domain`, `ports`, and generic `services` may not.
3. `cli` may import the public API/application layer, but scientific modules may not import `cli`.
4. `plugins` discovers extensions; it does not implement their science.
5. `schema` stores/loads canonical semantic definitions; source-specific field mappings may live with the relevant backend when that keeps coupling explicit.
6. New top-level packages require a clear architectural responsibility rather than convenience alone.

---

## 6. Core runtime model

### 6.1 Dataset session

A user-visible dataset session represents an opened, validated view of a specific dataset identity and its available local/remote artifacts.

Conceptually it provides access to:

- dataset metadata;
- available capabilities;
- subjects/cohorts;
- scientific quantities;
- sites/segments/paths;
- waveforms;
- provenance context.

It must not imply that the entire dataset is loaded in memory.

Opening a dataset should establish metadata and availability, not trigger a 44+ GB download.

### 6.2 Capability resolution

Scientific operations declare the capabilities they require. The application layer resolves those requirements to source artifacts or derived prerequisites.

Conceptually:

```text
research request
    -> required canonical quantities/capabilities
    -> available directly?
         yes -> obtain through backend
         no  -> derivable?
                  yes -> resolve prerequisites and derive
                  no  -> fail with an explicit capability error
```

Capability resolution must not silently substitute a scientifically different quantity because it happens to have a similar name.

### 6.3 Results

Scientific operations return structured results rather than unlabelled arrays whenever context would otherwise be lost.

A result must be able to expose, where applicable:

- values/data;
- dimensions/coordinates;
- canonical quantity identity;
- physical unit metadata;
- subject/cohort/site/path context;
- evidence class;
- provenance;
- method/operator identity;
- warnings or admissibility information.

Simple scalar access may have lightweight convenience forms, but the structured result remains the authoritative representation for reproducible workflows.

### 6.4 Immutability boundary

Canonical source artifacts are immutable.

Domain objects should behave as immutable value objects where practical. Large numerical arrays do not need defensive copies on every operation; instead, the API must document ownership/read-only expectations and avoid in-place mutation of source-backed data.

Derived caches and exported products are separate artifacts and must never masquerade as upstream source files.

---

## 7. Scientific integrity architecture

### 7.1 Evidence class is mandatory state

`SOURCE`, `RECONSTRUCTED`, `DERIVED`, `INFERRED`, and `MODELLED` are part of the type/metadata model, not descriptive strings added at report time.

Any operation that changes the scientific status of a quantity must assign the correct resulting evidence class.

No interface may suppress this information when the distinction is scientifically material.

### 7.2 Units and dimensions

Canonical units and dimensions are governed by the versioned scientific schema.

The architecture must support:

- source unit metadata;
- canonical unit metadata;
- explicit conversion where supported;
- dimensional validation of derivations/operators;
- traceability of known upstream metadata defects.

This document intentionally defines **no new haemodynamic equations**. Mathematical definitions will be introduced only in scientific modules where they can be tied to authoritative sources, unit tests, and validation evidence.

### 7.3 Provenance graph

Provenance is represented as a directed record of how a result was produced.

At minimum, provenance must be able to link:

```text
source dataset/artifacts
        -> canonical source quantities
        -> transformations/derivations
        -> operators/discovery methods
        -> result
```

The implementation may serialize this graph compactly; it does not need a graph database.

Provenance construction is a core service. Individual CLI commands must not invent ad-hoc provenance formats.

### 7.4 Warnings and validity

Research operators and discovery methods may declare assumptions, validated/admissible domains, and warnings.

VascuQuest must distinguish:

- missing data/capability;
- scientifically inadmissible inputs;
- method warnings;
- numerical failure;
- successful result with limited validation scope.

A model result outside a declared validated domain must not be silently presented as equivalent to an in-domain result.

---

## 8. Dataset backend architecture

### 8.1 Backend responsibility

A dataset backend translates a concrete dataset into VascuQuest canonical concepts.

The PWDB `3275625` backend is responsible for:

- understanding source artifact roles;
- subject identity/alignment;
- source-specific field names and structures;
- exposing available sites/signals/paths/geometry;
- applying the canonical schema mapping;
- requesting required artifacts from the acquisition layer;
- reading data selectively where the source format permits;
- returning canonical domain results with `SOURCE` provenance.

The backend must not implement unrelated research theories.

### 8.2 Backend capability declaration

Each backend must advertise what it can provide without forcing users to discover availability by trial and error.

Capabilities should be expressed canonically, for example in terms of subject metadata, waveform signals, geometry, path-resolved signals, or named scientific quantities—not in terms of historical archive filenames.

### 8.3 No universal-storage assumption

Different source representations may require different access strategies.

Therefore the architecture permits a backend to combine readers internally while presenting one canonical interface externally.

The ingestion spike determines whether v1 should read some artifacts directly, build local indexes, create optimized derivative stores, or combine these strategies.

No permanent conversion step is assumed by this architecture.

---

## 9. Extension architecture

### 9.1 Standard Python entry points

Third-party extensions will be discovered using Python package metadata entry points through `importlib.metadata`.

This choice is deliberately conservative:

- it is part of standard Python;
- extensions remain normal installable packages;
- no bespoke plugin directory or arbitrary file execution is required;
- environments can audit installed distributions normally.

Exact entry-point group names and protocol signatures are defined later in `API_PLUGIN_CONTRACT.md`.

### 9.2 Extension categories

Initial extension categories are:

- dataset backends;
- derivations;
- research operators;
- discovery methods;
- result exporters.

Visualization and alternative execution engines may become extension categories later if real requirements justify stable contracts.

They are **not required to be first-class plugin protocols in the first implementation merely because they might eventually be useful**.

### 9.3 Plugin trust model

A plugin is executable Python code and is trusted only after installation by the user/environment administrator.

VascuQuest must not:

- download and execute arbitrary Python scripts supplied as CLI arguments;
- auto-install plugins in response to a research request;
- conceal the distribution/version that supplied a plugin.

Plugin identity and version must enter provenance when a plugin affects a scientific result.

### 9.4 Compatibility

Core extension protocols require explicit API/protocol versions.

A plugin that declares an incompatible protocol version must fail clearly during discovery or activation rather than later during a scientific computation.

---

## 10. Public Python API architecture

The user-facing Python API must be substantially smaller than the internal module surface.

Users should not need to import concrete PWDB reader classes for normal research.

The public facade should make it possible to:

- open/register/inspect supported datasets;
- select subjects/cohorts;
- retrieve canonical source quantities and waveforms;
- request derivations;
- run research operators;
- run discovery methods;
- inspect provenance;
- export/reproduce results.

The facade may expose domain objects directly when they are stable and useful, but backend implementation types are not public API merely because Python technically permits importing them.

Public API stability and exact signatures are deferred to `API_PLUGIN_CONTRACT.md`.

---

## 11. CLI architecture

The CLI is an adapter over the same application services used by Python.

Rules:

1. A CLI command may parse arguments, invoke an application operation, and render/serialize its result.
2. A CLI command may not contain the only implementation of a scientific calculation.
3. CLI and Python execution of the same deterministic operation must produce scientifically equivalent results and provenance.
4. Machine-readable CLI output must be available for automation where appropriate.
5. Progress messages and human formatting must remain separate from machine-readable scientific output.
6. CLI framework selection must not leak into the domain or application layers.

Exact commands, output rules, and exit codes are deferred to `CLI_CONTRACT.md`.

---

## 12. Error architecture

VascuQuest needs a small, stable exception hierarchy so Python callers and the CLI can distinguish failure classes.

At minimum the hierarchy must represent:

- dataset/source not available;
- source integrity/checksum failure;
- unsupported or missing capability;
- schema/semantic validation failure;
- incompatible dimensions/units;
- invalid cohort/query;
- scientific admissibility failure;
- plugin incompatibility/load failure;
- reproducibility/provenance incompatibility;
- generic VascuQuest internal error.

Low-level exceptions from HTTP clients, HDF5 readers, CSV parsers, or CLI libraries should not normally leak as the only public explanation of a failure.

The hierarchy should stay shallow. Creating a unique exception for every function is prohibited.

---

## 13. Dependency policy

### 13.1 Mandatory dependency rule

A package becomes a mandatory runtime dependency only if it is required for a broad, core VascuQuest capability and its cost is justified by measured workloads.

### 13.2 Standard library first where appropriate

Use the standard library for capabilities it already handles adequately, including examples such as:

- plugin discovery via `importlib.metadata`;
- paths and file operations;
- structured logging foundations;
- hashing/checksum primitives;
- metadata/configuration primitives where sufficient.

This does not mean reimplementing numerical or scientific libraries.

### 13.3 Scientific dependencies

NumPy/SciPy or other scientific dependencies may be selected where they materially simplify correct numerical work. Their exact mandatory status belongs to implementation planning and validation.

### 13.4 Optional dependencies

Specialized capabilities should use optional dependency groups rather than expanding the mandatory installation footprint without need.

Likely candidates include plotting, particular source formats, advanced statistics/ML, and acceleration stacks, but the exact groups are not frozen here.

### 13.5 Prohibited architectural dependency patterns

- no mandatory MATLAB runtime;
- no mandatory cloud SDK;
- no mandatory GPU framework;
- no mandatory distributed-computing framework;
- no database server;
- no web application framework;
- no dependency-injection framework.

These may be reconsidered only if a future requirement demonstrates that the core cannot meet a real use case without them.

---

## 14. Caching and persistence boundaries

The architecture distinguishes four persistence classes:

1. **canonical source artifacts** — immutable upstream files;
2. **source cache** — verified local copies of canonical artifacts;
3. **derived research store** — indexes, optimized local representations, derived quantities, and reusable computation products;
4. **user outputs** — exported tables, figures, reports, provenance records, and analysis products.

These classes must not share ambiguous filenames/locations that make provenance unclear.

The exact directory layout is deferred to `DATA_ENGINEERING.md`.

Derived caches must be invalidated or namespaced when any scientifically material identity changes, including dataset checksum/schema version/algorithm version where relevant.

---

## 15. Concurrency and performance model

The default runtime is a single local Python process.

The architecture must allow efficient vectorized and lazy I/O operations where supported by the selected scientific libraries, but it does not require a task scheduler.

Rules:

- correctness and bounded memory use take priority over maximal throughput;
- large source files must not be loaded wholesale when the requested operation needs only a slice and the format permits selective access;
- parallelism must not alter deterministic scientific results;
- derived-cache writes require basic inter-process safety/atomicity where concurrent runs could collide;
- GPU/HPC execution belongs behind future adapters/extensions, not in the core execution model.

Performance targets will be based on the ingestion spike and representative scientific workflows, not invented benchmarks.

---

## 16. Configuration model

Configuration should be explicit and small.

Expected configuration categories include:

- local cache/research-store path;
- registered dataset location;
- optional institutional mirror/source;
- offline mode;
- default output preferences that do not alter scientific meaning.

Scientific parameters belong to explicit research requests/provenance, not hidden global configuration.

Environment variables may override deployment-oriented locations/secrets where appropriate, but scientific calculations must not depend on undocumented ambient state.

---

## 17. Security and supply-chain boundaries

The architecture must support:

- checksum verification of acquired source files;
- safe archive extraction;
- atomic/temporary-file download patterns;
- explicit trust boundary for installed plugins;
- no arbitrary script execution as a plugin shortcut;
- no mandatory telemetry;
- no hidden network calls once required artifacts are local, except when the user requests acquisition/update operations;
- clear reporting of external package/plugin versions affecting scientific results.

The package processes synthetic/public research data, so user authentication and medical-record security systems are not core requirements for v1.

---

## 18. Testing architecture

The code structure must make the following test layers possible without special-case hooks:

- pure domain tests with no filesystem/network;
- port contract tests using fake/minimal implementations;
- backend tests against compact fixtures;
- cross-representation scientific validation;
- application-service integration tests;
- CLI-to-API parity tests;
- provenance determinism/compatibility tests;
- plugin conformance tests;
- separate full-dataset/release validation.

The detailed acceptance matrix, tolerances, fixtures, and CI policy are deferred to `TEST_VALIDATION_CONTRACT.md`.

Testability is a module-boundary requirement: code that can only be tested by downloading the complete dataset is architecturally unacceptable for ordinary CI.

---

## 19. Decisions intentionally deferred

The following choices are **not frozen by this architecture** because doing so now would violate the empirical-gate rule or unnecessarily constrain later contracts:

- permanent internal waveform/path storage format;
- whether xarray is a mandatory core abstraction;
- whether DuckDB/Parquet/Arrow/Polars/pandas is used for tabular querying;
- Zarr chunking/layout;
- exact HDF5/MAT reader strategy for every large source object;
- exact cache directory structure;
- final mandatory dependency list;
- CLI framework;
- final public method signatures;
- plugin entry-point group names;
- statistical algorithms offered by the initial discovery engine;
- plotting framework;
- HPC/GPU backend design.

These are not omissions. They are controlled decisions assigned to later contracts or empirical validation.

---

## 20. Implementation invariants

The following rules can be checked mechanically or during review and must hold throughout implementation.

1. `domain` imports no `backends`, `data`, `cli`, or concrete plugin modules.
2. `ports` imports no concrete adapters.
3. `services` depends on domain/ports, not PWDB-specific file layouts.
4. `backends/pwdb3275625` is the only built-in area allowed to encode dataset-specific historical source structure, apart from declarative manifest/schema resources.
5. `cli` contains no unique scientific calculation.
6. all scientific results capable of leaving the process carry evidence/provenance semantics when materially applicable;
7. source files are never modified in place;
8. plugin code is discovered from installed distributions, not arbitrary paths;
9. a normal metadata/query operation must not trigger an unconditional full-dataset download;
10. storage technology does not leak into the stable public scientific API unless it is deliberately exposed as an interoperability object.

---

## 21. Minimal architecture acceptance scenarios

The architecture is considered implementable only if it can support the following scenarios without violating dependency rules.

### Scenario A — metadata-only exploration

A researcher installs VascuQuest, acquires/registers only the required small metadata artifacts, and queries available subjects and canonical haemodynamic quantities without downloading path-resolved wave files.

### Scenario B — waveform investigation

A researcher requests a pressure waveform at a supported site. The backend resolves and acquires only the required artifact(s), returns a canonical waveform object/result, and records source provenance.

### Scenario C — derived quantity

A researcher requests a registered derivation. The application resolves its declared input quantities, executes the derivation, validates units/dimensions, and returns a `DERIVED` result with provenance linking all inputs and method identity.

### Scenario D — external research operator

An installed third-party operator declares required inputs, assumptions, outputs, and protocol version. VascuQuest resolves its inputs, checks declared compatibility/admissibility where possible, executes it, and records a `MODELLED` result with plugin identity/version.

### Scenario E — discovery method

A researcher defines a cohort and invokes a discovery method. The method receives canonical inputs rather than raw PWDB filenames, and its `INFERRED` output retains cohort definition, method parameters, and provenance.

### Scenario F — reproducibility

A saved provenance/workflow record can identify the compatible dataset version/checksums, schema version, algorithms/plugins, parameters, and requested scientific operation sufficiently for VascuQuest to determine whether reproduction is possible.

### Scenario G — future dataset

A future validated vascular-population backend can implement the public backend contract and participate in generic query/derivation/discovery workflows without changes to PWDB-specific code or the scientific domain layer.

---

## 22. Architecture audit checklist

Before `ARCHITECTURE.md` is accepted, reviewers must answer **yes** to all of the following.

### Fidelity

- Does the architecture preserve all six binding decisions in `DESIGN_CONTRACT.md`?
- Does it preserve the distinction between source, reconstructed, derived, inferred, and modelled science?
- Does it avoid introducing unsupported mathematical claims or equations?

### Simplicity

- Can the architecture be implemented as an ordinary Python package without services or infrastructure outside the user's machine?
- Are module boundaries fewer and clearer than the problems they solve?
- Are speculative subsystems deferred rather than implemented pre-emptively?

### Feasibility

- Can PWDB-specific complexity remain inside one backend while the rest of the package stays format-independent?
- Can large-file strategies remain provisional until the ingestion spike?
- Can routine tests run without the full dataset?

### Extensibility

- Can new datasets and scientific methods enter through stable ports/plugins?
- Can a plugin be identified and versioned in provenance?
- Can a future backend participate without rewriting generic discovery logic?

### Scientific integrity

- Are units, evidence class, admissibility, and provenance first-class concerns?
- Is model output prevented from masquerading as source truth?
- Are source artifacts immutable?

### API/CLI coherence

- Is there one scientific implementation path shared by Python and CLI?
- Can CLI rendering change without changing scientific computation?

If any answer is no, the architecture must be amended before proceeding to `DATA_ENGINEERING.md`.

---

## 23. Approval consequence

Once this architecture passes audit, it freezes the **structural boundaries** of the v1 implementation.

It does **not** freeze source-format mechanics or storage technologies reserved for the ingestion spike and `DATA_ENGINEERING.md`.

The next contract after approval is `DATA_ENGINEERING.md`.
