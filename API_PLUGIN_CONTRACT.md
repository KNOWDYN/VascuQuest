# VascuQuest API and Plugin Contract

**Status:** Public-interface and extension contract for implementation  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`, `SCIENTIFIC_MODEL.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Freeze the minimum public Python API, extension protocol categories, plugin discovery/versioning rules, provenance obligations, and compatibility boundaries required to implement VascuQuest without exposing storage details or embedding scientific equations in interface code.

---

## 1. Objective

VascuQuest needs one coherent scientific API that serves three audiences:

1. researchers using Python directly;
2. the VascuQuest CLI, which must call the same implementation path;
3. third-party developers providing validated dataset backends, derivations, research operators, discovery methods, or exporters.

The API must be small enough to learn and implement, but strong enough to preserve scientific meaning, provenance, units, evidence class, and dataset identity.

This contract therefore favors:

- ordinary Python objects and functions;
- typed protocols and immutable request/metadata objects where useful;
- explicit composition through `bootstrap.py`;
- standard Python package entry points for installed plugins;
- structured scientific results rather than unlabelled arrays;
- compatibility checks at plugin activation rather than deep inside a computation.

It deliberately avoids:

- a service framework;
- a dependency-injection framework;
- a remote plugin protocol;
- an RPC layer;
- a custom package manager;
- runtime execution of arbitrary `.py` files;
- a universal dataframe/array type in the public contract;
- equations or model-specific notation in the interface layer.

---

## 2. Binding relationship to previous contracts

The API and plugin design must preserve the following already-frozen rules.

1. PWDB Zenodo record `3275625` is the sole canonical v1 source dataset.
2. Dataset/source artifacts remain immutable and manifest-verified.
3. Storage and file-format implementation details remain behind adapters/backends.
4. Every material scientific result exposes one of the five evidence classes:
   - `SOURCE`
   - `RECONSTRUCTED`
   - `DERIVED`
   - `INFERRED`
   - `MODELLED`
5. Canonical scientific meaning and units come from the versioned schema.
6. Source and modelled/inferred science must remain distinguishable.
7. A virtual subject is a simulation instance, not a patient.
8. The CLI and Python API must share the same services and scientific implementation.
9. External theories belong in registered derivations/operators rather than the core ontology.
10. Large-data storage choices remain provisional until the ingestion spike.

If this file conflicts with an earlier governing contract, the earlier contract wins unless a formal design amendment explicitly changes it.

---

## 3. Public API design rule

The stable public surface must be substantially smaller than the internal package surface.

Normal users should import from:

```python
import vascuquest as vq
```

or documented public submodules such as:

```python
from vascuquest import DatasetSession, ScientificResult, Waveform
from vascuquest.errors import VascuQuestError
```

Users must not need to import from internal source readers such as:

```text
vascuquest.backends.pwdb3275625.*
vascuquest.data.* internal readers
vascuquest.schema.* internal loaders
```

for ordinary research workflows.

Undocumented internal modules are not stable merely because Python permits importing them.

---

## 4. Minimal public vocabulary

The initial public API should expose only the concepts that users need repeatedly.

### Stable public concepts

- `DatasetSession`
- `DatasetIdentity`
- `VirtualSubject`
- `Cohort`
- `VascularLocation` and its supported location values/types
- `QuantityDefinition`
- `ScientificResult`
- `Waveform`
- `EvidenceClass`
- `ProvenanceRecord`
- stable public exceptions

### Public service entry points

- `open_dataset(...)`
- `register_source(...)`
- `dataset_status(...)` or equivalent session/status operation
- plugin discovery/inspection operations

The exact number of convenience methods may evolve, but the API must not become a one-function wrapper around every CLI command or every source file.

---

## 5. Dataset opening

The primary Python entry point is conceptually:

```python
session = vq.open_dataset(
    "pwdb:3275625",
    source=None,
    offline=False,
)
```

The exact spelling may be adjusted during implementation only if tests demonstrate a clearer equivalent. The semantics are frozen:

- the dataset identifier is explicit;
- opening does not imply downloading all source artifacts;
- `source` may identify a registered/local source configuration without redefining canonical dataset identity;
- `offline=True` prohibits hidden network acquisition;
- the returned object is a `DatasetSession` or equivalent stable facade.

For v1, aliases such as `"pwdb"` may be accepted only if they resolve unambiguously to record `3275625` and the resolved identity remains explicit in the returned session/provenance.

---

## 6. `DatasetSession`

`DatasetSession` is the main research facade over one opened dataset identity.

It must provide capabilities equivalent to the following groups.

### 6.1 Identity and availability

```python
session.identity
session.capabilities()
session.status()
```

These operations must be lightweight and must not materialize large source artifacts.

### 6.2 Subject access

```python
session.subject(subject_id)
session.subjects(...)
```

A subject reference must remain lightweight and must not load all waveforms or geometry on creation.

### 6.3 Cohort construction

```python
session.select(...)
```

The returned `Cohort` must preserve a reproducible selection specification and resolved subject identifiers.

The v1 API must not require a custom query language before ordinary filtering works. Keyword/structured selection is preferred initially; a richer expression language may be added later if justified.

### 6.4 Scientific retrieval

```python
session.get(quantity, *, subjects=None, location=None, ...)
session.waveform(signal, *, subject, location, ...)
```

These return canonical scientific objects/results, not raw PWDB parser objects.

### 6.5 Registered scientific methods

```python
session.derive(method, *, inputs=None, subjects=None, location=None, **parameters)
session.model(operator, *, inputs=None, subjects=None, location=None, **parameters)
session.discover(method, *, cohort=None, inputs=None, **parameters)
```

These are semantic examples. Implementation may consolidate common request handling, but the user-facing distinction between derivation, modelling, and discovery must remain visible because their scientific meanings differ.

### 6.6 Export and reproduction

```python
session.export(result, ...)
session.reproduce(provenance_or_workflow, ...)
```

Exact reproduction mechanics may initially support only deterministic workflows whose required components are available. Failure to reproduce must be explicit rather than silently substituting a different method/version.

---

## 7. Public API must not expose backend storage mechanics

Public scientific calls must not require arguments such as:

```text
mat_struct_path
hdf5_group
zarr_chunk
parquet_partition
wfdb_record_path
zenodo_file_url
```

Such arguments belong to backend/data-engineering internals or explicit low-level diagnostic tools.

A user may choose source/acquisition policy, but scientific calls should be expressed using dataset, subject, quantity, signal, location, cohort, and method semantics.

---

## 8. Result contract

All nontrivial scientific operations return `ScientificResult`, `Waveform`, `DiscoveryResult`, or another explicitly documented structured scientific result that preserves the same required semantics.

A result must expose, where applicable:

```text
quantity identity/definition
values
dimensions/coordinates
unit
subject/cohort context
vascular location context
evidence class
provenance
validity/admissibility
warnings
method identity
```

Convenience access to raw numerical values is allowed, for example conceptually:

```python
result.values
```

but `.values` alone is not the authoritative scientific object.

---

## 9. Array/container interoperability

VascuQuest must interoperate with common scientific Python workflows without declaring one third-party container to be the scientific truth.

The public result contract should therefore support:

- NumPy-compatible value access for numerical arrays where practical;
- conversion/export helpers for common tabular or labelled-array ecosystems when optional dependencies are installed;
- ordinary Python scalars/mappings for lightweight metadata.

The stable scientific identity must not depend on whether values are internally stored in NumPy, xarray, pandas, Polars, Arrow, HDF5, or another backend.

No mandatory xarray/pandas object appears in the plugin protocol solely for convenience.

---

## 10. Units interface

The public contract requires unit and dimensional semantics but does not mandate a third-party units package.

At minimum, public quantity/result metadata must provide:

```text
canonical unit identifier
physical dimensionality or equivalent validated dimension specification
source unit/label where relevant
```

Plugin inputs/outputs must declare unit requirements using VascuQuest canonical quantity definitions or a simple public unit specification—not a private backend unit object.

The implementation may adopt a unit library internally if it improves correctness. If so, adapters must prevent that library from becoming an accidental irreversible plugin ABI unless explicitly approved.

No new physical equations are defined by this contract.

---

## 11. Evidence and validity in the API

`EvidenceClass` is a stable public enum with exactly the five contract values.

A result must make its evidence status inspectable without parsing prose.

Validity/admissibility is a separate concept and must not be encoded by changing the evidence class.

For example, a `MODELLED` result may simultaneously be marked out of the operator's declared validated domain.

Plugin protocols must therefore return structured validity/warning metadata where scientifically applicable.

---

## 12. Public exception hierarchy

The public API must expose a shallow stable exception hierarchy rooted at:

```python
VascuQuestError
```

Required semantic subclasses are conceptually:

- `DatasetUnavailableError`
- `IntegrityError`
- `CapabilityError`
- `SchemaError`
- `UnitError`
- `SelectionError`
- `AdmissibilityError`
- `PluginError`
- `PluginCompatibilityError`
- `ReproducibilityError`
- `VascuQuestInternalError`

Names may be adjusted once during initial implementation for consistency, but the semantic classes must remain distinguishable.

Low-level exceptions from HTTP, ZIP, HDF5, WFDB, or parser libraries should be chained as causes while the public exception explains the VascuQuest-level failure.

---

## 13. Extension philosophy

VascuQuest plugins extend declared scientific capabilities; they do not patch arbitrary internal state.

The v1 extension categories are exactly:

1. dataset backends;
2. derivations;
3. research operators;
4. discovery methods;
5. result exporters.

Visualization and execution accelerators are not first-class v1 plugin protocols unless implementation evidence demonstrates a concrete need before release.

This keeps the extension surface small enough to test.

---

## 14. Python protocol strategy

Extension contracts should be represented using normal Python typing constructs, preferably `typing.Protocol` for structural contracts plus small immutable metadata/request objects.

Abstract base classes may be used when shared implementation behavior is genuinely useful, but plugin conformance must not require inheritance solely for branding.

The protocol layer must not depend on concrete PWDB adapters.

A plugin should be testable with compact public fixtures and protocol conformance tests.

---

## 15. Shared plugin descriptor

Every plugin-provided component must expose a descriptor equivalent to:

```text
kind
name
qualified_id
implementation_version
protocol_version
distribution_name (when installed as a package)
distribution_version
summary
citations (where scientifically applicable)
```

`qualified_id` must be globally collision-resistant within the local plugin environment. A recommended convention is:

```text
<distribution-or-namespace>:<component-name>
```

Examples are illustrative, not mandatory syntax.

Human display names are not stable identifiers.

---

## 16. Protocol versioning

Each plugin category has an explicit VascuQuest protocol version.

For v1:

```text
protocol major = 1
```

The implementation may serialize this as `"1"` or `"1.x"`, but compatibility must be deterministic.

Rules:

1. a component declaring an unsupported major protocol version is rejected before scientific execution;
2. backward-compatible additions within the same major version must not break existing conforming plugins;
3. required method signature changes or semantic reinterpretations require a new major protocol version;
4. scientific-method implementation versions are distinct from protocol versions;
5. the VascuQuest package version is distinct from both.

This prevents package release numbers from being mistaken for plugin ABI compatibility.

---

## 17. Standard plugin discovery

Installed plugins are discovered using `importlib.metadata.entry_points()`.

The approved v1 entry-point groups are:

```text
vascuquest.backends
vascuquest.derivations
vascuquest.operators
vascuquest.discovery
vascuquest.exporters
```

Each entry point resolves to one component, component factory, or small provider object documented by the relevant protocol.

VascuQuest must not scan arbitrary directories for Python scripts.

VascuQuest must not auto-install missing plugins during scientific execution.

---

## 18. Built-in components and the same registry

Built-in PWDB backends and built-in scientific components should appear through the same logical registry/descriptor interface as third-party components where practical.

They do not need to be packaged as external plugins.

The purpose is behavioral consistency:

- one way to list components;
- one way to identify versions;
- one way to validate protocol metadata;
- one provenance representation.

The registry itself must stay lightweight and deterministic.

---

## 19. Plugin loading policy

Plugin discovery and plugin import are separate concerns where practical.

Listing installed plugin metadata should avoid importing every heavy scientific package when package metadata is sufficient.

Actual component import/activation may be lazy.

On load failure, VascuQuest must report:

- plugin/entry-point identity;
- distribution/version where known;
- category;
- underlying exception as chained diagnostic information.

One broken optional plugin must not make the core package unusable if that plugin is not required for the requested operation.

---

## 20. Dataset backend protocol

`DatasetBackend` translates a concrete virtual-population dataset into VascuQuest canonical scientific concepts.

It must provide capabilities equivalent to:

```python
identity() -> DatasetIdentity
capabilities() -> CapabilitySet
subjects(...) -> subject identifiers/metadata
get_quantity(request) -> ScientificResult
get_waveform(request) -> Waveform
locations(...) -> canonical locations
geometry(...) -> ScientificResult or canonical geometry result
```

The exact typed request objects are fixed during implementation, but the following semantics are mandatory.

A backend:

- declares the dataset identity it implements;
- returns canonical domain/result types;
- advertises capabilities before expensive access;
- uses the acquisition/artifact layer rather than embedding download logic into scientific result objects;
- retains source provenance;
- does not expose raw storage objects as its stable contract;
- does not implement unrelated research theories.

PWDB record `3275625` is the built-in v1 backend.

---

## 21. Artifact source is not a public plugin category

`ArtifactSource` is an architectural port used for Zenodo, local registrations, and mirrors, but it is **not** a general v1 third-party plugin entry-point category.

Reason:

- arbitrary retrieval plugins expand the security and reproducibility surface;
- v1 already supports canonical Zenodo, local registration, and configured institutional mirrors;
- a stable external acquisition ABI is unnecessary for the initial research goal.

The internal port remains replaceable/testable. A public artifact-source plugin group may be added later only if real deployment requirements justify it.

This is a deliberate simplification relative to making every architectural port a public plugin.

---

## 22. Schema provider is not a free-standing scientific plugin category

The canonical schema is version-controlled by VascuQuest for supported built-in datasets.

A dataset backend plugin may ship the schema mapping needed for its own source, but third-party plugins must not silently override the meaning of an existing canonical quantity.

Schema extension rules are:

1. backend-specific source mappings may be supplied with that backend;
2. operator-scoped quantity definitions may be supplied with that operator;
3. an installed plugin cannot overwrite an existing canonical definition under the same identity;
4. promotion of a quantity into the core canonical schema requires explicit VascuQuest schema review/versioning.

---

## 23. Derivation protocol

A `Derivation` is a deterministic registered scientific transformation.

It must expose metadata equivalent to:

```text
qualified_id
implementation_version
protocol_version
required inputs
output quantity definition
evidence class
parameter definitions/defaults
unit/dimension requirements
location/coordinate requirements
missing-data policy
citations/authoritative definition
validation scope
```

Execution is conceptually:

```python
result = derivation.run(inputs, parameters, context)
```

where:

- `inputs` are canonical `ScientificResult` objects or validated views of them;
- `parameters` are explicit and serializable;
- `context` contains execution/provenance support, not PWDB-specific parser objects.

A derivation must not reach into backend files by filename to obtain undeclared data.

If additional inputs are required, they must be declared so application services can resolve them.

---

## 24. Research operator protocol

A `ResearchOperator` represents an explicit scientific model or algorithm beyond direct source interpretation.

Required descriptor/contract information includes:

```text
qualified_id
implementation_version
protocol_version
required canonical inputs
output quantity definitions or operator-scoped definitions
parameter definitions
units/dimensions
assumptions
admissible/validated domain
citations
evidence class, normally MODELLED
deterministic/random behavior
```

Execution is conceptually:

```python
result = operator.run(inputs, parameters, context)
```

Rules:

1. operator equations remain owned by the operator implementation/documentation;
2. operator outputs do not become `SOURCE` because inputs came from PWDB;
3. the operator may not mutate source-backed inputs;
4. validation/admissibility checks are explicit;
5. random behavior requires explicit seed/random-state provenance when reproducibility is expected;
6. operator-scoped quantities must be namespaced to prevent collisions.

The protocol itself contains no haemodynamic equation.

---

## 25. Discovery method protocol

A `DiscoveryMethod` operates on a defined cohort and canonical scientific inputs.

It must declare, where applicable:

```text
qualified_id
implementation_version
protocol_version
required input quantities/features
parameter definitions
missing-data policy
random behavior
output/result schema
evidence semantics
validation/resampling requirements
```

Execution is conceptually:

```python
result = method.run(cohort, inputs, parameters, context)
```

A discovery method must not silently:

- change the cohort;
- exclude missing subjects without its declared policy;
- claim human causation from virtual-population association;
- relabel deterministic summaries as inferred solely because they were generated by the discovery subsystem.

Exploratory/confirmatory status and validation information must remain inspectable where scientifically relevant.

---

## 26. Result exporter protocol

A `ResultExporter` serializes a VascuQuest scientific result without changing its scientific meaning.

It must declare:

```text
qualified_id
implementation_version
protocol_version
supported result kinds
supported output format(s)
provenance retention behavior
```

Execution is conceptually:

```python
exporter.export(result, destination, options)
```

Rules:

1. exporters do not recompute scientific values unless the conversion is explicitly part of a documented serialization rule;
2. evidence class and provenance must be retained when the target format can represent them;
3. when the target format cannot preserve required metadata, the exporter must either create a sidecar/companion metadata representation or warn/fail according to the export contract;
4. an exporter must not silently reduce units or coordinates to ambiguous unlabeled numbers.

---

## 27. Execution context

Plugins need a small execution context, not unrestricted access to the entire `DatasetSession` implementation.

A public `ExecutionContext` or equivalent may expose only services such as:

- package/runtime version metadata;
- provenance builder hooks;
- deterministic logging/warning channel;
- optional temporary workspace;
- explicit random-state support;
- cancellation/progress callback if later required.

It must not expose:

- private PWDB reader objects;
- mutable global registries;
- CLI parser state;
- arbitrary cache internals.

If a plugin needs additional scientific data, it declares inputs rather than reaching backward through the context.

---

## 28. Request objects

To avoid unstable long function signatures, complex scientific operations should use small immutable request objects where the number of parameters would otherwise become ambiguous.

Examples may include:

- `QuantityRequest`
- `WaveformRequest`
- `DerivationRequest`
- `OperatorRequest`
- `DiscoveryRequest`

A request object should contain only scientific/application inputs, not storage mechanics.

Simple public calls may construct these internally so ordinary users do not need to instantiate them manually.

The implementation must not create a request class for every trivial helper function.

---

## 29. Parameter specification

Scientific method parameters must be explicit and machine-readable.

Each registered method should expose enough parameter metadata to support:

- validation;
- CLI generation/help;
- provenance serialization;
- reproducible re-execution.

Parameter metadata may contain:

```text
name
type/kind
required/default
unit if dimensional
allowed values/range where scientifically defined
description
```

VascuQuest must not invent scientific bounds that the method does not define.

Implementation validation ranges must be distinguished from scientifically validated/admissible domains.

---

## 30. Input requirement specification

Derivations/operators/discovery methods must declare required inputs canonically rather than by source filename or column.

An input requirement may specify:

```text
quantity identity/category
acceptable dimensions/units
required coordinate kinds
required location kind
single-subject/cohort semantics
optional versus required
```

The resolver may satisfy a requirement from `SOURCE`, `RECONSTRUCTED`, or another allowed evidence class only when the method contract permits that input status.

A plugin may restrict acceptable evidence classes when scientifically necessary.

No automatic substitution based only on similar quantity names is permitted.

---

## 31. Capability resolution and plugins

Application services are responsible for resolving declared plugin requirements.

The intended flow is:

```text
user request
  -> selected registered component
  -> validate protocol/version
  -> inspect declared input requirements
  -> resolve canonical inputs through session/backend/derivations
  -> validate units/dimensions/context/evidence constraints
  -> execute component
  -> validate returned result metadata
  -> attach/finalize provenance
  -> return structured result
```

A plugin is therefore not responsible for recursively downloading or discovering undeclared PWDB source files.

---

## 32. Provenance obligations for plugins

When a plugin affects a scientific result, provenance must identify at least:

```text
plugin component qualified_id
plugin implementation version
plugin protocol version
Python distribution name/version when available
input result identities/provenance links
parameters
assumptions when material
citations when scientific
random seed/state when applicable
output evidence class
validation/admissibility information
```

The core provenance service, not each plugin, owns the final serialized provenance format.

Plugins contribute structured provenance facts through the protocol.

This avoids incompatible ad-hoc provenance formats.

---

## 33. Plugin scientific validation boundary

Protocol conformance does not certify scientific correctness.

VascuQuest distinguishes:

1. **protocol-conformant** — the component obeys the technical contract;
2. **scientifically validated** — the method has documented validation evidence appropriate to its claims;
3. **core/built-in** — distributed with VascuQuest, which still does not imply universal scientific validity.

Plugin descriptors may expose validation status/reference metadata, but VascuQuest must not label an arbitrary third-party plugin scientifically validated solely because it imports successfully.

---

## 34. Plugin trust and security

An installed plugin is executable Python code and therefore part of the trusted local environment.

VascuQuest must:

- load only explicitly installed distributions through normal Python packaging mechanisms;
- identify the supplying distribution where possible;
- avoid executing arbitrary scripts passed as scientific-method paths;
- avoid auto-installing plugin packages;
- keep network behavior under plugin control visible/documented where possible, but not pretend it can sandbox arbitrary Python code.

VascuQuest v1 does not attempt process isolation or a Python sandbox.

Such a sandbox would add major complexity without providing reliable security guarantees for arbitrary Python extensions.

---

## 35. Duplicate identifiers and conflict handling

Two active plugin components must not silently share the same `qualified_id` within one category.

On collision, VascuQuest must fail activation or require explicit disambiguation.

Resolution must not depend on environment discovery order.

Built-in component identities are reserved and cannot be silently shadowed by third-party plugins.

---

## 36. Plugin enable/disable behavior

V1 may support configuration-based disabling of installed plugins without uninstalling them.

The default registry should load compatible installed components unless disabled, subject to normal lazy-import behavior.

Disabling a plugin is an operational choice and must cause workflows requiring that plugin to fail explicitly rather than substitute another implementation with the same display name.

---

## 37. Dependency isolation

Third-party plugins may depend on large or specialized packages without forcing those dependencies into the VascuQuest core installation.

A plugin owns its own dependency declarations.

The core package must not add TensorFlow, PyTorch, JAX, Dask, graph databases, symbolic-algebra stacks, or similar heavy dependencies merely to make hypothetical plugins easier.

Optional built-in capabilities may use extras when justified.

---

## 38. Licensing boundary

The Apache-2.0 VascuQuest core must not copy incompatible plugin/upstream source code into the core.

Third-party plugins retain their own licenses.

Plugin metadata should expose distribution identity so users can inspect the installed package and its licensing terms.

An external GPL plugin may be separately installed and invoked according to its own license obligations; its existence does not authorize copying its implementation into the permissive core.

---

## 39. Reproducibility and plugin availability

A saved workflow/provenance record must be able to determine whether its required plugin component/version is available.

Reproduction rules:

- exact implementation version should be preferred for strict reproduction;
- compatible newer versions must not be silently treated as identical when algorithm changes may affect results;
- if exact reproduction is impossible, VascuQuest reports the mismatch and may offer a separate explicit rerun-under-current-version operation;
- the new run receives new provenance.

---

## 40. Determinism and random methods

A component must declare whether it is deterministic for fixed inputs/parameters/environment.

If randomness is used:

- the API must allow an explicit seed or random-state specification where the underlying method supports reproducibility;
- that state must enter provenance;
- plugins must not rely solely on undocumented global random state for reproducible workflows.

Hardware-level nondeterminism, if material, must be documented by the component rather than hidden.

---

## 41. Mutation policy

Plugins receive inputs as logically read-only scientific results.

They must not mutate:

- canonical source artifacts;
- source-backed input arrays in place;
- cohort membership supplied by the caller;
- schema definitions;
- other plugin registry entries.

A plugin may allocate its own working arrays and return new result objects.

The implementation does not require defensive copying of every large array; read-only expectations and tests are sufficient where copying would be wasteful.

---

## 42. Serialization contract

Public metadata needed for plugin interchange and reproducibility must have a portable serialization form.

The initial metadata representation should be JSON-compatible wherever practical:

- strings;
- numbers;
- booleans;
- null;
- lists;
- mappings with string keys.

Large numerical arrays do not need to be serialized through JSON for plugin execution.

The result/export layer may reference or encode arrays separately.

A plugin parameter that cannot be serialized reproducibly must be rejected from reproducible workflows or represented through an explicit stable reference mechanism.

---

## 43. API/CLI parity requirement

Every CLI scientific operation must map onto the public/application API defined here.

The CLI may add:

- argument parsing;
- interactive confirmations for destructive operations;
- progress display;
- human-readable tables;
- shell-oriented output formatting.

The CLI may not add:

- scientific calculations unavailable from Python;
- hidden input substitutions;
- different evidence classification;
- different provenance semantics.

`CLI_CONTRACT.md` will freeze exact command grammar and exit/output behavior.

---

## 44. Introspection API

Researchers must be able to inspect the scientific environment before running a method.

The public API should support operations equivalent to:

```python
vq.plugins.list(kind=None)
vq.plugins.describe(component_id)
session.quantities()
session.capabilities()
```

Plugin descriptions should expose required inputs, outputs, parameters, citations, versions, and validation/admissibility metadata where applicable.

This reduces trial-and-error research workflows.

---

## 45. Explicit non-goals

The v1 API/plugin implementation will not:

- expose one method per PWDB source file;
- make backend readers part of the stable research API;
- create a remote plugin marketplace;
- auto-install missing scientific packages;
- sandbox arbitrary Python extensions;
- support arbitrary script paths as plugins;
- require inheritance from a large framework base class;
- make every architectural port a public plugin category;
- allow plugins to redefine existing canonical quantities silently;
- require one universal array/dataframe library at the protocol boundary;
- infer missing scientific parameters from similarly named source columns;
- put model equations in protocol definitions;
- claim protocol conformance equals scientific validation;
- permit plugin execution to mutate canonical source data.

---

## 46. Implementation invariants

The following rules must remain true in code.

1. `open_dataset()` returns a stable scientific facade, not a raw backend.
2. opening a dataset does not trigger full-dataset acquisition.
3. the public API expresses scientific identities rather than source paths.
4. backend storage types do not leak into stable result contracts.
5. `EvidenceClass` is programmatically inspectable.
6. nontrivial scientific results retain provenance.
7. plugin components have stable qualified identities and implementation versions.
8. plugin protocol compatibility is checked before execution.
9. plugin discovery uses installed Python entry points.
10. arbitrary `.py` paths are not executed as plugins.
11. derivations/operators/discovery methods declare required canonical inputs.
12. plugin methods do not reach into PWDB files to find undeclared inputs.
13. operator-scoped quantities cannot silently shadow canonical quantities.
14. plugins cannot mutate source artifacts or source-backed inputs in place.
15. plugin-supplied scientific results receive the evidence classification appropriate to the actual operation.
16. random-state provenance is retained when reproducibility depends on it.
17. CLI scientific operations use the same application/public implementation path.
18. one broken optional plugin does not prevent unrelated core workflows from running.
19. heavy plugin dependencies remain plugin-owned unless independently justified as core dependencies.
20. no mathematical equation is introduced by the API/plugin framework itself.

---

## 47. Minimal acceptance scenarios

### Scenario A — open and inspect PWDB

```python
session = vq.open_dataset("pwdb:3275625")
session.identity
session.capabilities()
```

Expected behavior:

- no unconditional 44.3 GB download;
- exact canonical identity is visible;
- capabilities are expressed scientifically.

### Scenario B — retrieve source data

```python
p = session.waveform("pressure", subject=..., location=...)
```

Expected behavior:

- result is a `Waveform`/scientific result;
- unit/location/time context is retained;
- evidence is `SOURCE`;
- no WFDB/MAT/HDF5 object leaks into the stable API.

### Scenario C — run a built-in derivation

```python
r = session.derive("vascuquest:<method>", inputs=[p], ...)
```

Expected behavior:

- inputs are canonical;
- method/version/parameters are recorded;
- output evidence follows the derivation definition;
- equations, if any, are owned and tested by that derivation implementation rather than the API layer.

### Scenario D — run an external research operator

An installed package publishes an entry point under `vascuquest.operators`.

Expected behavior:

- component appears in introspection;
- protocol compatibility is validated;
- canonical inputs are resolved;
- output quantity is canonical or operator-scoped;
- plugin/distribution/version/citations/assumptions enter provenance;
- evidence is normally `MODELLED`.

### Scenario E — incompatible plugin

A plugin declares protocol major `2` while the running VascuQuest supports major `1`.

Expected behavior:

- activation fails clearly before scientific execution;
- unrelated core functionality continues to work.

### Scenario F — duplicate plugin ID

Two distributions publish the same component `qualified_id`.

Expected behavior:

- VascuQuest reports a deterministic conflict;
- discovery order does not silently choose a winner.

### Scenario G — missing plugin for reproduction

A provenance record references an operator/version not installed locally.

Expected behavior:

- strict reproduction fails with a `ReproducibilityError`/plugin availability diagnostic;
- VascuQuest does not substitute a different operator silently.

### Scenario H — discovery method with randomness

A discovery plugin uses random initialization.

Expected behavior:

- random state/seed is explicit where supported;
- it enters provenance;
- rerun semantics are defined by the plugin's determinism declaration.

---

## 48. Audit checklist

`API_PLUGIN_CONTRACT.md` passes only if all answers are **yes**.

### Simplicity

- Is the public research API smaller than the internal package structure?
- Are there only five v1 public plugin categories?
- Is standard `importlib.metadata` discovery sufficient?
- Are artifact sources and schema overrides kept out of the public plugin surface unless actually needed?
- Is there no dependency-injection framework, RPC layer, marketplace, sandbox, or custom plugin package manager?

### Completeness

- Can users open datasets, select subjects/cohorts, retrieve quantities/waveforms, derive, model, discover, export, and inspect provenance?
- Can plugins declare identity, version, inputs, outputs, parameters, assumptions, citations, and evidence semantics?
- Can incompatible or broken plugins fail without breaking unrelated workflows?

### Feasibility

- Can the contracts be implemented using ordinary Python protocols/dataclasses/value objects?
- Can plugins remain normal installable Python distributions?
- Can heavy optional dependencies stay outside the core?
- Can large arrays pass through validated scientific results without mandatory copies or serialization into JSON?

### Scientific integrity

- Do plugins consume canonical scientific inputs rather than source filenames?
- Are source, derived, inferred, and modelled results kept distinct?
- Can units/dimensions and admissibility be checked before/after execution?
- Are equations owned by scientific components rather than the interface framework?
- Is protocol conformance explicitly separated from scientific validation?

### Reproducibility

- Are plugin component ID, implementation version, protocol version, inputs, parameters, assumptions, and random state recordable?
- Does strict reproduction reject silent method/version substitution?

### Architecture compatibility

- Does the API avoid leaking HDF5/WFDB/MAT/Zenodo mechanics?
- Does the CLI remain an adapter over this same implementation path?
- Do plugin protocols depend on canonical domain types rather than concrete PWDB readers?

### Extensibility

- Can a new backend, derivation, operator, discovery method, or exporter be added without modifying unrelated core modules?
- Can plugin quantity identities avoid collisions with canonical source quantities?
- Can protocol versions evolve without tying compatibility to the overall package version?

If any answer is no, this file must be amended before proceeding to `CLI_CONTRACT.md`.

---

## 49. Approval consequence

Once this contract passes audit:

- the v1 public Python surface and extension categories are structurally frozen;
- plugin discovery uses standard Python entry points;
- protocol identity/version/provenance rules are fixed;
- exact internal dataclass field ordering and type annotations may be refined during implementation without changing these semantics;
- the next contract is `CLI_CONTRACT.md`.

---

## 50. Implementation restraint rule

When implementing this contract, choose the smallest mechanism that satisfies the defined semantics.

Specifically:

- prefer functions/value objects over manager classes when no persistent behavior is needed;
- prefer `Protocol` over inheritance when only structural behavior is required;
- prefer explicit immutable metadata over hidden global registries;
- prefer one registry with category views over separate complex plugin subsystems;
- prefer application-level input resolution over plugin access to backend internals;
- do not add abstraction layers merely to mirror terminology in this document.

The purpose of the contract is to remove ambiguity from implementation, not to require one Python class for every heading.