"""Structural ports for derivations, research operators, and discovery methods.

This module defines scientific execution contracts only. It contains no
method-specific equations, source-reader access, plugin discovery, or CLI state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, runtime_checkable

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import ScientificResult


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _optional_text(value: str | None, field_name: str) -> None:
    if value is not None:
        _required_text(value, field_name)


def _text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple of strings")
    seen: set[str] = set()
    for value in values:
        _required_text(value, field_name)
        if value in seen:
            raise ValueError(f"{field_name} must not contain duplicate values")
        seen.add(value)


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """Portable declaration of one scientific method parameter.

    ``allowed_values`` remains storage-agnostic because legitimate parameter
    values may be numeric, boolean, textual, or another later-normalized
    portable scalar. Application services own serialization normalization.
    """

    name: str
    kind: str
    description: str
    required: bool = False
    default: object | None = None
    unit: str | None = None
    allowed_values: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        _required_text(self.name, "name")
        _required_text(self.kind, "kind")
        _required_text(self.description, "description")
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")
        _optional_text(self.unit, "unit")
        if not isinstance(self.allowed_values, tuple):
            raise TypeError("allowed_values must be a tuple")
        if self.required and self.default is not None:
            raise ValueError("a required parameter must not also declare a default")


@dataclass(frozen=True, slots=True)
class InputRequirement:
    """Canonical scientific input requirement for a method component."""

    name: str
    quantity: str | None = None
    category: str | None = None
    accepted_units: tuple[str, ...] = ()
    physical_dimension: str | None = None
    required_coordinates: tuple[str, ...] = ()
    location_kind: str | None = None
    cohort_required: bool = False
    accepted_evidence: tuple[EvidenceClass, ...] = ()

    def __post_init__(self) -> None:
        _required_text(self.name, "name")
        _optional_text(self.quantity, "quantity")
        _optional_text(self.category, "category")
        if self.quantity is None and self.category is None:
            raise ValueError("an input requirement must declare quantity or category")
        _text_tuple(self.accepted_units, "accepted_units")
        _optional_text(self.physical_dimension, "physical_dimension")
        _text_tuple(self.required_coordinates, "required_coordinates")
        _optional_text(self.location_kind, "location_kind")
        if not isinstance(self.cohort_required, bool):
            raise TypeError("cohort_required must be a boolean")
        if not isinstance(self.accepted_evidence, tuple):
            raise TypeError("accepted_evidence must be a tuple of EvidenceClass values")
        if any(not isinstance(item, EvidenceClass) for item in self.accepted_evidence):
            raise TypeError("accepted_evidence must contain only EvidenceClass values")
        if len(set(self.accepted_evidence)) != len(self.accepted_evidence):
            raise ValueError("accepted_evidence must not contain duplicate values")


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Small infrastructure context supplied to scientific components.

    The context intentionally cannot expose backend readers, mutable registries,
    CLI parser state, or undeclared scientific inputs.
    """

    runtime_version: str
    random_state: object | None = None
    warning_sink: Callable[[str], None] | None = None

    def __post_init__(self) -> None:
        _required_text(self.runtime_version, "runtime_version")
        if self.warning_sink is not None and not callable(self.warning_sink):
            raise TypeError("warning_sink must be callable or None")

    def emit_warning(self, message: str) -> None:
        """Emit one validated scientific/operational warning when a sink exists."""

        _required_text(message, "message")
        if self.warning_sink is not None:
            self.warning_sink(message)


@runtime_checkable
class Derivation(Protocol):
    """Deterministic registered scientific transformation."""

    @property
    def descriptor(self) -> object: ...

    @property
    def required_inputs(self) -> tuple[InputRequirement, ...]: ...

    @property
    def output_quantity(self) -> QuantityDefinition: ...

    @property
    def output_evidence(self) -> EvidenceClass: ...

    @property
    def parameter_specs(self) -> tuple[ParameterSpec, ...]: ...

    @property
    def missing_data_policy(self) -> str: ...

    @property
    def citations(self) -> tuple[str, ...]: ...

    @property
    def validation_scope(self) -> str: ...

    @property
    def deterministic(self) -> bool: ...

    def run(
        self,
        *,
        inputs: Mapping[str, ScientificResult],
        parameters: Mapping[str, object],
        context: ExecutionContext,
    ) -> ScientificResult: ...


@runtime_checkable
class ResearchOperator(Protocol):
    """Explicit scientific model operating on canonical inputs."""

    @property
    def descriptor(self) -> object: ...

    @property
    def required_inputs(self) -> tuple[InputRequirement, ...]: ...

    @property
    def output_quantities(self) -> tuple[QuantityDefinition, ...]: ...

    @property
    def parameter_specs(self) -> tuple[ParameterSpec, ...]: ...

    @property
    def assumptions(self) -> tuple[str, ...]: ...

    @property
    def admissible_domain(self) -> str: ...

    @property
    def citations(self) -> tuple[str, ...]: ...

    @property
    def output_evidence(self) -> EvidenceClass: ...

    @property
    def deterministic(self) -> bool: ...

    def run(
        self,
        *,
        inputs: Mapping[str, ScientificResult],
        parameters: Mapping[str, object],
        context: ExecutionContext,
    ) -> ScientificResult: ...


@runtime_checkable
class DiscoveryMethod(Protocol):
    """Auditable discovery method over a defined virtual-population cohort."""

    @property
    def descriptor(self) -> object: ...

    @property
    def required_inputs(self) -> tuple[InputRequirement, ...]: ...

    @property
    def parameter_specs(self) -> tuple[ParameterSpec, ...]: ...

    @property
    def missing_data_policy(self) -> str: ...

    @property
    def output_schema(self) -> str: ...

    @property
    def evidence_semantics(self) -> str: ...

    @property
    def validation_scope(self) -> str: ...

    @property
    def deterministic(self) -> bool: ...

    def run(
        self,
        *,
        cohort: Cohort,
        inputs: Mapping[str, ScientificResult],
        parameters: Mapping[str, object],
        context: ExecutionContext,
    ) -> ScientificResult: ...


__all__ = [
    "Derivation",
    "DiscoveryMethod",
    "ExecutionContext",
    "InputRequirement",
    "ParameterSpec",
    "ResearchOperator",
]
