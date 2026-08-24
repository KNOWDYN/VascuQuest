# VascuQuest CLI Contract

**Status:** Command-line interface contract for implementation  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`, `SCIENTIFIC_MODEL.md`, `API_PLUGIN_CONTRACT.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Freeze the v1 command grammar, output-channel rules, machine-readable behavior, exit-code semantics, destructive-operation safeguards, and Python-API parity required for a reliable research CLI without introducing CLI-only science.

---

## 1. Objective

The VascuQuest CLI is a thin command-line adapter over the same application services and scientific API used from Python.

It must support four practical researcher workflows:

1. inspect and prepare the canonical dataset;
2. query source scientific information;
3. run registered derivations, research operators, and discovery methods;
4. export and reproduce results in automation-safe form.

The CLI must remain small enough to learn from `vascuquest --help` and deterministic enough to use safely in shell scripts and reproducible research pipelines.

The CLI must not contain scientific equations, independently parse PWDB source files, or implement calculations unavailable from the Python API.

---

## 2. Framework choice

V1 uses **Typer** as the command-line adapter.

This is an implementation choice, not a scientific or public-data dependency. The stable contract is the command grammar and behavior defined here.

Rules:

- Typer may perform argument parsing, help generation, shell completion, and command dispatch;
- Typer types must be converted into VascuQuest application/domain request objects before scientific execution;
- no Typer object may leak into the scientific API, plugin protocols, domain layer, or provenance model;
- replacement of Typer in a future release is permitted if the stable CLI behavior remains compatible.

V1 does not add a second CLI framework or a custom parser abstraction around Typer.

---

## 3. Executable and invocation

The installed command is:

```text
vascuquest
```

The package should also support:

```text
python -m vascuquest
```

when practical, with equivalent command behavior.

Global help and version are:

```text
vascuquest --help
vascuquest --version
```

`--version` reports the VascuQuest package version only. Dataset, schema, and plugin versions are reported by the relevant inspection commands.

---

## 4. Command design rules

The CLI follows these rules throughout v1.

1. Commands use lowercase kebab-case names.
2. Scientific identifiers remain canonical machine identifiers; display labels are presentation only.
3. Dataset identity is explicit whenever ambiguity could exist.
4. One option has one meaning across commands.
5. Destructive behavior is never hidden behind a normally read-only command.
6. Machine-readable output is deterministic and free of progress decoration.
7. Scientific calculations are delegated to application services/API methods.
8. Plugin methods are invoked by stable `qualified_id`, not by filesystem path.
9. A command that may require a multi-gigabyte acquisition must reveal that requirement before acquisition begins.
10. No command invents scientific defaults that are absent from the registered method/schema.

---

## 5. V1 command surface

The approved v1 command tree is intentionally compact.

```text
vascuquest
├── dataset
│   ├── info
│   ├── status
│   ├── register
│   ├── acquire
│   ├── verify
│   └── clean
├── subjects
├── quantities
├── locations
├── get
├── waveform
├── derive
├── model
├── discover
├── plugins
│   ├── list
│   └── describe
├── export
└── reproduce
```

No additional top-level v1 command should be created unless it represents a genuinely distinct application capability that cannot be expressed clearly through this tree.

---

## 6. Dataset selection

The canonical v1 dataset identifier is:

```text
pwdb:3275625
```

Commands that operate on a dataset accept:

```text
--dataset pwdb:3275625
```

V1 may default to `pwdb:3275625` because it is the only canonical built-in dataset, but the resolved dataset identity must remain visible in structured output and provenance.

A short alias such as `pwdb` may be accepted only if it resolves unambiguously to the canonical record.

No CLI command may silently reinterpret another PWDB release as `3275625`.

---

## 7. Global operational options

The following options should be available consistently where applicable:

```text
--dataset <id>
--source <registered-source-name-or-path>
--offline
--format <text|json|jsonl|csv>
--output <path>
--quiet
--debug
```

Not every command must expose every option.

Semantics:

- `--offline` forbids network acquisition;
- `--format` selects presentation/serialization only and must not alter scientific computation;
- `--output` writes the primary result to a file instead of standard output when supported;
- `--quiet` suppresses nonessential human diagnostics, not requested scientific data;
- `--debug` enables chained diagnostic detail/tracebacks on standard error.

Scientific method parameters are command-specific and are normalized to the serializable parameter mapping defined in `API_PLUGIN_CONTRACT.md`.

---

## 8. Standard output and standard error

The channel contract is strict.

### `stdout`

Standard output contains only the requested primary command result.

Examples:

- human-readable table/text in default text mode;
- valid JSON object/array in `--format json` mode;
- valid JSON Lines records in `--format jsonl` mode;
- CSV data in `--format csv` mode.

### `stderr`

Standard error contains operational information:

- progress;
- warnings;
- download notices;
- acquisition-size notices;
- confirmation prompts where interactive;
- recoverable diagnostics;
- error messages;
- debug tracebacks when requested.

A progress bar, warning, citation notice, or download message must never corrupt JSON/JSONL/CSV written to `stdout`.

---

## 9. Output format rules

### 9.1 Text

`text` is the default for interactive use.

Text output may use terminal-aware formatting but must remain understandable without color.

Color must never encode the only representation of scientific state.

### 9.2 JSON

`json` is the preferred machine-readable representation for one bounded result or metadata object.

It must be valid JSON with stable semantic keys.

Large numeric arrays need not be embedded when doing so would be impractical. In those cases the command must use a supported export representation or explicitly documented external/sidecar array reference.

### 9.3 JSON Lines

`jsonl` is intended for iterable collections such as subjects, quantities, locations, or row-oriented discovery output.

Each line must be an independent valid JSON object.

### 9.4 CSV

`csv` is supported only where the result is naturally tabular and can retain unambiguous column identities/units through headers or companion metadata.

A command must reject `--format csv` when the result cannot be represented faithfully rather than flattening scientific structure ambiguously.

### 9.5 Format support is explicit

Each command documents the formats it supports. Unsupported format/command combinations are usage errors.

---

## 10. Structured-output envelope

Machine-readable scientific outputs must preserve the semantics defined by the public result contract.

A JSON scientific result should expose an envelope equivalent to:

```text
kind
quantity or result identity
dataset identity
evidence class
unit/dimensional metadata
subject/cohort/location context
values or value reference
coordinates where applicable
validity/admissibility
warnings
provenance
```

Exact field spelling will be shared with the public serialization implementation and tests; the CLI must not maintain a separate scientific JSON schema.

Metadata-only commands may use simpler schemas.

---

## 11. `dataset info`

Purpose: inspect canonical dataset identity and static manifest-level information.

Conceptual usage:

```text
vascuquest dataset info
vascuquest dataset info --format json
```

It reports at least:

- dataset family;
- canonical record ID;
- DOI;
- schema version;
- artifact count;
- canonical artifact inventory summary;
- canonical-data licence/citation information when available through package metadata.

It must not download the full dataset.

---

## 12. `dataset status`

Purpose: report local availability and verification state.

Conceptual usage:

```text
vascuquest dataset status
vascuquest dataset status --format json
```

It reports:

- registered/local source locations in non-sensitive normalized form;
- canonical artifact states (`missing`, `present_unverified`, `verified`, `checksum_failed`, `unreadable`);
- available scientific capabilities;
- missing capability requirements;
- source/derived/result-store disk use where available.

A status command is read-only and must not initiate large acquisition.

---

## 13. `dataset register`

Purpose: register an existing local canonical source directory without copying it.

Conceptual usage:

```text
vascuquest dataset register /path/to/pwdb
```

Rules:

- recognized canonical artifacts are discovered by the manifest;
- canonical use requires checksum verification;
- partial datasets are valid;
- source files are never modified;
- the command reports available/missing capabilities after registration;
- registration identity is operational metadata and does not redefine canonical dataset identity.

The command fails clearly when no recognized artifact is found.

---

## 14. `dataset acquire`

Purpose: explicitly acquire canonical source artifacts or capability bundles.

Conceptual usage:

```text
vascuquest dataset acquire --artifact pwdb_model_configs.csv
vascuquest dataset acquire --capability common-waveforms
vascuquest dataset acquire --capability path:aorta-brain
```

The exact capability IDs come from the backend capability registry rather than being hard-coded independently in the CLI.

Before downloading a multi-gigabyte artifact, the command must report:

- artifact/capability requested;
- artifact filenames;
- expected total size when known;
- destination/cache context.

Interactive execution requests confirmation for large acquisition unless `--yes` is supplied.

Non-interactive execution without a TTY must not hang waiting for confirmation; it fails with a clear instruction to use `--yes` when confirmation is required.

Acquired source artifacts are not considered canonical-ready until checksum verification succeeds.

---

## 15. `dataset verify`

Purpose: verify registered/cached source artifacts against the canonical manifest.

Conceptual usage:

```text
vascuquest dataset verify
vascuquest dataset verify --artifact <artifact-id>
```

The command reports expected/observed state and checksum status.

A checksum mismatch is never downgraded to a warning followed by scientific use.

Verification may be I/O-expensive for large files; progress belongs on `stderr`.

---

## 16. `dataset clean`

Purpose: remove VascuQuest-managed temporary or derived cache material.

Conceptual usage:

```text
vascuquest dataset clean --derived
vascuquest dataset clean --temporary
```

Rules:

- default cleaning does not delete user research outputs;
- registered external source files are never deleted;
- canonical cached source copies require an explicit source-removal option plus confirmation;
- destructive actions support `--yes` for controlled automation;
- the command prints a deletion plan before confirmation in interactive mode.

There is no generic `clean --all` shortcut that silently destroys source and results together.

---

## 17. `subjects`

Purpose: inspect/select virtual-subject metadata without loading large waveform/path data.

Conceptual usage:

```text
vascuquest subjects
vascuquest subjects --where age=55
vascuquest subjects --where age=55 --where plausibility=<canonical-value>
vascuquest subjects --format jsonl
```

`--where` is a simple repeated field comparison mechanism over validated canonical subject attributes.

V1 does **not** introduce a full expression language.

The initial selector supports equality and a small set of typed comparison operators only if implementation remains unambiguous. More complex filtering belongs in Python until justified.

Missing-value policy must be explicit whenever the filter could otherwise silently exclude subjects.

---

## 18. `quantities`

Purpose: list/describe canonical quantities available in the opened dataset/schema.

Conceptual usage:

```text
vascuquest quantities
vascuquest quantities --category haemodynamic_parameter
vascuquest quantities --format jsonl
```

Output may include:

- canonical quantity ID;
- label/description;
- category;
- canonical unit;
- dimensionality;
- contexts/locations;
- source availability;
- known source-semantic notes where material.

The command does not compute all quantities merely to list definitions.

---

## 19. `locations`

Purpose: inspect canonical sites, segments, paths, and path positions supported by the backend.

Conceptual usage:

```text
vascuquest locations --kind site
vascuquest locations --kind path
```

Location kinds remain scientifically distinct.

The command must not collapse a measurement site into an arterial segment merely because a mapping exists.

---

## 20. `get`

Purpose: retrieve a canonical non-waveform scientific quantity.

Conceptual usage:

```text
vascuquest get <quantity-id> --subject <id>
vascuquest get <quantity-id> --where age=55
vascuquest get <quantity-id> --location <canonical-location-id>
```

Rules:

- quantity identity is canonical;
- subject/cohort selection is explicit;
- location is explicit where scientifically required;
- missing required capability produces a capability error describing the artifact needed;
- evidence/provenance are retained in structured output;
- the CLI does not silently substitute a similarly named quantity.

---

## 21. `waveform`

Purpose: retrieve a canonical source or registered waveform result.

Conceptual usage:

```text
vascuquest waveform pressure --subject <id> --location <site-id>
```

A waveform request must identify the subject and scientifically required location.

Output retains:

- signal identity;
- samples/value reference;
- time/sampling context;
- unit;
- location;
- evidence class;
- provenance.

Plotting is not a required v1 CLI command. Researchers may export data or use Python visualization. This avoids adding a plotting subsystem before it is required.

---

## 22. `derive`

Purpose: execute a registered deterministic derivation.

Conceptual usage:

```text
vascuquest derive <qualified-id> [selection/input options] --param name=value
```

Rules:

- the derivation is resolved through the component registry;
- required inputs are resolved canonically by application services;
- repeated `--param name=value` values are parsed against the registered parameter specification;
- unspecified parameters use only registered defaults;
- unknown parameters fail before execution;
- method identity/version and normalized parameters enter provenance;
- the CLI contains no derivation equation.

`--help` for the generic command may show common options; method-specific requirements are available through plugin/component description and validation errors. V1 does not dynamically generate a permanent subcommand for every installed method.

---

## 23. `model`

Purpose: execute a registered research operator.

Conceptual usage:

```text
vascuquest model <qualified-id> [selection/input options] --param name=value
```

Rules mirror `derive`, with additional operator semantics:

- assumptions and admissibility metadata remain visible;
- outputs are normally `MODELLED` unless the operator declares and justifies another classification;
- out-of-domain results are not silently presented as fully validated;
- operator equations remain owned by the operator implementation, never the CLI.

---

## 24. `discover`

Purpose: execute a registered discovery method on an explicit cohort/input space.

Conceptual usage:

```text
vascuquest discover <qualified-id> --where age=55 --param name=value
```

Rules:

- cohort definition is preserved;
- missing-data policy comes from explicit user/method configuration, not CLI defaults hidden from provenance;
- random seed/state is accepted through registered parameters when supported;
- exploratory/confirmatory and validation information remain visible where applicable;
- statistical outputs are not converted into causal human claims by CLI wording.

---

## 25. `plugins list`

Purpose: inspect available built-in and installed extension components.

Conceptual usage:

```text
vascuquest plugins list
vascuquest plugins list --kind operator
vascuquest plugins list --format jsonl
```

It reports at least:

- kind;
- qualified ID;
- implementation version;
- protocol version;
- supplying distribution/version where available;
- load/compatibility state.

Listing should avoid importing heavy plugin implementations where package metadata permits.

---

## 26. `plugins describe`

Purpose: inspect one registered component before execution.

Conceptual usage:

```text
vascuquest plugins describe <qualified-id>
```

It exposes, where applicable:

- component identity/version;
- required inputs;
- output definitions;
- parameter specifications/defaults;
- assumptions;
- citations;
- evidence semantics;
- admissibility/validation scope;
- deterministic/random behavior.

This is the primary CLI mechanism for researchers to understand a method before running it.

---

## 27. `export`

Purpose: serialize a previously obtained result or a result reference through a registered exporter.

Conceptual usage:

```text
vascuquest export <result-or-provenance-reference> --format <export-format> --output <path>
```

Where shell chaining is practical, commands may also support direct `--output` on the producing command so users are not forced to persist an intermediate registry entry.

Rules:

- export does not alter scientific values;
- evidence/provenance are retained or written to a companion metadata file when the target cannot hold them;
- ambiguous lossy export requires explicit user choice or fails;
- result exporter plugins are identified in output provenance/metadata when they materially affect representation.

V1 does not require a persistent global result database merely to support `export`.

---

## 28. `reproduce`

Purpose: execute or validate a saved VascuQuest provenance/workflow specification.

Conceptual usage:

```text
vascuquest reproduce <provenance-or-workflow-file>
```

Rules:

- required dataset/schema/component identities and versions are checked before execution where possible;
- strict reproduction does not silently replace unavailable plugin/method versions;
- missing source artifacts are reported before acquisition and remain subject to normal acquisition policy;
- a rerun under changed versions is a distinct explicit operation with new provenance;
- provenance documents are data, not executable Python scripts.

---

## 29. Selection syntax

The CLI intentionally avoids a bespoke scientific query language in v1.

Simple filtering uses repeated structured conditions such as:

```text
--where field=value
```

If comparison operators are implemented, the accepted grammar must be deliberately small and documented, for example canonical forms equivalent to:

```text
field=value
field!=value
field>value
field>=value
field<value
field<=value
```

String parsing must use schema-defined data types.

No Python `eval`, arbitrary expressions, SQL fragments, or executable predicates are accepted.

Complex cohort construction remains available through the Python API until a real need justifies richer CLI syntax.

---

## 30. Method parameter syntax

Registered method parameters use repeated:

```text
--param name=value
```

The application layer validates the value against the component's `ParameterSpecification`.

Rules:

- booleans, integers, floats, strings, enum-like values, and explicitly supported simple lists may be accepted;
- dimensional values must use the unit conventions defined by the parameter specification;
- unknown parameters fail;
- duplicate scalar parameters fail unless the specification explicitly permits repeated/list values;
- CLI parsing never invents scientific parameter ranges/defaults;
- normalized parameter values enter provenance exactly as executed.

For complex parameter structures, a method may support:

```text
--params-file <json-file>
```

JSON is sufficient for v1; YAML is not required merely for convenience.

---

## 31. Interactive versus automated execution

The CLI must behave predictably in both terminals and pipelines.

### Interactive mode

When attached to a TTY, the CLI may:

- show progress;
- request confirmation before large downloads/destructive actions;
- use terminal formatting.

### Non-interactive mode

When no TTY is available:

- no command waits indefinitely for input;
- confirmation-requiring actions fail unless `--yes` is explicitly supplied;
- machine output remains clean;
- progress may be suppressed or written to `stderr` only.

No scientific result depends on whether execution is interactive.

---

## 32. Large-download safeguard

V1 defines a large acquisition operationally as an acquisition for which the backend/data layer marks confirmation as advisable based on artifact size/policy.

The CLI contract does **not** invent a fixed scientific threshold.

For a large acquisition, the CLI must display expected size and obtain confirmation in interactive mode unless `--yes` is supplied.

This mechanism is operational protection only; it does not alter capability resolution or source identity.

---

## 33. Warnings

Warnings fall into two categories.

### Operational warnings

Examples: cache state, slow verification, optional plugin failure.

These go to `stderr`.

### Scientific warnings

Examples: out-of-domain operator use, limited validation scope, missing-data policy consequences.

These must be retained in `ScientificResult`/provenance and may also be summarized on `stderr` in human mode.

`--quiet` may suppress the duplicate human summary but must not remove scientific warning metadata from the result.

---

## 34. Exit codes

V1 uses a small stable exit-code map.

| Code | Meaning |
|---:|---|
| `0` | success |
| `2` | CLI usage/argument/parameter syntax error |
| `3` | dataset/source/capability unavailable or acquisition failure |
| `4` | source integrity/checksum failure |
| `5` | schema/unit/selection/scientific-input validation failure |
| `6` | scientific admissibility or numerical-method failure |
| `7` | plugin load/compatibility/identity failure |
| `8` | reproducibility/version mismatch failure |
| `70` | unexpected VascuQuest internal software failure |

Rules:

- an expected user/scientific error must not return `70` merely because a low-level library raised an exception;
- the CLI maps the public exception hierarchy to these codes centrally;
- plugin-specific exceptions are translated into the closest stable VascuQuest category;
- signal/keyboard interruption follows normal platform/shell behavior rather than being redefined as a scientific exit code.

---

## 35. Error rendering

Default error output must include:

- concise error class/category;
- actionable message;
- relevant dataset/component/artifact identity;
- recovery hint when known.

Default execution must not dump an internal traceback for ordinary expected failures.

`--debug` enables chained traceback/diagnostic context on `stderr`.

Machine-readable error mode may be added if needed, but v1 does not require a second error-serialization framework. Exit code plus `stderr` is sufficient for shell automation; structured success output remains on `stdout`.

---

## 36. Progress behavior

Progress reporting is permitted only for operations where it materially helps, such as:

- downloading;
- checksum verification;
- archive extraction;
- long cohort computations.

Rules:

- progress goes to `stderr`;
- progress is disabled or simplified when not attached to a terminal;
- progress output never changes scientific computation;
- the CLI does not estimate scientific confidence from progress indicators.

---

## 37. Logging

The CLI is not a substitute for a logging framework visible to ordinary users.

Default output should remain concise.

`--debug` may expose diagnostic logging useful for developers.

The core scientific API must not depend on CLI logging configuration.

No telemetry or remote logging is enabled by default.

---

## 38. Shell completion

Shell completion may be provided through Typer's supported mechanisms.

Completion is an ergonomic feature only.

It must not require network access or import every heavy plugin just to complete ordinary static command/option names.

Dynamic completion for plugin/quantity IDs is optional and should be implemented only if it remains fast and side-effect free.

---

## 39. Citation visibility

Scientific methods and dataset usage may require citations.

The CLI must make citations discoverable through dataset/component inspection and structured provenance.

It need not print a full bibliography after every command.

This avoids clutter while retaining reproducibility and attribution.

---

## 40. Security boundaries

The CLI must never execute arbitrary Python supplied through:

- `--plugin` file paths;
- selection expressions;
- parameter expressions;
- provenance/workflow files.

Plugins come only from installed distributions through the approved entry-point registry.

Workflow/provenance files are declarative data interpreted against registered operations.

Archive and download safety remain governed by `DATA_ENGINEERING.md`.

---

## 41. Cross-platform requirements

The CLI must work on supported Windows, macOS, and Linux Python environments.

Rules:

- use `pathlib`/platform-safe path handling internally;
- do not require POSIX shell tools for core operations;
- machine-readable output uses explicit UTF-8 handling where file encoding matters;
- commands must not assume `/tmp`, `/home`, Unix path separators, or shell-specific quoting in core logic;
- examples may show POSIX-style paths, but tests must cover Windows path semantics where relevant.

---

## 42. Scientific-language discipline

CLI wording must preserve the scientific model.

It must use terms such as:

- virtual subject;
- source quantity;
- derived result;
- modelled result;
- inferred result;
- measurement site;
- arterial segment;
- arterial path/path position;
- physiological plausibility;

according to their defined meanings.

It must not relabel virtual subjects as patients, call model predictions measurements, or call virtual-population associations human causal effects.

No mathematical equation is defined or reformulated by CLI help text.

---

## 43. API/CLI parity matrix

Every scientific CLI operation maps to an existing application/API capability.

| CLI | API/application equivalent |
|---|---|
| `dataset info/status` | dataset/session identity/status services |
| `dataset register` | `register_source(...)` |
| `dataset acquire/verify/clean` | data-management services |
| `subjects` | `session.subjects(...)` / selection service |
| `quantities` | `session.quantities()` |
| `locations` | location/capability inspection |
| `get` | `session.get(...)` |
| `waveform` | `session.waveform(...)` |
| `derive` | `session.derive(...)` |
| `model` | `session.model(...)` |
| `discover` | `session.discover(...)` |
| `plugins list/describe` | plugin registry introspection |
| `export` | `session.export(...)` / exporter service |
| `reproduce` | `session.reproduce(...)` / reproduction service |

A CLI command may not bypass this mapping to gain access to backend internals.

---

## 44. Explicit non-goals

V1 CLI will not:

- provide one command per PWDB source file;
- expose HDF5/MAT/WFDB internal paths as normal scientific arguments;
- include a built-in SQL shell;
- include a custom expression language;
- include arbitrary Python evaluation;
- auto-install plugins;
- execute plugin files by path;
- add a plotting subsystem before required;
- create dynamic permanent subcommands for every installed scientific method;
- require interactive prompts for normal read-only science;
- place progress messages in machine-readable stdout;
- hide evidence class or scientific warnings in structured results;
- silently perform full-dataset acquisition;
- silently choose method versions during reproduction;
- define or modify scientific equations.

---

## 45. Implementation invariants

The following must remain true in code.

1. `vascuquest` is the single installed CLI entry point.
2. Typer exists only in the CLI/interface layer.
3. CLI command functions perform parsing/dispatch/rendering, not scientific calculations.
4. all scientific commands use shared application/API services.
5. stdout contains only primary requested output.
6. diagnostics/progress/prompts go to stderr.
7. JSON/JSONL/CSV output cannot be corrupted by terminal decoration.
8. dataset identity is canonical and visible in structured results/provenance.
9. large downloads are never hidden behind lightweight inspection commands.
10. non-interactive commands never block on an unseen prompt.
11. destructive actions require explicit intent.
12. registered external methods are addressed by qualified component ID.
13. scientific parameters are validated against registered parameter specifications.
14. CLI parsing does not invent scientific defaults/ranges.
15. method equations remain outside the CLI.
16. evidence and validity semantics match Python results.
17. exit-code mapping is centralized and stable.
18. debug tracebacks are opt-in.
19. no arbitrary Python evaluation occurs in filters/params/workflows.
20. the CLI remains cross-platform without external shell-tool dependencies.

---

## 46. Minimal acceptance scenarios

### A. Fresh installation, metadata inspection

```text
vascuquest dataset info
```

Expected: dataset identity/manifest summary; no full dataset download.

### B. Partial local source registration

```text
vascuquest dataset register /research/pwdb
vascuquest dataset status
```

Expected: recognized files verified, partial capabilities reported, no file modification.

### C. Automation-safe subjects output

```text
vascuquest subjects --where age=55 --format jsonl
```

Expected: one valid JSON object per line on stdout; warnings/progress absent from stdout.

### D. Missing waveform artifact

```text
vascuquest waveform pressure --subject <id> --location <site-id> --offline
```

Expected: explicit capability/source error with required artifact; exit `3`; no hidden network call.

### E. Run operator

```text
vascuquest model example:operator --subject <id> --param alpha=...
```

Expected: parameters validated from descriptor, canonical inputs resolved, operator executed through application services, `MODELLED` result/provenance returned; CLI owns no equation.

### F. Incompatible plugin

```text
vascuquest model incompatible:operator ...
```

Expected: compatibility error before science; exit `7`.

### G. Machine-readable error isolation

A command using `--format json` encounters a checksum error.

Expected: no malformed partial JSON is mixed with error text; error appears on stderr; exit `4`.

### H. Destructive clean in CI

```text
vascuquest dataset clean --derived
```

without a TTY and where confirmation is required.

Expected: fail rather than hang; instruct use of `--yes`.

---

## 47. Audit checklist

`CLI_CONTRACT.md` passes only if every answer is **yes**.

### Simplicity

- Is the top-level command set compact?
- Is there one CLI framework and no parser abstraction layer?
- Are complex query languages, SQL shells, plotting subsystems, and dynamic method subcommands avoided?

### Completeness

- Can researchers inspect/acquire/verify data, inspect subjects/quantities/locations, retrieve data, run derivations/operators/discovery, inspect plugins, export, and reproduce?
- Can partial/offline environments be used explicitly?
- Are destructive and large-download operations controlled?

### Feasibility

- Can every command be implemented with Typer plus existing application services?
- Does machine output work in pipes without terminal corruption?
- Can Windows/macOS/Linux be supported without shell-specific dependencies?

### Scientific integrity

- Are evidence, provenance, units, locations, cohorts, and validity preserved?
- Does CLI wording maintain virtual-subject/source/model distinctions?
- Are method parameters driven by registered definitions rather than CLI guesses?
- Are there no equations in CLI code/help that redefine scientific methods?

### Automation

- Are stdout/stderr roles deterministic?
- Are exit codes stable and small in number?
- Can non-interactive execution avoid prompts/hangs?
- Is structured output deterministic and parseable?

### Architecture/API compatibility

- Does every scientific command map to shared API/application functionality?
- Are backend formats/storage hidden?
- Is Typer isolated to the interface layer?
- Are plugin methods invoked through the registry rather than imported by path?

If any answer is no, this file must be amended before `TEST_VALIDATION_CONTRACT.md`.

---

## 48. Approval consequence

Once this contract passes audit:

- the v1 command grammar is frozen;
- stdout/stderr and machine-output behavior are frozen;
- exit-code categories are frozen;
- selection and method-parameter syntax are frozen at their intentionally small v1 scope;
- Typer is approved as the v1 adapter without entering scientific layers;
- exact help prose and cosmetic terminal formatting may evolve without changing semantics;
- the next contract is `TEST_VALIDATION_CONTRACT.md`.

---

## 49. Implementation restraint

The CLI exists to expose the research API, not to become a second application.

During implementation:

- one command function should normally translate CLI arguments into one application request and render one result;
- shared parsing helpers are acceptable only for truly repeated behavior;
- no `cli/utils.py` dumping ground should emerge;
- no command should open PWDB files directly;
- no feature is added merely because Typer can support it;
- scientific correctness and automation stability take precedence over decorative terminal behavior.
