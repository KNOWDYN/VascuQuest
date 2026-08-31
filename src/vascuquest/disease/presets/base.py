"""Preset descriptor contracts for Virtual Disease v1.

Descriptors declare parameter names and admissible scalar forms only. They do
not contain disease equations or execute haemodynamic transformations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import math

from vascuquest.errors import AdmissibilityError

from ..model import DiseaseCondition, DiseaseScalar, DiseaseSpecification


class DiseaseParameterKind(str, Enum):
    TEXT = "text"
    NUMBER = "number"


@dataclass(frozen=True, slots=True)
class DiseaseParameterSpec:
    """One scalar disease-preset parameter contract."""

    name: str
    kind: DiseaseParameterKind
    description: str
    required: bool = True
    allowed_values: tuple[DiseaseScalar, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    default: DiseaseScalar = None
    has_default: bool = False

    def __post_init__(self) -> None:
        for value, field_name in ((self.name, "name"), (self.description, "description")):
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field_name} must be a non-empty trimmed string")
        if not isinstance(self.kind, DiseaseParameterKind):
            raise TypeError("kind must be a DiseaseParameterKind")
        if self.unit is not None and (
            not isinstance(self.unit, str) or not self.unit or self.unit != self.unit.strip()
        ):
            raise ValueError("unit must be None or a non-empty trimmed string")
        if self.minimum is not None and not math.isfinite(self.minimum):
            raise ValueError("minimum must be finite")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("maximum must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if self.allowed_values and len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("allowed_values must not contain duplicates")
        if self.has_default:
            self.validate(self.default)

    def validate(self, value: object) -> DiseaseScalar:
        if self.kind is DiseaseParameterKind.TEXT:
            if not isinstance(value, str) or not value or value != value.strip():
                raise AdmissibilityError(f"parameter {self.name!r} must be a non-empty trimmed string")
            normalized: DiseaseScalar = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AdmissibilityError(f"parameter {self.name!r} must be numeric")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise AdmissibilityError(f"parameter {self.name!r} must be finite")
            if self.minimum is not None and numeric < self.minimum:
                raise AdmissibilityError(
                    f"parameter {self.name!r} must be >= {self.minimum}"
                )
            if self.maximum is not None and numeric > self.maximum:
                raise AdmissibilityError(
                    f"parameter {self.name!r} must be <= {self.maximum}"
                )
            normalized = value
        if self.allowed_values and normalized not in self.allowed_values:
            raise AdmissibilityError(
                f"parameter {self.name!r} must be one of {self.allowed_values!r}"
            )
        return normalized


@dataclass(frozen=True, slots=True)
class DiseasePresetDescriptor:
    """Non-executable scientific contract for one frozen disease preset."""

    condition: DiseaseCondition
    name: str
    summary: str
    parameter_specs: tuple[DiseaseParameterSpec, ...]
    assumptions: tuple[str, ...]
    validated_domain: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.condition, DiseaseCondition):
            raise TypeError("condition must be a DiseaseCondition")
        for value, field_name in (
            (self.name, "name"),
            (self.summary, "summary"),
            (self.validated_domain, "validated_domain"),
        ):
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field_name} must be a non-empty trimmed string")
        names = tuple(spec.name for spec in self.parameter_specs)
        if len(names) != len(set(names)):
            raise ValueError("parameter_specs must have unique names")
        if any(not isinstance(spec, DiseaseParameterSpec) for spec in self.parameter_specs):
            raise TypeError("parameter_specs must contain DiseaseParameterSpec values")
        for collection, field_name in (
            (self.assumptions, "assumptions"),
            (self.citations, "citations"),
        ):
            if not isinstance(collection, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            if any(
                not isinstance(item, str) or not item or item != item.strip()
                for item in collection
            ):
                raise ValueError(f"{field_name} must contain non-empty trimmed strings")

    def normalize_parameters(
        self, parameters: Mapping[str, object] | None
    ) -> tuple[tuple[str, DiseaseScalar], ...]:
        supplied = {} if parameters is None else dict(parameters)
        if any(not isinstance(name, str) for name in supplied):
            raise AdmissibilityError("disease parameter names must be strings")
        specs = {spec.name: spec for spec in self.parameter_specs}
        unknown = sorted(set(supplied) - set(specs))
        if unknown:
            raise AdmissibilityError(f"unknown disease parameters: {unknown!r}")

        normalized: dict[str, DiseaseScalar] = {}
        for spec in self.parameter_specs:
            if spec.name in supplied:
                normalized[spec.name] = spec.validate(supplied[spec.name])
            elif spec.required and not spec.has_default:
                raise AdmissibilityError(f"required disease parameter {spec.name!r} is missing")
            elif spec.has_default:
                normalized[spec.name] = spec.validate(spec.default)
        return tuple(sorted(normalized.items()))

    def specification(
        self, parameters: Mapping[str, object] | None = None
    ) -> DiseaseSpecification:
        return DiseaseSpecification(
            condition=self.condition,
            parameters=self.normalize_parameters(parameters),
        )


__all__ = [
    "DiseaseParameterKind",
    "DiseaseParameterSpec",
    "DiseasePresetDescriptor",
]
