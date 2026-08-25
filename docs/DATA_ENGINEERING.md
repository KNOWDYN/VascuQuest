# VascuQuest Data Engineering Contract

**Status:** Implementation contract, subject only to the mandatory empirical ingestion spike defined below  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Dataset DOI:** `10.5281/zenodo.3275625`  
**Purpose:** Define how VascuQuest identifies, acquires, verifies, registers, reads, caches, and exposes the canonical PWDB source data without modifying or re-hosting it, while keeping concrete large-file storage decisions empirical.

---

## 1. Objective

VascuQuest must make the PWDB ageing dataset usable as a research substrate without forcing researchers to understand its historical archive layout or to download all 44.3 GB before doing useful work.

The data engineering layer therefore has five responsibilities:

1. identify the exact canonical source artifacts for Zenodo record `3275625`;
2. acquire only the artifacts required for a requested capability;
3. verify that every source artifact is the expected canonical file before it is trusted;
4. expose source data through the PWDB backend without changing scientific meaning;
5. maintain a strict boundary between immutable upstream source data and all VascuQuest-created caches, indexes, conversions, and research products.

This contract intentionally does **not** prescribe a permanent internal representation for the multi-gigabyte path data. That decision remains gated by the empirical ingestion spike.

---

## 2. Authoritative source

For VascuQuest v1, the only canonical source dataset is:

- **Zenodo record:** `3275625`
- **DOI:** `10.5281/zenodo.3275625`
- **Dataset:** Pulse Wave Database (PWDB): a database of arterial pulse waves representative of healthy adults
- **Canonical record URL:** `https://zenodo.org/records/3275625`

The record reports 4,374 virtual subjects and provides pressure (`P`), flow velocity (`U`), luminal area (`A`), and photoplethysmogram (`PPG`) waves in MATLAB, CSV, and WFDB representations, together with subject/model metadata, haemodynamic parameters, pulse-wave indices, geometry, onset times, and path-resolved data.

No other Zenodo record is assumed equivalent.

The authoritative upstream record is the source of truth for artifact identity. VascuQuest may keep a version-controlled manifest derived from that record, but the manifest must preserve the upstream artifact names, byte sizes where recorded, and checksums exactly.

---

## 3. Canonical artifact manifest

The v1 manifest must contain the following 16 artifacts from Zenodo record `3275625`.

| Artifact | Reported size | Upstream MD5 |
|---|---:|---|
| `geo.zip` | 7.4 MB | `4b1fba2da497094e6ad71fcee14b0f7e` |
| `pwdb_data.mat` | 701.7 MB | `3bd22caacaa7d7a83b3a04c71e1b2d49` |
| `pwdb_data_w_aorta_brain_path.mat` | 8.2 GB | `132c52b9962d83bfa672ff2bc96de6ac` |
| `pwdb_data_w_aorta_finger_path.mat` | 8.2 GB | `801dbfc7927dc951a87034ebb40ff12f` |
| `pwdb_data_w_aorta_foot_path_a.mat` | 5.9 GB | `01f6f7c079ccbd245d44996ad95ff58f` |
| `pwdb_data_w_aorta_foot_path_p.mat` | 5.9 GB | `58a5bfc5eeeb6584652c8238eceba73c` |
| `pwdb_data_w_aorta_foot_path_u.mat` | 5.9 GB | `bc00c1cc9c9ddef5d5070123be4b0f44` |
| `pwdb_data_w_aorta_rsubclavian_path.mat` | 8.2 GB | `85052a34c42b847af397e42bd6300fc7` |
| `pwdb_haemod_params.csv` | 927.1 kB | `43e1244665e6cee6b77501102404b70a` |
| `pwdb_model_configs.csv` | 556.8 kB | `8c3b4f2f86386b72250766aedea9db52` |
| `pwdb_model_variations.csv` | 95.2 kB | `3f1987efbc131b2cab8e576807385d5b` |
| `pwdb_onset_times.csv` | 1.3 MB | `1103ddc3852d6f2164b981582fad8d23` |
| `pwdb_pw_indices.csv` | 19.7 MB | `87946898d39d5a6d894901ad39f6b546` |
| `PWs_csv.zip` | 242.8 MB | `81067f96d6078bbbb5cd9fce5d73f5bd` |
| `PWs_mat.zip` | 683.9 MB | `50c03268de6ae2484367a881f92eaa3d` |
| `PWs_wfdb.zip` | 185.0 MB | `c4c3c3ba8163ee1f4f1495d7a4e70d73` |

The manifest is data, not executable code. It should be stored as a machine-readable package resource and validated during tests.

Required manifest fields per artifact are:

```text
artifact_id
filename
canonical_record_id
canonical_doi
role
reported_size_bytes (when available from authoritative metadata)
checksum_algorithm
checksum_value
source_locator
container_format
compression (if any)
capabilities_provided
required_for (optional convenience metadata)
```

Human-readable sizes may be displayed, but byte-level sizes from authoritative metadata should be used for strict validation when available.

---

## 4. Artifact roles

The 16 source artifacts are grouped by scientific/data role rather than by file extension.

### 4.1 Subject/model tables

- `pwdb_model_configs.csv`
- `pwdb_model_variations.csv`
- `pwdb_haemod_params.csv`
- `pwdb_onset_times.csv`
- `pwdb_pw_indices.csv`

These are the preferred source for lightweight metadata-first exploration when the requested quantity is available in them.

### 4.2 Common-site waveform archives

- `PWs_csv.zip`
- `PWs_mat.zip`
- `PWs_wfdb.zip`

These are alternative upstream representations of common-site waveform data. VascuQuest must not assume numerical equivalence until cross-representation validation confirms the expected tolerances and metadata semantics.

A v1 operation should use the lightest validated representation capable of satisfying the request, subject to user configuration and installed optional format support.

### 4.3 Unified MATLAB representation

- `pwdb_data.mat`

This is a rich source containing multiple logical data classes. It is important for schema archaeology and may be a useful source for capabilities not adequately represented in lightweight tables/archives.

It is not automatically the preferred runtime source merely because it is comprehensive.

### 4.4 Subject-specific geometry

- `geo.zip`

Geometry is a first-class scientific capability. It must not be treated as incidental metadata.

### 4.5 Path-resolved waveform data

- `pwdb_data_w_aorta_brain_path.mat`
- `pwdb_data_w_aorta_finger_path.mat`
- `pwdb_data_w_aorta_foot_path_a.mat`
- `pwdb_data_w_aorta_foot_path_p.mat`
- `pwdb_data_w_aorta_foot_path_u.mat`
- `pwdb_data_w_aorta_rsubclavian_path.mat`

These are the dominant storage burden and enable spatially resolved research. They must remain supported by the architecture even if their production access strategy differs from smaller artifacts.

The official PWDB export code conditionally saves oversized path datasets using MATLAB v7.3, which is HDF5-backed. VascuQuest may exploit HDF5-style selective access where the real files confirm it works reliably, but this is an empirical conclusion to be verified by the ingestion spike rather than assumed universally.

---

## 5. Capability-driven acquisition

Users request scientific capabilities; they do not request historical archive filenames unless using explicit low-level inspection tools.

The PWDB backend maps canonical capabilities to the minimum sufficient source artifacts.

Conceptually:

```text
scientific request
    -> canonical capability requirements
    -> backend artifact plan
    -> local verified artifact available?
         yes -> use it
         no  -> registered source available?
                  yes -> verify/use it
                  no  -> online source allowed?
                           yes -> acquire required artifact only
                           no  -> fail with explicit availability information
```

Examples of capability classes include:

- subject/model configuration;
- model variations;
- haemodynamic parameters;
- pulse-wave indices;
- onset times;
- common-site waveforms;
- geometry;
- specific path-resolved wave families.

The exact mapping from individual canonical scientific quantities to artifacts belongs in the machine-readable backend schema/capability map and will be refined after the ingestion spike.

### 5.1 No hidden full-dataset acquisition

No metadata, query, inspection, or small-waveform operation may trigger unconditional acquisition of all 16 artifacts.

A command or API call that would require a multi-gigabyte artifact must be able to report that requirement before beginning the download.

### 5.2 Explicit acquisition is also supported

Users may proactively request artifacts or capability bundles for offline work, but bundles must remain transparent about which canonical artifacts they contain and their expected total size.

---

## 6. Source acquisition protocol

### 6.1 Manifest-first resolution

The software must resolve source artifacts from the packaged canonical manifest, not construct download URLs from filename conventions alone.

The upstream record API may be queried to validate or refresh source locators, but v1 scientific reproducibility must not depend on silently accepting a changed artifact under the same logical identity.

### 6.2 Streaming downloads

Downloads must stream to disk rather than buffering complete artifacts in memory.

For large files, the downloader must:

1. write to a temporary/incomplete path;
2. update checksum state while streaming where practical;
3. flush/close the file before verification;
4. verify the authoritative checksum;
5. atomically promote the verified file into the source cache;
6. remove or quarantine failed incomplete artifacts.

### 6.3 Resume behaviour

Resumable downloads are highly desirable for the 5.9–8.2 GB path files.

The implementation may use HTTP range requests only after the upstream behaviour is tested. If safe resume is unsupported or cannot be validated, VascuQuest must restart the download rather than concatenate uncertain byte ranges.

Resume capability is therefore a required ingestion-spike test, not an unverified promise.

### 6.4 Network independence after acquisition

Once required artifacts are present and verified locally, normal scientific reads must not make hidden network calls.

An explicit offline mode must prohibit network acquisition and produce a clear missing-capability/artifact error instead.

---

## 7. Integrity model

### 7.1 Canonical verification

The authoritative Zenodo record supplies MD5 checksums. VascuQuest must use those values for canonical artifact verification because they are the upstream-published identity checksums.

MD5 here is an **integrity identifier supplied by the source**, not a claim of cryptographic security against a malicious publisher.

### 7.2 Verification states

A source artifact must have an explicit state such as:

```text
missing
present_unverified
verified
checksum_failed
unreadable
```

Only `verified` canonical source artifacts may be used silently for scientific operations.

A registered external artifact may be inspected before verification, but scientific use must either verify it against the canonical manifest or require an explicit noncanonical workflow outside the v1 canonical-backend guarantees.

### 7.3 Reverification

VascuQuest should not hash multi-gigabyte files on every access.

A verified-artifact record may cache verification metadata. Reverification is required when material file metadata changes, the user requests verification, cache metadata is absent/inconsistent, or integrity is otherwise uncertain.

The exact local verification-record format is an implementation detail, but it must never replace the canonical checksum stored in the manifest.

---

## 8. Source registration and mirrors

### 8.1 Existing local copies

Researchers who already hold PWDB files must be able to register a directory without copying the files into a VascuQuest-managed cache.

Registration must:

- discover recognized canonical filenames;
- verify them against the manifest before canonical use;
- record the location separately from canonical identity;
- tolerate partial datasets;
- report which capabilities are available and which remain missing.

Registration must not modify source files.

### 8.2 Institutional mirrors

A user or institution may configure a mirror/source root.

Mirror use must preserve:

- canonical record identity;
- canonical artifact filenames/IDs;
- checksum verification;
- provenance identifying the canonical dataset and, separately, the retrieval source where useful.

A mirror is a transport/location choice, not a new scientific dataset version.

### 8.3 Source precedence

The initial resolution policy should be deterministic:

1. explicitly registered canonical local source;
2. verified VascuQuest source cache;
3. configured institutional mirror;
4. canonical Zenodo source, when online acquisition is allowed.

User configuration may select among valid sources, but VascuQuest must never silently choose an unverified artifact because it is closer or faster.

---

## 9. Persistence classes and directory separation

The implementation must maintain separate namespaces for:

```text
source/        immutable verified upstream artifacts or references
work/          temporary/incomplete acquisition and extraction state
derived/       indexes, optimized representations, reusable derived data
results/       user-requested research outputs
state/         manifests, verification records, registrations, cache metadata
```

The exact platform-specific root directories are deferred to implementation, but should follow normal user cache/data conventions rather than writing into the installed Python package.

Important rules:

1. canonical source files are never overwritten by derived products;
2. extraction output is not mistaken for the canonical archive itself;
3. derived stores are namespaced by scientifically material identities;
4. temporary files can be deleted without destroying canonical source identity;
5. user results are not evicted merely because a cache-clean command is run.

---

## 10. Archive extraction

ZIP archives are source containers, not trusted filesystem layouts.

Extraction must defend against path traversal and must reject archive members that escape the intended destination.

Where practical, readers should avoid extracting a complete archive when direct access or selective extraction is demonstrably simpler and reliable. This is a performance/implementation choice, not a scientific requirement.

If extraction is used:

- it occurs outside the immutable canonical archive;
- extracted contents are treated as derived/access-cache material unless independently listed as canonical Zenodo artifacts;
- extraction is repeatable and invalidated when the source archive checksum changes;
- partial extraction cannot be reported as complete.

---

## 11. Format adapters

VascuQuest must keep source-format mechanics inside the PWDB backend/data adapters.

### 11.1 CSV

CSV readers must preserve source column names for traceability while mapping them through the canonical schema.

Parsing must define explicitly:

- subject identifier interpretation;
- numeric conversion policy;
- missing-value handling;
- column ordering irrelevance where possible;
- source units and canonical units.

No scientific meaning may be inferred solely from column position when a named field is available.

### 11.2 WFDB

WFDB reading should use a maintained Python WFDB implementation rather than a home-grown binary parser unless a documented incompatibility makes that impossible.

The adapter must validate:

- record identity;
- signal names;
- sample frequency metadata;
- units;
- subject mapping;
- signal length/missing-sample behaviour.

The final dependency choice belongs to implementation planning, but binary format reimplementation is not a project goal.

### 11.3 MATLAB files below v7.3

MATLAB readers must be selected based on the real source format and structures observed during the ingestion spike.

The adapter must convert historical MATLAB structs/cells only at the backend boundary and expose canonical Python/domain objects upward.

### 11.4 MATLAB v7.3 / HDF5-backed files

Large path files must be tested for selective, bounded-memory access.

VascuQuest must not first deserialize an 8 GB file into a giant Python object merely to retrieve one subject/path slice if the HDF5 structure permits selective reads.

No permanent HDF5 object or storage-library type may leak into the stable scientific API.

### 11.5 Geometry

Geometry parsing must preserve the source network/segment identity needed to relate geometry to subjects, sites, paths, and waveforms.

The geometry adapter must not invent three-dimensional coordinates, curvature, torsion, or other anatomical information not actually present in the source.

---

## 12. Subject and cross-artifact alignment

Cross-file joins are scientifically critical and must never rely on casual row-number assumptions without validation.

The ingestion spike and schema audit must establish:

- canonical subject identifier range and encoding;
- whether each artifact covers all 4,374 simulations or a subset;
- whether subject ordering is identical across representations;
- whether any archive/file embeds its own subject identifier;
- how age groups and baseline/variation configurations map to subject IDs;
- how geometry files map to subject IDs;
- how common-site and path-resolved signals map to subject IDs;
- how plausibility information is represented and joined.

Once established, the mapping becomes a tested backend invariant.

If a source artifact lacks an explicit identifier and alignment is inferred from authoritative generation/export logic, that inference must be documented in the schema/provenance rather than hidden.

---

## 13. Scientific schema boundary

Data engineering parses source structures; the canonical scientific schema interprets them.

The backend therefore retains both:

```text
source identity/field/unit
canonical identity/meaning/unit
```

Known upstream metadata defects are corrected only in the canonical semantic layer. The raw file and raw metadata remain inspectable.

A source reader may perform lossless representation normalization, such as converting a numeric MATLAB vector to a NumPy-compatible array, without changing the evidence class from `SOURCE`.

A scientific calculation, unit conversion with material semantic consequence, reconstruction, filtering, interpolation, resampling, derivative, or statistical transformation must be represented explicitly in the appropriate scientific layer/provenance rather than disguised as parsing.

---

## 14. Local derived research store

VascuQuest may construct local indexes or optimized data representations when they demonstrably improve repeated research workflows.

Such products are **not canonical source data**.

Every derived store must be reproducibly tied to at least:

- canonical dataset record/version;
- source artifact checksum(s);
- VascuQuest schema version;
- conversion/index builder version;
- material conversion parameters.

A derived store must be rebuildable from verified canonical artifacts.

### 14.1 No mandatory conversion in the architecture

The v1 architecture does not require that all users convert PWDB into Zarr, Parquet, HDF5, Arrow, or any other common format before use.

The ingestion spike may justify one or more optional/recommended optimized stores, but direct validated access must remain possible where practical.

### 14.2 Cache invalidation

A derived artifact must not be reused when any identity that materially affects its contents changes.

At minimum this includes relevant source checksum, schema version, and builder/algorithm version.

---

## 15. Memory model

Data access must be bounded by the requested scientific operation, not by total dataset size.

Rules:

- metadata tables may be loaded eagerly if measured sizes make that reasonable;
- waveform/path access should support per-subject, per-site, per-signal, or other natural slicing where the source allows it;
- iterators/batches may be used for cohort-scale computations;
- arrays should not be copied merely to satisfy architectural purity;
- source-backed arrays must not be mutated in place;
- a user-requested materialization of a large cohort must be explicit enough that its memory cost is not surprising.

No numeric memory threshold is invented here. Representative thresholds and warnings must follow measured ingestion-spike results.

---

## 16. Concurrency and locking

The data layer must tolerate two local VascuQuest processes attempting to acquire or build the same artifact.

Minimum requirements:

- downloads/builds use temporary paths;
- final promotion is atomic on supported local filesystems;
- a second process must not treat an incomplete file as verified;
- derived-store builders must avoid concurrent destructive writes;
- stale temporary/lock state must be recoverable.

A lightweight filesystem locking approach is sufficient. A database server or distributed lock service is explicitly unnecessary for v1.

---

## 17. Failure behaviour

Failures must be specific and recoverable where possible.

### Missing artifact

Report the capability and exact artifact(s) required, with expected size when known. Do not silently download in offline mode.

### Checksum mismatch

Never use the artifact as canonical source. Keep it quarantined or remove it safely and report the expected and observed checksum.

### Interrupted download

Retain only clearly marked incomplete state. Never rename it to the canonical cache path until verification succeeds.

### Unsupported source structure

Fail with a source-format/schema error identifying the artifact and observed structure. Do not guess field meanings.

### Partial registered dataset

Open successfully if the requested operation is supported by available verified artifacts; advertise unavailable capabilities explicitly.

### Corrupted derived cache

Discard/rebuild the derived artifact when safe. Never discard the canonical source merely because a derived store is invalid.

### Network failure

Preserve any verified local data and report acquisition failure separately from scientific capability of already-local artifacts.

---

## 18. Mandatory empirical ingestion spike

The ingestion spike is the final gate before production source-reader/storage choices are frozen.

It must use real artifacts from Zenodo record `3275625`, not synthetic approximations alone.

### 18.1 Required representative sources

The spike must exercise at minimum:

1. `pwdb_model_configs.csv` or another representative metadata CSV;
2. at least one common-site WFDB record from `PWs_wfdb.zip`;
3. representative geometry from `geo.zip`;
4. `pwdb_data.mat`;
5. at least one bounded slice from one large `pwdb_data_w_*_path.mat` file.

Where useful, `PWs_csv.zip` or `PWs_mat.zip` should also be inspected to establish cross-representation equivalence and practical trade-offs.

### 18.2 Measurements

For each tested source, record:

- canonical artifact name and checksum;
- operating system;
- Python version;
- relevant library versions;
- local filesystem type where material;
- artifact open/initialization time;
- representative first-access latency;
- representative repeated-access latency;
- peak/resident memory estimate for representative operations;
- actual hierarchy/shape/dtype structure;
- subject/site/signal/path indexing semantics;
- unit metadata observed;
- missing/NaN/padding behaviour;
- whether selective/lazy reads are real or only apparent;
- whether archive extraction is required;
- failure behaviour for incomplete or malformed reads.

The spike is an engineering benchmark, not a publication benchmark. Measurements need to be sufficient to choose robust access strategies, not statistically overengineered.

### 18.3 Required scientific consistency checks

The spike must establish, where overlapping representations permit:

- subject identity consistency;
- signal/site naming consistency;
- sampling-frequency consistency;
- unit consistency or documented discrepancy;
- representative numerical equivalence within justified tolerances;
- geometry-to-subject alignment;
- path-to-subject alignment.

No tolerance may be invented merely to make a test pass. Tolerances must follow representation precision, documented conversion behaviour, or measured round-trip differences.

### 18.4 Required large-file questions

Before the production path backend is frozen, answer empirically:

1. Are the large path MAT files consistently MATLAB v7.3/HDF5?
2. What is their actual internal group/dataset/reference structure?
3. Can one subject/path/signal slice be read without loading the whole file?
4. What is the minimum reliable Python reader stack?
5. Does access require dereferencing MATLAB object references in a way that materially changes performance?
6. Is direct source access adequate for common research queries?
7. If not, what optimized local representation yields a measured benefit large enough to justify its complexity and disk cost?
8. Does the source support reliable resumable HTTP acquisition for these files?

### 18.5 Spike decision outcomes

After the spike, each source class receives one of three production decisions:

```text
DIRECT       read canonical artifact directly
INDEXED      read canonical artifact with a lightweight local index
CONVERTED    build a versioned local optimized representation for practical access
```

`CONVERTED` must be justified by measured evidence. It must never mean replacing the canonical Zenodo artifact or re-hosting a modified dataset.

The spike results should be recorded in a separate implementation report or issue. They do not require rewriting this contract unless they contradict a rule rather than merely selecting an allowed strategy.

---

## 19. Initial capability-to-artifact strategy

Before the ingestion spike, the following is an **intentional provisional strategy**, not a frozen optimization plan.

| Research need | Preferred source class before benchmarking | Reason |
|---|---|---|
| subject/model exploration | relevant CSV tables | small, transparent, selective acquisition |
| haemodynamic parameter exploration | `pwdb_haemod_params.csv` | dedicated small source |
| pulse-wave index exploration | `pwdb_pw_indices.csv` | dedicated source |
| onset-time exploration | `pwdb_onset_times.csv` | dedicated source |
| common-site waveform access | WFDB or other validated common-site archive | benchmark/readability dependent |
| geometry | `geo.zip` contents | dedicated geometry source |
| rich combined inspection | `pwdb_data.mat` | comprehensive source where needed |
| spatial/path research | corresponding path MAT artifact | only canonical source class for that capability |

If empirical evidence shows a different source representation is materially more reliable or efficient while scientifically equivalent, the backend may choose it without changing the public scientific API.

---

## 20. Data-management API responsibilities

Exact signatures are deferred to `API_PLUGIN_CONTRACT.md`, but the data layer must support application-level operations equivalent to:

- inspect canonical dataset identity/manifest;
- report local artifact/capability status;
- acquire a required artifact or capability;
- verify one/all available artifacts;
- register an existing local dataset directory;
- configure/inspect a mirror;
- remove derived/temp cache safely;
- remove canonical cached copies only through an explicit destructive operation;
- report disk usage by persistence class;
- enter offline mode;
- explain why a requested scientific capability is unavailable.

These operations must remain usable from both Python and the CLI through shared services.

---

## 21. Reproducibility requirements

Any scientific result that depends on source data must be able to identify the canonical artifacts actually used.

At minimum, source provenance includes:

```text
dataset family
Zenodo record id
DOI
artifact filename/id
canonical checksum algorithm/value
schema version
subject/cohort/site/path selection where applicable
```

Retrieval location is operational metadata; canonical identity is scientific provenance.

A result obtained from an institutional mirror and the same verified canonical bytes obtained from Zenodo should retain the same canonical dataset/artifact identity.

---

## 22. Data privacy and clinical-data scope

PWDB record `3275625` contains simulated/virtual-subject research data, not patient-identifiable clinical records.

Therefore v1 does not require a patient-data security subsystem, identity management, de-identification pipeline, or regulated clinical data store.

Future backends containing human-subject data would require a separate design/security amendment and must not inherit this assumption silently.

---

## 23. Explicit non-goals

The v1 data engineering implementation will not:

- mirror or republish the 44.3 GB canonical dataset;
- bundle canonical PWDB artifacts in the wheel;
- require users to download all artifacts;
- rewrite canonical source files in place;
- invent missing anatomical dimensions or variables;
- assume all MATLAB files share one internal format;
- require a database server;
- require a cloud object store;
- require a permanent Zarr/Parquet/DuckDB/xarray representation before benchmarking;
- implement a bespoke WFDB binary format unless unavoidable;
- promise resumable large-file downloads before testing upstream range behaviour;
- silently substitute another PWDB Zenodo record;
- use unverified registered files as canonical truth.

---

## 24. Data engineering implementation invariants

The following must remain true throughout implementation:

1. canonical source identity is manifest-driven;
2. every canonical artifact used scientifically is checksum-verified;
3. source artifacts are immutable;
4. incomplete downloads cannot occupy verified canonical paths;
5. cache cleanup cannot silently delete user research results;
6. partial local datasets are valid and advertise only their available capabilities;
7. normal lightweight queries do not force path-file downloads;
8. source-format objects do not leak into the stable domain API;
9. known source metadata defects are handled in the semantic schema, not by editing source files;
10. cross-artifact subject alignment is tested, not casually assumed;
11. large-file access remains bounded-memory where the source representation permits it;
12. optimized local representations remain reproducibly tied to canonical checksums and schema/builder versions;
13. offline scientific operations make no hidden network calls;
14. mirrors do not alter canonical scientific identity;
15. no storage technology is promoted from provisional to mandatory before the ingestion spike supplies evidence.

---

## 25. Audit checklist

`DATA_ENGINEERING.md` passes only if all answers are **yes**.

### Source fidelity

- Does it identify Zenodo `3275625` as the sole v1 canonical source?
- Does the manifest match the authoritative 16-artifact record?
- Are canonical source bytes preserved unchanged?
- Are checksums treated as source identity/integrity rather than silently replaced?

### Scientific integrity

- Is parsing separated from scientific derivation?
- Are source and canonical semantic metadata both traceable?
- Is subject/cross-artifact alignment explicitly validated?
- Does geometry parsing avoid inventing unavailable anatomy?

### Feasibility

- Can small research workflows run without 44.3 GB acquisition?
- Can large files be streamed to disk rather than RAM?
- Are bounded-memory reads required where source format permits them?
- Is a local single-process implementation sufficient?

### Simplicity

- Is there no mandatory data server, cloud store, workflow engine, or universal conversion pipeline?
- Are derived stores introduced only when measured benefit justifies them?
- Is one canonical manifest sufficient to drive acquisition/verification?

### Robustness

- Are partial downloads, checksum failures, partial registrations, archive traversal, and corrupt derived caches handled explicitly?
- Are source, work, derived, result, and state data kept distinguishable?
- Can concurrent local runs avoid mistaking incomplete data for complete data?

### Architecture compatibility

- Does the PWDB backend own source-format knowledge?
- Do domain/services remain free of Zenodo filenames and HDF5/WFDB implementation details?
- Are Python and CLI data operations routed through shared services?

### Empirical discipline

- Are permanent storage/chunking choices still deferred?
- Is the ingestion spike specific enough to close those decisions with real evidence?
- Are numerical equivalence tolerances required to be justified rather than guessed?

If any answer is no, this file must be amended before proceeding to `SCIENTIFIC_MODEL.md`.

---

## 26. Approval consequence

Once this contract passes audit:

- canonical source identification, acquisition, integrity, registration, cache boundaries, failure semantics, and ingestion-spike requirements are frozen for v1;
- concrete production reader/storage technology for the large path files remains provisional until the mandatory spike is complete;
- the next contract is `SCIENTIFIC_MODEL.md`.

---

## 27. Upstream references

- Zenodo canonical record: `https://zenodo.org/records/3275625`
- Zenodo REST API documentation: `https://developers.zenodo.org/`
- Official PWDB algorithms repository: `https://github.com/peterhcharlton/pwdb`
- Official PWDB project: `https://peterhcharlton.github.io/pwdb/`

These references document the upstream data and mechanisms. VascuQuest's machine-readable manifest and schema remain version-controlled so scientific workflows do not depend on live documentation pages remaining unchanged.