"""Common contracts for VascuQuest research-analysis operations.

The analysis layer consumes existing :class:`ScientificResult` objects and
creates new provenance-aware results. It never mutates PWDB, HEMOSPACE, or
Virtual Disease state.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import json
from typing import Any

import numpy as np

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, Waveform
from vascuquest.errors import AdmissibilityError, CapabilityError


def _portable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _portable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_portable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def analysis_provenance_ref(method_id: str, inputs: Iterable[ScientificResult], parameters: Mapping[str, Any] | None = None) -> str:
    """Create a deterministic analysis reference from immutable scientific inputs."""
    refs = []
    for result in inputs:
        if not isinstance(result, ScientificResult):
            raise TypeError("analysis inputs must be ScientificResult objects")
        refs.append({
            "dataset": result.dataset_identity.persistent_identifier,
            "quantity": result.quantity.canonical_name,
            "provenance_ref": result.provenance_ref,
            "subject": None if result.subject is None else result.subject.canonical_subject_id,
            "cohort": None if result.cohort is None else list(result.cohort.canonical_subject_ids),
            "method": result.method_id,
        })
    payload = {
        "method_id": method_id,
        "inputs": refs,
        "parameters": _portable(parameters or {}),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"analysis:{digest}"


def quantity_for(
    template: ScientificResult,
    canonical_name: str,
    *,
    label: str,
    description: str,
    value_kind: str,
    canonical_unit: str | None,
    physical_dimension: str | None,
    evidence: EvidenceClass,
    citations: tuple[str, ...] = (),
) -> QuantityDefinition:
    """Create a derived quantity definition in the template dataset schema."""
    if not isinstance(template, ScientificResult):
        raise TypeError("template must be a ScientificResult")
    return QuantityDefinition(
        canonical_name=canonical_name,
        label=label,
        description=description,
        value_kind=value_kind,
        schema_version=template.dataset_identity.schema_version,
        physical_dimension=physical_dimension,
        canonical_unit=canonical_unit,
        default_evidence=evidence,
        citations=citations,
        applicable_contexts=("research_analysis",),
    )


def make_result(
    template: ScientificResult,
    *,
    canonical_name: str,
    label: str,
    description: str,
    values: object,
    method_id: str,
    inputs: tuple[ScientificResult, ...] | None = None,
    parameters: Mapping[str, Any] | None = None,
    evidence: EvidenceClass = EvidenceClass.DERIVED,
    canonical_unit: str | None = None,
    physical_dimension: str | None = None,
    value_kind: str = "numeric",
    dimensions: tuple[str, ...] = (),
    coordinates: tuple[Coordinate, ...] = (),
    subject: SubjectKey | None | object = ...,
    cohort: Cohort | None | object = ...,
    location: object = ...,
    warnings: tuple[str, ...] = (),
    citations: tuple[str, ...] = (),
) -> ScientificResult:
    """Build an immutable analysis result while preserving VascuQuest identity."""
    input_results = inputs or (template,)
    ensure_same_dataset(*input_results)
    result_subject = template.subject if subject is ... else subject
    result_cohort = template.cohort if cohort is ... else cohort
    result_location = template.location if location is ... else location
    q = quantity_for(
        template,
        canonical_name,
        label=label,
        description=description,
        value_kind=value_kind,
        canonical_unit=canonical_unit,
        physical_dimension=physical_dimension,
        evidence=evidence,
        citations=citations,
    )
    return ScientificResult(
        dataset_identity=template.dataset_identity,
        quantity=q,
        values=values,
        provenance_ref=analysis_provenance_ref(method_id, input_results, parameters),
        dimensions=dimensions,
        coordinates=coordinates,
        source_unit=canonical_unit,
        source_label=label,
        subject=result_subject,
        cohort=result_cohort,
        location=result_location,
        evidence=evidence,
        validity=ValidityState.VALID if not warnings else ValidityState.VALID_WITH_WARNING,
        warnings=warnings,
        method_id=method_id,
    )


def wrap_external(
    *,
    dataset_identity: DatasetIdentity,
    quantity: QuantityDefinition,
    values: object,
    provenance_ref: str,
    dimensions: tuple[str, ...] = (),
    coordinates: tuple[Coordinate, ...] = (),
    subject: SubjectKey | None = None,
    cohort: Cohort | None = None,
    location: object = None,
    evidence: EvidenceClass = EvidenceClass.SOURCE,
    source_unit: str | None = None,
    source_label: str | None = None,
    warnings: tuple[str, ...] = (),
) -> ScientificResult:
    """Explicitly wrap externally supplied research data into VascuQuest.

    This is the only supported raw-data entry point for the v1 analysis stack.
    The caller must provide scientific identity, quantity semantics, units and
    provenance explicitly; anonymous arrays are intentionally insufficient.
    """
    if quantity.schema_version != dataset_identity.schema_version:
        raise AdmissibilityError("external quantity schema_version must match dataset identity")
    if not provenance_ref or provenance_ref != provenance_ref.strip():
        raise ValueError("external provenance_ref must be a non-empty trimmed string")
    return ScientificResult(
        dataset_identity=dataset_identity,
        quantity=quantity,
        values=values,
        provenance_ref=provenance_ref,
        dimensions=dimensions,
        coordinates=coordinates,
        source_unit=source_unit,
        source_label=source_label,
        subject=subject,
        cohort=cohort,
        location=location,
        evidence=evidence,
        validity=ValidityState.NOT_EVALUATED,
        warnings=warnings,
        method_id=None if evidence is EvidenceClass.SOURCE else "vascuquest:analysis:external-wrapper-v1",
    )


def numeric_values(result: ScientificResult, *, finite: bool = True, min_size: int = 1) -> np.ndarray:
    if not isinstance(result, ScientificResult):
        raise TypeError("result must be a ScientificResult")
    try:
        array = np.asarray(result.values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise AdmissibilityError(f"{result.quantity.canonical_name!r} is not a numeric result") from exc
    if array.size < min_size:
        raise AdmissibilityError(f"analysis requires at least {min_size} numeric observations")
    if finite and not np.all(np.isfinite(array)):
        raise AdmissibilityError("analysis inputs must contain only finite numeric values")
    return array


def time_values(waveform: Waveform) -> np.ndarray:
    if not isinstance(waveform, Waveform):
        raise TypeError("waveform must be a Waveform")
    values = np.asarray(waveform.time_coordinate.values, dtype=float)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise AdmissibilityError("waveform time coordinate must be a finite one-dimensional vector")
    if np.any(np.diff(values) <= 0):
        raise AdmissibilityError("waveform time coordinate must be strictly increasing")
    return values


def waveform_values(waveform: Waveform, *, min_size: int = 3) -> np.ndarray:
    values = numeric_values(waveform, min_size=min_size)
    if values.ndim != 1:
        raise AdmissibilityError("waveform analysis requires a one-dimensional signal")
    if values.size != time_values(waveform).size:
        raise AdmissibilityError("waveform values and time coordinate must have identical lengths")
    return values


def ensure_same_dataset(*results: ScientificResult) -> None:
    if not results:
        raise ValueError("at least one result is required")
    first = results[0].dataset_identity
    if any(r.dataset_identity != first for r in results[1:]):
        raise AdmissibilityError("analysis inputs must share the exact dataset identity")


def ensure_same_subject(*results: ScientificResult) -> None:
    ensure_same_dataset(*results)
    subjects = [r.subject for r in results]
    if any(subject is None for subject in subjects):
        raise AdmissibilityError("analysis requires explicit subject identity on every input")
    if any(subject != subjects[0] for subject in subjects[1:]):
        raise AdmissibilityError("analysis inputs must refer to the same canonical virtual subject")


def ensure_same_location(*results: ScientificResult) -> None:
    locations = [r.location for r in results]
    if any(location is None for location in locations):
        raise AdmissibilityError("analysis requires explicit vascular location on every input")
    if any(location != locations[0] for location in locations[1:]):
        raise AdmissibilityError("analysis inputs must refer to the same vascular location")


def ensure_aligned_waveforms(*waveforms: Waveform, atol: float = 1e-12, require_same_location: bool = True) -> np.ndarray:
    if len(waveforms) < 2:
        raise ValueError("at least two waveforms are required")
    ensure_same_subject(*waveforms)
    if require_same_location:
        ensure_same_location(*waveforms)
    reference = time_values(waveforms[0])
    for waveform in waveforms[1:]:
        current = time_values(waveform)
        if current.shape != reference.shape or not np.allclose(current, reference, rtol=0.0, atol=atol):
            raise AdmissibilityError("waveform time coordinates are not aligned; VascuQuest will not silently resample")
    return reference


def cohort_subject_ids(result: ScientificResult) -> tuple[str, ...]:
    if result.cohort is None:
        raise AdmissibilityError("cohort analysis requires a result with explicit Cohort context")
    ids = result.cohort.canonical_subject_ids
    values = np.asarray(result.values)
    if values.ndim == 0 or values.shape[0] != len(ids):
        raise AdmissibilityError("cohort result first dimension must align one-to-one with canonical subject IDs")
    return ids


def ensure_paired(a: ScientificResult, b: ScientificResult) -> tuple[str, ...]:
    ensure_same_dataset(a, b)
    a_ids = cohort_subject_ids(a)
    b_ids = cohort_subject_ids(b)
    if a_ids != b_ids:
        raise AdmissibilityError("paired analysis requires identical canonical subject IDs in identical deterministic order")
    return a_ids


def require_optional_dependency(module: str, extra: str) -> Any:
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:
        raise CapabilityError(f"{module} is required for this operation; install VascuQuest with the [{extra}] extra") from exc


__all__ = [
    "analysis_provenance_ref",
    "cohort_subject_ids",
    "ensure_aligned_waveforms",
    "ensure_paired",
    "ensure_same_dataset",
    "ensure_same_location",
    "ensure_same_subject",
    "make_result",
    "numeric_values",
    "quantity_for",
    "require_optional_dependency",
    "time_values",
    "waveform_values",
    "wrap_external",
]
