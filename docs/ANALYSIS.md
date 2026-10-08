# Common research-analysis contract in VascuQuest 1.0

## 1. Purpose

`vascuquest.analysis` is the semantic bridge between existing VascuQuest scientific results and downstream research operations such as statistics, vascular mechanics, spectral/wave analysis, and plotting.

It does not replace `ScientificResult`. It formalizes how analytical code consumes and creates `ScientificResult` objects without losing identity, units, coordinates, evidence, validity, or provenance.

The architectural rule is:

> Analysis consumes existing scientific objects. It does not mutate PWDB, HEMOSPACE, or Virtual Disease state.

## 2. Why an analysis layer is necessary

A generic NumPy array does not tell the researcher:

- which dataset it came from;
- which virtual subjects it represents;
- whether rows are paired;
- what physical quantity/unit it contains;
- where in the arterial network it was measured;
- whether it is SOURCE, RECONSTRUCTED, DERIVED, INFERRED, or MODELLED;
- which method produced it;
- which provenance chain it belongs to.

VascuQuest therefore performs compatibility/alignment checks before extracting anonymous numeric arrays for a mathematical operation.

## 3. `analysis_provenance_ref`

```python
analysis_provenance_ref(method_id, inputs, parameters=None)
```

creates a deterministic SHA-256-based analysis reference from:

- method ID;
- input dataset identifiers;
- quantity names;
- upstream provenance references;
- subject IDs;
- cohort subject lists;
- upstream method IDs;
- normalized method parameters.

The returned reference has the form:

```text
analysis:<sha256>
```

This provides deterministic identity for an analysis step without modifying the upstream provenance records.

## 4. Derived quantity creation

`quantity_for(...)` creates a `QuantityDefinition` in the same schema version as an existing template result.

It records:

- canonical analysis quantity name;
- label/description;
- value kind;
- unit and physical dimension;
- evidence class;
- citations;
- `research_analysis` applicability.

## 5. `make_result`

`make_result(...)` is the standard helper for building immutable downstream results.

It:

1. verifies that all input results share the same exact dataset identity;
2. creates the derived quantity definition;
3. calculates a deterministic analysis provenance reference;
4. preserves subject/cohort/location context from the template unless explicitly overridden;
5. records evidence, method ID, coordinates, warnings, and validity.

Outputs with warnings are marked `VALID_WITH_WARNING`; otherwise the helper marks the result `VALID`.

## 6. Controlled external-data entry

`wrap_external(...)` is the only supported raw/external-data entry point for the v1 analysis stack.

The caller must provide explicitly:

- `DatasetIdentity`;
- `QuantityDefinition`;
- values;
- provenance reference;
- dimensions/coordinates where applicable;
- subject or cohort context where applicable;
- vascular location where applicable;
- evidence class;
- source unit/label;
- warnings.

Anonymous arrays are intentionally insufficient.

For non-`SOURCE` external data, the wrapper identifies the operation as an explicit external-analysis wrapper rather than pretending the values were read directly from PWDB.

## 7. Numeric extraction

`numeric_values(result, finite=True, min_size=1)` converts a `ScientificResult` value payload to a numeric NumPy array only after confirming that the result is numerically admissible for the requested operation.

By default it rejects:

- non-numeric values;
- insufficient observations;
- NaN/infinite values.

Methods that legitimately need missing/non-finite values must define a different explicit handling rule rather than inheriting silent coercion.

## 8. Time-coordinate extraction

`time_values(waveform)` requires:

- a `Waveform` object;
- finite one-dimensional time coordinates;
- at least two time points;
- strictly increasing time.

`waveform_values(...)` additionally requires one-dimensional signal values and exact length agreement between signal and time coordinate.

## 9. Dataset compatibility

`ensure_same_dataset(*results)` requires exact `DatasetIdentity` equality.

Results from different source/model dataset identities cannot be combined silently merely because their quantity names or subject numbers match.

A deliberate cross-dataset comparison requires an explicit study design/adapter rather than bypassing the identity contract.

## 10. Subject compatibility

`ensure_same_subject(*results)` requires:

- exact dataset identity;
- explicit subject context on every input;
- identical canonical subject identity.

This is used by local multi-waveform operations.

## 11. Location compatibility

`ensure_same_location(*results)` requires explicit identical vascular location on all inputs.

This is necessary for definitions such as local pressure-area compliance and pressure-flow impedance.

Cross-site methods must explicitly disable the same-location requirement only when their scientific definition allows cross-site signals.

## 12. Waveform alignment

`ensure_aligned_waveforms(*waveforms, atol=1e-12, require_same_location=True)` requires:

- at least two waveforms;
- same canonical virtual subject;
- same vascular location by default;
- identical time-coordinate shapes;
- numerical equality of time coordinates within the declared absolute tolerance.

Critical rule:

> VascuQuest will not silently resample misaligned waveforms.

Cross-site spectral methods may set `require_same_location=False` while retaining same-subject/time alignment.

## 13. Cohort subject identity

`cohort_subject_ids(result)` requires:

- explicit `Cohort` context;
- first result dimension in one-to-one correspondence with the cohort's canonical subject IDs.

This prevents a summary vector with unknown row semantics from being treated as a valid cohort endpoint.

## 14. Paired analysis

`ensure_paired(a, b)` requires:

- same dataset identity;
- explicit cohort context for both inputs;
- identical canonical subject-ID tuples;
- identical deterministic order.

Same vector length is not sufficient.

This rule is central to healthy↔disease comparisons.

## 15. Optional dependencies

`require_optional_dependency(module, extra)` provides explicit capability failure with installation guidance.

For example:

- SciPy/PyWavelets → `research` extra;
- Matplotlib → `plot` extra.

VascuQuest does not silently replace a missing optional scientific dependency with a different implementation.

## 16. Individual analysis pattern

For one virtual subject:

```text
ScientificResult / Waveform
        ↓
compatibility checks
        ↓
mechanics or spectral operation
        ↓
new ScientificResult
```

The output keeps the same subject and location context unless the scientific operation deliberately changes the context.

## 17. Cohort analysis pattern

For a cohort endpoint:

```text
ScientificResult(values[N], cohort=...)
        ↓
cohort_subject_ids
        ↓
qualified stats
        ↓
ScientificResult(statistic/diagnostic)
```

The cohort identity must remain available throughout the operation.

## 18. Healthy/disease paired pattern

```text
healthy cohort result
        +
matched disease cohort result
        ↓
ensure_paired
        ↓
paired statistical/model-response analysis
```

The result is a statistical/derived statement about a modelled counterfactual experiment, not a clinical treatment effect.

## 19. External comparison-data pattern

An external experimental/clinical dataset can participate only after an explicit wrapper defines its own dataset identity and scientific quantity semantics.

VascuQuest does not force external observations to pretend they are PWDB subjects. Cross-dataset comparison requires an explicit higher-level research design rather than exact-dataset alignment functions.

## 20. Evidence behavior

`make_result` defaults to `DERIVED` for research-analysis outputs.

This does not overwrite the evidence class of inputs. A derived statistic from modelled inputs remains traceable to those modelled inputs through the analysis provenance reference.

## 21. Validity behavior

Analysis helpers use VascuQuest validity states independently of evidence.

Typical behavior:

- no warnings → `VALID`;
- declared scientific warning → `VALID_WITH_WARNING`;
- invalid alignment/domain → explicit exception before producing a result.

## 22. Non-goals

The common analysis layer does not:

- implement every statistical method;
- infer missing clinical variables;
- automatically merge different datasets;
- guess subject correspondence;
- silently convert units not supported by the method;
- silently resample waveforms;
- run the disease solver;
- change upstream evidence or source identity;
- replace the full provenance subsystem.

It exists to keep research analytics scientifically connected to VascuQuest's established object model.
