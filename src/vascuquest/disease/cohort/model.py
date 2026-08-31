"""Immutable contracts for parameterized Virtual Disease cohort generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import (
    DiseaseCondition,
    DiseaseScalar,
    DiseaseSpecification,
    normalize_parameters,
)
from vascuquest.errors import AdmissibilityError

PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION = "vdc1"
PARAMETERIZED_DISEASE_COHORT_PLANNER_VERSION = "planner1"
STRATIFIED_UNIFORM_SAMPLING = "stratified_uniform_v1"

_SEVERITY_PARAMETER = {
    DiseaseCondition.CAROTID_STENOSIS: "nascet_stenosis",
    DiseaseCondition.ILIAC_STENOSIS: "diameter_stenosis",
    DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM: "maximum_diameter_m",
    DiseaseCondition.LARGE_ARTERY_STIFFENING: "target_cfpwv_m_per_s",
}


def severity_parameter(condition: DiseaseCondition | str) -> str:
    """Return the one disease parameter permitted to vary across a vdc1 cohort."""
    if not isinstance(condition, DiseaseCondition):
        try:
            condition = DiseaseCondition(condition)
        except (TypeError, ValueError) as exc:
            raise AdmissibilityError(f"unknown Virtual Disease condition {condition!r}") from exc
    return _SEVERITY_PARAMETER[condition]


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class ParameterizedDiseaseCohortRequest:
    """One reproducible heterogeneous Virtual Disease cohort request.

    Age bounds filter source-supported PWDB simulation ages; no interpolation is
    implied. Exactly one disease-specific severity parameter varies in vdc1.
    """

    patients: int
    age_min: int
    age_max: int
    condition: DiseaseCondition
    severity_min: float
    severity_max: float
    fixed_parameters: tuple[tuple[str, DiseaseScalar], ...] = ()
    seed: int = 0
    sampling_policy: str = STRATIFIED_UNIFORM_SAMPLING
    contract_version: str = PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.patients, bool) or not isinstance(self.patients, int):
            raise TypeError("patients must be an integer")
        if self.patients < 1:
            raise ValueError("patients must be at least 1")
        for value, name in ((self.age_min, "age_min"), (self.age_max, "age_max")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer number of years")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.age_max < self.age_min:
            raise ValueError("age_max must be >= age_min")
        if not isinstance(self.condition, DiseaseCondition):
            raise TypeError("condition must be a DiseaseCondition")
        severity_min = _finite_float(self.severity_min, "severity_min")
        severity_max = _finite_float(self.severity_max, "severity_max")
        if severity_max < severity_min:
            raise ValueError("severity_max must be >= severity_min")
        if not isinstance(self.fixed_parameters, tuple):
            raise TypeError("fixed_parameters must be a normalized tuple")
        normalized = normalize_parameters(dict(self.fixed_parameters))
        if normalized != self.fixed_parameters:
            raise ValueError("fixed_parameters must be uniquely named and sorted")
        varying = severity_parameter(self.condition)
        if varying in dict(self.fixed_parameters):
            raise AdmissibilityError(
                f"{varying!r} is the cohort severity parameter and must not also "
                "appear in fixed_parameters"
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if self.sampling_policy != STRATIFIED_UNIFORM_SAMPLING:
            raise AdmissibilityError(
                f"unsupported cohort severity sampling policy {self.sampling_policy!r}"
            )
        if self.contract_version != PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION:
            raise AdmissibilityError(
                f"unsupported parameterized cohort contract {self.contract_version!r}"
            )

        # Reuse the frozen disease catalogue for request semantics and units.
        # Subject-specific anatomy/mechanics are checked by the planner via the
        # executable disease transformation.
        for value in (severity_min, severity_max):
            parameters = dict(self.fixed_parameters)
            parameters[varying] = value
            specification(self.condition, parameters)
        if self.condition in {
            DiseaseCondition.CAROTID_STENOSIS,
            DiseaseCondition.ILIAC_STENOSIS,
        } and severity_max >= 1.0:
            raise AdmissibilityError("open-vessel stenosis cohorts require severity_max < 1")

    @classmethod
    def from_mapping(
        cls,
        *,
        patients: int,
        age_min: int,
        age_max: int,
        condition: DiseaseCondition | str,
        severity_min: float,
        severity_max: float,
        fixed_parameters: Mapping[str, object] | None = None,
        seed: int = 0,
    ) -> "ParameterizedDiseaseCohortRequest":
        resolved = condition if isinstance(condition, DiseaseCondition) else DiseaseCondition(condition)
        return cls(
            patients=patients,
            age_min=age_min,
            age_max=age_max,
            condition=resolved,
            severity_min=float(severity_min),
            severity_max=float(severity_max),
            fixed_parameters=normalize_parameters(fixed_parameters),
            seed=seed,
        )

    @property
    def severity_parameter(self) -> str:
        return severity_parameter(self.condition)

    def specification_for(self, severity: float) -> DiseaseSpecification:
        value = _finite_float(severity, "severity")
        if value < self.severity_min or value > self.severity_max:
            raise AdmissibilityError("severity lies outside the requested cohort interval")
        parameters = dict(self.fixed_parameters)
        parameters[self.severity_parameter] = value
        return specification(self.condition, parameters)

    def to_dict(self) -> dict[str, object]:
        return {
            "patients": self.patients,
            "age_min": self.age_min,
            "age_max": self.age_max,
            "condition": self.condition.value,
            "severity_parameter": self.severity_parameter,
            "severity_min": self.severity_min,
            "severity_max": self.severity_max,
            "fixed_parameters": dict(self.fixed_parameters),
            "seed": self.seed,
            "sampling_policy": self.sampling_policy,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ParameterizedDiseaseCohortRequest":
        return cls.from_mapping(
            patients=int(payload["patients"]),
            age_min=int(payload["age_min"]),
            age_max=int(payload["age_max"]),
            condition=str(payload["condition"]),
            severity_min=float(payload["severity_min"]),
            severity_max=float(payload["severity_max"]),
            fixed_parameters=dict(payload.get("fixed_parameters", {})),
            seed=int(payload.get("seed", 0)),
        )


@dataclass(frozen=True, slots=True)
class DiseaseCohortAssignment:
    """One preserved PWDB subject and its exact disease specification."""

    canonical_subject_id: str
    age_years: int
    severity_parameter: str
    severity_value: float
    specification: DiseaseSpecification

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_subject_id, str) or not self.canonical_subject_id.strip():
            raise ValueError("canonical_subject_id must be a non-empty string")
        if isinstance(self.age_years, bool) or not isinstance(self.age_years, int) or self.age_years < 0:
            raise ValueError("age_years must be a non-negative integer")
        if not isinstance(self.severity_parameter, str) or not self.severity_parameter:
            raise ValueError("severity_parameter must be non-empty")
        _finite_float(self.severity_value, "severity_value")
        if not isinstance(self.specification, DiseaseSpecification):
            raise TypeError("specification must be a DiseaseSpecification")
        parameters = self.specification.parameter_mapping()
        if self.severity_parameter not in parameters:
            raise ValueError("assignment specification lacks its severity parameter")
        if not math.isclose(
            float(parameters[self.severity_parameter]),
            float(self.severity_value),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("assignment severity does not match its disease specification")

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_subject_id": self.canonical_subject_id,
            "age_years": self.age_years,
            "severity_parameter": self.severity_parameter,
            "severity_value": self.severity_value,
            "condition": self.specification.condition.value,
            "parameters": dict(self.specification.parameters),
            "preset_version": self.specification.preset_version,
        }


@dataclass(frozen=True, slots=True)
class DiseaseCohortRejection:
    canonical_subject_id: str
    age_years: int
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_subject_id, str) or not self.canonical_subject_id.strip():
            raise ValueError("canonical_subject_id must be a non-empty string")
        if isinstance(self.age_years, bool) or not isinstance(self.age_years, int) or self.age_years < 0:
            raise ValueError("age_years must be a non-negative integer")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_subject_id": self.canonical_subject_id,
            "age_years": self.age_years,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ParameterizedDiseaseCohortPlan:
    """Frozen deterministic plan produced before any disease haemodynamic solve."""

    parent_dataset_identity: DatasetIdentity
    request: ParameterizedDiseaseCohortRequest
    supported_ages: tuple[int, ...]
    assignments: tuple[DiseaseCohortAssignment, ...]
    rejections: tuple[DiseaseCohortRejection, ...] = ()
    planner_version: str = PARAMETERIZED_DISEASE_COHORT_PLANNER_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.parent_dataset_identity, DatasetIdentity):
            raise TypeError("parent_dataset_identity must be a DatasetIdentity")
        if not isinstance(self.request, ParameterizedDiseaseCohortRequest):
            raise TypeError("request must be a ParameterizedDiseaseCohortRequest")
        if not isinstance(self.supported_ages, tuple) or not self.supported_ages:
            raise ValueError("supported_ages must be a non-empty tuple")
        if tuple(sorted(set(self.supported_ages))) != self.supported_ages:
            raise ValueError("supported_ages must be sorted and unique")
        if any(age < self.request.age_min or age > self.request.age_max for age in self.supported_ages):
            raise ValueError("supported_ages must lie inside the requested age interval")
        if not isinstance(self.assignments, tuple) or len(self.assignments) != self.request.patients:
            raise ValueError("assignments must match the requested patient count")
        ids = tuple(item.canonical_subject_id for item in self.assignments)
        if len(ids) != len(set(ids)):
            raise ValueError("assignments must preserve unique canonical subject IDs")
        for item in self.assignments:
            if item.age_years not in self.supported_ages:
                raise ValueError("assignment age must be source-supported")
            if item.specification.condition is not self.request.condition:
                raise ValueError("assignment disease condition must match the request")
            if item.severity_parameter != self.request.severity_parameter:
                raise ValueError("assignment severity parameter must match the request")
            if not self.request.severity_min <= item.severity_value <= self.request.severity_max:
                raise ValueError("assignment severity must lie inside request bounds")
        if not isinstance(self.rejections, tuple):
            raise TypeError("rejections must be a tuple")
        if self.planner_version != PARAMETERIZED_DISEASE_COHORT_PLANNER_VERSION:
            raise ValueError("unsupported parameterized cohort planner version")

    @property
    def canonical_subject_ids(self) -> tuple[str, ...]:
        return tuple(item.canonical_subject_id for item in self.assignments)

    @property
    def run_id(self) -> str:
        encoded = json.dumps(
            self.to_dict(include_run_id=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self, *, include_run_id: bool = True) -> dict[str, object]:
        identity = self.parent_dataset_identity
        payload: dict[str, object] = {
            "format": "vascuquest-parameterized-disease-cohort-plan",
            "format_version": 1,
            "parent_dataset_identity": {
                "dataset_family": identity.dataset_family,
                "record_id": identity.record_id,
                "persistent_identifier": identity.persistent_identifier,
                "schema_version": identity.schema_version,
            },
            "request": self.request.to_dict(),
            "supported_ages": list(self.supported_ages),
            "assignments": [item.to_dict() for item in self.assignments],
            "rejections": [item.to_dict() for item in self.rejections],
            "planner_version": self.planner_version,
            "population_interpretation": "designed_counterfactual_not_epidemiological",
            "evidence": "MODELLED",
            "clinical_validation": False,
        }
        if include_run_id:
            payload["run_id"] = self.run_id
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ParameterizedDiseaseCohortPlan":
        if payload.get("format") != "vascuquest-parameterized-disease-cohort-plan":
            raise ValueError("not a VascuQuest parameterized disease cohort plan")
        identity_payload = dict(payload["parent_dataset_identity"])
        identity = DatasetIdentity(
            dataset_family=str(identity_payload["dataset_family"]),
            record_id=str(identity_payload["record_id"]),
            persistent_identifier=str(identity_payload["persistent_identifier"]),
            schema_version=str(identity_payload["schema_version"]),
        )
        request = ParameterizedDiseaseCohortRequest.from_dict(dict(payload["request"]))
        assignments: list[DiseaseCohortAssignment] = []
        for raw in payload["assignments"]:
            item = dict(raw)
            spec = specification(request.condition, dict(item["parameters"]))
            assignments.append(
                DiseaseCohortAssignment(
                    canonical_subject_id=str(item["canonical_subject_id"]),
                    age_years=int(item["age_years"]),
                    severity_parameter=str(item["severity_parameter"]),
                    severity_value=float(item["severity_value"]),
                    specification=spec,
                )
            )
        rejections = tuple(
            DiseaseCohortRejection(
                canonical_subject_id=str(dict(item)["canonical_subject_id"]),
                age_years=int(dict(item)["age_years"]),
                reason=str(dict(item)["reason"]),
            )
            for item in payload.get("rejections", [])
        )
        plan = cls(
            parent_dataset_identity=identity,
            request=request,
            supported_ages=tuple(int(x) for x in payload["supported_ages"]),
            assignments=tuple(assignments),
            rejections=rejections,
            planner_version=str(
                payload.get("planner_version", PARAMETERIZED_DISEASE_COHORT_PLANNER_VERSION)
            ),
        )
        expected = payload.get("run_id")
        if expected is not None and str(expected) != plan.run_id:
            raise ValueError("parameterized cohort plan run_id does not match its content")
        return plan


__all__ = [
    "DiseaseCohortAssignment",
    "DiseaseCohortRejection",
    "PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION",
    "PARAMETERIZED_DISEASE_COHORT_PLANNER_VERSION",
    "ParameterizedDiseaseCohortPlan",
    "ParameterizedDiseaseCohortRequest",
    "STRATIFIED_UNIFORM_SAMPLING",
    "severity_parameter",
]
