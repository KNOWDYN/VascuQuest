# VascuQuest API and Plugin Contract

**Status:** Public-interface and extension contract for implementation  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`, `SCIENTIFIC_MODEL.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Freeze the smallest practical public Python API and plugin contract required to implement VascuQuest without exposing storage details, weakening provenance, or placing scientific equations in interface code.

---

## 1. Design objective

VascuQuest has one scientific implementation path shared by:

1. researchers using Python;
2. the CLI;
3. installed third-party extensions.

The interface must be small enough to implement and test in ordinary Python while preserving dataset identity, quantity semantics, units, evidence class, validity, and provenance.

V1 therefore uses:

- normal Python functions and value objects;
- `typing.Protocol` where structural extension contracts are needed;
- small immutable request/descriptor objects where they reduce ambiguity;
- one explicit composition root in `bootstrap.py`;
- standard Python package entry points for installed plugins;
- structured scientific results rather than unlabelled arrays.

V1 does **not** require a dependency-injection framework, RPC layer, plugin marketplace, custom package manager, remote execution protocol, Python sandbox, universal dataframe type, or scientific equations in the API layer.

---

## 2. Binding scientific and architectural rules

This contract preserves the already-approved rules:

- PWDB Zenodo `3275625` is the sole canonical v1 dataset;
- source artifacts are immutable and checksum-verified;
- source/storage mechanics remain behind adapters/backends;
- scientific results distinguish `SOURCE`, `RECONSTRUCTED`, `DERIVED`, `INFERRED`, and `MODELLED`;
- canonical meaning and units come from the versioned scientific schema;
- a virtual subject is a simulation instance, not a patient;
- source and modelled/inferred science never become interchangeable by convenience;
- external theories belong in registered derivations/operators;
- CLI and Python use the same services;
- permanent large-data storage choices remain gated by the ingestion spike.

If this file conflicts with an earlier governing contract, the earlier contract wins unless formally amended.

---

## 3. Stable public Python surface

Normal users should be able to begin with:

```python
import vascuquest as vq
```

The stable public vocabulary for v1 is limited to:

- `DatasetSession`
- `DatasetIdentity`
- `VirtualSubject`
- `Cohort`
- `VascularLocation` and its supported location value types
- `QuantityDefinition`
- `ScientificResult`
- `Waveform`
- `DiscoveryResult`
- `EvidenceClass`
- `ProvenanceRecord`
- stable public exceptions

The primary public functions are conceptually:

```python
vq.open_dataset(...)
vq.register_source(...)
vq.plugins.list(...)
vq.plugins.describe(...)
```

Normal research code must not require imports from concrete PWDB readers, HDF5/WFDB/MAT adapters, cache internals, or Zenodo-specific modules.

Undocumented internal modules are not stable API.

---

## 4. Opening a dataset

The primary entry point is:

```python
session = vq.open_dataset(
    "pwdb:3275625",
    source=None,
    offline=False,
)
```

Semantics are binding even if final argument typing is refined during implementation:

- dataset identity is explicit;
- opening does not download all artifacts;
- `source` selects a configured/registered retrieval location without changing canonical dataset identity;
- `offline=True` prohibits hidden network acquisition;
- the returned object is a stable `DatasetSession` facade, not a raw backend.

A short alias such as `"pwdb"` may exist only if it resolves unambiguously to `3275625` and the resolved identity remains visible in the session and provenance.

---

## 5. `DatasetSession`

`DatasetSession` is the main user-facing research facade for one dataset identity.

It must support operations equivalent to:

```python
session.identity
session.status()
session.capabilities()
session.quantities()

session.subject(subject_id)
session.subjects(...)
session.select(...)

session.get(quantity, *, subjects=None, location=None, ...)
session.waveform(signal, *, subject, location, ...)

session.derive(method, *, inputs=None, subjects=None, location=None, parameters=None)
session.model(operator, *, inputs=None, subjects=None, location=None, parameters=None)
session.discover(method, *, cohort=None, inputs=None, parameters=None)

session.export(result, ...)
session.reproduce(provenance_or_workflow, ...)
```

Rules:

1. identity/status/capability inspection must remain lightweight;
2. subject/cohort creation must not materialize all subject data;
3. ordinary selection must work without inventing a custom query language first;
4. scientific retrieval returns canonical result objects, not source-reader objects;
5. derivation, modelling, and discovery remain visibly distinct operations;
6. strict reproduction never silently substitutes another method/version.

Public convenience methods may accept keyword parameters, but the application layer must normalize scientific method parameters into one explicit serializable mapping before validation, execution, and provenance capture.

---

## 6. Stable result contract

A nontrivial scientific operation returns `ScientificResult`, `Waveform`, `DiscoveryResult`, or another explicitly documented structured subtype preserving the same semantics.

A result must expose, where applicable:

```text
quantity definition/identity
values
dimensions and coordinates
canonical unit
source unit/label where relevant
subject or cohort context
vascular location context
evidence class
provenance
validity/admissibility
warnings
method identity
```

Numerical convenience access such as `result.values` is allowed, but the bare values are not the authoritative scientific result.

The stable contract must not depend on whether storage is internally NumPy, xarray, pandas, Polars, Arrow, HDF5, Zarr, or another representation.

For numerical arrays, NumPy-compatible access is preferred where practical because it is lightweight and broadly interoperable. Optional conversion helpers may support richer ecosystems without making them mandatory plugin ABI types.

---

## 7. Units, evidence, and validity

Every dimensional canonical quantity/result exposes a canonical unit and dimensional semantics defined by the scientific schema.

The public/plugin contract does not mandate a third-party units library. If one is used internally, its private type must not become an accidental permanent plugin ABI.

`EvidenceClass` is a stable public enum with exactly:

```text
SOURCE
RECONSTRUCTED
DERIVED
INFERRED
MODELLED
```

Validity/admissibility is separate from evidence class. A `MODELLED` result may, for example, also be out of the operator's declared validated domain.

No physical or haemodynamic equation is defined by this API contract.

---

## 8. Public exceptions

All expected public failures derive from:

```python
VascuQuestError
```

V1 must distinguish at least these semantic classes:

- dataset/source unavailable;
- source integrity failure;
- capability unavailable;
- schema/semantic failure;
- units/dimensions failure;
- invalid selection/cohort;
- scientific admissibility failure;
- plugin load/activation failure;
- plugin protocol incompatibility;
- reproduction incompatibility;
- internal VascuQuest failure.

The implementation may use names such as `DatasetUnavailableError`, `IntegrityError`, `CapabilityError`, `SchemaError`, `UnitError`, `SelectionError`, `AdmissibilityError`, `PluginError`, `PluginCompatibilityError`, `ReproducibilityError`, and `VascuQuestInternalError`.

The hierarchy must stay shallow. Low-level library exceptions should be chained as causes instead of leaking as the only public explanation.

---

## 9. V1 plugin categories

There are exactly five public plugin categories in v1:

1. dataset backends;
2. derivations;
3. research operators;
4. discovery methods;
5. result exporters.

The approved entry-point groups are:

```text
vascuquest.backends
vascuquest.derivations
vascuquest.operators
vascuquest.discovery
vascuquest.exporters
```

Artifact sources, schema override providers, visualization engines, and execution accelerators are **not** independent public v1 plugin categories.

This is intentional restraint. Internal architectural ports remain replaceable/testable without forcing every internal seam into a public ABI.

---

## 10. One deterministic entry-point shape

Every VascuQuest entry point must resolve to a **zero-argument factory callable**.

The factory returns exactly one protocol-conforming component instance.

Conceptually:

```python
def create_component() -> ComponentProtocol:
    ...
```

This rule eliminates class/instance/provider ambiguity.

The factory may perform lightweight component construction but must not start a scientific computation merely because the plugin is loaded.

Built-in components should use the same internal factory convention even though they do not need external package entry points.

---

## 11. Component descriptor

Every plugin component exposes one immutable `ComponentDescriptor` or equivalent public value with at least:

```text
kind
name
qualified_id
implementation_version
protocol_version
distribution_name
distribution_version
summary
citations, when scientifically applicable
```

### 11.1 Qualified identity

The v1 canonical component identifier format is:

```text
<namespace>:<component>
```

Both parts must be non-empty stable machine identifiers. Display labels are separate.

The namespace should normally be the owning distribution/project namespace.

Two active components in the same category may not share a `qualified_id`. Conflict must fail deterministically; environment discovery order must never choose a silent winner.

Built-in IDs are reserved and cannot be silently shadowed.

### 11.2 Protocol version

`protocol_version` is an **integer major version**.

For v1:

```text
protocol_version = 1
```

Compatibility is exact at the major level: a component declaring any unsupported integer is rejected before scientific execution.

Scientific implementation version and Python distribution version are separate fields and must not be confused with protocol compatibility.

---

## 12. Plugin discovery and loading

Plugins are discovered with `importlib.metadata.entry_points()`.

Rules:

1. VascuQuest never scans arbitrary directories for `.py` plugins;
2. it never auto-installs missing plugins during scientific execution;
3. installed distribution metadata may be inspected without loading heavy plugin modules where practical;
4. actual factory/component import may be lazy;
5. one broken optional plugin must not disable unrelated core functionality;
6. load failure reports entry-point identity, category, distribution/version when known, and the chained underlying exception.

An installed plugin is executable trusted-local-environment code. V1 does not attempt unreliable in-process sandboxing or process isolation of arbitrary Python extensions.

---

## 13. Common component rules

All scientific plugin components must:

- expose their descriptor;
- accept only declared canonical scientific inputs;
- declare parameters in machine-readable form;
- declare output meaning/evidence semantics;
- contribute structured provenance facts;
- avoid mutation of source artifacts and source-backed input arrays;
- avoid reading undeclared PWDB files directly;
- avoid silently replacing canonical quantity definitions;
- report validation/admissibility limitations where scientifically applicable.

Protocol conformance is a technical statement. It is **not** scientific certification.

---

## 14. Dataset backend protocol

`DatasetBackend` translates one concrete virtual-population dataset into VascuQuest canonical concepts.

Its protocol must provide capabilities equivalent to:

```python
descriptor: ComponentDescriptor
identity() -> DatasetIdentity
capabilities() -> CapabilitySet
subjects(request) -> subject metadata/identities
locations(request) -> canonical locations
get_quantity(request) -> ScientificResult
get_waveform(request) -> Waveform
geometry(request) -> ScientificResult or canonical geometry result
```

Binding semantics:

- it declares the exact dataset identity it implements;
- it returns canonical domain/result types;
- it advertises capabilities before expensive access;
- source acquisition occurs through the data/artifact layer;
- source provenance is preserved;
- raw HDF5/MAT/WFDB/storage objects do not become stable API;
- unrelated research theories do not enter the backend.

PWDB `3275625` is the built-in v1 backend.

A third-party backend may ship source mappings/schema definitions required for its own dataset but may not silently redefine existing canonical quantities.

---

## 15. Derivation protocol

A `Derivation` is a deterministic registered scientific transformation.

It must declare:

```text
descriptor
required canonical inputs
output quantity definition
default output evidence class
parameter specifications
unit/dimension requirements
coordinate/location requirements
missing-data policy
citations or authoritative definition
validation scope
```

Execution is conceptually:

```python
result = derivation.run(
    inputs=validated_inputs,
    parameters=normalized_parameters,
    context=context,
)
```

Rules:

- inputs are canonical `ScientificResult` objects or validated views;
- parameters are explicit and serializable;
- additional scientific inputs must be declared rather than fetched by source filename;
- the derivation owns and validates any mathematical definition it implements;
- the protocol itself contains no derivation equation.

---

## 16. Research operator protocol

A `ResearchOperator` introduces an explicit scientific model beyond direct source interpretation.

It must declare:

```text
descriptor
required canonical inputs
canonical or operator-scoped outputs
parameter specifications
units/dimensions
assumptions
admissible/validated domain
citations
output evidence class, normally MODELLED
deterministic/random behavior
```

Execution is conceptually:

```python
result = operator.run(
    inputs=validated_inputs,
    parameters=normalized_parameters,
    context=context,
)
```

Rules:

- operator equations remain owned by the operator implementation/documentation;
- PWDB inputs do not make operator outputs `SOURCE`;
- source-backed inputs are logically read-only;
- admissibility is explicit;
- random state is explicit/provenanced where reproducibility is expected;
- operator-scoped quantities use namespaced identities and cannot shadow canonical quantities.

Project-specific Womersley, anisotropy, fractional-order, susceptibility, CGL, constitutive, or related formulations therefore fit naturally here without contaminating the core dataset model.

---

## 17. Discovery method protocol

A `DiscoveryMethod` operates on a defined cohort and canonical scientific inputs.

It must declare:

```text
descriptor
required input quantities/features
parameter specifications
missing-data policy
random behavior
output/result schema
evidence semantics
validation/resampling requirements where applicable
```

Execution is conceptually:

```python
result = method.run(
    cohort=cohort,
    inputs=validated_inputs,
    parameters=normalized_parameters,
    context=context,
)
```

A discovery method must not silently:

- alter cohort membership;
- exclude missing subjects without its declared policy;
- claim human causation from virtual-population association;
- label deterministic grouping/sorting as `INFERRED` merely because it occurs in discovery.

Exploratory/confirmatory status and validation information remain inspectable when relevant.

---

## 18. Result exporter protocol

A `ResultExporter` serializes a VascuQuest result without changing scientific meaning.

It must declare:

```text
descriptor
supported result kinds
supported output formats
provenance-retention behavior
```

Execution is conceptually:

```python
exporter.export(result, destination, options)
```

Rules:

- exporters do not silently recompute scientific values;
- units, coordinates, evidence class, and provenance remain available when the target format supports them;
- if a target cannot contain essential metadata, the exporter creates a documented companion/sidecar representation or warns/fails according to the format contract;
- exporters never reduce scientific values to ambiguous unlabeled numbers without explicit user choice.

---

## 19. Request and parameter objects

Complex operations should use a small number of immutable request/value objects rather than unstable long signatures.

Likely public/internal request types include:

```text
QuantityRequest
WaveformRequest
DerivationRequest
OperatorRequest
DiscoveryRequest
```

A request contains scientific/application inputs only, never storage mechanics such as HDF5 groups or Zenodo URLs.

Scientific method parameters are normalized to a mapping whose keys are parameter names and whose values are portable/serializable values or explicitly supported stable references.

Each parameter specification may contain:

```text
name
type/kind
required/default
unit when dimensional
allowed values/range only where the method actually defines them
description
```

Implementation-validation ranges must not be presented as scientifically validated domains.

---

## 20. Input requirements and resolution

Derivations, operators, and discovery methods declare inputs canonically, for example:

```text
quantity identity or category
acceptable units/dimensions
required coordinate kinds
required location kind
single-subject/cohort semantics
optional/required status
acceptable evidence classes when scientifically restricted
```

Application services—not plugins—resolve those requirements.

The execution flow is:

```text
user request
  -> choose registered component
  -> validate protocol version
  -> validate/normalize parameters
  -> resolve declared canonical inputs
  -> validate units/dimensions/context/evidence restrictions
  -> execute component
  -> validate returned result metadata
  -> finalize provenance
  -> return structured result
```

No automatic substitution is allowed based only on similar names.

A plugin needing additional scientific data must declare it as an input rather than reaching backward through execution context into backend files.

---

## 21. Execution context

Plugins receive a small `ExecutionContext` or equivalent, not unrestricted access to session/backend internals.

It may expose only infrastructure such as:

- VascuQuest/runtime version metadata;
- provenance-building hooks;
- warning/log channel;
- explicit random-state support;
- temporary workspace;
- optional progress/cancellation callback if later required.

It must not expose:

- private PWDB reader objects;
- mutable global registries;
- CLI parser state;
- arbitrary cache internals.

The execution context is not a hidden service locator for undeclared scientific inputs.

---

## 22. Plugin provenance and reproducibility

When a plugin affects a scientific result, provenance records at least:

```text
component qualified_id
component implementation version
protocol version
distribution name/version when available
input-result provenance links
normalized parameters
assumptions when material
citations when scientific
random seed/state when applicable
output evidence class
validation/admissibility result
```

The core provenance service owns serialization. Plugins contribute structured facts rather than inventing their own provenance file format.

Strict reproduction prefers the exact component implementation version used originally.

A different installed version must not be silently treated as identical when scientific output may change. An explicit rerun under a new version is a new computation with new provenance.

---

## 23. Determinism and mutation

A component declares whether it is deterministic for fixed inputs/parameters/environment.

When randomness is used and the method supports reproducibility:

- the seed/random-state input is explicit;
- it is retained in provenance;
- undocumented global random state is insufficient.

Plugin inputs are logically read-only.

Plugins must not mutate:

- canonical source artifacts;
- source-backed input arrays in place;
- caller cohort membership;
- canonical schema definitions;
- other registry entries.

Defensive copying of every large array is not required; the implementation should enforce/read-test immutability without unnecessary memory duplication.

---

## 24. Registry, failures, and dependencies

The registry is one lightweight component registry with category views, not five unrelated plugin frameworks.

Rules:

- incompatible protocol versions fail before execution;
- duplicate IDs fail deterministically;
- disabled/missing plugins are never silently replaced;
- a broken optional plugin does not block unrelated workflows;
- heavy dependencies belong to the plugin that needs them;
- core does not acquire TensorFlow, PyTorch, JAX, Dask, graph databases, symbolic-algebra stacks, or similar packages merely for hypothetical extensions.

Third-party plugins retain their own licenses. The Apache-2.0 core does not copy incompatible plugin/upstream implementations.

---

## 25. Introspection

Researchers must be able to inspect available science before executing it.

The API supports operations equivalent to:

```python
vq.plugins.list(kind=None)
vq.plugins.describe(component_id)
session.quantities()
session.capabilities()
```

Descriptions expose, where relevant:

- component identity/version;
- required inputs;
- output quantities;
- parameters;
- evidence semantics;
- assumptions;
- citations;
- validation/admissibility information.

This is essential for a research explorer: users should not discover method requirements only by triggering failures.

---

## 26. API/CLI parity

Every CLI scientific operation maps onto this same application/public API.

The CLI may add argument parsing, progress display, confirmations, shell formatting, and human-readable presentation.

It may not add unique scientific mathematics, hidden substitutions, different evidence classification, or different provenance semantics.

`CLI_CONTRACT.md` will freeze exact command names, output channels, structured-output rules, and exit codes.

---

## 27. Explicit non-goals

V1 will not:

- expose one public method per PWDB file;
- expose backend reader objects as stable research API;
- create a remote plugin marketplace;
- auto-install scientific plugins;
- support arbitrary script paths as plugins;
- attempt to sandbox arbitrary Python plugin code;
- require framework inheritance for plugin conformance;
- make every internal port a public plugin category;
- permit silent canonical-schema overrides;
- require one universal array/dataframe library at the protocol boundary;
- infer missing scientific parameters from similarly named fields;
- put model equations into protocol definitions;
- claim protocol conformance equals scientific validation;
- permit plugin execution to mutate canonical source data.

---

## 28. Implementation invariants

The following must remain true in code.

1. `open_dataset()` returns a scientific facade, never a raw backend.
2. opening a dataset does not imply full-dataset acquisition.
3. public calls use scientific identities rather than source paths.
4. backend storage types do not leak into stable result contracts.
5. `EvidenceClass` is programmatically inspectable.
6. nontrivial transformed/modelled/inferred results retain provenance.
7. there are exactly five public v1 plugin categories.
8. every external entry point resolves to a zero-argument factory.
9. every factory returns one protocol-conforming component.
10. `protocol_version` is integer major `1` for v1.
11. component IDs are stable namespaced identifiers.
12. plugin compatibility is checked before execution.
13. plugin discovery uses installed package entry points.
14. arbitrary `.py` paths are not executed.
15. scientific plugins declare required canonical inputs.
16. plugins do not reach into PWDB files for undeclared inputs.
17. operator-scoped quantities cannot silently shadow canonical quantities.
18. source-backed inputs are not mutated in place.
19. output evidence follows the actual scientific operation.
20. random-state provenance is retained when needed.
21. CLI uses the same scientific implementation path.
22. one broken optional plugin does not disable unrelated core work.
23. heavy plugin dependencies remain plugin-owned unless independently justified as core dependencies.
24. no mathematical equation is introduced by the API/plugin framework.

---

## 29. Acceptance scenarios

### A. Open and inspect PWDB

```python
session = vq.open_dataset("pwdb:3275625")
session.identity
session.capabilities()
```

Must not trigger unconditional 44.3 GB acquisition.

### B. Retrieve a source waveform

```python
p = session.waveform("pressure", subject=..., location=...)
```

The result retains canonical signal, location, time/sampling context, unit, `SOURCE` evidence, and provenance without exposing WFDB/MAT/HDF5 internals.

### C. Run a derivation

The derivation receives canonical inputs and normalized parameters; its own validated implementation owns any mathematics; method/version/parameters enter provenance.

### D. Run an external research operator

A package publishes a factory under `vascuquest.operators`. VascuQuest loads the factory lazily, validates protocol `1`, resolves declared canonical inputs, executes the operator, and records component/distribution/version/assumptions/citations in provenance. Output is normally `MODELLED`.

### E. Incompatible plugin

A component declares protocol version `2` while the runtime supports `1`. Activation fails before scientific execution; unrelated functionality remains available.

### F. Duplicate plugin identity

Two active components expose the same qualified ID in the same category. Registration fails deterministically rather than selecting by discovery order.

### G. Missing plugin during reproduction

Strict reproduction reports the required missing component/version and does not substitute another implementation silently.

### H. Random discovery method

Random state is explicit and retained in provenance where the method supports reproducible execution.

---

## 30. Audit checklist

`API_PLUGIN_CONTRACT.md` passes only if every answer is **yes**.

### Simplicity

- Is the public API materially smaller than the internal package?
- Are there exactly five plugin categories?
- Is there exactly one entry-point object shape: a zero-argument factory?
- Is standard `importlib.metadata` sufficient for discovery?
- Are framework-heavy mechanisms absent?

### Completeness

- Can users inspect, select, retrieve, derive, model, discover, export, and reproduce?
- Can components declare identity, version, inputs, outputs, parameters, assumptions, citations, evidence, and validity information?
- Can plugin failures remain isolated?

### Feasibility

- Can this be implemented with standard Python, protocols, dataclasses/value objects, and normal packaging?
- Can large arrays pass without mandatory copying or JSON serialization?
- Can heavy optional science stay outside the core?

### Scientific integrity

- Do plugins consume canonical scientific inputs rather than filenames?
- Are source/derived/inferred/modelled results distinguishable?
- Are units/dimensions and admissibility preserved?
- Are equations owned by scientific implementations rather than protocols?
- Is technical conformance separated from scientific validation?

### Reproducibility

- Are component identity/version/protocol, inputs, parameters, assumptions, and random state recordable?
- Is silent method-version substitution forbidden?

### Architecture compatibility

- Are storage mechanics hidden?
- Does CLI remain an adapter over the same implementation?
- Can plugins work through canonical domain types without concrete PWDB readers?

### Extensibility

- Can each of the five extension categories be added independently?
- Are namespaced quantities and component IDs collision-safe?
- Is protocol compatibility independent of overall package release version?

If any answer is no, this file must be amended before `CLI_CONTRACT.md`.

---

## 31. Approval consequence

Once this contract passes audit:

- the v1 public Python surface is structurally frozen;
- the five extension categories and their entry-point groups are frozen;
- every external entry point resolves to one zero-argument factory;
- protocol major version `1`, component identity, and provenance requirements are frozen;
- exact internal dataclass field ordering/type annotations may be refined without changing these semantics;
- the next contract is `CLI_CONTRACT.md`.

---

## 32. Implementation restraint

Use the smallest mechanism that satisfies this contract:

- functions/value objects before manager classes;
- `Protocol` before inheritance when only behavior matters;
- explicit immutable metadata before hidden global state;
- one registry with category views rather than several plugin subsystems;
- application-level input resolution rather than backend access from plugins;
- no abstraction layer merely because a heading exists in this document.

The contract removes ambiguity; it does not require one Python class for every concept described here.