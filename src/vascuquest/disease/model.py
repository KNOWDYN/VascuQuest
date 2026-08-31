"""Immutable contracts for VascuQuest Virtual Disease v1.

This module defines disease specifications, population requests, quantity-status
metadata, and deterministic runtime identities. It deliberately contains no
haemodynamic equations and does not generate disease data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.errors import AdmissibilityError


VIRTUAL_DISEASE_CONTRACT_VERSION = "vd1"
DiseaseScalar = str | int | float | bool | None


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed string")
    return value


def _normalize_scalar(value: object) -> DiseaseScalar:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AdmissibilityError("disease parameters must contain finite numbers")
        return value
    raise AdmissibilityError("Virtual Disease v1 parameters must be JSON scalar values")


def normalize_parameters(
    parameters: Mapping[str, object] | None,
) -> tuple[tuple[str, DiseaseScalar], ...]:
    """Return immutable, name-sorted scalar parameters."""

    if parameters is None:
        return ()
    if not isinstance(parameters, Mapping):
        raise TypeError("parameters must be a mapping or None")
    normalized: list[tuple[str, DiseaseScalar]] = []
    for name in sorted(parameters):
        normalized.append(
            (_required_text(name, "parameter name"), _normalize_scalar(parameters[name]))
        )
    return tuple(normalized)


class DiseaseCondition(str, Enum):
    """Frozen Virtual Disease v1 condition identities."""

    CAROTID_STENOSIS = "carotid_stenosis"
    ILIAC_STENOSIS = "iliac_stenosis"
    FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM = "fusiform_abdominal_aortic_aneurysm"
    LARGE_ARTERY_STIFFENING = "large_artery_stiffening"


class DiseaseQuantityStatus(str, Enum):
    """How one runtime quantity relates to the disease transformation."""

    UNCHANGED_CAUSAL_INPUT = "UNCHANGED_CAUSAL_INPUT"
    MODEL_PARAMETER_MODIFIED = "MODEL_PARAMETER_MODIFIED"
    RECOMPUTED = "RECOMPUTED"
    DERIVED_FROM_RECOMPUTED = "DERIVED_FROM_RECOMPUTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


@dataclass(frozen=True, slots=True)
class DiseaseSpecification:
    """One immutable disease intervention specification.

    The object describes the requested causal intervention only. It never
    contains generated waveforms or other haemodynamic outputs.
    """

    condition: DiseaseCondition
    parameters: tuple[tuple[str, DiseaseScalar], ...] = ()
    preset_version: str = VIRTUAL_DISEASE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.condition, DiseaseCondition):
            raise TypeError("condition must be a DiseaseCondition")
        _required_text(self.preset_version, "preset_version")
        if not isinstance(self.parameters, tuple):
            raise TypeError("parameters must be a normalized tuple")
        names: list[str] = []
        for item in self.parameters:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("parameters must contain (name, value) tuples")
            name, value = item
            names.append(_required_text(name, "parameter name"))
            _normalize_scalar(value)
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("parameters must be uniquely named and sorted")

    @classmethod
    def from_mapping(
        cls,
        condition: DiseaseCondition,
        parameters: Mapping[str, object] | None = None,
        *,
        preset_version: str = VIRTUAL_DISEASE_CONTRACT_VERSION,
    ) -> "DiseaseSpecification":
        return cls(
            condition=condition,
            parameters=normalize_parameters(parameters),
            preset_version=preset_version,
        )

    def parameter_mapping(self) -> dict[str, DiseaseScalar]:
        return dict(self.parameters)


@dataclass(frozen=True, slots=True)
class DiseasePopulationRequest:
    """Selection and intervention request for a future disease population."""

    patients: int
    age_group: int
    specification: DiseaseSpecification
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.patients, bool) or not isinstance(self.patients, int):
            raise TypeError("patients must be an integer")
        if self.patients < 1:
            raise ValueError("patients must be at least 1")
        if isinstance(self.age_group, bool) or not isinstance(self.age_group, int):
            raise TypeError("age_group must be an integer number of years")
        if self.age_group < 0:
            raise ValueError("age_group must be non-negative")
        if not isinstance(self.specification, DiseaseSpecification):
            raise TypeError("specification must be a DiseaseSpecification")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")


@dataclass(frozen=True, slots=True)
class DiseaseRunIdentity:
    """Content-addressed identity for one selected disease-population request."""

    parent_dataset_identity: DatasetIdentity
    canonical_subject_ids: tuple[str, ...]
    request: DiseasePopulationRequest
    contract_version: str = VIRTUAL_DISEASE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.parent_dataset_identity, DatasetIdentity):
            raise TypeError("parent_dataset_identity must be a DatasetIdentity")
        if not isinstance(self.request, DiseasePopulationRequest):
            raise TypeError("request must be a DiseasePopulationRequest")
        if not isinstance(self.canonical_subject_ids, tuple):
            raise TypeError("canonical_subject_ids must be a tuple")
        if len(self.canonical_subject_ids) != self.request.patients:
            raise ValueError("canonical_subject_ids must match the requested patient count")
        seen: set[str] = set()
        for subject_id in self.canonical_subject_ids:
            normalized = _required_text(subject_id, "canonical_subject_id")
            if normalized in seen:
                raise ValueError("canonical_subject_ids must not contain duplicates")
            seen.add(normalized)
        _required_text(self.contract_version, "contract_version")

    @property
    def run_id(self) -> str:
        identity = self.parent_dataset_identity
        payload = {
            "parent_dataset": {
                "dataset_family": identity.dataset_family,
                "record_id": identity.record_id,
                "persistent_identifier": identity.persistent_identifier,
                "schema_version": identity.schema_version,
            },
            "canonical_subject_ids": list(self.canonical_subject_ids),
            "patients": self.request.patients,
            "age_group": self.request.age_group,
            "seed": self.request.seed,
            "condition": self.request.specification.condition.value,
            "parameters": dict(self.request.specification.parameters),
            "preset_version": self.request.specification.preset_version,
            "contract_version": self.contract_version,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "DiseaseCondition",
    "DiseasePopulationRequest",
    "DiseaseQuantityStatus",
    "DiseaseRunIdentity",
    "DiseaseScalar",
    "DiseaseSpecification",
    "VIRTUAL_DISEASE_CONTRACT_VERSION",
    "normalize_parameters",
]
